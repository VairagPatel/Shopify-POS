"""Same-origin UI APIs and security boundary for both new and original routes."""

import hashlib
import hmac
import json
import logging
import os
import threading
import time
import csv
import io
from typing import Literal
from contextlib import asynccontextmanager
from datetime import datetime, date, timedelta
from pathlib import Path
from uuid import uuid4
from fastapi import Request, Response, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from app.security import login, authenticate, require_role, require_store
from app.operations import (
    OperationsGateway,
    audit,
    rows,
    now_iso,
    INDIA,
    analytics,
    current_till,
    open_till,
    till_summary,
    close_till,
    founder_digest,
)
from app.persistence.sqlite import CheckoutNotFound, StateConflict
from app.services.sale import SaleService
from app.services.reporting import DayEndService
from app.domain.money import money
from app.gateways.billing import BillingAdapter
from app.services.catalog import load_json
from app.domain.models import CheckoutStatus
from app.gateways.http import GatewayError
from app.phone import PhoneNumber, normalize_phone
from app.customer_schemas import (
    CustomerLookupRequest,
    CustomerLookupResponse,
    PrescriptionInput,
)
from app.logging_filters import QueryStringFilter
from app.constants import MANAGER_DISCOUNT_LIMIT_BPS, SESSION_DURATION_SECONDS

ROOT = Path(__file__).resolve().parents[1]


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class AmountRequest(BaseModel):
    store_code: str
    amount_paise: int = Field(strict=True, ge=0, le=100000000)
    reason: str = Field(default="", max_length=500)


class RemakeRequest(BaseModel):
    checkout_id: str
    lens_variant_id: int
    wearer_phone: PhoneNumber
    reason: str = Field(min_length=3, max_length=500)
    cost_owner: str
    lab_cost_paise: int = Field(strict=True, ge=0, le=100000000)


# Mount additive routes and guard every existing business endpoint.
def install(app, store_factory):
    """Mount additive routes and guard every existing business endpoint."""
    logging.getLogger("uvicorn.access").addFilter(QueryStringFilter())
    app.mount(
        "/static",
        StaticFiles(directory=ROOT / "app/static", check_dir=False),
        name="static",
    )
    mutation_lock = threading.Lock()

    # Start the report scheduler and stop it cleanly with the application.
    @asynccontextmanager
    async def lifespan(application):
        """Start the report scheduler and stop it cleanly with the application."""
        from app.scheduler import scheduler_loop

        stop = threading.Event()
        worker = threading.Thread(
            target=scheduler_loop, args=(stop, store_factory), daemon=True
        )
        worker.start()
        yield
        stop.set()
        worker.join(timeout=2)

    app.router.lifespan_context = lifespan

    # Resolve a checkout while enforcing store ownership.
    def checkout_for(user, identifier):
        """Resolve a checkout while enforcing store ownership."""
        checkout = store_factory().get_checkout(identifier)
        require_store(user, checkout["store_code"])
        return checkout

    # Apply authentication, CSRF, role checks and store scoping to original APIs.
    @app.middleware("http")
    async def guard(request: Request, call_next):
        """Apply authentication, CSRF, role checks and store scoping to original APIs."""
        path = request.url.path
        public = path in {
            "/",
            "/health",
            "/auth/login",
            "/docs",
            "/openapi.json",
            "/docs/oauth2-redirect",
            "/favicon.ico",
        } or path.startswith("/static/")
        started = time.perf_counter()
        locked = False
        try:
            if not public:
                store = store_factory()
                user = authenticate(store, request.cookies.get("eluno_session"))
                request.state.user = user
                mutating = request.method not in {"GET", "HEAD", "OPTIONS"}
                if mutating and not hmac.compare_digest(
                    request.headers.get("x-csrf-token", ""), user["csrf"]
                ):
                    raise HTTPException(403, "Missing or invalid CSRF token")
                if mutating:
                    await run_in_threadpool(mutation_lock.acquire)
                    locked = True
                if path.startswith(("/sales/", "/refunds/")) and mutating:
                    require_role(
                        user,
                        "manager"
                        if path.startswith("/refunds/") or "reconcile" in path
                        else "cashier",
                        "manager",
                    )
                if path == "/api/prescriptions" and mutating:
                    require_role(user, "optometrist")
                if (
                    path in {"/sales/prepare", "/refunds/prepare"}
                    and request.method == "POST"
                ):
                    try:
                        body = await request.json()
                    except (ValueError, UnicodeDecodeError) as exception:
                        raise HTTPException(
                            422, "Supply a valid JSON object"
                        ) from exception
                    if not isinstance(body, dict):
                        raise HTTPException(422, "Supply a JSON object")
                if path == "/sales/prepare" and request.method == "POST":
                    require_store(user, body.get("store_code", ""))
                    selected_offer_id = body.get("selected_offer_id")
                    if selected_offer_id is not None and (
                        not isinstance(selected_offer_id, str)
                        or not 1 <= len(selected_offer_id) <= 80
                    ):
                        raise HTTPException(422, "Choose one valid coupon ID")
                    if (
                        user["role"] != "admin"
                        and body.get("staff_id") != user["staff_id"]
                    ):
                        raise HTTPException(
                            403, "Staff identity must match your account"
                        )
                    if body.get("override_bps") is not None:
                        require_role(user, "manager")
                        if (
                            type(body["override_bps"]) is not int
                            or not 0
                            <= body["override_bps"]
                            <= MANAGER_DISCOUNT_LIMIT_BPS
                        ):
                            raise HTTPException(
                                422, "Manager discount must be between 0 and 10%"
                            )
                    members = body.get("members")
                    if members is not None and (
                        not isinstance(members, list)
                        or not 1 <= len(members) <= 10
                        or any(
                            not isinstance(item, dict)
                            or not isinstance(item.get("phone"), str)
                            or not isinstance(item.get("variant_ids", []), list)
                            or not isinstance(
                                item.get("lens_only_variant_ids", []), list
                            )
                            or not isinstance(item.get("frame_only_variant_ids", []), list)
                            or not 1
                            <= len(item.get("variant_ids", []))
                            + len(item.get("lens_only_variant_ids", []))
                            + len(item.get("frame_only_variant_ids", []))
                            <= 30
                            or any(
                                type(value) is not int
                                for value in item.get("variant_ids", [])
                            )
                            or any(
                                type(value) is not int
                                for value in item.get("lens_only_variant_ids", [])
                            )
                            or any(type(value) is not int for value in item.get("frame_only_variant_ids", []))
                            for item in members
                        )
                    ):
                        raise HTTPException(
                            422,
                            "Supply up to ten wearers, each with a phone and 1–30 frame/pair or lens-only variants",
                        )
                segments = path.strip("/").split("/")
                checkout = None
                if (
                    segments[0] in {"checkouts", "sales"}
                    and len(segments) > 1
                    and segments[1] != "prepare"
                ):
                    checkout = checkout_for(user, segments[1])
                if segments[0] == "refunds" and len(segments) > 1:
                    if segments[1] == "prepare":
                        if request.method == "POST":
                            checkout = checkout_for(user, body.get("checkout_id", ""))
                    else:
                        refund = store.get_refund(segments[1])
                        checkout = checkout_for(user, refund["checkout_id"])
                if checkout and path.endswith("/complete"):
                    quote = store.load_quote(checkout["checkout_id"])
                    if (
                        quote
                        and quote["method"] == "cash"
                        and not current_till(store, checkout["store_code"])
                    ):
                        if checkout["status"] == "draft" or (
                            path.startswith("/refunds/")
                            and refund["status"] == "prepared"
                        ):
                            raise HTTPException(
                                409,
                                "Open the drawer before accepting or refunding cash",
                            )
                if path == "/reports/day-end":
                    require_store(user, request.query_params.get("store_code", ""))
            response = await call_next(request)
            if not public and request.method not in {"GET", "HEAD", "OPTIONS"}:
                audit(
                    store,
                    user["username"],
                    request.method + " " + path,
                    path,
                    {"http_status": response.status_code},
                )
                if (
                    path.startswith("/sales/")
                    and path.endswith("/complete")
                    and response.status_code == 200
                ):
                    elapsed = round((time.perf_counter() - started) * 1000, 2)
                    with store._connect() as connection:
                        connection.execute(
                            "UPDATE checkouts SET checkout_elapsed_ms=?,timing_recorded_at=? "
                            "WHERE checkout_id=? AND checkout_elapsed_ms IS NULL",
                            (elapsed, now_iso(), segments[1]),
                        )
        except HTTPException as exception:
            response = JSONResponse(
                {"detail": exception.detail}, status_code=exception.status_code
            )
        except CheckoutNotFound:
            response = JSONResponse({"detail": "Record not found"}, status_code=404)
        finally:
            if locked:
                mutation_lock.release()
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cache-Control"] = "no-store"
        return response

    # Expose actionable business validation without internal stack traces.
    @app.exception_handler(ValueError)
    async def validation_error(request, exception):
        """Expose actionable business validation without internal stack traces."""
        return JSONResponse({"detail": str(exception)}, status_code=422)

    # Report invalid state transitions rather than retrying financial writes.
    @app.exception_handler(StateConflict)
    async def state_error(request, exception):
        """Report invalid state transitions rather than retrying financial writes."""
        return JSONResponse({"detail": str(exception)}, status_code=409)

    # Map unknown operational identifiers to a stable not-found response.
    @app.exception_handler(CheckoutNotFound)
    async def missing_error(request, exception):
        """Map unknown operational identifiers to a stable not-found response."""
        return JSONResponse({"detail": "Record not found"}, status_code=404)

    # Keep uncertain outcomes visible for explicit reconciliation.
    @app.exception_handler(GatewayError)
    async def upstream_error(request, exception):
        """Keep uncertain outcomes visible for explicit reconciliation."""
        return JSONResponse(
            {"detail": str(exception), "uncertain": exception.uncertain},
            status_code=502,
        )

    # Serve the laptop interface from the same origin as the API.
    @app.get("/")
    def homepage():
        """Serve the laptop interface from the same origin as the API."""
        return FileResponse(ROOT / "app/static/index.html")

    # Preserve Swagger's interactive requests using the signed-in browser session.
    @app.get("/docs", include_in_schema=False)
    def swagger_docs():
        """Preserve Swagger's interactive requests using the signed-in browser session."""
        response = get_swagger_ui_html(openapi_url="/openapi.json", title="Eluno API")
        html = response.body.decode().replace(
            "SwaggerUIBundle({",
            """SwaggerUIBundle({
          requestInterceptor: async (request) => {
            const response = await fetch('/auth/me', {credentials:'same-origin'});
            if (response.ok) { const session = await response.json(); request.headers['X-CSRF-Token'] = session.csrf; }
            return request;
          },""",
        )
        return HTMLResponse(html)

    # Verify credentials and set a revocable HttpOnly session cookie.
    @app.post("/auth/login")
    def sign_in(body: Credentials, response: Response):
        """Verify credentials and set a revocable HttpOnly session cookie."""
        token, csrf, user = login(store_factory(), body.username, body.password)
        response.set_cookie(
            "eluno_session",
            token,
            httponly=True,
            samesite="strict",
            secure=os.environ.get("ELUNO_SECURE_COOKIES") == "1",
            max_age=SESSION_DURATION_SECONDS,
        )
        return {"user": user, "csrf": csrf}

    # Restore the active principal and CSRF token after reload.
    @app.get("/auth/me")
    def me(request: Request):
        """Restore the active principal and CSRF token after reload."""
        return request.state.user

    # Delete the session server-side and expire the browser cookie.
    @app.post("/auth/logout")
    def logout(request: Request, response: Response):
        """Delete the session server-side and expire the browser cookie."""
        with store_factory()._connect() as connection:
            connection.execute(
                "DELETE FROM sessions WHERE token_hash=?",
                (
                    hashlib.sha256(
                        request.cookies["eluno_session"].encode()
                    ).hexdigest(),
                ),
            )
        response.delete_cookie("eluno_session")
        return {"ok": True}

    # Load permitted stores, the product catalog and synthetic customer directory.
    @app.get("/api/bootstrap")
    def bootstrap(request: Request):
        """Load permitted stores, the product catalog and synthetic customer directory."""
        user = request.state.user
        gateway = OperationsGateway(store_factory())
        try:
            stores = [
                location
                for location in gateway.locations()
                if location["eluno"]["kind"] == "store"
                and (
                    user["role"] in {"admin", "finance"}
                    or location["eluno"]["store_code"] == user["store_code"]
                )
            ]
            products = gateway.shopify("GET", "products.json", params={"limit": 250})[
                "products"
            ]
            return {
                "stores": stores,
                "catalog": [
                    {**variant, "product_title": product["title"]}
                    for product in products
                    for variant in product["variants"]
                ],
                "customers": [
                    {
                        key: customer[key]
                        for key in ("id", "first_name", "last_name", "phone", "tags")
                    }
                    for customer in load_json("customers.json")
                ],
                "staff": gateway.staff(""),
                "offers": load_json("offers.json"),
                "today": datetime.now(INDIA).date().isoformat(),
            }
        finally:
            gateway.client.close()

    # Fetch the live customer record and all available prescriptions.
    @app.post("/api/customers", response_model=CustomerLookupResponse)
    def customer(body: CustomerLookupRequest, request: Request):
        """Fetch the live customer record and all available prescriptions."""
        gateway = OperationsGateway(store_factory())
        try:
            phone = body.phone
            record = gateway.customer(phone)
            if not record:
                raise HTTPException(404, "Customer not found")
            return {"customer": record, "prescriptions": gateway.prescriptions(phone)}
        finally:
            gateway.client.close()

    # Read all stock at the authorized store in one backend request.
    @app.get("/api/inventory")
    def inventory(store_code: str, request: Request):
        """Read all stock at the authorized store in one backend request."""
        require_store(request.state.user, store_code)
        gateway = OperationsGateway(store_factory())
        try:
            location = next(
                (
                    item
                    for item in gateway.locations()
                    if item["eluno"]["store_code"] == store_code
                ),
                None,
            )
            if not location:
                raise ValueError("Unknown store")
            return gateway.shopify(
                "GET", "inventory_levels.json", params={"location_ids": location["id"]}
            )
        finally:
            gateway.client.close()

    # List persisted bills and pending states without exposing another store.
    @app.get("/api/transactions")
    def transactions(store_code: str, request: Request):
        """List persisted bills and pending states without exposing another store."""
        require_store(request.state.user, store_code)
        records = rows(
            store_factory(),
            "SELECT c.*,q.quote_json,r.status AS refund_status,r.refund_id,r.shopify_refund_id "
            "FROM checkouts c LEFT JOIN checkout_quotes q USING(checkout_id) "
            "LEFT JOIN refund_attempts r USING(checkout_id) WHERE c.store_code=? ORDER BY c.created_at DESC LIMIT 200",
            (store_code,),
        )
        for record in records:
            quote = json.loads(record.pop("quote_json") or "{}")
            customer = quote.get("customer", {})
            record.update(
                total_paise=quote.get("total_paise", 0),
                method=quote.get("method"),
                remake=quote.get("remake"),
                customer_name=" ".join(
                    [customer.get("first_name", ""), customer.get("last_name", "")]
                ),
            )
        return records

    # Combine saved quote, source order and refund for receipts and recovery.
    @app.get("/api/checkouts/{identifier}/detail")
    def detail(identifier: str, request: Request):
        """Combine saved quote, source order and refund for receipts and recovery."""
        checkout = checkout_for(request.state.user, identifier)
        store = store_factory()
        gateway = OperationsGateway(store)
        try:
            return {
                "checkout": checkout,
                "quote": store.load_quote(identifier),
                "invoice": store.get_invoice(identifier),
                "refund_events": rows(store, "SELECT * FROM refund_events WHERE refund_id IN (SELECT refund_id FROM refund_attempts WHERE checkout_id=?) ORDER BY event_id", (identifier,)),
                "order": gateway.order_by_id(checkout["shopify_order_id"])
                if checkout["shopify_order_id"]
                else None,
                "refunds": rows(
                    store,
                    "SELECT * FROM refund_attempts WHERE checkout_id=?",
                    (identifier,),
                ),
            }
        finally:
            gateway.client.close()

    # Cancel an unpaid draft and retain its invoice number in the register.
    @app.post("/api/checkouts/{identifier}/cancel")
    def cancel(identifier: str, body: dict, request: Request):
        """Cancel an unpaid draft and retain its invoice number in the register."""
        require_role(request.state.user, "cashier", "manager")
        checkout_for(request.state.user, identifier)
        reason = str(body.get("reason", "")).strip()
        if len(reason) < 3:
            raise ValueError("A cancellation reason is required")
        store = store_factory()
        store.change_status(
            identifier,
            CheckoutStatus.DRAFT,
            CheckoutStatus.CANCELLED,
            error_detail=reason,
        )
        with store._connect() as connection:
            connection.execute(
                "UPDATE invoice_allocations SET status='cancelled' WHERE checkout_id=?",
                (identifier,),
            )
        return store.get_checkout(identifier)

    # Restore the user's saved cart without initiating a payment.
    @app.get("/api/draft")
    def draft(request: Request):
        """Restore the user's saved cart without initiating a payment."""
        result = rows(
            store_factory(),
            "SELECT payload FROM drafts WHERE username=?",
            (request.state.user["username"],),
        )
        return json.loads(result[0]["payload"]) if result else {}

    # Return draft tracking metadata separately to preserve the existing cart API shape.
    @app.get("/api/draft/metadata")
    def draft_metadata(request: Request):
        """Return the current draft ID and timestamps without changing GET /api/draft."""
        result = rows(
            store_factory(),
            "SELECT draft_id,created_by,created_by_staff_id,created_at,updated_at FROM drafts WHERE username=?",
            (request.state.user["username"],),
        )
        return result[0] if result else {}

    # Save a bounded browser cart for cross-reload recovery.
    @app.put("/api/draft")
    def save_draft(body: dict, request: Request):
        """Save a bounded browser cart for cross-reload recovery."""
        require_role(request.state.user, "cashier", "manager")
        if body.get("store_code"):
            require_store(request.state.user, body["store_code"])
        if "members" in body:
            if not isinstance(body["members"], list) or any(
                not isinstance(member, dict) for member in body["members"]
            ):
                raise ValueError("Supply a list of wearer objects")
            body = {
                **body,
                "members": [
                    {**member, "phone": normalize_phone(member.get("phone"))}
                    for member in body["members"]
                ],
            }
        actor = request.state.user
        store = store_factory()
        saved_at = now_iso()
        supplied_draft_id = body.get("draft_id")
        if supplied_draft_id is not None and (
            not isinstance(supplied_draft_id, str)
            or not 1 <= len(supplied_draft_id) <= 80
        ):
            raise ValueError("draft_id must be a string of 1 to 80 characters")
        with store._connect() as connection:
            previous = connection.execute(
                "SELECT draft_id,created_at,updated_at FROM drafts WHERE username=?",
                (actor["username"],),
            ).fetchone()
            draft_id = supplied_draft_id or (previous["draft_id"] if previous else None) or "DR-" + str(uuid4())
            same_draft = bool(previous and previous["draft_id"] == draft_id)
            created_at = previous["created_at"] if same_draft and previous["created_at"] else saved_at
            elapsed_ms = None
            if same_draft and previous["updated_at"]:
                try:
                    previous_time = datetime.fromisoformat(previous["updated_at"].replace("Z", "+00:00"))
                    current_time = datetime.fromisoformat(saved_at.replace("Z", "+00:00"))
                    elapsed_ms = max(0.0, round((current_time - previous_time).total_seconds() * 1000, 2))
                except ValueError:
                    elapsed_ms = None
        payload_body = {
            key: value for key, value in body.items()
            if key not in {"draft_id", "created_at", "updated_at", "created_by", "created_by_staff_id"}
        }
        payload = json.dumps(payload_body)
        if len(payload) > 40000:
            raise HTTPException(413, "Cart is too large")
        with store._connect() as connection:
            connection.execute(
                "INSERT INTO drafts(username,payload,draft_id,created_by,created_by_staff_id,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?) ON CONFLICT(username) DO UPDATE SET payload=excluded.payload, "
                "draft_id=excluded.draft_id,created_by=excluded.created_by,created_by_staff_id=excluded.created_by_staff_id,"
                "created_at=excluded.created_at,updated_at=excluded.updated_at",
                (actor["username"], payload, draft_id, actor["username"], actor["staff_id"], created_at, saved_at),
            )
            connection.execute(
                "INSERT INTO cart_snapshots(username,store_code,status,checkout_id,payload,saved_at,draft_id,created_by,created_by_staff_id,created_at,elapsed_ms) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    actor["username"],
                    str(payload_body.get("store_code", actor["store_code"])),
                    "quoted" if payload_body.get("quote_id") else "draft",
                    payload_body.get("quote_id"),
                    payload,
                    saved_at,
                    draft_id,
                    actor["username"],
                    actor["staff_id"],
                    created_at,
                    elapsed_ms,
                ),
            )
        return {"saved": True, "draft_id": draft_id, "created_at": created_at, "updated_at": saved_at}

    # List immutable draft snapshots with their associated checkout and source order.
    @app.get("/api/drafts/history")
    def draft_history(request: Request, store_code: str | None = None):
        """List immutable draft snapshots with actor, timing, checkout and Shopify references."""
        user = request.state.user
        if user["role"] in {"admin", "finance"}:
            if store_code:
                require_store(user, store_code)
                predicate, parameters = "WHERE snapshot.store_code=?", (store_code,)
            else:
                predicate, parameters = "", ()
        else:
            require_store(user, store_code or user["store_code"])
            predicate, parameters = "WHERE snapshot.store_code=?", (store_code or user["store_code"],)
        records = rows(
            store_factory(),
            "SELECT snapshot.snapshot_id,snapshot.draft_id,snapshot.username,snapshot.created_by,"
            "snapshot.created_by_staff_id,snapshot.store_code,snapshot.status,snapshot.checkout_id,"
            "snapshot.created_at,snapshot.saved_at,snapshot.elapsed_ms,checkout.status AS checkout_status,"
            "checkout.invoice_no,checkout.shopify_order_id "
            "FROM cart_snapshots AS snapshot "
            "LEFT JOIN checkouts AS checkout ON checkout.checkout_id=snapshot.checkout_id "
            + predicate
            + " ORDER BY snapshot.saved_at DESC",
            parameters,
        )
        return records

    # Record a clinician-authored prescription with five-degree manual axis steps.
    @app.post("/api/prescriptions")
    def prescription(body: PrescriptionInput, request: Request):
        """Record a clinician-authored prescription with five-degree manual axis steps."""
        require_role(request.state.user, "optometrist")
        body = body.model_dump(mode="json")
        clinical_store = body.get("store_code") or request.state.user["store_code"]
        if clinical_store != "*":
            require_store(request.state.user, clinical_store)
        from decimal import Decimal, InvalidOperation

        for side in ("od", "os"):
            eye = body.get(side, {})
            try:
                sphere, cylinder = Decimal(str(eye["sph"])), Decimal(str(eye["cyl"]))
                if (
                    not sphere.is_finite()
                    or not cylinder.is_finite()
                    or not -30 <= sphere <= 30
                    or not -12 <= cylinder <= 12
                ):
                    raise ValueError("Invalid sphere or cylinder")
                axis = eye.get("axis")
                if type(axis) is not int or not 0 <= axis <= 180 or axis % 5:
                    raise ValueError("New axis entries must use 5-degree intervals")
                if not 0 <= Decimal(str(eye["add"])) <= 5:
                    raise ValueError("ADD must be between 0 and 5")
            except (KeyError, InvalidOperation, TypeError) as exception:
                raise ValueError("Enter valid prescription values") from exception
        today = datetime.now(INDIA).date()
        valid_until = date.fromisoformat(body.get("valid_until", ""))
        if not today <= valid_until <= today + timedelta(days=730):
            raise ValueError("Validity must be within the next two years")
        gateway = OperationsGateway(store_factory())
        try:
            if clinical_store != "*" and not any(location["eluno"]["store_code"] == clinical_store
                                                  and location["eluno"]["kind"] == "store"
                                                  for location in gateway.locations()):
                raise ValueError("Unknown clinical store")
            customer = gateway.customer(body.get("phone", ""))
            if not customer:
                raise ValueError("Unknown customer")
        finally:
            gateway.client.close()
        identifier = "RX-" + str(uuid4())
        record = {key: body[key] for key in ("phone", "od", "os", "valid_until")}
        record.update(
            rx_id=identifier,
            date=datetime.now(INDIA).isoformat(),
            source="in_store",
            customer_id=customer["id"],
            optometrist_id=request.state.user["staff_id"],
        )
        with store_factory()._connect() as connection:
            connection.execute(
                "INSERT INTO prescriptions(rx_id,phone,payload,created_by,created_by_staff_id,created_at,store_code) VALUES(?,?,?,?,?,?,?)",
                (identifier, record["phone"], json.dumps(record), request.state.user["username"], request.state.user["staff_id"], now_iso(), clinical_store),
            )
        return record

    # Show who entered local prescriptions and when, without exposing phone numbers.
    @app.get("/api/prescriptions/history")
    def prescription_history(request: Request, store_code: str | None = None):
        """Show clinical record IDs, author, store and timestamp without exposing phone numbers."""
        user = request.state.user
        require_role(user, "optometrist", "finance")
        if user["role"] not in {"admin", "finance"}:
            require_store(user, store_code or user["store_code"])
            predicate, parameters = "WHERE store_code=?", (store_code or user["store_code"],)
        elif store_code:
            require_store(user, store_code)
            predicate, parameters = "WHERE store_code=?", (store_code,)
        else:
            predicate, parameters = "", ()
        return rows(
            store_factory(),
            "SELECT rx_id,created_by,created_by_staff_id,created_at,store_code,"
            "json_extract(payload,'$.customer_id') AS customer_id,"
            "json_extract(payload,'$.valid_until') AS valid_until FROM prescriptions "
            + predicate + " ORDER BY created_at DESC",
            parameters,
        )

    # Prepare a linked lens-only remake and retain its cost owner and approver.
    @app.post("/api/remakes/prepare")
    def remake(body: RemakeRequest, request: Request):
        """Prepare a linked lens-only remake and retain its cost owner and approver."""
        user = request.state.user
        require_role(user, "manager")
        original = checkout_for(user, body.checkout_id)
        if original["status"] != "order_recorded" or body.cost_owner not in {
            "company",
            "customer",
            "external_optometrist",
        }:
            raise ValueError("Choose a completed bill and a valid remake cost owner")
        store = store_factory()
        quote = store.load_quote(body.checkout_id)
        if body.wearer_phone not in {
            line.get("wearer_phone") for line in quote.get("lines", [])
        }:
            raise ValueError("Choose a wearer from the original invoice")
        gateway = OperationsGateway(store)
        try:
            if gateway.variant(body.lens_variant_id)["eluno"]["line_type"] != "lens":
                raise ValueError("Remakes must contain only a lens")
            if gateway.order_by_id(original["shopify_order_id"]).get("refunds"):
                raise ValueError("A refunded bill cannot be remade")
            staff_id = (
                user["staff_id"]
                if user["role"] != "admin"
                else next(
                    staff["staff_id"]
                    for staff in gateway.staff(original["store_code"])
                    if staff["can_override_discount"]
                )
            )
            return SaleService(store, BillingAdapter(gateway)).prepare(
                phone=body.wearer_phone,
                store_code=original["store_code"],
                staff_id=staff_id,
                variant_ids=[body.lens_variant_id],
                remake={
                    **body.model_dump(),
                    "original_invoice": original["invoice_no"],
                    "approver": user["username"],
                },
            )
        finally:
            gateway.client.close()

    # Display expected cash from source transactions and local expenses.
    @app.get("/api/till")
    def till(store_code: str, request: Request):
        """Display expected cash from source transactions and local expenses."""
        require_store(request.state.user, store_code)
        gateway = OperationsGateway(store_factory())
        try:
            return till_summary(gateway.store, gateway, store_code)
        finally:
            gateway.client.close()

    # Open, expense or close a drawer with role and store enforcement.
    @app.post("/api/till/{action}")
    def till_action(action: str, body: AmountRequest, request: Request):
        """Open, expense or close a drawer with role and store enforcement."""
        require_role(
            request.state.user, "manager" if action == "close" else "cashier", "manager"
        )
        require_store(request.state.user, body.store_code)
        store = store_factory()
        if action == "open":
            return {"id": open_till(store, body.store_code, body.amount_paise)}
        if action in {"expense", "paid-in"}:
            active = current_till(store, body.store_code)
            if not active:
                raise HTTPException(409, "Open a drawer first")
            if body.amount_paise <= 0 or len(body.reason.strip()) < 3:
                raise ValueError("A positive cash movement and reason are required")
            identifier = str(uuid4())
            table = "expenses" if action == "expense" else "paid_ins"
            with store._connect() as connection:
                connection.execute(
                    f"INSERT INTO {table} VALUES(?,?,?,?,?,?)",
                    (
                        identifier,
                        active["id"],
                        body.amount_paise,
                        body.reason,
                        request.state.user["username"],
                        now_iso(),
                    ),
                )
            return {"id": identifier}
        if action == "close":
            gateway = OperationsGateway(store)
            try:
                return close_till(store, gateway, body.store_code, body.amount_paise)
            finally:
                gateway.client.close()
        raise HTTPException(404, "Unknown drawer action")

    # Return store-local sales, channel totals, refunds and reconciliation deltas.
    @app.get("/api/reports")
    def reports(day: str, request: Request, store_code: str | None = None):
        """Return store-local sales, channel totals, refunds and reconciliation deltas."""
        user = request.state.user
        if user["role"] not in {"admin", "finance"}:
            store_code = store_code or user["store_code"]
        if store_code:
            require_store(user, store_code)
        gateway = OperationsGateway(store_factory())
        try:
            return analytics(gateway, day, store_code)
        finally:
            gateway.client.close()

    # Export Shopify-derived figures with an explicit refund accounting basis.
    @app.get("/api/reports/export", response_class=Response, responses={
        200: {"description": "Downloadable Shopify-derived report.", "content": {"text/csv": {"schema": {"type": "string"}}}},
    })
    def export_report(day: str, request: Request, store_code: str | None = None,
                      basis: Literal["day_end", "daily"] = "day_end"):
        """Download exact INR amounts; store roles can export only their own store."""
        day = date.fromisoformat(day).isoformat()
        user = request.state.user
        if user["role"] not in {"admin", "finance"}:
            store_code = store_code or user["store_code"]
        if store_code:
            require_store(user, store_code)
        gateway = OperationsGateway(store_factory())
        try:
            if basis == "daily":
                result = analytics(gateway, day, store_code)
                summaries = result["stores"]
                refund_basis = result["refund_basis"]
            else:
                stores = [location["eluno"]["store_code"] for location in gateway.locations()
                          if location["eluno"]["kind"] == "store"
                          and (not store_code or location["eluno"]["store_code"] == store_code)]
                if not stores:
                    raise ValueError("Unknown store")
                summaries = [DayEndService(BillingAdapter(gateway)).report(code, day) for code in stores]
                refund_basis = "Refunds on orders from the selected date, regardless of refund date."
            output = io.StringIO(newline="")
            writer = csv.writer(output)
            writer.writerow(["date", "store", "bill_count", "gross_inr", "taxable_inr", "tax_inr",
                             "discounts_inr", "refunds_inr", "sales_inr", "net_collected_inr",
                             "cash_inr", "card_inr", "upi_inr", "other_payments_inr", "source", "refund_basis"])
            combined = {key: 0 for key in ("bill_count", "gross_paise", "taxable_paise", "tax_paise",
                                          "discounts_paise", "refunds_paise", "net_collected_paise")}
            combined["store_code"] = "ALL"
            combined["payment_methods"] = {}
            for summary in summaries:
                for key in combined:
                    if key not in {"store_code", "payment_methods"}:
                        combined[key] += summary[key]
                for method, amount in summary["payment_methods"].items():
                    combined["payment_methods"][method] = combined["payment_methods"].get(method, 0) + amount
            for summary in summaries + ([combined] if len(summaries) > 1 else []):
                methods = summary["payment_methods"]
                writer.writerow([
                    day, summary["store_code"], summary["bill_count"], money(summary["gross_paise"]),
                    money(summary["taxable_paise"]), money(summary["tax_paise"]),
                    money(summary["discounts_paise"]), money(summary["refunds_paise"]),
                    money(summary["gross_paise"] - summary["discounts_paise"]), money(summary["net_collected_paise"]),
                    money(methods.get("cash", 0)), money(methods.get("card", 0)), money(methods.get("upi", 0)),
                    money(sum(value for method, value in methods.items() if method not in {"cash", "card", "upi"})),
                    "Shopify orders", refund_basis,
                ])
            return Response(
                content=output.getvalue(), media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="eluno-{basis}-{store_code or "all-stores"}-{day}.csv"'},
            )
        finally:
            gateway.client.close()

    # Expose every invoice allocation including cancelled numbers.
    @app.get("/api/register")
    def register(store_code: str, request: Request):
        """Expose every invoice allocation including cancelled numbers."""
        require_store(request.state.user, store_code)
        return store_factory().invoice_allocations(store_code)

    # Show acceptance criteria and measured mock latency without a production claim.
    @app.get("/api/evidence")
    def evidence(request: Request):
        """Show acceptance criteria and measured mock latency without a production claim."""
        user = request.state.user
        predicate, parameters = (
            ("", ())
            if user["role"] in {"admin", "finance"}
            else (" AND c.store_code=?", (user["store_code"],))
        )
        measurements = rows(
            store_factory(),
            "SELECT c.checkout_id,c.checkout_elapsed_ms AS elapsed_ms,c.timing_recorded_at AS at "
            "FROM checkouts c WHERE c.checkout_elapsed_ms IS NOT NULL"
            + predicate,
            parameters,
        )
        values = sorted(item["elapsed_ms"] for item in measurements)
        import math

        return {
            "requirements": json.loads(
                (ROOT / "app/requirements.json").read_text(encoding="utf-8")
            ),
            "timings": {
                "samples": len(values),
                "p95_ms": values[max(0, math.ceil(len(values) * 0.95) - 1)]
                if values
                else None,
                "target_ms": 10000,
            },
            "scope": "Local mock confirmation API latency; not a production SLA.",
        }

    # Restrict cross-store audit history to central finance and administrators.
    @app.get("/api/audit")
    def audit_log(request: Request):
        """Restrict cross-store audit history to central finance and administrators."""
        require_role(request.state.user, "finance")
        return rows(store_factory(), "SELECT * FROM audit ORDER BY id DESC LIMIT 200")

    # Distinguish reviewable queued messages from actual SMTP delivery.
    @app.get("/api/outbox")
    def outbox(request: Request):
        """Distinguish reviewable queued messages from actual SMTP delivery."""
        require_role(request.state.user, "finance")
        return {
            "delivery": "SMTP configured"
            if os.environ.get("ELUNO_SMTP_HOST")
            else "Preview only — SMTP not configured",
            "schedule": "10:00 Asia/Kolkata, with catch-up after restart",
            "messages": rows(
                store_factory(),
                "SELECT * FROM outbox ORDER BY created_at DESC LIMIT 50",
            ),
        }

    # Generate a repeat-safe founder report preview for a selected day.
    @app.post("/api/reports/digest")
    def digest(day: str, request: Request):
        """Generate a repeat-safe founder report preview for a selected day."""
        require_role(request.state.user, "finance")
        gateway = OperationsGateway(store_factory())
        try:
            return founder_digest(gateway.store, gateway, day)
        finally:
            gateway.client.close()
