"""Sale orchestration, including distinct-variant multi-pair carts."""

import json
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from collections import Counter
from uuid import uuid4
from app.domain.models import (
    Cart,
    CartLine,
    CheckoutStatus,
    Customer,
    Prescription,
    EyePower,
    LensConfiguration,
)
from app.persistence.sqlite import StateConflict
from app.gateways.http import GatewayError
from app.services.prescriptions import validate_lens, latest_valid_prescription
from app.services.offers import evaluate_offers
from app.services.taxes import inclusive_tax_line, invoice_totals
from app.services.catalog import load_json, tax_catalog


# Format integer paise as the fixed-decimal strings required by the mock.
def money(paise):
    "Format integer paise as the fixed-decimal strings required by the mock."
    return f"{paise // 100}.{paise % 100:02d}"


# Convert source decimal money strings to exact integer paise.
def paise(value):
    "Convert source decimal money strings to exact integer paise."
    return int(Decimal(str(value)) * 100)


# Adapt a source prescription record into the clinical domain model.
def _rx(raw):
    "Adapt a source prescription record into the clinical domain model."

    # Normalize one eye record into the typed prescription representation.
    def eye(obj):
        "Normalize one eye record into the typed prescription representation."
        return EyePower(
            str(obj["sph"]),
            str(obj["cyl"]),
            obj.get("axis"),
            None if obj.get("add") is None else str(obj["add"]),
        )

    return Prescription(
        str(raw["rx_id"]),
        raw["phone"],
        eye(raw["od"]),
        eye(raw["os"]),
        date.fromisoformat(raw["valid_until"]),
        datetime.fromisoformat(raw["date"]),
    )


class SaleValidationError(ValueError):
    pass


class SaleService:
    # Initialize the adapter or service with its explicit dependencies.
    def __init__(self, store, gateway):
        "Initialize the adapter or service with its explicit dependencies."
        self.store = store
        self.gateway = gateway

    # Read live mock records, validate and persist an immutable sale quote BEFORE charging.
    def prepare(
        self,
        *,
        phone,
        store_code,
        staff_id,
        variant_ids,
        payment_method="upi",
        channel="walk_in",
        on_date=None,
        manager_role=None,
        reason_code=None,
        override_bps=None,
        checkout_id=None,
        members=None,
        remake=None,
    ):
        """Read live mock records, validate and persist an immutable sale quote BEFORE charging."""
        on_date = (
            on_date or datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
        )
        member_phones = []
        pair_refs = {}
        if members:
            variant_ids = []
            for number, member in enumerate(members, 1):
                if not self.gateway.customer(member["phone"]):
                    raise SaleValidationError(
                        "Family member must be an existing customer"
                    )
                selected = member["variant_ids"]
                if not 1 <= len(selected) <= 30:
                    raise SaleValidationError(
                        "Each wearer needs between 1 and 30 units"
                    )
                selected_kinds = [
                    self.gateway.variant(item)["eluno"]["line_type"]
                    for item in selected
                ]
                # Match frame and lens units within this wearer; extra units are standalone.
                offset = len(variant_ids)
                frames = [i for i, kind in enumerate(selected_kinds) if kind == "frame"]
                lenses = [i for i, kind in enumerate(selected_kinds) if kind == "lens"]
                for pair_number, (frame, lens) in enumerate(zip(frames, lenses), 1):
                    pair_refs[offset + frame] = pair_refs[offset + lens] = (
                        f"{number}:{pair_number}"
                    )
                for item in selected:
                    variant_ids.append(item)
                    member_phones.append(member["phone"])
        if payment_method not in {"upi", "card", "cash"}:
            raise SaleValidationError("Choose UPI, card or cash")
        if channel not in {"walk_in", "whatsapp", "online_pickup"}:
            raise SaleValidationError("Unknown sales channel")
        if not variant_ids or any(not isinstance(v, int) for v in variant_ids):
            raise SaleValidationError("variant_ids must contain numeric variant IDs")
        locations = [
            l
            for l in self.gateway.locations()
            if l["eluno"]["store_code"] == store_code and l["eluno"]["kind"] == "store"
        ]
        if len(locations) != 1:
            raise SaleValidationError("Unknown billing store")
        location = locations[0]
        customer_raw = self.gateway.customer(phone)
        if not customer_raw:
            raise SaleValidationError("Existing customer not found in Shopify")
        staff = next(
            (s for s in self.gateway.staff(store_code) if s["staff_id"] == staff_id),
            None,
        )
        if not staff:
            raise SaleValidationError("Staff member not found in this store")
        if override_bps is not None:
            if not staff.get("can_override_discount") or not reason_code:
                raise SaleValidationError(
                    "Manager override needs authorized staff and reason"
                )
            manager_role = "store_manager"
        variants = [self.gateway.variant(v) for v in variant_ids]
        kinds = [v["eluno"]["line_type"] for v in variants]
        if any(
            kind not in ("frame", "lens", "sunglass", "sunglasses") for kind in kinds
        ):
            raise SaleValidationError("Unsupported product category")
        if not members and len(variant_ids) != len(set(variant_ids)):
            raise SaleValidationError(
                "Duplicate variant IDs are not supported; select distinct variants"
            )
        frame_positions = [i for i, kind in enumerate(kinds) if kind == "frame"]
        lens_positions = [i for i, kind in enumerate(kinds) if kind == "lens"]
        # Every multi-pair cart has an unambiguous positional frame/lens match.
        # Single frame-only and lens-only bills remain valid.
        if (
            not members
            and len(variants) > 1
            and len(frame_positions) != len(lens_positions)
        ):
            raise SaleValidationError("Multi-pair bills need one frame for each lens")
        for i in frame_positions:
            if (i in pair_refs if members else lens_positions) and not variants[i][
                "eluno"
            ].get("rx_able"):
                raise SaleValidationError(
                    "Selected frame is not prescription-compatible"
                )
        quantities = Counter(
            v["inventory_item_id"] for v in variants if v.get("inventory_item_id")
        )
        for i in [
            index
            for index, variant in enumerate(variants)
            if variant.get("inventory_item_id")
        ]:
            if (
                self.gateway.stock(variants[i]["inventory_item_id"], location["id"])
                < quantities[variants[i]["inventory_item_id"]]
            ):
                raise SaleValidationError(
                    f"Frame out of stock at selected store: {variants[i]['sku']}"
                )
        rx = None
        prescriptions_by_line = {}
        if lens_positions:
            for i in lens_positions:
                wearer_phone = member_phones[i] if members else phone
                rx_rows = self.gateway.prescriptions(wearer_phone)
                rx = latest_valid_prescription(
                    [_rx(row) for row in rx_rows], on_date=on_date
                )
                if not rx:
                    raise SaleValidationError(
                        "No valid prescription available for " + wearer_phone
                    )
                prescriptions_by_line[i] = rx
                lens = variants[i]
                meta = lens["eluno"]
                validation = validate_lens(
                    rx,
                    LensConfiguration(
                        meta["lens_type"],
                        str(meta["index"]),
                        meta["coating"],
                        str(lens["id"]),
                    ),
                    meta,
                    on_date=on_date,
                )
                if not validation.valid:
                    raise SaleValidationError(
                        f"Lens {lens['sku']}: " + "; ".join(validation.reasons)
                    )
        if not members and frame_positions and lens_positions:
            for n, (frame_index, lens_index) in enumerate(
                zip(frame_positions, lens_positions), 1
            ):
                pair_refs[frame_index] = pair_refs[lens_index] = str(n)
        customer = Customer(
            str(customer_raw["id"]),
            phone,
            tuple(
                x.strip() for x in customer_raw.get("tags", "").split(",") if x.strip()
            ),
        )
        lines = tuple(
            CartLine(
                v["sku"],
                str(v["id"]),
                1,
                paise(v["price"]),
                v["eluno"]["line_type"],
                pair_refs.get(i),
                prescriptions_by_line[i].prescription_id
                if i in prescriptions_by_line
                else None,
            )
            for i, v in enumerate(variants)
        )
        cart = Cart(customer.customer_id, store_code, lines)
        discounts = evaluate_offers(
            cart,
            customer,
            load_json("offers.json"),
            on_date=on_date,
            lens_metadata={str(v["id"]): v["eluno"] for v in variants},
            manager_role=manager_role,
            reason_code=reason_code,
            override_bps=override_bps,
        )
        line_discounts = discounts.discounts_paise
        if remake and remake["cost_owner"] != "customer":
            line_discounts = tuple(line.unit_price_paise for line in lines)
        catalog = tax_catalog()
        taxes = tuple(
            inclusive_tax_line(
                hsn=v["eluno"]["hsn"],
                quantity=1,
                unit_price_paise=lines[i].unit_price_paise,
                discount_paise=line_discounts[i],
                rate_bps=catalog.rate_for(v["eluno"]["hsn"], on_date),
            )
            for i, v in enumerate(variants)
        )
        totals = invoice_totals(taxes)
        if totals["total_paise"] <= 0 and not remake:
            raise SaleValidationError("Zero-charge transactions are outside Stage 5")
        checkout_identifier = checkout_id or str(uuid4())
        self.store.create_checkout(
            store_code, customer.customer_id, checkout_identifier
        )
        invoice = self.store.reserve_invoice(
            checkout_identifier, store_code, location["eluno"]["invoice_prefix"]
        )
        payload_lines = []
        for i, v in enumerate(variants):
            tax = taxes[i]
            props = [
                {"name": "line_type", "value": v["eluno"]["line_type"]},
                {"name": "hsn", "value": tax.hsn},
            ]
            if i in pair_refs:
                props.append({"name": "pair_ref", "value": pair_refs[i]})
            if i in lens_positions:
                props.extend(
                    [
                        {
                            "name": "rx_id",
                            "value": prescriptions_by_line[i].prescription_id,
                        },
                        {
                            "name": "wearer_phone",
                            "value": member_phones[i] if members else phone,
                        },
                        {
                            "name": "lens_config",
                            "value": f"{v['eluno']['lens_type']}/{v['eluno']['index']}/{v['eluno']['coating']}",
                        },
                    ]
                )
            payload_lines.append(
                {
                    "variant_id": int(v["id"]),
                    "quantity": 1,
                    "price": money(tax.gross_paise),
                    "total_discount": money(tax.discount_paise),
                    "properties": props,
                    "tax_lines": [
                        {
                            "title": key,
                            "rate": tax.rate_bps / 20000,
                            "price": money(getattr(tax, key.lower() + "_paise")),
                        }
                        for key in ("CGST", "SGST")
                    ],
                }
            )
        applications = []
        for d in discounts.decisions:
            if d.applied:
                applications.append(
                    {
                        "type": "manual",
                        "title": d.offer_id,
                        "value": money(d.amount_paise),
                        "value_type": "fixed_amount",
                        "allocation_method": "each",
                        "target_selection": "explicit",
                        "target_type": "line_item",
                    }
                )
        for i, line in enumerate(payload_lines):
            allocations = []
            for j, d in enumerate([d for d in discounts.decisions if d.applied]):
                if d.allocations_paise[i]:
                    allocations.append(
                        {
                            "amount": money(d.allocations_paise[i]),
                            "discount_application_index": j,
                        }
                    )
            line["discount_allocations"] = allocations
        notes = [
            {"name": k, "value": str(v)}
            for k, v in {
                "invoice_no": invoice,
                "checkout_id": checkout_identifier,
                "store_code": store_code,
                "channel": channel,
                "staff_id": staff_id,
                "payment_method": payment_method,
                "discount_reason": reason_code or "",
                "discount_approver": staff_id if override_bps is not None else "",
                "remake": json.dumps(remake) if remake else "",
            }.items()
        ]
        if remake and remake["cost_owner"] != "customer":
            applications = [
                {
                    "type": "manual",
                    "title": "REMAKE_COST_ALLOCATION",
                    "value": money(sum(line_discounts)),
                    "value_type": "fixed_amount",
                    "allocation_method": "each",
                    "target_selection": "explicit",
                    "target_type": "line_item",
                }
            ]
            for index, line in enumerate(payload_lines):
                line["discount_allocations"] = [
                    {
                        "amount": money(line_discounts[index]),
                        "discount_application_index": 0,
                    }
                ]
        payload = {
            "taxes_included": True,
            "location_id": location["id"],
            "inventory_behaviour": "decrement_obeying_policy",
            "source_name": "eluno-pos",
            "customer": {"id": customer_raw["id"]},
            "note_attributes": notes,
            "line_items": payload_lines,
            "discount_applications": applications,
        }
        quote = {
            "checkout_id": checkout_identifier,
            "invoice_no": invoice,
            "total_paise": totals["total_paise"],
            "tax_paise": totals["cgst_paise"] + totals["sgst_paise"],
            "method": payment_method,
            "order_payload": payload,
            "offer_decisions": [d.__dict__ for d in discounts.decisions],
            "remake": remake,
            "customer": customer_raw,
            "lines": [
                {
                    "title": v["sku"] + " / " + v["title"],
                    "variant_id": v["id"],
                    "wearer_phone": member_phones[i] if members else phone,
                    "rx_id": prescriptions_by_line[i].prescription_id
                    if i in prescriptions_by_line
                    else None,
                    **taxes[i].__dict__,
                }
                for i, v in enumerate(variants)
            ],
        }
        self.store.save_quote(checkout_identifier, quote)
        return {
            "checkout_id": checkout_identifier,
            "invoice_no": invoice,
            "total_paise": totals["total_paise"],
            "tax_paise": quote["tax_paise"],
            "offers": quote["offer_decisions"],
            "status": "draft",
        }

    # Perform one external charge and one order POST, never blindly retry unsafe writes.
    def complete(self, checkout_id):
        """Perform one external charge and one order POST, never blindly retry unsafe writes."""
        state = self.store.get_checkout(checkout_id)
        if state["status"] == CheckoutStatus.ORDER_RECORDED.value:
            return state
        if state["status"] != CheckoutStatus.DRAFT.value:
            raise StateConflict(
                "Checkout already started: inspect/reconcile; do not charge again"
            )
        quote = self.store.load_quote(checkout_id)
        if not quote:
            raise StateConflict("Missing persisted quote")
        # Quotes do not reserve stock. Reject a stale cart before any payment side effect.
        demand = Counter()
        for line in quote["order_payload"]["line_items"]:
            variant = self.gateway.variant(line["variant_id"])
            if variant.get("inventory_item_id"):
                demand[variant["inventory_item_id"]] += line["quantity"]
        for item, quantity in demand.items():
            if (
                self.gateway.stock(item, quote["order_payload"]["location_id"])
                < quantity
            ):
                raise StateConflict(
                    "Stock changed since quote; review the bill before payment"
                )
        payment_reference = "elu-checkout-" + checkout_id
        self.store.record_external_ref(checkout_id, "payment_ref", payment_reference)
        self.store.change_status(
            checkout_id, CheckoutStatus.DRAFT, CheckoutStatus.PAYMENT_PENDING
        )
        try:
            charged = (
                {"charge_id": "cash-" + checkout_id}
                if quote["method"] == "cash"
                else {"charge_id": "no-charge-" + checkout_id}
                if quote["total_paise"] == 0
                else self.gateway.charge(
                    payment_reference, quote["total_paise"], quote["method"]
                )
            )
        except GatewayError as exc:
            self.store.change_status(
                checkout_id,
                CheckoutStatus.PAYMENT_PENDING,
                CheckoutStatus.PAYMENT_UNCERTAIN,
                error_detail=str(exc),
            )
            raise
        self.store.record_external_ref(
            checkout_id, "payment_charge_id", charged["charge_id"]
        )
        self.store.change_status(
            checkout_id, CheckoutStatus.PAYMENT_PENDING, CheckoutStatus.PAYMENT_CAPTURED
        )
        return self._record_order(checkout_id, quote, charged["charge_id"])

    # Record the paid order once and advance the invoice register to issued.
    def _record_order(self, checkout_id, quote, charge_id):
        self.store.change_status(
            checkout_id, CheckoutStatus.PAYMENT_CAPTURED, CheckoutStatus.ORDER_PENDING
        )
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
        try:
            order = self.gateway.order(payload)
        except GatewayError as exc:
            self.store.change_status(
                checkout_id,
                CheckoutStatus.ORDER_PENDING,
                CheckoutStatus.ORDER_UNCERTAIN,
                error_detail=str(exc),
            )
            raise
        self.store.record_external_ref(
            checkout_id, "shopify_order_id", str(order["id"])
        )
        self.store.change_status(
            checkout_id, CheckoutStatus.ORDER_PENDING, CheckoutStatus.ORDER_RECORDED
        )
        with self.store._connect() as connection:
            connection.execute(
                "UPDATE invoice_allocations SET status='issued' WHERE checkout_id=?",
                (checkout_id,),
            )
        return self.store.get_checkout(checkout_id)

    # Read-only reconciliation; Shopify may lack the order. Never re-post automatically.
    def reconcile_order(self, checkout_id):
        """Read-only reconciliation; Shopify may lack the order. Never re-post automatically."""
        state = self.store.get_checkout(checkout_id)
        if state["status"] != CheckoutStatus.ORDER_UNCERTAIN.value:
            raise StateConflict("Reconciliation only permitted for order_uncertain")
        matches = [
            o
            for o in self.gateway.orders()
            if any(
                a.get("name") == "checkout_id" and a.get("value") == checkout_id
                for a in o.get("note_attributes", [])
            )
        ]
        if len(matches) == 1:
            self.store.record_external_ref(
                checkout_id, "shopify_order_id", str(matches[0]["id"])
            )
            self.store.change_status(
                checkout_id,
                CheckoutStatus.ORDER_UNCERTAIN,
                CheckoutStatus.ORDER_RECORDED,
            )
        elif len(matches) > 1:
            self.store.change_status(
                checkout_id,
                CheckoutStatus.ORDER_UNCERTAIN,
                CheckoutStatus.RECONCILIATION_REQUIRED,
                error_detail="Duplicate matching orders: manual intervention",
            )
        return self.store.get_checkout(checkout_id)
