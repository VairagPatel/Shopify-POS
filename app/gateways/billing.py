"""Translate the exercise providers into neutral billing-port records and opaque write snapshots."""

from datetime import date, datetime
from app.domain.models import Prescription, EyePower
from app.domain.money import money, paise
from app.domain.records import (
    StoreRecord,
    ProductRecord,
    CustomerRecord,
    OrderRecord,
    RefundCalculation,
)
from app.constants import MOCK_ORDER_LIMIT
from app.gateways.shopify_mapping import build_order_payload


# Turn provider attribute arrays into a simple lookup inside the adapter only.
def attributes(values):
    return {item["name"]: item["value"] for item in values}


# Convert payment amounts at the external boundary.
def payment_record(source, method=None):
    return {
        "kind": source.get("kind", ""),
        "status": source.get("status", ""),
        "method": method or source.get("gateway", "unknown"),
        "amount_paise": paise(source["amount"]),
    }


# Strip provider-only shape from source sales and nested reversals.
def order_record(source) -> OrderRecord:
    notes = attributes(source.get("note_attributes", []))
    lines = []
    for line in source["line_items"]:
        lines.append(
            {
                "id": line.get("id", 0),
                "quantity": line["quantity"],
                "kind": attributes(line.get("properties", [])).get("line_type"),
                "gross_paise": paise(line["price"]) * line["quantity"],
                "discount_paise": paise(line.get("total_discount", "0.00")),
                "tax_paise": sum(
                    paise(tax["price"]) for tax in line.get("tax_lines", [])
                ),
            }
        )
    refunds = [
        {
            "id": refund.get("id", 0),
            "reference": attributes(refund.get("note_attributes", [])).get(
                "eluno_refund_id"
            ),
            "payments": [
                payment_record(payment) for payment in refund.get("transactions", [])
            ],
        }
        for refund in source.get("refunds", [])
    ]
    return {
        "id": source["id"],
        "location_id": source.get("location_id"),
        "created_at": source["created_at"],
        "cancelled": bool(source.get("cancelled_at")),
        "total_paise": paise(source["total_price"]),
        "checkout_reference": notes.get("checkout_id"),
        "lines": lines,
        "payments": [
            payment_record(payment, notes.get("payment_method"))
            for payment in source.get("transactions", [])
        ],
        "refunds": refunds,
    }


class BillingAdapter:
    # Compose the transport/clinical overlay at the boundary, not inside the services.
    def __init__(self, source):
        self.source = source

    # Project locations into store records independent of provider extension fields.
    def locations(self) -> list[StoreRecord]:
        return [
            {
                "id": row["id"],
                "store_code": row["eluno"]["store_code"],
                "kind": row["eluno"]["kind"],
                "invoice_prefix": row["eluno"].get("invoice_prefix", ""),
            }
            for row in self.source.locations()
        ]

    # Project source identity without exposing a provider customer type.
    def customer(self, phone) -> CustomerRecord | None:
        row = self.source.customer(phone)
        if row is None:
            return None
        return {
            key: row.get(key, "" if key == "tags" else None)
            for key in ("id", "phone", "first_name", "last_name", "tags")
        }

    # Convert prices once and expose clinical/catalog metadata under a neutral contract.
    def variant(self, variant_id) -> ProductRecord:
        row = self.source.variant(variant_id)
        return {
            "id": row["id"],
            "sku": row["sku"],
            "title": row["title"],
            "price_paise": paise(row["price"]),
            "inventory_item_id": row.get("inventory_item_id"),
            "metadata": dict(row["eluno"]),
        }

    # Read physical stock at the explicit source location.
    def stock(self, item_id, location_id):
        return self.source.stock(item_id, location_id)

    # Convert clinical source fields to the existing domain objects.
    def prescriptions(self, phone) -> list[Prescription]:
        result = []
        for row in self.source.prescriptions(phone):
            eyes = [
                EyePower(
                    str(row[side]["sph"]),
                    str(row[side]["cyl"]),
                    row[side].get("axis"),
                    None if row[side].get("add") is None else str(row[side]["add"]),
                )
                for side in ("od", "os")
            ]
            result.append(
                Prescription(
                    str(row["rx_id"]),
                    row["phone"],
                    eyes[0],
                    eyes[1],
                    date.fromisoformat(row["valid_until"]),
                    datetime.fromisoformat(row["date"]),
                )
            )
        return result

    # Keep only the staff fields needed by the billing authorization rule.
    def staff(self, store_code):
        return [
            {
                "staff_id": row["staff_id"],
                "can_override_discount": row.get("can_override_discount", False),
            }
            for row in self.source.staff(store_code)
        ]

    # Serialize neutral pricing context into the legacy persisted provider snapshot.
    def build_order_payload(self, **context):
        context["variants"] = [
            {**variant, "eluno": variant["metadata"]} for variant in context["variants"]
        ]
        return build_order_payload(**context)

    # Decode persisted snapshots here so old quotes remain usable after the refactor.
    def quote_inventory(self, quote):
        payload = quote["order_payload"]
        return payload["location_id"], [
            (line["variant_id"], line["quantity"]) for line in payload["line_items"]
        ]

    # Attach a captured payment using provider transaction field names only at the boundary.
    def paid_payload(self, quote, charge_id):
        payload = dict(quote["order_payload"])
        payload["transactions"] = [
            {
                "kind": "sale",
                "status": "success",
                "gateway": "cash" if quote["method"] == "cash" else "razorpay_terminal",
                "amount": money(quote["total_paise"]),
                "authorization": charge_id,
            }
        ]
        return payload

    # Execute one payment through the supplied terminal contract.
    def charge(self, order_ref, amount_paise, method):
        return self.source.charge(order_ref, amount_paise, method)

    # Inspect an existing charge without submitting a financial write.
    def charge_status(self, charge_id):
        return self.source.charge_status(charge_id)

    # Create a source order and return only its neutral identifier result.
    def order(self, payload):
        return {"id": self.source.order(payload)["id"]}

    # Project source rows for reconciliation and day-end.
    def orders(self, limit=MOCK_ORDER_LIMIT) -> list[OrderRecord]:
        return [order_record(row) for row in self.source.orders(limit=limit)]

    # Read the original sale for a reversal.
    def order_by_id(self, order_id) -> OrderRecord:
        return order_record(self.source.order_by_id(order_id))

    # Map neutral reversal selections to the provider's restocking vocabulary.
    def refund_lines(self, lines):
        return [
            {
                "line_item_id": line["line_id"],
                "quantity": line["quantity"],
                "restock_type": "return" if line["restock"] else "no_restock",
                **({"location_id": line["location_id"]} if line["restock"] else {}),
            }
            for line in lines
        ]

    # Convert source reversal totals into exact domain money fields.
    def refund_calculate(self, order_id, lines) -> RefundCalculation:
        source = self.source.refund_calculate(order_id, self.refund_lines(lines))
        payments = source.get("transactions") or []
        if len(payments) != 1:
            raise ValueError("Missing single suggested refund transaction")
        payment = payments[0]
        return {
            "amount_paise": paise(payment["amount"]),
            "maximum_paise": paise(payment["maximum_refundable"]),
            "tax_paise": sum(
                paise(line["total_tax"]) for line in source["refund_line_items"]
            ),
            "payment_parent": payment.get("parent_id"),
            "payment_provider": payment.get("gateway") or "razorpay_terminal",
        }

    # Build a provider refund snapshot after business totals have been verified.
    def build_refund_payload(self, lines, calculation, reason, refund_id):
        return {
            "refund_line_items": self.refund_lines(lines),
            "transactions": [
                {
                    "kind": "refund",
                    "gateway": calculation["payment_provider"],
                    "parent_id": calculation["payment_parent"],
                    "amount": money(calculation["amount_paise"]),
                }
            ],
            "note": "Eluno full refund: " + reason.strip(),
            "note_attributes": [{"name": "eluno_refund_id", "value": refund_id}],
        }

    # Reverse the captured payment once.
    def terminal_refund(self, charge_id, amount_paise, reason):
        return self.source.terminal_refund(charge_id, amount_paise, reason)

    # Record source tax/stock reversal and return its identifier only.
    def create_refund(self, order_id, payload):
        return {"id": self.source.create_refund(order_id, payload)["id"]}
