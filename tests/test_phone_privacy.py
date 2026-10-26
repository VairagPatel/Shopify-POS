"""Phone canonicalization, body-only lookup and prescription-link regression checks."""

import logging
import socket
import subprocess
import sys
import time
from datetime import datetime, timedelta
import pytest
from app.phone import normalize_phone
from app.gateways.http import MockHTTP, GatewayError
from app.logging_filters import QueryStringFilter
from app.operations import INDIA
from test_production_matrix import production_env, identity_template, backend


# Equivalent supported Indian input styles identify the same existing person.
@pytest.mark.parametrize(
    "phone",
    [
        "9000000005",
        "+919000000005",
        "919000000005",
        "09000000005",
        " +91 90000-00005 ",
        "(90000) 00005",
    ],
)
def test_normalize_indian_mobile(phone):
    assert normalize_phone(phone) == "+919000000005"


# Do not guess a country or silently convert arbitrary text/numeric identifiers.
@pytest.mark.parametrize(
    "phone",
    [
        None,
        9000000005,
        True,
        "",
        "+1 9000000005",
        "1234567890",
        "+919000000005x",
        "00919000000005",
        "90000000050",
        "９００００００００５",
    ],
)
def test_reject_invalid_phone(phone):
    with pytest.raises(ValueError):
        normalize_phone(phone)


# Even requests from obsolete clients must not put query values into standard access logs.
def test_access_log_query_redaction():
    record = logging.LogRecord(
        "uvicorn.access",
        20,
        "",
        0,
        "%s %s %s %s %s",
        ("client", "GET", "/api/customers?phone=%2B919000000005", "1.1", 405),
        None,
    )
    assert QueryStringFilter().filter(record)
    assert "9000000005" not in record.getMessage()


# Start the additive privacy wrapper while keeping the original exercise server untouched.
@pytest.fixture
def private_source(tmp_path):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    log_path = tmp_path / "source.log"
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "scripts/persistent_mock.py",
                "--port",
                str(port),
                "--snapshot",
                str(tmp_path / "mock.json"),
            ],
            stdout=log,
            stderr=log,
        )
        gateway = MockHTTP(f"http://127.0.0.1:{port}", private_lookup=True, timeout=1)
        try:
            for _ in range(50):
                try:
                    if gateway.request("GET", "/health")["ok"]:
                        break
                except GatewayError:
                    time.sleep(0.1)
            else:
                pytest.fail("Private source did not start")
            yield gateway, log_path
        finally:
            gateway.client.close()
            process.terminate()
            process.wait(timeout=10)


# Demonstrate source lookups contain the phone only in the request body, not URL/logs.
def test_wrapper_body_lookups(private_source):
    source, log_path = private_source
    requests = []
    source.client.event_hooks["request"] = [
        lambda request: requests.append((str(request.url), request.content.decode()))
    ]
    assert source.customer("9000000005")["phone"] == "+919000000005"
    assert source.prescriptions("919000000005")
    assert len(requests) == 2
    assert all(
        "9000000005" not in url and "?" not in url and "+919000000005" in body
        for url, body in requests
    )
    assert "9000000005" not in log_path.read_text()


# Customer, clinical overlay, draft and quote share the canonical key without creating a customer.
def test_lookup_prescription_and_quote_share_phone(
    production_env, private_source, monkeypatch
):
    clients, store, _, _ = production_env
    source, _ = private_source
    monkeypatch.setenv("ELUNO_PRIVATE_LOOKUP", "1")
    monkeypatch.setenv("ELUNO_MOCK_URL", str(source.client.base_url))
    client = clients("cashier")
    response = client.post("/api/customers", json={"phone": "9000000005"})
    assert response.status_code == 200, response.text
    customer = response.json()["customer"]
    assert customer["phone"] == "+919000000005"
    assert client.get("/api/customers").status_code == 405
    assert (
        client.post("/api/customers", json={"phone": "9000000999"}).status_code == 404
    )
    clinical = clients("optometrist").post(
        "/api/prescriptions",
        json={
            "phone": "09000000005",
            "od": {"sph": "-2.00", "cyl": "0", "axis": 90, "add": "1.50"},
            "os": {"sph": "-2.00", "cyl": "0", "axis": 90, "add": "1.50"},
            "valid_until": (
                datetime.now(INDIA).date() + timedelta(days=180)
            ).isoformat(),
        },
    )
    assert clinical.status_code == 200, clinical.text
    prescriptions = client.post(
        "/api/customers", json={"phone": "+91 90000 00005"}
    ).json()["prescriptions"]
    local = next(row for row in prescriptions if row["rx_id"].startswith("RX-"))
    assert local["customer_id"] == customer["id"]
    assert local["phone"] == "+919000000005"
    assert (
        client.put(
            "/api/draft",
            json={"members": [{"phone": "9000000005", "variant_ids": [91000003]}]},
        ).status_code
        == 200
    )
    assert client.get("/api/draft").json()["members"][0]["phone"] == "+919000000005"
    quote = client.post(
        "/sales/prepare",
        json={
            "phone": "9000000005",
            "store_code": "HSR",
            "staff_id": "S105",
            "variant_ids": [],
            "members": [{"phone": "919000000005", "variant_ids": [91000003, 91000083]}],
        },
    )
    assert quote.status_code == 200, quote.text
    saved = store.load_quote(quote.json()["checkout_id"])
    assert saved["lines"][1]["rx_id"] == local["rx_id"]
    assert saved["lines"][1]["wearer_phone"] == "+919000000005"
