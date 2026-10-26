import json
from datetime import date
from pathlib import Path
import pytest
from app.domain.models import (
    Cart,
    CartLine,
    Customer,
    Prescription,
    EyePower,
    LensConfiguration,
)
from app.services.prescriptions import validate_lens, latest_valid_prescription
from app.services.offers import evaluate_offers
from app.services.taxes import TaxCatalog, inclusive_tax_line, invoice_totals
from app.services.catalog import load_json, tax_catalog, variant_metadata

TODAY = date(2026, 10, 24)


# Support rx.
def rx(
    right=EyePower("-3.00", "-1.00", 90, "1.50"),
    left=EyePower("-2.00", "0", 90, "1.50"),
    expiry=date(2026, 12, 31),
):
    "Support rx."
    return Prescription("RX1", "+919000000000", right, left, expiry)


# Support lens.
def lens(metadata, variant_id="L1"):
    "Support lens."
    return LensConfiguration(
        metadata["lens_type"], str(metadata["index"]), metadata["coating"], variant_id
    )


# Support basic meta.
@pytest.fixture
def basic_meta():
    "Support basic meta."
    return {
        "line_type": "lens",
        "lens_type": "single_vision",
        "index": 1.6,
        "coating": "standard",
        "rx_limits": {
            "sph_min": -4,
            "sph_max": 4,
            "cyl_abs_max": 2,
            "add_required": False,
        },
    }


# Verify rx valid boundaries.
def test_rx_valid_boundaries(basic_meta):
    "Verify rx valid boundaries."
    result = validate_lens(
        rx(right=EyePower("-4", "-2", 180, "1.50"), left=EyePower("4", "2", 5, "1.50")),
        lens(basic_meta),
        basic_meta,
        on_date=TODAY,
    )
    assert result.valid


# Accept a missing optional single-vision ADD, but reject missing axis or off-grid axis.
def test_rx_allows_optional_single_vision_add_and_requires_axis(basic_meta):
    """Single-vision validation allows absent ADD but still requires a valid axis."""
    incomplete = rx(right=EyePower("-2", "0"), left=EyePower("-2", "0", 90, "1.50"))
    result = validate_lens(incomplete, lens(basic_meta), basic_meta, on_date=TODAY)
    assert not result.valid
    assert any("axis is required" in reason for reason in result.reasons)
    assert not any("ADD" in reason for reason in result.reasons)

    off_grid = rx(
        right=EyePower("-2", "0", 91, "1.50"),
        left=EyePower("-2", "0", 90, "1.50"),
    )
    result = validate_lens(off_grid, lens(basic_meta), basic_meta, on_date=TODAY)
    assert not result.valid
    assert any("5-degree steps" in reason for reason in result.reasons)


# Verify rx rejects expired and outside limits.
def test_rx_rejects_expired_and_outside_limits(basic_meta):
    "Verify rx rejects expired and outside limits."
    result = validate_lens(
        rx(right=EyePower("-5", "-3", None), expiry=date(2026, 1, 1)),
        lens(basic_meta),
        basic_meta,
        on_date=TODAY,
    )
    assert not result.valid and len(result.reasons) >= 3
    assert "expired" in " ".join(result.reasons)


# Verify rx requires add for progressive.
def test_rx_requires_add_for_progressive(basic_meta):
    "Verify rx requires add for progressive."
    meta = {
        **basic_meta,
        "lens_type": "progressive",
        "rx_limits": {
            **basic_meta["rx_limits"],
            "add_required": True,
            "add_min": 0.75,
            "add_max": 3.0,
        },
    }
    result = validate_lens(
        rx(right=EyePower("-2", "0"), left=EyePower("-2", "0", "", "4.00")),
        lens(meta),
        meta,
        on_date=TODAY,
    )
    assert not result.valid and any("ADD" in x for x in result.reasons)


# Verify a missing ADD is accepted for a single-vision lens, but not progressive.
def test_missing_add_is_optional_only_for_single_vision(basic_meta):
    "Verify a missing ADD is optional only for single vision."
    no_add = rx(
        right=EyePower("-2", "0", 90, None),
        left=EyePower("-2", "0", 90, None),
    )
    single_vision = validate_lens(no_add, lens(basic_meta), basic_meta, on_date=TODAY)
    assert single_vision.valid

    progressive_meta = {
        **basic_meta,
        "lens_type": "progressive",
        "rx_limits": {
            **basic_meta["rx_limits"],
            "add_required": True,
            "add_min": 0.75,
            "add_max": 3.0,
        },
    }
    progressive = validate_lens(
        no_add,
        LensConfiguration("progressive", "1.6", "standard", "L2"),
        progressive_meta,
        on_date=TODAY,
    )
    assert not progressive.valid
    assert any("ADD is required" in reason for reason in progressive.reasons)


# Verify rx rejects variant mismatch.
def test_rx_rejects_variant_mismatch(basic_meta):
    "Verify rx rejects variant mismatch."
    config = LensConfiguration("progressive", "1.6", "standard", "L1")
    assert not validate_lens(rx(), config, basic_meta, on_date=TODAY).valid


# Verify catalog real seed lens validation.
def test_catalog_real_seed_lens_validation():
    "Verify catalog real seed lens validation."
    products = load_json("products.json")
    v = next(
        v
        for p in products
        for v in p["variants"]
        if v["eluno"].get("line_type") == "lens"
    )
    meta = variant_metadata(str(v["id"]))
    result = validate_lens(
        rx(right=EyePower("0", "0", 90, "1.00"), left=EyePower("0", "0", 90, "1.00")),
        lens(meta, str(v["id"])),
        meta,
        on_date=TODAY,
    )
    assert result.valid


# Verify rx latest valid excludes expired.
def test_rx_latest_valid_excludes_expired():
    "Verify rx latest valid excludes expired."
    assert latest_valid_prescription(
        [rx(expiry=date(2025, 1, 1)), rx(expiry=date(2026, 12, 31))], on_date=TODAY
    ).valid_until == date(2026, 12, 31)


# Verify rate effective dates.
def test_rate_effective_dates():
    "Verify rate effective dates."
    t = tax_catalog()
    assert t.rate_for("90015000", date(2025, 9, 21)) == 1200
    assert t.rate_for("90015000", date(2025, 9, 22)) == 500
    assert t.rate_for("90031900", TODAY) == 1800
    with pytest.raises(ValueError):
        t.rate_for("NOT-A-HSN", TODAY)


# Verify tax reconcile paisa.
def test_tax_reconcile_paisa():
    "Verify tax reconcile paisa."
    for rate in (0, 500, 1200, 1800):
        for amount in (1, 2, 99, 10000, 1907215):
            line = inclusive_tax_line(
                hsn="90015000",
                quantity=1,
                unit_price_paise=amount,
                discount_paise=0,
                rate_bps=rate,
            )
            assert line.taxable_paise + line.cgst_paise + line.sgst_paise == amount
            assert abs(line.cgst_paise - line.sgst_paise) <= 1


# Verify tax discount and multiline.
def test_tax_discount_and_multiline():
    "Verify tax discount and multiline."
    a = inclusive_tax_line(
        hsn="90031900",
        quantity=1,
        unit_price_paise=1299800,
        discount_paise=129980,
        rate_bps=1800,
    )
    b = inclusive_tax_line(
        hsn="90015000",
        quantity=2,
        unit_price_paise=449900,
        discount_paise=45000,
        rate_bps=500,
    )
    totals = invoice_totals([a, b])
    assert totals["gross_paise"] - totals["discount_paise"] == totals["total_paise"]
    assert (
        totals["taxable_paise"] + totals["cgst_paise"] + totals["sgst_paise"]
        == totals["total_paise"]
    )
    with pytest.raises(ValueError):
        inclusive_tax_line(
            hsn="x", quantity=1, unit_price_paise=100, discount_paise=101, rate_bps=500
        )


# Support cart.
def cart(lines):
    "Support cart."
    return Cart("c1", "HSR", tuple(lines))


# Support line.
def line(kind, price, sku, pair=None, variant=None):
    "Support line."
    return CartLine(sku, variant or sku, 1, price, kind, pair)


# Support offers.
def offers():
    "Support offers."
    return load_json("offers.json")


# Verify coupon remains blank until explicitly selected.
def test_coupon_requires_explicit_selection():
    "Verify no coupon applies until the cashier selects one."
    result = evaluate_offers(
        cart([line("frame", 100000, "f")]),
        Customer("c1", "999"),
        offers(),
        on_date=TODAY,
    )
    assert result.total_discount_paise == 0
    assert not any(decision.applied for decision in result.decisions)
    selected = evaluate_offers(
        cart([line("frame", 100000, "f")]),
        Customer("c1", "999"),
        offers(),
        on_date=TODAY,
        selected_offer_id="FESTIVE10",
    )
    assert selected.total_discount_paise == 10000


# Verify explicitly selected coupon is the only applied offer, even when stackable.
def test_selected_coupon_applies_alone():
    "Verify explicitly selected coupon is the only applied offer."
    c = cart(
        [
            line("frame", 200000, "f", "p1"),
            line("lens", 100000, "l", "p1"),
            line("frame", 200000, "f2", "p2"),
            line("lens", 80000, "l2", "p2"),
        ]
    )
    result = evaluate_offers(
        c,
        Customer("c1", "999", ("priority",)),
        offers(),
        on_date=TODAY,
        selected_offer_id="BUNDLE300",
    )
    assert result.total_discount_paise == 30000
    assert {decision.offer_id for decision in result.decisions if decision.applied} == {
        "BUNDLE300"
    }


# Verify manager percentage is exact and excludes every standard promotion.
def test_selected_manager_discount_is_exact_and_exclusive():
    "Verify manager percentage is exact and excludes standard offers."
    result = evaluate_offers(
        cart([line("frame", 100000, "f")]),
        Customer("c1", "999"),
        offers(),
        on_date=TODAY,
        manager_role="store_manager",
        reason_code="walk_out_retention",
        override_bps=500,
        selected_offer_id="MANAGER_OVERRIDE",
    )
    assert result.total_discount_paise == 5000
    assert {decision.offer_id for decision in result.decisions if decision.applied} == {
        "MANAGER_OVERRIDE"
    }


# Verify standalone lens pairs count toward the second-pair lens promotion.
def test_lens_only_pairs_support_lens_offers():
    "Verify standalone lens pairs are offer-eligible without frame bundle discounts."
    c = cart([line("lens", 40000, "l1"), line("lens", 30000, "l2")])
    result = evaluate_offers(
        c, Customer("c1", "999"), offers(), on_date=TODAY,
        selected_offer_id="SECONDPAIR50",
    )
    assert next(
        decision for decision in result.decisions if decision.offer_id == "SECONDPAIR50"
    ).amount_paise == 15000
    assert not next(
        decision for decision in result.decisions if decision.offer_id == "BUNDLE300"
    ).applied


# Verify multiple eligible coupons remain unapplied without selection.
def test_eligible_coupons_are_not_stacked_automatically():
    "Verify eligible coupons remain blank until one is selected."
    c = cart([line("frame", 200000, "f", "p1"), line("lens", 100000, "l", "p1")])
    result = evaluate_offers(
        c, Customer("c1", "999", ("priority",)), offers(), on_date=TODAY
    )
    assert result.total_discount_paise == 0
    assert not any(decision.applied for decision in result.decisions)


# Verify second pair eligible and single pair rejected.
def test_second_pair_eligible_and_single_pair_rejected():
    "Verify second pair eligible and single pair rejected."
    lines = [
        line("frame", 100000, "f1", "p1"),
        line("lens", 40000, "l1", "p1"),
        line("frame", 100000, "f2", "p2"),
        line("lens", 30000, "l2", "p2"),
    ]
    result = evaluate_offers(
        cart(lines), Customer("c1", "999"), offers(), on_date=TODAY,
        selected_offer_id="SECONDPAIR50",
    )
    second = next(x for x in result.decisions if x.offer_id == "SECONDPAIR50")
    assert second.applied and second.amount_paise == 15000
    single = evaluate_offers(
        cart(lines[:2]), Customer("c1", "999"), offers(), on_date=TODAY
    )
    assert not next(x for x in single.decisions if x.offer_id == "SECONDPAIR50").applied


# Verify expired offer and manager requires approval.
def test_expired_offer_and_manager_requires_approval():
    "Verify expired offer and manager requires approval."
    c = cart([line("frame", 100000, "f")])
    customer = Customer("c1", "999")
    result = evaluate_offers(c, customer, offers(), on_date=TODAY)
    assert not next(x for x in result.decisions if x.offer_id == "MONSOON20").applied
    assert not next(
        x for x in result.decisions if x.offer_id == "MANAGER_OVERRIDE"
    ).applied
    permitted = evaluate_offers(
        c,
        customer,
        offers(),
        on_date=TODAY,
        manager_role="store_manager",
        reason_code="LOYALTY",
        override_bps=1000,
        selected_offer_id="MANAGER_OVERRIDE",
    )
    assert (
        any(
            x.offer_id == "MANAGER_OVERRIDE" and x.amount_paise == 10000
            for x in permitted.decisions
            if x.applied
        )
        or permitted.total_discount_paise == 10000
    )


# Verify discount never exceeds gross and reconciles.
def test_discount_never_exceeds_gross_and_reconciles():
    "Verify discount never exceeds gross and reconciles."
    c = cart([line("frame", 1, "f", "p"), line("lens", 1, "l", "p")])
    r = evaluate_offers(c, Customer("c", "", ("priority",)), offers(), on_date=TODAY)
    assert r.total_discount_paise <= 2
    assert all(0 <= d <= 1 for d in r.discounts_paise)
    assert sum(d.amount_paise for d in r.decisions) == r.total_discount_paise
