"""Acceptance amounts and exclusions from the supplied offers.json catalogue."""

from datetime import date
import pytest
from app.domain.models import Cart, CartLine, Customer
from app.services.catalog import load_json
from app.services.offers import evaluate_offers


# Keep a mixed-coating two-pair bill so every seeded coupon has a known basis.
def coupon_cart():
    return Cart("customer", "HSR", (
        CartLine("frame-a", "f1", 1, 300000, "frame", "pair-a"),
        CartLine("lens-a", "l1", 1, 200000, "lens", "pair-a"),
        CartLine("frame-b", "f2", 1, 200000, "frame", "pair-b"),
        CartLine("lens-b", "l2", 1, 100000, "lens", "pair-b"),
    ))


# Check configured amounts, explicit selection, line allocations and offer isolation.
@pytest.mark.parametrize("code,expected", [
    (None, 0), ("FESTIVE10", 50000), ("SECONDPAIR50", 50000),
    ("PRIORITY500", 50000), ("PGX_CAMPAIGN15", 45000),
    ("FREE_BLUECUT_PGX", 100000), ("BUNDLE300", 30000),
    ("MANAGER_OVERRIDE", 40000), ("MONSOON20", 0),
])
def test_seed_coupon_amounts(code, expected):
    result = evaluate_offers(
        coupon_cart(), Customer("customer", "+919000000005", ("priority", "campaign:progressive_oct26")),
        load_json("offers.json"), on_date=date(2026, 10, 26), selected_offer_id=code,
        lens_metadata={
            "l1": {"lens_type": "progressive", "index": 1.6, "coating": "blue_cut"},
            "l2": {"lens_type": "progressive", "index": 1.67, "coating": "photochromic"},
        }, manager_role="store_manager", reason_code="walk_out_retention", override_bps=500,
    )
    assert result.total_discount_paise == expected
    assert sum(result.discounts_paise) == expected
    assert {decision.offer_id for decision in result.decisions if decision.applied} == ({code} if expected else set())


# The seeded cap is stored on rule, rather than inside rule.discount.
def test_festive_cap_from_offers_json():
    cart = Cart("customer", "HSR", (CartLine("expensive-frame", "f1", 1, 3000000, "frame"),))
    result = evaluate_offers(cart, Customer("customer", ""), load_json("offers.json"),
                             on_date=date(2026, 10, 26), selected_offer_id="FESTIVE10")
    assert result.total_discount_paise == 200000  # ₹2,000 cap on a ₹30,000 frame.


# Dates are inclusive at both ends; an expired but otherwise eligible offer is rejected.
@pytest.mark.parametrize("day,expected", [("2026-09-30", 0), ("2026-10-01", 50000), ("2026-11-15", 50000), ("2026-11-16", 0)])
def test_festive_date_boundaries(day, expected):
    result = evaluate_offers(coupon_cart(), Customer("customer", ""), load_json("offers.json"),
                             on_date=date.fromisoformat(day), selected_offer_id="FESTIVE10")
    assert result.total_discount_paise == expected


# Type, index and coating must match the same lens, rather than different cart lines.
def test_bluecut_conditions_cannot_be_split_between_lenses():
    result = evaluate_offers(
        coupon_cart(), Customer("customer", ""), load_json("offers.json"),
        on_date=date(2026, 10, 26), selected_offer_id="FREE_BLUECUT_PGX",
        lens_metadata={
            "l1": {"lens_type": "progressive", "index": 1.5, "coating": "standard"},
            "l2": {"lens_type": "single_vision", "index": 1.67, "coating": "blue_cut"},
        },
    )
    assert result.total_discount_paise == 0


# A reason or a percentage alone never authorizes a manager discount.
@pytest.mark.parametrize("percentage,reason", [(None, "walk_out_retention"), (500, None)])
def test_manager_requires_percentage_and_reason(percentage, reason):
    result = evaluate_offers(coupon_cart(), Customer("customer", ""), load_json("offers.json"),
                             on_date=date(2026, 10, 26), selected_offer_id="MANAGER_OVERRIDE",
                             manager_role="store_manager", override_bps=percentage, reason_code=reason)
    assert result.total_discount_paise == 0
