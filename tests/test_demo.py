"""Acceptance coverage for authenticated stakeholder workflows against the real mock."""

import json
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient
from app.main import app, state_store
from app.security import provision_user
from app.operations import analytics, founder_digest, rows, INDIA, store_day
from test_stage5 import backend


# Isolate API state and provision real role-bound credentials for each test.
@pytest.fixture
def demo(tmp_path, monkeypatch, backend):
    """Isolate API state and provision real role-bound credentials for each test."""
    monkeypatch.setenv("ELUNO_DB_PATH", str(tmp_path / "demo.sqlite3"))
    monkeypatch.setenv("ELUNO_MOCK_URL", str(backend.client.base_url))
    store = state_store()
    for username, role, staff in [
        ("manager", "manager", "S108"),
        ("cashier", "cashier", "S105"),
        ("finance", "finance", "F001"),
        ("doctor", "optometrist", "S107"),
    ]:
        provision_user(
            store, username, "Test-password-2026!", role, "HSR", staff, username.title()
        )
    return TestClient(app), store, backend


# Use the actual password/session flow and attach its anti-CSRF token.
def sign_in(client, username="manager"):
    """Use the actual password/session flow and attach its anti-CSRF token."""
    response = client.post(
        "/auth/login", json={"username": username, "password": "Test-password-2026!"}
    )
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf"]


# Prepare a valid fixture bill while allowing targeted scenario changes.
def prepare(client, **changes):
    """Prepare a valid fixture bill while allowing targeted scenario changes."""
    payload = {
        "phone": "+919000000005",
        "store_code": "HSR",
        "staff_id": "S108",
        "variant_ids": [91000003, 91000083],
    }
    payload.update(changes)
    response = client.post("/sales/prepare", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


# Assert successful completion through the protected original API contract.
def complete(client, checkout_id):
    """Assert successful completion through the protected original API contract."""
    response = client.post(f"/sales/{checkout_id}/complete")
    assert response.status_code == 200, response.text
    return response.json()


# Anonymous calls, missing CSRF and revoked cookies must not reach business logic.
def test_authentication_csrf_and_revocation(demo):
    """Anonymous calls, missing CSRF and revoked cookies must not reach business logic."""
    client, _, _ = demo
    assert client.get("/api/bootstrap").status_code == 401
    assert client.post("/sales/prepare", json={}).status_code == 401
    sign_in(client)
    token = client.headers.pop("X-CSRF-Token")
    assert client.post("/sales/prepare", json={}).status_code == 403
    client.headers["X-CSRF-Token"] = token
    assert client.post("/auth/logout").status_code == 200
    assert client.get("/api/bootstrap").status_code == 401


# Hidden controls are backed by API restrictions on role, staff and store.
def test_role_and_store_cannot_be_spoofed(demo):
    """Hidden controls are backed by API restrictions on role, staff and store."""
    client, _, _ = demo
    sign_in(client, "cashier")
    assert (
        client.post(
            "/refunds/prepare", json={"checkout_id": "x", "reason": "return"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/sales/prepare",
            json={
                "phone": "x",
                "store_code": "HSR",
                "staff_id": "S108",
                "variant_ids": [],
            },
        ).status_code
        == 403
    )
    assert client.get("/api/transactions?store_code=MM").status_code == 403
    assert (
        client.post(
            "/api/till/close", json={"store_code": "HSR", "amount_paise": 0}
        ).status_code
        == 403
    )
    assert client.post("/api/prescriptions", json={}).status_code == 403
    assert client.get("/api/audit").status_code == 403
    sign_in(client, "finance")
    assert client.post("/sales/prepare", json={}).status_code == 403


# Three wearers share one invoice while preserving three prescription references.
def test_family_distinct_prescriptions_single_order(demo):
    """Three wearers share one invoice while preserving three prescription references."""
    client, _, gateway = demo
    sign_in(client)
    quote = prepare(
        client,
        variant_ids=[],
        members=[
            {"phone": "+919000000005", "variant_ids": [91000003, 91000083]},
            {"phone": "+919000000004", "variant_ids": [91000005, 91000083]},
            {"phone": "+919000000007", "variant_ids": [91000006, 91000083]},
        ],
    )
    finished = complete(client, quote["checkout_id"])
    order = gateway.order_by_id(finished["shopify_order_id"])
    lens_lines = [
        line
        for line in order["line_items"]
        if any(prop["name"] == "rx_id" for prop in line["properties"])
    ]
    assert len(order["line_items"]) == 6
    assert (
        len(
            {
                next(
                    prop["value"]
                    for prop in line["properties"]
                    if prop["name"] == "rx_id"
                )
                for line in lens_lines
            }
        )
        == 3
    )
    assert (
        complete(client, quote["checkout_id"])["shopify_order_id"]
        == finished["shopify_order_id"]
    )


# Cancelling an unpaid bill preserves its number and blocks subsequent charging.
def test_cancelled_invoice_retained_and_next_number(demo):
    """Cancelling an unpaid bill preserves its number and blocks subsequent charging."""
    client, _, _ = demo
    sign_in(client)
    first = prepare(client)
    assert (
        client.post(
            "/api/checkouts/" + first["checkout_id"] + "/cancel",
            json={"reason": "customer changed mind"},
        ).status_code
        == 200
    )
    assert (
        client.post("/sales/" + first["checkout_id"] + "/complete").status_code == 409
    )
    second = prepare(client)
    register = client.get("/api/register?store_code=HSR").json()
    assert [item["status"] for item in register] == ["cancelled", "reserved"]
    assert first["invoice_no"] != second["invoice_no"]


# An override without a reason fails; a valid approval survives on the source order.
def test_manager_reason_and_identity_persist(demo):
    """An override without a reason fails; a valid approval survives on the source order."""
    client, _, gateway = demo
    sign_in(client)
    denied = client.post(
        "/sales/prepare",
        json={
            "phone": "+919000000005",
            "store_code": "HSR",
            "staff_id": "S108",
            "variant_ids": [91000003, 91000083],
            "override_bps": 1001,
            "reason_code": "retention",
        },
    )
    assert denied.status_code == 422
    quote = prepare(client, override_bps=500, reason_code="walk_out_retention")
    result = complete(client, quote["checkout_id"])
    attributes = {
        item["name"]: item["value"]
        for item in gateway.order_by_id(result["shopify_order_id"])["note_attributes"]
    }
    assert attributes["discount_approver"] == "S108"
    assert attributes["discount_reason"] == "walk_out_retention"


# Physical cash reconciles exactly after a sale, full return and reasoned expense.
def test_cash_sale_expense_refund_close(demo):
    """Physical cash reconciles exactly after a sale, full return and reasoned expense."""
    client, _, _ = demo
    sign_in(client)
    quote = prepare(client, payment_method="cash")
    assert (
        client.post("/sales/" + quote["checkout_id"] + "/complete").status_code == 409
    )
    assert (
        client.post(
            "/api/till/open", json={"store_code": "HSR", "amount_paise": 200000}
        ).status_code
        == 200
    )
    complete(client, quote["checkout_id"])
    summary = client.get("/api/till?store_code=HSR").json()
    assert summary["expected_paise"] == 200000 + quote["total_paise"]
    assert (
        client.post(
            "/api/till/expense",
            json={"store_code": "HSR", "amount_paise": 5000, "reason": "courier"},
        ).status_code
        == 200
    )
    refund = client.post(
        "/refunds/prepare",
        json={"checkout_id": quote["checkout_id"], "reason": "customer return"},
    ).json()
    assert (
        client.post("/refunds/" + refund["refund_id"] + "/complete").status_code == 200
    )
    assert client.get("/api/till?store_code=HSR").json()["expected_paise"] == 195000
    closed = client.post(
        "/api/till/close", json={"store_code": "HSR", "amount_paise": 195000}
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["variance_paise"] == 0


# Only a variance above ₹200 flags finance, and repeated digest generation queues once.
def test_variance_threshold_and_digest_idempotency(demo):
    """Only a variance above ₹200 flags finance, and repeated digest generation queues once."""
    client, store, gateway = demo
    sign_in(client)
    client.post("/api/till/open", json={"store_code": "HSR", "amount_paise": 50000})
    response = client.post(
        "/api/till/close", json={"store_code": "HSR", "amount_paise": 29999}
    )
    assert response.json()["flagged"] is True
    day = datetime.now(INDIA).date().isoformat()
    founder_digest(store, gateway, day)
    founder_digest(store, gateway, day)
    assert len(rows(store, "SELECT * FROM outbox")) == 2


# New prescriptions require a clinician and reject off-grid axis values.
def test_clinical_axis_validation_and_role(demo):
    """New prescriptions require a clinician and reject off-grid axis values."""
    client, _, _ = demo
    sign_in(client, "doctor")
    eye = {"sph": -2, "cyl": -0.5, "axis": 91, "add": 2.5}
    body = {
        "phone": "+919000000005",
        "valid_until": (datetime.now(INDIA).date() + timedelta(days=90)).isoformat(),
        "od": eye.copy(),
        "os": eye.copy(),
    }
    assert client.post("/api/prescriptions", json=body).status_code == 422
    body["od"]["axis"] = body["os"]["axis"] = 90
    response = client.post("/api/prescriptions", json=body)
    assert response.status_code == 200, response.text
    assert response.json()["optometrist_id"] == "S107"
    sign_in(client, "manager")
    quote = prepare(client)
    detail = client.get("/api/checkouts/" + quote["checkout_id"] + "/detail").json()
    assert detail["quote"]["lines"][1]["rx_id"] == response.json()["rx_id"]


# Prevent mixed legacy date-only and clinical timezone-aware records breaking billing.
def test_prescription_order_accepts_mixed_timestamp_shapes():
    """A newer aware clinical entry must sort after an older naive fixture record."""
    from app.domain.models import Prescription, EyePower
    from app.services.prescriptions import latest_valid_prescription
    from datetime import date, timezone

    eye = EyePower("-2", "0")
    legacy = Prescription(
        "legacy", "phone", eye, eye, date(2027, 1, 1), datetime(2026, 1, 1)
    )
    clinical = Prescription(
        "clinical",
        "phone",
        eye,
        eye,
        date(2027, 1, 1),
        datetime(2026, 10, 25, tzinfo=timezone.utc),
    )
    assert (
        latest_valid_prescription([legacy, clinical], on_date=date(2026, 10, 25))
        == clinical
    )


# A company-paid replacement creates a zero-charge lens order linked to the original.
def test_company_remake_does_not_touch_frame(demo):
    """A company-paid replacement creates a zero-charge lens order linked to the original."""
    client, _, gateway = demo
    sign_in(client)
    original = prepare(client)
    complete(client, original["checkout_id"])
    before = gateway.stock(92000003, 70000002)
    response = client.post(
        "/api/remakes/prepare",
        json={
            "checkout_id": original["checkout_id"],
            "lens_variant_id": 91000083,
            "wearer_phone": "+919000000005",
            "reason": "progressive adaptation",
            "cost_owner": "company",
            "lab_cost_paise": 120000,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["total_paise"] == 0
    result = complete(client, response.json()["checkout_id"])
    assert gateway.stock(92000003, 70000002) == before
    order = gateway.order_by_id(result["shopify_order_id"])
    assert len(order["line_items"]) == 1
    assert order["line_items"][0]["variant_id"] == 91000083
    assert original["invoice_no"] in next(
        item["value"] for item in order["note_attributes"] if item["name"] == "remake"
    )


# Source-backed report totals change after refund and retain original tax evidence.
def test_source_channels_refunds_and_credit_detail(demo):
    """Source-backed report totals change after refund and retain original tax evidence."""
    client, _, gateway = demo
    sign_in(client)
    quote = prepare(client, channel="whatsapp")
    result = complete(client, quote["checkout_id"])
    day = store_day(gateway.order_by_id(result["shopify_order_id"])["created_at"])
    report = client.get(
        "/api/reports", params={"day": day, "store_code": "HSR"}
    ).json()["stores"][0]
    assert report["channels"]["whatsapp"] >= quote["total_paise"]
    assert report["reconciliation_delta_paise"] == 0
    refund = client.post(
        "/refunds/prepare",
        json={"checkout_id": quote["checkout_id"], "reason": "return"},
    ).json()
    client.post("/refunds/" + refund["refund_id"] + "/complete")
    after = client.get("/api/reports", params={"day": day, "store_code": "HSR"}).json()[
        "stores"
    ][0]
    assert after["refunds_paise"] - report["refunds_paise"] == quote["total_paise"]
    detail = client.get("/api/checkouts/" + quote["checkout_id"] + "/detail").json()
    assert detail["refunds"][0]["status"] == "recorded"
    assert detail["quote"]["lines"][0]["hsn"]


# Sunglasses can sell without an Rx and cart drafts persist for the signed-in user.
def test_sunglasses_and_draft_restore(demo):
    """Sunglasses can sell without an Rx and cart drafts persist for the signed-in user."""
    client, _, gateway = demo
    sign_in(client)
    catalog = client.get("/api/bootstrap").json()["catalog"]
    sunglasses = next(
        item
        for item in catalog
        if item["eluno"].get("category") == "sunglasses"
        and gateway.stock(item["inventory_item_id"], 70000002) > 0
    )
    quote = prepare(client, variant_ids=[sunglasses["id"]])
    complete(client, quote["checkout_id"])
    draft = {"members": [{"phone": "+919000000005", "variant_ids": [sunglasses["id"]]}]}
    assert client.put("/api/draft", json=draft).status_code == 200
    assert client.get("/api/draft").json() == draft


# UTC midnight boundaries and mock tuple/numeric keys survive serialization.
def test_store_day_and_persistent_mock_snapshot():
    """UTC midnight boundaries and mock tuple/numeric keys survive serialization."""
    from scripts.persistent_mock import load_mock, snapshot_state, restore_state

    assert store_day("2026-10-24T20:00:00+00:00") == "2026-10-25"
    source = load_mock().S
    restored = restore_state(json.loads(json.dumps(snapshot_state(source))))
    assert restored["inventory"] == source["inventory"]
    assert restored["orders"] == source["orders"]
