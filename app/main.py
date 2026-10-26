"""Original API contracts, extended with authenticated store operations and UI."""

import os
from contextlib import contextmanager
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from app.persistence.sqlite import SQLiteStore, CheckoutNotFound, StateConflict
from app.gateways.http import GatewayError
from app.services.sale import SaleService, SaleValidationError
from app.operations import OperationsGateway
from app.gateways.billing import BillingAdapter
from app.security import initialize_security
from app.api_documentation import WearerSelection, install_api_documentation
from app.phone import PhoneNumber

app = FastAPI(title="Eluno Store Studio", version="1.0.0", docs_url=None)


# Open the configured SQLite store and apply additive migrations.
def state_store():
    "Open the configured SQLite store and apply additive migrations."
    store = SQLiteStore(os.environ.get("ELUNO_DB_PATH", "runtime/eluno.sqlite3"))
    initialize_security(store)
    return store


# Construct sale orchestration with the authenticated app prescription overlay.
@contextmanager
def service(service_type=SaleService):
    """Scope an operation's HTTP client so connections close on success and error."""
    store = state_store()
    gateway = OperationsGateway(store)
    try:
        yield (
            service_type(BillingAdapter(gateway))
            if service_type is DayEndService
            else service_type(store, BillingAdapter(gateway))
        )
    finally:
        gateway.client.close()


class PrepareRequest(BaseModel):
    phone: PhoneNumber
    store_code: str
    staff_id: str
    variant_ids: List[int]
    payment_method: str = "upi"
    channel: str = "walk_in"
    checkout_id: Optional[str] = None
    reason_code: Optional[str] = None
    override_bps: Optional[int] = Field(
        default=None,
        description="Manager-entered discount in basis points (500 = 5%). Applies exactly as entered and exclusively of other offers; requires manager permission and a reason.",
        ge=0,
        le=1000,
    )
    selected_offer_id: Optional[str] = Field(
        default=None,
        description="Optional offer_id from offers.json. Only this offer is applied after server validation. Omit to apply no coupon discount.",
        min_length=1,
        max_length=80,
    )
    members: Optional[List[WearerSelection]] = None


# Verify local database readiness while preserving the original health contract.
@app.get("/health")
def health():
    state_store()
    return {"status": "ok", "stage": 6, "checkout_enabled": True}


# Return the persisted checkout state for recovery and inspection.
@app.get("/checkouts/{checkout_id}")
def checkout_state(checkout_id: str):
    "Return the persisted checkout state for recovery and inspection."
    try:
        return state_store().get_checkout(checkout_id)
    except CheckoutNotFound:
        raise HTTPException(404, "checkout not found")


# Validate the request and persist a quote before any financial side effect.
@app.post("/sales/prepare")
def prepare(request_model: PrepareRequest):
    "Validate the request and persist a quote before any financial side effect."
    try:
        with service() as sale_service:
            return sale_service.prepare(**request_model.model_dump())
    except (SaleValidationError, ValueError) as exc:
        raise HTTPException(422, str(exc))
    except StateConflict as exc:
        raise HTTPException(409, str(exc))
    except GatewayError as exc:
        raise HTTPException(502, str(exc))


# Complete the persisted financial operation without repeating uncertain writes.
@app.post("/sales/{checkout_id}/complete")
def complete(checkout_id: str):
    "Complete the persisted financial operation without repeating uncertain writes."
    try:
        with service() as sale_service:
            return sale_service.complete(checkout_id)
    except CheckoutNotFound:
        raise HTTPException(404, "checkout not found")
    except StateConflict as exc:
        raise HTTPException(409, str(exc))
    except GatewayError as exc:
        raise HTTPException(
            502,
            {
                "message": str(exc),
                "uncertain": exc.uncertain,
                "action": "Inspect checkout and reconcile; do not retry payment",
            },
        )


# Find the original uncertain order using its saved checkout reference.
@app.post("/sales/{checkout_id}/reconcile-order")
def reconcile_order(checkout_id: str):
    "Find the original uncertain order using its saved checkout reference."
    try:
        with service() as sale_service:
            return sale_service.reconcile_order(checkout_id)
    except (CheckoutNotFound, StateConflict) as exc:
        raise HTTPException(409, str(exc))
    except GatewayError as exc:
        raise HTTPException(502, str(exc))


# Stage 6: full refunds and Shopify-sourced day-end report.
from app.services.refunds import RefundService, RefundValidationError
from app.services.reporting import DayEndService, ReportValidationError


class RefundPrepareRequest(BaseModel):
    checkout_id: str
    reason: str
    refund_id: Optional[str] = None


# Calculate a full refund without moving money or inventory.
@app.post("/refunds/prepare")
def refund_prepare(request_model: RefundPrepareRequest):
    "Calculate a full refund without moving money or inventory."
    try:
        with service(RefundService) as refund_service:
            return refund_service.prepare(**request_model.model_dump())
    except CheckoutNotFound:
        raise HTTPException(404, "checkout not found")
    except (RefundValidationError, ValueError) as exc:
        raise HTTPException(422, str(exc))
    except StateConflict as exc:
        raise HTTPException(409, str(exc))
    except GatewayError as exc:
        raise HTTPException(502, str(exc))


# Return the saved refund status and external references.
@app.get("/refunds/{refund_id}")
def refund_state(refund_id: str):
    "Return the saved refund status and external references."
    try:
        return state_store().get_refund(refund_id)
    except CheckoutNotFound:
        raise HTTPException(404, "refund not found")


# Complete the refund through the guarded terminal and Shopify sequence.
@app.post("/refunds/{refund_id}/complete")
def refund_complete(refund_id: str):
    "Complete the refund through the guarded terminal and Shopify sequence."
    try:
        with service(RefundService) as refund_service:
            return refund_service.complete(refund_id)
    except CheckoutNotFound:
        raise HTTPException(404, "refund not found")
    except StateConflict as exc:
        raise HTTPException(409, str(exc))
    except GatewayError as exc:
        raise HTTPException(
            502,
            {"message": str(exc), "action": "Reconcile; do not retry uncertain refund"},
        )


# Locate an already-created Shopify refund without reposting it.
@app.post("/refunds/{refund_id}/reconcile-shopify")
def refund_reconcile(refund_id: str):
    "Locate an already-created Shopify refund without reposting it."
    try:
        with service(RefundService) as refund_service:
            return refund_service.reconcile_shopify(refund_id)
    except CheckoutNotFound:
        raise HTTPException(404, "refund not found")
    except StateConflict as exc:
        raise HTTPException(409, str(exc))
    except GatewayError as exc:
        raise HTTPException(502, str(exc))


# Return the original Shopify order-day reporting contract.
@app.get("/reports/day-end")
def day_end(store_code: str, date: str):
    "Return the original Shopify order-day reporting contract."
    try:
        with service(DayEndService) as reporting_service:
            return reporting_service.report(store_code, date)
    except (ReportValidationError, ValueError) as exc:
        raise HTTPException(422, str(exc))
    except GatewayError as exc:
        raise HTTPException(502, str(exc))


from app.web import install

install(app, state_store)
install_api_documentation(app)
