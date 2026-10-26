"""Run the same sale/refund/report services with a non-Shopify provider and opaque snapshots."""

from datetime import date, datetime
import pytest
from app.domain.models import Prescription, EyePower
from app.persistence.sqlite import SQLiteStore
from app.services.sale import SaleService, SaleValidationError
from app.services.refunds import RefundService
from app.services.reporting import DayEndService


class ReplacementProvider:
    # Maintain only neutral records, with deliberately different write snapshot names.
    def __init__(self):
        self.saved_order = None
        self.stock_units = 4

    # Supply a provider-neutral store.
    def locations(self):
        return [
            {"id": 1, "store_code": "HSR", "kind": "store", "invoice_prefix": "HSR-"}
        ]

    # Supply an already normalized person.
    def customer(self, phone):
        return {
            "id": 42,
            "phone": phone,
            "first_name": "Demo",
            "last_name": "Person",
            "tags": "",
        }

    # Supply neutral product prices and clinical metadata.
    def variant(self, variant_id):
        lens = variant_id in (2, 3)
        metadata = {
            "line_type": "lens" if lens else "frame",
            "hsn": "90015000" if lens else "90031900",
            "rx_able": True,
        }
        if lens:
            metadata.update(
                lens_type="single_vision",
                index="1.56",
                coating="clear",
                rx_limits={
                    "sph_min": -6,
                    "sph_max": 6,
                    "cyl_abs_max": 4,
                    "add_required": False,
                },
            )
        return {
            "id": variant_id,
            "sku": str(variant_id),
            "title": "Lens" if lens else "Frame",
            "price_paise": 315000 if lens else 236000,
            "inventory_item_id": None if lens else 1,
            "metadata": metadata,
        }

    # Return a domain prescription instead of source OD/OS dictionaries.
    def prescriptions(self, phone):
        return [
            Prescription(
                "rx-test",
                phone,
                EyePower("-2", "0", 90, "0"),
                EyePower("-2", "0", 90, "0"),
                date(2030, 1, 1),
                datetime(2026, 1, 1),
            )
        ]

    # Supply neutral authorization information.
    def staff(self, store_code):
        return [{"staff_id": "staff-1", "can_override_discount": False}]

    # Read stock through the same port.
    def stock(self, item_id, location_id):
        return self.stock_units

    # Use a write schema with no Shopify line_items/tax_lines/transaction fields.
    def build_order_payload(self, **context):
        self.pending = {
            "id": 101,
            "location_id": 1,
            "created_at": "2026-09-01T12:00:00+05:30",
            "cancelled": False,
            "checkout_reference": context["checkout_identifier"],
            "total_paise": sum(t.total_paise for t in context["taxes"]),
            "lines": [
                {
                    "id": index + 1,
                    "quantity": 1,
                    "kind": product["metadata"]["line_type"],
                    "gross_paise": tax.gross_paise,
                    "discount_paise": tax.discount_paise,
                    "tax_paise": tax.cgst_paise + tax.sgst_paise,
                }
                for index, (product, tax) in enumerate(
                    zip(context["variants"], context["taxes"])
                )
            ],
            "payments": [],
            "refunds": [],
        }
        return {
            "replacement_items": [product["id"] for product in context["variants"]],
            "amount_units": self.pending["total_paise"],
        }

    # Interpret this provider's opaque quote snapshot at the boundary.
    def quote_inventory(self, quote):
        return 1, [
            (identifier, 1)
            for identifier in quote["order_payload"]["replacement_items"]
        ]

    # Return a neutral charge result.
    def charge(self, order_ref, amount_paise, method):
        return {"charge_id": "replacement-charge"}

    # Encode captured payment in this provider's own write format.
    def paid_payload(self, quote, charge_id):
        return {**quote["order_payload"], "replacement_receipt": charge_id}

    # Record one order and decrement physical stock.
    def order(self, payload):
        assert payload["replacement_receipt"] == "replacement-charge"
        self.saved_order = self.pending
        self.saved_order["payments"] = [
            {
                "kind": "sale",
                "status": "success",
                "method": "upi",
                "amount_paise": payload["amount_units"],
            }
        ]
        self.stock_units -= 1
        return {"id": 101}

    # Expose neutral order reads for reporting.
    def orders(self, limit=250):
        return [self.saved_order] if self.saved_order else []

    # Resolve the sale without provider-specific parsing in the service.
    def order_by_id(self, order_id):
        return self.saved_order

    # Calculate the original reversal using neutral amounts.
    def refund_calculate(self, order_id, lines):
        assert [line["restock"] for line in lines] == [True, False]
        return {
            "amount_paise": self.saved_order["total_paise"],
            "maximum_paise": self.saved_order["total_paise"],
            "tax_paise": sum(line["tax_paise"] for line in self.saved_order["lines"]),
            "payment_parent": 1,
            "payment_provider": "replacement",
        }

    # Serialize an opaque reversal snapshot.
    def build_refund_payload(self, lines, calculation, reason, refund_id):
        return {
            "replacement_ref": refund_id,
            "amount_units": calculation["amount_paise"],
        }

    # Execute a terminal reversal once.
    def terminal_refund(self, charge_id, amount_paise, reason):
        return {"refund_id": "replacement-terminal-refund"}

    # Record neutral refund results after provider-specific serialization.
    def create_refund(self, order_id, payload):
        self.saved_order["refunds"] = [
            {
                "id": 202,
                "reference": payload["replacement_ref"],
                "payments": [
                    {
                        "kind": "refund",
                        "status": "success",
                        "method": "upi",
                        "amount_paise": payload["amount_units"],
                    }
                ],
            }
        ]
        self.stock_units += 1
        return {"id": 202}


# Demonstrate replacement is a port implementation, not a rewrite of pricing/refund rules.
def test_sale_refund_and_report_without_shopify_shapes(tmp_path):
    provider = ReplacementProvider()
    store = SQLiteStore(str(tmp_path / "replacement.sqlite3"))
    sale = SaleService(store, provider)
    prepared = sale.prepare(
        phone="9000000005",
        store_code="HSR",
        staff_id="staff-1",
        variant_ids=[1, 2],
        on_date=date(2026, 9, 1),
    )
    completed = sale.complete(prepared["checkout_id"])
    assert completed["status"] == "order_recorded"
    assert provider.stock_units == 3
    report = DayEndService(provider).report("HSR", "2026-09-01")
    assert report["bill_count"] == 1
    assert (
        report["gross_paise"] - report["discounts_paise"] - report["tax_paise"]
        == report["taxable_paise"]
    )
    refund = RefundService(store, provider)
    preview = refund.prepare(prepared["checkout_id"], "return")
    assert refund.complete(preview["refund_id"])["status"] == "recorded"
    assert provider.stock_units == 4
    assert (
        DayEndService(provider).report("HSR", "2026-09-01")["net_collected_paise"] == 0
    )


# Prevent an optical frame from being sold without a pair or with extra lenses.
def test_sale_requires_exactly_one_lens_pair_per_optical_frame(tmp_path):
    """Optical frames need one lens pair; extra lenses cannot be orphaned."""
    provider = ReplacementProvider()
    sale = SaleService(SQLiteStore(str(tmp_path / "pair-validation.sqlite3")), provider)
    for variants in ([1], [1, 2, 3]):
        with pytest.raises(SaleValidationError, match="one frame for each lens"):
            sale.prepare(
                phone="9000000005",
                store_code="HSR",
                staff_id="staff-1",
                variant_ids=list(variants),
            )
