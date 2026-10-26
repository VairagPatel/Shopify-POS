"""Multi-item cashier, stock and refund acceptance tests against the source mock."""

from concurrent.futures import ThreadPoolExecutor
import pytest
from test_production_matrix import production_env, identity_template, backend


# Build the same wearer-based request the cashier screen submits.
def cart(ids, **changes):
    return {
        "phone": "+919000000004",
        "store_code": "HSR",
        "staff_id": "S105",
        "variant_ids": [],
        "members": [{"phone": "+919000000004", "variant_ids": ids}],
        **changes,
    }


# Assert sale/refund effects for multiple frames, repeated units and multiple pairs.
@pytest.mark.parametrize(
    "ids",
    [
        [91000003, 91000083],
        [91000003, 91000083, 91000005, 91000084],
        [91000003, 91000005, 91000083, 91000084],
    ],
)
def test_multi_item_sale_and_refund(production_env, ids):
    clients, store, source, _ = production_env
    client = clients("cashier")
    before = source.stock(92000003, 70000002)
    response = client.post("/sales/prepare", json=cart(ids))
    assert response.status_code == 200, response.text
    identifier = response.json()["checkout_id"]
    quote = store.load_quote(identifier)
    assert len(quote["lines"]) == len(ids)
    result = client.post(f"/sales/{identifier}/complete")
    assert result.status_code == 200, result.text
    order = source.order_by_id(result.json()["shopify_order_id"])
    assert sum(line["quantity"] for line in order["line_items"]) == len(ids)
    assert source.stock(92000003, 70000002) == before - ids.count(91000003)
    manager = clients("manager")
    refund = manager.post(
        "/refunds/prepare", json={"checkout_id": identifier, "reason": "returned"}
    )
    assert refund.status_code == 200, refund.text
    assert (
        manager.post("/refunds/" + refund.json()["refund_id"] + "/complete").status_code
        == 200
    )
    assert source.stock(92000003, 70000002) == before


# Aggregate repeated units before reserving invoices or charging payments.
def test_combined_quantity_cannot_exceed_stock(production_env):
    clients, _, source, _ = production_env
    stock = source.stock(92000003, 70000002)
    response = clients("cashier").post(
        "/sales/prepare", json=cart([91000003, 91000083] * (stock + 1))
    )
    assert response.status_code == 422, response.text


# A prepared quote is not a stock reservation; recheck before accepting money.
def test_stale_quote_cannot_charge_after_stock_consumed(production_env):
    clients, store, source, _ = production_env
    client = clients("cashier")
    stock = source.stock(92000003, 70000002)
    first = client.post("/sales/prepare", json=cart([91000003, 91000083])).json()["checkout_id"]
    second = client.post("/sales/prepare", json=cart([91000003, 91000083] * stock))
    assert second.status_code == 200, second.text
    assert (
        client.post("/sales/" + second.json()["checkout_id"] + "/complete").status_code
        == 200
    )
    response = client.post("/sales/" + first + "/complete")
    assert response.status_code == 409, response.text
    assert store.get_checkout(first)["status"] == "draft"
    assert not store.get_checkout(first).get("payment_charge_id")


# Concurrent confirmation must return the same order and decrement stock only once.
def test_concurrent_completion_is_idempotent(production_env):
    clients, _, source, _ = production_env
    before = source.stock(92000003, 70000002)
    identifier = (
        clients("cashier")
        .post("/sales/prepare", json=cart([91000003, 91000083]))
        .json()["checkout_id"]
    )

    # Give each thread its own cookie jar and request connection.
    def complete(_):
        return clients("cashier").post("/sales/" + identifier + "/complete")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(complete, range(2)))
    assert all(result.status_code == 200 for result in results)
    assert len({result.json()["shopify_order_id"] for result in results}) == 1
    assert source.stock(92000003, 70000002) == before - 1


# Retrying an already-recorded cash refund must not need a fresh drawer session.
def test_completed_cash_refund_repeat_after_close(production_env):
    clients, _, _, _ = production_env
    manager = clients("manager")
    assert (
        manager.post(
            "/api/till/open", json={"store_code": "HSR", "amount_paise": 100000}
        ).status_code
        == 200
    )
    sale = (
        clients("cashier")
        .post("/sales/prepare", json=cart([91000003, 91000083], payment_method="cash"))
        .json()["checkout_id"]
    )
    assert clients("cashier").post("/sales/" + sale + "/complete").status_code == 200
    refund = manager.post(
        "/refunds/prepare", json={"checkout_id": sale, "reason": "returned"}
    ).json()["refund_id"]
    assert manager.post("/refunds/" + refund + "/complete").status_code == 200
    assert (
        manager.post(
            "/api/till/close", json={"store_code": "HSR", "amount_paise": 100000}
        ).status_code
        == 200
    )
    assert manager.post("/refunds/" + refund + "/complete").status_code == 200


# Standalone sunglasses must not inherit another wearer's prescription-frame check.
def test_family_sunglasses_and_prescription_pair(production_env):
    clients, _, source, _ = production_env
    client = clients("cashier")
    catalog = client.get("/api/bootstrap").json()["catalog"]
    sunglasses = next(
        item
        for item in catalog
        if item["eluno"].get("category") == "sunglasses"
        and source.stock(item["inventory_item_id"], 70000002) > 0
    )
    response = client.post(
        "/sales/prepare",
        json=cart(
            [],
            members=[
                {"phone": "+919000000004", "variant_ids": [sunglasses["id"]]},
                {"phone": "+919000000004", "variant_ids": [91000003, 91000083]},
            ],
        ),
    )
    assert response.status_code == 200, response.text
