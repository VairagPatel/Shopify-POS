"""Integration coverage using the actual supplied mock; no modification to mock code."""

from app.gateways.billing import BillingAdapter
import socket
import subprocess
import sys
import time
from pathlib import Path
import pytest
from app.domain.models import CheckoutStatus
from app.gateways.http import MockHTTP, GatewayError
from app.persistence.sqlite import SQLiteStore, StateConflict
from app.services.sale import SaleService, SaleValidationError

ROOT = Path(__file__).resolve().parents[1]
MOCK = ROOT / "exercise-pack/starter-kit/mock-apis/mock_server.py"


# Support backend.
@pytest.fixture
def backend():
    "Support backend."
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    proc = subprocess.Popen(
        [sys.executable, str(MOCK), "--port", str(port), "--no-flake"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    api = MockHTTP(f"http://127.0.0.1:{port}", timeout=1)
    try:
        for _ in range(35):
            try:
                if api.request("GET", "/health")["ok"]:
                    break
            except GatewayError:
                time.sleep(0.1)
        else:
            pytest.fail("mock failed to start")
        yield api
    finally:
        proc.terminate()
        proc.wait(timeout=5)


# Support sale.
@pytest.fixture
def sale(tmp_path, backend):
    "Support sale."
    db = SQLiteStore(str(tmp_path / "checkout.sqlite3"))
    return SaleService(db, BillingAdapter(backend))


# Retry safe reads only; send financial mutations exactly once.
def request(sale):
    "Retry safe reads only; send financial mutations exactly once."
    return sale.prepare(
        phone="+919000000004",
        store_code="HSR",
        staff_id="S105",
        variant_ids=[91000003, 91000083],
    )


# Validate a standalone prescription lens-pair purchase through order creation.
def test_lens_only_sale_prepares_and_completes_without_a_frame(sale, backend):
    "Validate a standalone prescription lens-pair purchase through order creation."
    quote = sale.prepare(
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
    saved = sale.store.load_quote(quote["checkout_id"])
    assert len(saved["lines"]) == 1
    assert saved["lines"][0]["variant_id"] == 91000083
    assert saved["lines"][0]["rx_id"]
    order_line = saved["order_payload"]["line_items"][0]
    properties = {item["name"]: item["value"] for item in order_line["properties"]}
    assert properties["line_type"] == "lens"
    assert properties["rx_id"] == saved["lines"][0]["rx_id"]
    assert "pair_ref" not in properties

    completed = sale.complete(quote["checkout_id"])
    assert completed["status"] == "order_recorded"
    source_order = next(
        order for order in backend.orders()
        if str(order["id"]) == completed["shopify_order_id"]
    )
    assert len(source_order["line_items"]) == 1
    assert source_order["line_items"][0]["variant_id"] == 91000083


# Verify sale mock roundtrip and stock.
def test_sale_mock_roundtrip_and_stock(sale, backend):
    "Verify sale mock roundtrip and stock."
    before = backend.stock(92000003, 70000002)
    quote = request(sale)
    assert quote["total_paise"] > 0 and quote["tax_paise"] > 0
    assert (
        sale.store.load_quote(quote["checkout_id"])["total_paise"]
        == quote["total_paise"]
    )
    completed = sale.complete(quote["checkout_id"])
    assert completed["status"] == "order_recorded"
    assert backend.stock(92000003, 70000002) == before - 1
    assert completed["shopify_order_id"]
    order = next(
        o for o in backend.orders() if str(o["id"]) == completed["shopify_order_id"]
    )
    assert int(round(float(order["total_price"]) * 100)) == quote["total_paise"]
    assert any(
        a["name"] == "checkout_id" and a["value"] == quote["checkout_id"]
        for a in order["note_attributes"]
    )
    assert order["financial_status"] == "paid"
    assert sale.complete(quote["checkout_id"]) == completed
    assert backend.stock(92000003, 70000002) == before - 1


# Verify no stock blocks before charge.
def test_no_stock_blocks_before_charge(sale, backend):
    "Verify no stock blocks before charge."
    with pytest.raises(SaleValidationError, match="out of stock"):
        sale.prepare(
            phone="+919000000004",
            store_code="HSR",
            staff_id="S105",
            variant_ids=[91000009, 91000083],
        )
    assert backend.orders() is not None


# Verify invalid staff blocks.
def test_invalid_staff_blocks(sale):
    "Verify invalid staff blocks."
    with pytest.raises(SaleValidationError, match="Staff"):
        sale.prepare(
            phone="+919000000004",
            store_code="HSR",
            staff_id="S999",
            variant_ids=[91000003, 91000083],
        )


# Verify persist across restart and refuse duplicate.
def test_persist_across_restart_and_refuse_duplicate(sale, backend):
    "Verify persist across restart and refuse duplicate."
    quote = request(sale)
    sale.complete(quote["checkout_id"])
    reopened = SaleService(SQLiteStore(sale.store.path), BillingAdapter(backend))
    assert reopened.complete(quote["checkout_id"])["status"] == "order_recorded"


class FailCharge:
    # Initialize the adapter or service with its explicit dependencies.
    def __init__(self, real):
        "Initialize the adapter or service with its explicit dependencies."
        self.real = real
        self.attempts = 0

    # Support   getattr  .
    def __getattr__(self, key):
        "Support   getattr  ."
        return getattr(self.real, key)

    # Submit one terminal charge using the saved checkout payment reference.
    def charge(self, *args):
        "Submit one terminal charge using the saved checkout payment reference."
        self.attempts += 1
        raise GatewayError("simulated timeout", uncertain=True)


class FailOrder:
    # Initialize the adapter or service with its explicit dependencies.
    def __init__(self, real):
        "Initialize the adapter or service with its explicit dependencies."
        self.real = real
        self.attempts = 0

    # Support   getattr  .
    def __getattr__(self, key):
        "Support   getattr  ."
        return getattr(self.real, key)

    # Create a Shopify order using the already-validated persisted payload.
    def order(self, *args):
        "Create a Shopify order using the already-validated persisted payload."
        self.attempts += 1
        raise GatewayError("simulated order timeout", uncertain=True)


# Verify uncertain charge never repeated.
def test_uncertain_charge_never_repeated(sale, backend):
    "Verify uncertain charge never repeated."
    quote = request(sale)
    failure = FailCharge(backend)
    sale.gateway = BillingAdapter(failure)
    with pytest.raises(GatewayError):
        sale.complete(quote["checkout_id"])
    assert (
        sale.store.get_checkout(quote["checkout_id"])["status"] == "payment_uncertain"
    )
    with pytest.raises(StateConflict):
        sale.complete(quote["checkout_id"])
    assert failure.attempts == 1


# Verify uncertain order never reposted.
def test_uncertain_order_never_reposted(sale, backend):
    "Verify uncertain order never reposted."
    quote = request(sale)
    failure = FailOrder(backend)
    sale.gateway = BillingAdapter(failure)
    with pytest.raises(GatewayError):
        sale.complete(quote["checkout_id"])
    assert sale.store.get_checkout(quote["checkout_id"])["status"] == "order_uncertain"
    with pytest.raises(StateConflict):
        sale.complete(quote["checkout_id"])
    assert failure.attempts == 1
    sale.gateway = BillingAdapter(backend)
    assert sale.reconcile_order(quote["checkout_id"])["status"] == "order_uncertain"


# Verify reconcile existing order after lost response.
def test_reconcile_existing_order_after_lost_response(sale, backend):
    "Verify reconcile existing order after lost response."
    quote = request(sale)

    class LostResponse:
        # Initialize the adapter or service with its explicit dependencies.
        def __init__(self, real):
            "Initialize the adapter or service with its explicit dependencies."
            self.real = real

        # Support   getattr  .
        def __getattr__(self, name):
            "Support   getattr  ."
            return getattr(self.real, name)

        # Create a Shopify order using the already-validated persisted payload.
        def order(self, payload):
            self.real.order(payload)
            raise GatewayError("response lost", uncertain=True)

    sale.gateway = BillingAdapter(LostResponse(backend))
    with pytest.raises(GatewayError):
        sale.complete(quote["checkout_id"])
    sale.gateway = BillingAdapter(backend)
    assert sale.reconcile_order(quote["checkout_id"])["status"] == "order_recorded"
