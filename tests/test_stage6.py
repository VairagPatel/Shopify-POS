"""Mock integration coverage for Stage 6, isolated fresh server per test."""

from datetime import datetime
import pytest
from app.services.refunds import RefundService, RefundValidationError
from app.services.reporting import DayEndService
from app.persistence.sqlite import StateConflict, SQLiteStore
from app.gateways.http import GatewayError
from app.services.sale import SaleService
from test_stage5 import backend


# Support ready.
@pytest.fixture
def ready(tmp_path, backend):
    "Support ready."
    store = SQLiteStore(str(tmp_path / "state.sqlite3"))
    sale = SaleService(store, backend)
    quote = sale.prepare(
        phone="+919000000005",
        store_code="HSR",
        staff_id="S105",
        variant_ids=[91000003, 91000083],
    )
    finished = sale.complete(quote["checkout_id"])
    return store, backend, quote, finished


# Verify full refund amount tax and stock.
def test_full_refund_amount_tax_and_stock(ready):
    "Verify full refund amount tax and stock."
    store, api, quote, finished = ready
    svc = RefundService(store, api)
    before = api.stock(92000003, 70000002)
    preview = svc.prepare(quote["checkout_id"], "customer_return")
    assert preview["amount_paise"] == quote["total_paise"]
    assert preview["tax_reversed_paise"] == quote["tax_paise"]
    assert api.stock(92000003, 70000002) == before
    res = svc.complete(preview["refund_id"])
    assert res["status"] == "recorded"
    assert api.stock(92000003, 70000002) == before + 1
    order = api.order_by_id(finished["shopify_order_id"])
    assert order["financial_status"] == "refunded"
    assert len(order["refunds"]) == 1
    assert sorted(
        x["restock_type"] for x in order["refunds"][0]["refund_line_items"]
    ) == ["no_restock", "return"]
    assert svc.complete(preview["refund_id"])["status"] == "recorded"
    assert len(api.order_by_id(finished["shopify_order_id"])["refunds"]) == 1
    with pytest.raises(RefundValidationError, match="Existing refund"):
        svc.prepare(quote["checkout_id"], "duplicate")


# Verify terminal refund uncertain is not retried.
def test_terminal_refund_uncertain_is_not_retried(ready):
    "Verify terminal refund uncertain is not retried."
    store, api, quote, _ = ready
    svc = RefundService(store, api)
    preview = svc.prepare(quote["checkout_id"], "customer_return")

    class LostTerminal:
        calls = 0

        # Support   getattr  .
        def __getattr__(self, name):
            "Support   getattr  ."
            return getattr(api, name)

        # Submit one terminal refund against the captured charge.
        def terminal_refund(self, *a):
            "Submit one terminal refund against the captured charge."
            self.calls += 1
            raise GatewayError("lost response", uncertain=True)

    fail = LostTerminal()
    svc.gateway = fail
    with pytest.raises(GatewayError):
        svc.complete(preview["refund_id"])
    with pytest.raises(StateConflict):
        svc.complete(preview["refund_id"])
    assert fail.calls == 1
    assert store.get_refund(preview["refund_id"])["status"] == "terminal_uncertain"


# Verify lost shopify refund response reconciles.
def test_lost_shopify_refund_response_reconciles(ready):
    "Verify lost shopify refund response reconciles."
    store, api, quote, _ = ready
    svc = RefundService(store, api)
    preview = svc.prepare(quote["checkout_id"], "return")

    class LostShopify:
        # Support   getattr  .
        def __getattr__(self, name):
            "Support   getattr  ."
            return getattr(api, name)

        # Record the tax and inventory reversal in the source Shopify order.
        def create_refund(self, oid, payload):
            api.create_refund(oid, payload)
            raise GatewayError("response dropped", uncertain=True)

    svc.gateway = LostShopify()
    with pytest.raises(GatewayError):
        svc.complete(preview["refund_id"])
    assert store.get_refund(preview["refund_id"])["status"] == "shopify_uncertain"
    with pytest.raises(StateConflict):
        svc.complete(preview["refund_id"])
    svc.gateway = api
    assert svc.reconcile_shopify(preview["refund_id"])["status"] == "recorded"


# Verify report from shopify after refund.
def test_report_from_shopify_after_refund(ready):
    "Verify report from shopify after refund."
    store, api, quote, finished = ready
    when = (
        datetime.fromisoformat(
            api.order_by_id(finished["shopify_order_id"])["created_at"]
        )
        .date()
        .isoformat()
    )
    report = DayEndService(api).report("HSR", when)
    assert finished["shopify_order_id"] in [str(i) for i in report["order_ids"]]
    assert report["bill_count"] >= 1
    assert (
        report["gross_paise"] - report["discounts_paise"] - report["tax_paise"]
        == report["taxable_paise"]
    )
    svc = RefundService(store, api)
    preview = svc.prepare(quote["checkout_id"], "return")
    svc.complete(preview["refund_id"])
    after = DayEndService(api).report("HSR", when)
    assert after["refunds_paise"] - report["refunds_paise"] == quote["total_paise"]
    assert (
        after["net_collected_paise"]
        == report["net_collected_paise"] - quote["total_paise"]
    )


# Verify refund prepare does not restock or refund.
def test_refund_prepare_does_not_restock_or_refund(ready):
    "Verify refund prepare does not restock or refund."
    store, api, quote, finished = ready
    r = RefundService(store, api)
    before = api.stock(92000003, 70000002)
    r.prepare(quote["checkout_id"], "return")
    assert api.stock(92000003, 70000002) == before
    assert not api.order_by_id(finished["shopify_order_id"])["refunds"]
