"""Same-origin UI APIs and security boundary for both new and original routes."""

import hashlib
import hmac
import json
import os
import threading
import time
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
from app.services.catalog import load_json
from app.domain.models import CheckoutStatus
from app.gateways.http import GatewayError

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
    wearer_phone: str
    reason: str = Field(min_length=3, max_length=500)
    cost_owner: str
    lab_cost_paise: int = Field(strict=True, ge=0, le=100000000)


# Mount additive routes and guard every existing business endpoint.
def install(app, store_factory):
    """Mount additive routes and guard every existing business endpoint."""
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
                            or not 0 <= body["override_bps"] <= 1000
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
                            or not isinstance(item.get("variant_ids"), list)
                            or not 1 <= len(item["variant_ids"]) <= 30
                            or any(
                                type(value) is not int for value in item["variant_ids"]
                            )
                            for item in members
                        )
                    ):
                        raise HTTPException(
                            422,
                            "Supply up to ten wearers, each with a phone and 1–30 variant IDs; repeat an ID for quantity",
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
                            "INSERT OR IGNORE INTO timings VALUES(?,?,?)",
                            (segments[1], elapsed, now_iso()),
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
            max_age=28800,
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
                "today": datetime.now(INDIA).date().isoformat(),
            }
        finally:
            gateway.client.close()

    # Fetch the live customer record and all available prescriptions.
    @app.get("/api/customers")
    def customer(phone: str, request: Request):
        """Fetch the live customer record and all available prescriptions."""
        gateway = OperationsGateway(store_factory())
        try:
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
            "SELECT c.*,q.quote_json FROM checkouts c LEFT JOIN checkout_quotes q USING(checkout_id) WHERE store_code=? ORDER BY created_at DESC LIMIT 200",
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

    # Save a bounded browser cart for cross-reload recovery.
    @app.put("/api/draft")
    def save_draft(body: dict, request: Request):
        """Save a bounded browser cart for cross-reload recovery."""
        require_role(request.state.user, "cashier", "manager")
        payload = json.dumps(body)
        if len(payload) > 40000:
            raise HTTPException(413, "Cart is too large")
        with store_factory()._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO drafts VALUES(?,?)",
                (request.state.user["username"], payload),
            )
        return {"saved": True}

    # Record a clinician-authored prescription with five-degree manual axis steps.
    @app.post("/api/prescriptions")
    def prescription(body: dict, request: Request):
        """Record a clinician-authored prescription with five-degree manual axis steps."""
        require_role(request.state.user, "optometrist")
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
                if axis is not None and (
                    type(axis) is not int or not 5 <= axis <= 180 or axis % 5
                ):
                    raise ValueError("New axis entries must use 5-degree intervals")
                if cylinder and axis is None:
                    raise ValueError("Cylinder requires an axis")
                if (
                    eye.get("add") is not None
                    and not 0 <= Decimal(str(eye["add"])) <= 5
                ):
                    raise ValueError("ADD must be between 0 and 5")
            except (KeyError, InvalidOperation, TypeError) as exception:
                raise ValueError("Enter valid prescription values") from exception
        today = datetime.now(INDIA).date()
        valid_until = date.fromisoformat(body.get("valid_until", ""))
        if not today <= valid_until <= today + timedelta(days=730):
            raise ValueError("Validity must be within the next two years")
        gateway = OperationsGateway(store_factory())
        try:
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
                "INSERT INTO prescriptions VALUES(?,?,?)",
                (identifier, record["phone"], json.dumps(record)),
            )
        return record

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
            return SaleService(store, gateway).prepare(
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
        if action == "expense":
            active = current_till(store, body.store_code)
            if not active:
                raise HTTPException(409, "Open a drawer first")
            if body.amount_paise <= 0 or len(body.reason.strip()) < 3:
                raise ValueError("A positive expense and reason are required")
            identifier = str(uuid4())
            with store._connect() as connection:
                connection.execute(
                    "INSERT INTO expenses VALUES(?,?,?,?,?,?)",
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
            else (" WHERE c.store_code=?", (user["store_code"],))
        )
        measurements = rows(
            store_factory(),
            "SELECT t.* FROM timings t JOIN checkouts c USING(checkout_id)" + predicate,
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
