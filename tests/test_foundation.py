import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.domain.models import CartLine, CheckoutStatus
from app.persistence.sqlite import SQLiteStore, StateConflict, CheckoutNotFound


# Support store.
@pytest.fixture
def store(tmp_path):
    "Support store."
    return SQLiteStore(str(tmp_path / "state.db"))


# Verify health.
def test_health(tmp_path, monkeypatch):
    monkeypatch.setenv("ELUNO_DB_PATH", str(tmp_path / "api.db"))
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "stage": 6, "checkout_enabled": True}


# Verify checkout is durable.
def test_checkout_is_durable(store, tmp_path):
    "Verify checkout is durable."
    c = store.create_checkout("HSR", "customer1")
    assert (
        SQLiteStore(str(tmp_path / "state.db")).get_checkout(c["checkout_id"])["status"]
        == "draft"
    )
    with pytest.raises(StateConflict):
        store.create_checkout("HSR", checkout_id=c["checkout_id"])


# Verify checkout compare and set.
def test_checkout_compare_and_set(store):
    "Verify checkout compare and set."
    c = store.create_checkout("HSR")
    result = store.change_status(
        c["checkout_id"], CheckoutStatus.DRAFT, CheckoutStatus.PAYMENT_PENDING
    )
    assert result["status"] == "payment_pending"
    with pytest.raises(StateConflict):
        store.change_status(
            c["checkout_id"], CheckoutStatus.DRAFT, CheckoutStatus.CANCELLED
        )


# Verify invoice per store repeat and restart.
def test_invoice_per_store_repeat_and_restart(store, tmp_path):
    "Verify invoice per store repeat and restart."
    a = store.create_checkout("HSR")
    b = store.create_checkout("HSR")
    c = store.create_checkout("KOR")
    first = store.reserve_invoice(a["checkout_id"], "HSR", "HSR-")
    second = store.reserve_invoice(b["checkout_id"], "HSR", "HSR-")
    other = store.reserve_invoice(c["checkout_id"], "KOR", "KOR-")
    assert (first, second, other) == ("HSR-000001", "HSR-000002", "KOR-000001")
    reopened = SQLiteStore(str(tmp_path / "state.db"))
    assert reopened.reserve_invoice(a["checkout_id"], "HSR", "HSR-") == first
    assert len(reopened.invoice_allocations("HSR")) == 2
    with pytest.raises(StateConflict):
        store.reserve_invoice(a["checkout_id"], "KOR", "KOR-")
    with pytest.raises(StateConflict):
        store.reserve_invoice(
            store.create_checkout("HSR")["checkout_id"], "HSR", "WRONG-"
        )


# Verify ref unique and immutable.
def test_ref_unique_and_immutable(store):
    "Verify ref unique and immutable."
    a = store.create_checkout("HSR")["checkout_id"]
    b = store.create_checkout("HSR")["checkout_id"]
    store.record_external_ref(a, "payment_ref", "ref1")
    store.record_external_ref(a, "payment_ref", "ref1")
    with pytest.raises(StateConflict):
        store.record_external_ref(a, "payment_ref", "ref2")
    with pytest.raises(StateConflict):
        store.record_external_ref(b, "payment_ref", "ref1")
    with pytest.raises(ValueError):
        store.record_external_ref(a, "status", "paid")


# Verify domain guardrails.
def test_domain_guardrails():
    "Verify domain guardrails."
    with pytest.raises(ValueError):
        CartLine("F", "123", 0, 10, "frame")
    with pytest.raises(ValueError):
        CartLine("F", "123", 1, -1, "frame")
