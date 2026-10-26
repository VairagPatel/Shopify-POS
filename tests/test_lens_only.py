"""Regression tests for prescription lens-pair sales without a frame."""

from datetime import date

from app.domain.models import EyePower, Prescription
from app.persistence.sqlite import SQLiteStore
from app.services.sale import SaleService


class LensOnlyGateway:
    """Provide source-shaped records for the isolated sale-service regression."""

    # Return the one billing store used by this isolated test.
    def locations(self):
        "Return the one billing store used by this isolated test."
        return [
            {
                "id": 70000002,
                "store_code": "HSR",
                "kind": "store",
                "invoice_prefix": "HSR",
            }
        ]

    # Resolve the synthetic customer used for the prescription.
    def customer(self, phone):
        "Resolve the synthetic customer used for the prescription."
        return {
            "id": 80001004,
            "phone": phone,
            "first_name": "Divya",
            "last_name": "Iyer",
            "tags": "family",
        }

    # Return the one lens-pair variant from the local catalogue.
    def variant(self, variant_id):
        "Return the one lens-pair variant from the local catalogue."
        assert variant_id == 91000083
        return {
            "id": 91000083,
            "sku": "LN-0043",
            "title": "Progressive 1.60",
            "price_paise": 250000,
            "inventory_item_id": None,
            "metadata": {
                "line_type": "lens",
                "hsn": "90015000",
                "lens_type": "progressive",
                "index": 1.6,
                "coating": "blue_cut",
                "rx_limits": {
                    "sph_min": -8,
                    "sph_max": 6,
                    "cyl_abs_max": 4,
                    "add_required": True,
                    "add_min": 0.75,
                    "add_max": 3,
                },
            },
        }

    # Return a current prescription with ADD present in both eyes.
    def prescriptions(self, phone):
        "Return a current prescription with ADD present in both eyes."
        return [
            Prescription(
                "RX-LENS-ONLY",
                phone,
                EyePower("-2.00", "-0.50", 90, "1.50"),
                EyePower("-1.75", "-0.50", 90, "1.50"),
                date(2027, 12, 31),
            )
        ]

    # Return staff authorized to bill without a manager override.
    def staff(self, store_code):
        "Return staff authorized to bill without a manager override."
        return [{"staff_id": "S105", "can_override_discount": False}]

    # Confirm lens variants do not reserve physical frame inventory.
    def stock(self, inventory_item_id, location_id):
        "Confirm lens variants do not reserve physical frame inventory."
        raise AssertionError("A made-to-order lens pair must not read frame stock")

    # Save the prepared line evidence using the provider adapter contract.
    def build_order_payload(self, **context):
        "Save the prepared line evidence using the provider adapter contract."
        payload_lines = []
        for index, variant in enumerate(context["variants"]):
            properties = [
                {"name": "line_type", "value": variant["metadata"]["line_type"]}
            ]
            if index in context["pair_refs"]:
                properties.append(
                    {"name": "pair_ref", "value": context["pair_refs"][index]}
                )
            if index in context["lens_positions"]:
                properties.append(
                    {
                        "name": "rx_id",
                        "value": context["prescriptions_by_line"][index].prescription_id,
                    }
                )
            payload_lines.append(
                {"variant_id": variant["id"], "properties": properties}
            )
        return {"location_id": context["location"]["id"], "line_items": payload_lines}


# Keep the lens-only path working through prescription validation and SQLite quote persistence.
def test_lens_only_pair_is_quoted_without_frame_stock(tmp_path):
    "Keep the lens-only path working through validation and quote persistence."
    store = SQLiteStore(str(tmp_path / "lens-only.sqlite3"))
    service = SaleService(store, LensOnlyGateway())
    quote = service.prepare(
        phone="+919000000004",
        store_code="HSR",
        staff_id="S105",
        variant_ids=[],
        members=[
            {
                "phone": "+919000000004",
                "variant_ids": [],
                "lens_only_variant_ids": [91000083],
            }
        ],
    )

    saved = store.load_quote(quote["checkout_id"])
    assert saved["total_paise"] > 0
    assert len(saved["lines"]) == 1
    assert saved["lines"][0]["rx_id"] == "RX-LENS-ONLY"
    line_properties = {
        item["name"]: item["value"]
        for item in saved["order_payload"]["line_items"][0]["properties"]
    }
    assert line_properties["rx_id"] == "RX-LENS-ONLY"
    assert "pair_ref" not in line_properties
