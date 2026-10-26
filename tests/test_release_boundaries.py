"""Session, input, discount and notification boundary checks."""

import pytest
from app.security import provision_user
from app.scheduler import deliver_outbox
from app.operations import rows
from test_cart_regressions import cart
from test_production_matrix import production_env, identity_template, backend


# Public documentation remains usable without granting access to business data.
@pytest.mark.parametrize("path", ["/", "/health", "/docs", "/openapi.json"])
def test_public_entry_points(production_env, path):
    clients, _, _, _ = production_env
    assert clients(None).get(path).status_code == 200


# Login issues a protected cookie; logout immediately revokes server-side access.
def test_real_login_logout_and_cookie(production_env):
    clients, _, _, _ = production_env
    client = clients(None)
    response = client.post(
        "/auth/login",
        json={"username": "cashier", "password": "Acceptance-password-2026!"},
    )
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    client.headers["X-CSRF-Token"] = response.json()["csrf"]
    assert client.post("/auth/logout").status_code == 200
    assert client.get("/auth/me").status_code == 401


# Brute-force protection blocks even a correct password until the window resets.
def test_login_rate_limit(production_env):
    clients, _, _, _ = production_env
    client = clients(None)
    for _ in range(8):
        assert (
            client.post(
                "/auth/login", json={"username": "cashier", "password": "wrong"}
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/auth/login",
            json={"username": "cashier", "password": "Acceptance-password-2026!"},
        ).status_code
        == 429
    )


# Credential rotation must invalidate previously issued cookies.
def test_password_rotation_revokes_sessions(production_env):
    clients, store, _, _ = production_env
    provision_user(
        store, "cashier", "Rotated-password-2026!", "cashier", "HSR", "S105", "Cashier"
    )
    assert clients("cashier").get("/auth/me").status_code == 401


# Manager discounts require integer basis points and bounded authorized values.
@pytest.mark.parametrize("value", [-1, 1001, "ten", True, 1.5])
def test_discount_input_boundaries(production_env, value):
    clients, _, _, _ = production_env
    response = clients("manager").post(
        "/sales/prepare",
        json=cart(
            [91000003],
            staff_id="S108",
            override_bps=value,
            reason_code="walk_out_retention",
        ),
    )
    assert response.status_code == 422, response.text


# No cashier can impersonate a manager to acquire discount permission.
def test_staff_impersonation_denied(production_env):
    clients, _, _, _ = production_env
    response = clients("cashier").post(
        "/sales/prepare",
        json=cart(
            [91000003],
            staff_id="S108",
            override_bps=500,
            reason_code="walk_out_retention",
        ),
    )
    assert response.status_code == 403


# A family may buy extra frames without creating false second-pair eligibility.
def test_standalone_frames_are_not_offer_pairs(production_env):
    clients, _, _, _ = production_env
    response = clients("cashier").post(
        "/sales/prepare", json=cart([91000003, 91000083], members=[{
            "phone": "+919000000004", "variant_ids": [91000003, 91000083],
            "frame_only_variant_ids": [91000005],
        }])
    )
    assert response.status_code == 200, response.text
    assert not any(
        offer["offer_id"] == "SECONDPAIR50" and offer["applied"]
        for offer in response.json()["offers"]
    )


# Delivery status must match SMTP acknowledgement and never resend uncertain messages.
@pytest.mark.parametrize("mode", ["unconfigured", "success", "uncertain"])
def test_outbox_delivery_status(production_env, monkeypatch, mode):
    _, store, _, _ = production_env
    with store._connect() as connection:
        connection.execute(
            "INSERT INTO outbox(id,created_at,subject,body) VALUES('digest-test','2026-10-25','Test','Body')"
        )
    monkeypatch.delenv("ELUNO_SMTP_HOST", raising=False)
    sent = []

    class FakeSMTP:
        # Record a local SMTP connection without opening a network socket.
        def __init__(self, *args, **kwargs):
            pass

        # Match the SMTP context-manager interface.
        def __enter__(self):
            return self

        # Close the fake connection without suppressing exceptions.
        def __exit__(self, *args):
            return False

        # Accept the encrypted-session setup used by the delivery worker.
        def starttls(self):
            pass

        # Simulate acceptance or an ambiguous disconnect after submission.
        def send_message(self, message):
            sent.append(message)
            if mode == "uncertain":
                raise OSError("connection lost after DATA")

    monkeypatch.setattr("app.scheduler.smtplib.SMTP", FakeSMTP)
    monkeypatch.delenv("ELUNO_SMTP_USER", raising=False)
    if mode != "unconfigured":
        monkeypatch.setenv("ELUNO_SMTP_HOST", "local-test")
        monkeypatch.setenv("ELUNO_SMTP_FROM", "sender@example.test")
        monkeypatch.setenv("ELUNO_FOUNDER_EMAIL", "recipient@example.test")
    deliver_outbox(store)
    deliver_outbox(store)
    assert (
        rows(store, "SELECT status FROM outbox")[0]["status"]
        == {
            "unconfigured": "queued",
            "success": "sent",
            "uncertain": "delivery_uncertain",
        }[mode]
    )
    assert len(sent) == (0 if mode == "unconfigured" else 1)
