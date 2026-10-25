"""Role × endpoint, malformed input and IDOR checks in isolated environments."""

import shutil
import time
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.persistence.sqlite import SQLiteStore
from app.security import initialize_security, provision_user, login
from endpoint_matrix import ENDPOINTS, ALL
from test_stage5 import backend


# Hash real credentials once; each test receives an independent database copy and source mock.
@pytest.fixture(scope="session")
def identity_template(tmp_path_factory):
    """Provision all five roles with real password hashes and revocable sessions."""
    path = tmp_path_factory.mktemp("identities") / "template.sqlite3"
    store = SQLiteStore(str(path))
    initialize_security(store)
    sessions = {}
    for role, staff in [
        ("cashier", "S105"),
        ("manager", "S108"),
        ("optometrist", "S107"),
        ("finance", "F001"),
        ("admin", "S108"),
    ]:
        provision_user(
            store,
            role,
            "Acceptance-password-2026!",
            role,
            "*" if role in {"admin", "finance"} else "HSR",
            staff,
            role.title(),
        )
        token, csrf, _ = login(store, role, "Acceptance-password-2026!")
        sessions[role] = (token, csrf, staff)
    return path, sessions


# Reuse only immutable identity setup, never business state between cases.
@pytest.fixture
def production_env(tmp_path, monkeypatch, identity_template, backend):
    """Create fresh app data/source server so tests cannot modify the reviewer's demo."""
    path, sessions = identity_template
    destination = tmp_path / "application.sqlite3"
    shutil.copyfile(path, destination)
    monkeypatch.setenv("ELUNO_DB_PATH", str(destination))
    monkeypatch.setenv("ELUNO_MOCK_URL", str(backend.client.base_url))
    store = SQLiteStore(str(destination))

    # Construct a client using a valid copied session for an explicit test persona.
    def client_for(role):
        """Keep cookie state independent between concurrent roles and requests."""
        client = TestClient(app, raise_server_exceptions=False)
        if role:
            token, csrf, _ = sessions[role]
            client.cookies.set("eluno_session", token)
            client.headers["X-CSRF-Token"] = csrf
        return client

    return client_for, store, backend, sessions


# Assert independent expected permissions for every role and concrete endpoint action.
@pytest.mark.parametrize("role", sorted(ALL))
@pytest.mark.parametrize(
    "case",
    ENDPOINTS,
    ids=[method + " " + url.split("?")[0] for method, url, *_ in ENDPOINTS],
)
def test_role_endpoint_matrix(production_env, role, case):
    """Allowed calls have explicit results/preconditions; unauthorized ones must be 403."""
    client_for, _, _, sessions = production_env
    method, url, _, allowed, expected, body = case
    if body == "sale":
        body = {
            "phone": "+919000000005",
            "store_code": "HSR",
            "staff_id": sessions[role][2],
            "variant_ids": [91000003, 91000083],
        }
    response = client_for(role).request(
        method, url, **({"json": body} if body is not None else {})
    )
    assert response.status_code == (expected if role in allowed else 403), response.text


# Treat the endpoint manifest as a coverage gate when the API surface changes.
def test_every_business_endpoint_has_a_policy_case():
    """A new method/path must be added to the independent authorization manifest."""
    actual = {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
        if method in {"get", "post", "put", "patch", "delete"}
        and path not in {"/", "/health", "/auth/login"}
    }
    assert actual == {(method, path) for method, _, path, *_ in ENDPOINTS}


# Verify authentication applies uniformly even to read-only source and reporting APIs.
@pytest.mark.parametrize(
    "case",
    ENDPOINTS,
    ids=[method + " " + url.split("?")[0] for method, url, *_ in ENDPOINTS],
)
def test_every_business_endpoint_requires_login(production_env, case):
    """Anonymous requests must fail before parsing or invoking financial services."""
    client_for, _, _, _ = production_env
    method, url, *_ = case
    assert client_for(None).request(method, url, json={}).status_code == 401


# Check anti-CSRF enforcement on every mutating surface, not merely sale completion.
@pytest.mark.parametrize("case", [case for case in ENDPOINTS if case[0] != "GET"])
def test_every_mutation_requires_csrf(production_env, case):
    """A legitimate session cookie alone must not authorize a write."""
    client_for, _, _, _ = production_env
    client = client_for("admin")
    client.headers.pop("X-CSRF-Token")
    assert client.request(case[0], case[1], json={}).status_code == 403


# Reject malformed bodies in middleware and handlers without exposing a server exception.
@pytest.mark.parametrize(
    "path",
    [
        "/sales/prepare",
        "/refunds/prepare",
        "/api/prescriptions",
        "/api/checkouts/missing/cancel",
    ],
)
@pytest.mark.parametrize(
    "body",
    [
        None,
        [],
        "unexpected",
        {"override_bps": "ten"},
        {"od": None, "os": {}},
        {"od": [], "os": []},
    ],
)
def test_malformed_body_is_controlled_client_error(production_env, path, body):
    """Invalid JSON shapes may be rejected, but must never cause an HTTP 500."""
    client_for, _, _, _ = production_env
    response = client_for("admin").post(path, json=body)
    assert 400 <= response.status_code < 500, response.text


# Exercise syntactically invalid JSON separately from valid JSON with the wrong shape.
@pytest.mark.parametrize("path", ["/sales/prepare", "/refunds/prepare"])
def test_invalid_json_is_not_a_server_error(production_env, path):
    """The authentication middleware must not bypass FastAPI's input-error semantics."""
    client_for, _, _, _ = production_env
    response = client_for("admin").post(
        path, content="{broken", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422, response.text


# Ensure a wrong HTTP method never enters JSON-parsing or mutation-specific code.
def test_wrong_method_does_not_crash(production_env):
    """GET on a POST-only route returns a method error without touching business state."""
    client_for, _, _, _ = production_env
    assert client_for("manager").get("/sales/prepare").status_code == 405


# Test ownership at the record boundary rather than only on store-selector queries.
@pytest.mark.parametrize("role", ["cashier", "manager", "optometrist"])
def test_cross_store_record_access_is_denied(production_env, role):
    """Knowledge of another store's checkout/refund ID does not grant access."""
    client_for, store, _, _ = production_env
    checkout = store.create_checkout("MM", "80001005")
    store.initiate_refund("foreign-refund", checkout["checkout_id"], "123", 10000, {})
    client = client_for(role)
    for path in [
        f"/checkouts/{checkout['checkout_id']}",
        f"/api/checkouts/{checkout['checkout_id']}/detail",
        "/refunds/foreign-refund",
    ]:
        assert client.get(path).status_code == 403, path
    if role in {"cashier", "manager"}:
        assert (
            client.post(
                f"/api/checkouts/{checkout['checkout_id']}/cancel",
                json={"reason": "forged"},
            ).status_code
            == 403
        )


# Expiry must be checked in the database even if a browser retains its cookie.
def test_expired_session_is_rejected(production_env):
    """Expired sessions cannot read or write protected endpoints."""
    client_for, store, _, _ = production_env
    with store._connect() as connection:
        connection.execute("UPDATE sessions SET expires=?", (time.time() - 1,))
    assert client_for("admin").get("/api/bootstrap").status_code == 401


# Raw money fields must not accept booleans or silently truncate fractional paise.
@pytest.mark.parametrize("amount", [True, 1.25, -1, 100000001])
def test_cash_amount_requires_bounded_integer_paise(production_env, amount):
    """Invalid cash inputs cannot open a drawer or change its expected balance."""
    client_for, _, _, _ = production_env
    response = client_for("manager").post(
        "/api/till/open", json={"store_code": "HSR", "amount_paise": amount}
    )
    assert response.status_code == 422, response.text
