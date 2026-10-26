"""Guard active adapter contracts and keep transport implementations out of core services."""

import ast
from pathlib import Path

from app.gateways.contracts import (
    CommerceGateway,
    StoreToolGateway,
    TerminalGateway,
    SaleGateway,
    RefundGateway,
    ReportingGateway,
)
from app.gateways.http import MockHTTP
from app.gateways.billing import BillingAdapter
from app.main import app
from app.domain.errors import GatewayError, StateConflict


# A real adapter must expose the ports consumed by the services, not unused aspirational methods.
def test_http_adapter_supports_active_ports():
    adapter = MockHTTP(private_lookup=True)
    try:
        for port in (
            CommerceGateway,
            StoreToolGateway,
            TerminalGateway,
            SaleGateway,
            RefundGateway,
            ReportingGateway,
        ):
            assert isinstance(BillingAdapter(adapter), port)
    finally:
        adapter.client.close()


# Prevent a future service change from importing a concrete transport or SQL implementation.
def test_services_do_not_import_transport_or_database_implementations():
    for filename in ("sale.py", "refunds.py", "reporting.py"):
        tree = ast.parse((Path("app/services") / filename).read_text(encoding="utf-8"))
        imported = {
            node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        }
        assert not imported.intersection(
            {"app.gateways.http", "app.persistence.sqlite"}
        )


# The published lookup contract must use a body; regenerating Swagger must not restore a URL phone.
def test_customer_openapi_is_body_only():
    schema = app.openapi()
    lookup = schema["paths"]["/api/customers"]
    assert set(lookup) == {"post"}
    operation = lookup["post"]
    assert "requestBody" in operation
    assert not any(
        parameter.get("name") == "phone"
        for parameter in operation.get("parameters", [])
    )


# Existing imports keep their exception identity during the boundary refactor.
def test_legacy_error_imports_preserve_catch_behavior():
    from app.gateways.http import GatewayError as TransportError
    from app.persistence.sqlite import StateConflict as PersistenceConflict

    assert TransportError is GatewayError
    assert PersistenceConflict is StateConflict
