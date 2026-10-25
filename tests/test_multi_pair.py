"""Multi-pair support against the unmodified Shopify/store/terminal mock."""

import pytest
from app.services.sale import SaleValidationError, SaleService
from app.services.refunds import RefundService
from app.persistence.sqlite import SQLiteStore
from test_stage5 import backend


# Support cart env.
@pytest.fixture
def cart_env(tmp_path, backend):
    "Support cart env."
    service = SaleService(SQLiteStore(str(tmp_path / "multipair.db")), backend)
    return service, backend


# Support multi.
def multi(service, variants=None):
    "Support multi."
    return service.prepare(
        phone="+919000000005",
        store_code="HSR",
        staff_id="S105",
        variant_ids=variants or [91000003, 91000005, 91000083, 91000084],
    )


# Verify two pairs prescription offer order and full refund.
def test_two_pairs_prescription_offer_order_and_full_refund(cart_env):
    "Verify two pairs prescription offer order and full refund."
    service, api = cart_env
    before = {
        v: api.stock(item, 70000002)
        for v, item in [(91000003, 92000003), (91000005, 92000005)]
    }
    if not all(q >= 1 for q in before.values()):
        pytest.skip("Seed has insufficient inventory for selected two frames")
    q = multi(service)
    saved = service.store.load_quote(q["checkout_id"])
    lines = saved["order_payload"]["line_items"]
    assert len(lines) == 4
    props = [{p["name"]: p["value"] for p in line["properties"]} for line in lines]
    assert [p["pair_ref"] for p in props] == ["1", "2", "1", "2"]
    assert all(props[i]["rx_id"] for i in (2, 3))
    assert any(d["offer_id"] == "SECONDPAIR50" and d["applied"] for d in q["offers"])
    recorded = service.complete(q["checkout_id"])
    order = api.order_by_id(recorded["shopify_order_id"])
    assert len(order["line_items"]) == 4
    assert all(
        api.stock(item, 70000002) == before[v] - 1
        for v, item in [(91000003, 92000003), (91000005, 92000005)]
    )
    refund = RefundService(service.store, api)
    prepared = refund.prepare(q["checkout_id"], "returned")
    refund.complete(prepared["refund_id"])
    assert all(
        api.stock(item, 70000002) == before[v]
        for v, item in [(91000003, 92000003), (91000005, 92000005)]
    )
    result = api.order_by_id(recorded["shopify_order_id"])["refunds"][0]
    assert sorted(line["restock_type"] for line in result["refund_line_items"]) == [
        "no_restock",
        "no_restock",
        "return",
        "return",
    ]


# Verify reject mismatched pair counts.
def test_reject_mismatched_pair_counts(cart_env):
    "Verify reject mismatched pair counts."
    service, _ = cart_env
    with pytest.raises(SaleValidationError, match="one frame for each lens"):
        multi(service, [91000003, 91000005, 91000083])


# Verify reject repeated variant without quantity model.
def test_reject_repeated_variant_without_quantity_model(cart_env):
    "Verify reject repeated variant without quantity model."
    service, _ = cart_env
    with pytest.raises(SaleValidationError, match="Duplicate variant"):
        multi(service, [91000003, 91000003, 91000083, 91000084])
