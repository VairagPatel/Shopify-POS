"""Presentation-oriented OpenAPI documentation for the same APIs used by the UI."""

from typing import Any
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field
from app.phone import PhoneNumber


class WearerSelection(BaseModel):
    phone: PhoneNumber = Field(
        description="Existing wearer phone; their own latest complete valid prescription is used.",
        examples=["+919000000004"],
    )
    variant_ids: list[int] = Field(
        default_factory=list,
        description="Selected frame and lens variant IDs. Every optical frame needs exactly one paired lens. Sunglasses can be ready-to-wear or paired with one prescription lens.",
        max_length=30,
        examples=[[91000003, 91000083]],
    )
    lens_only_variant_ids: list[int] = Field(
        default_factory=list,
        description="Lens pairs sold without frames. Each item is one lens-pair variant and is validated against this wearer's current prescription.",
        max_length=30,
        examples=[[91000083]],
    )
    frame_only_variant_ids: list[int] = Field(
        default_factory=list,
        description="Explicit frame-only purchases. These frames have no lens or prescription attached; move a frame into variant_ids with its lens to sell a complete prescription pair.",
        max_length=30,
        examples=[[91000003]],
    )


class OfferDecisionSchema(BaseModel):
    offer_id: str
    applied: bool
    amount_paise: int
    reason: str
    allocations_paise: list[int]


class QuoteResult(BaseModel):
    checkout_id: str = Field(
        description="Copy this into the complete and detail endpoints."
    )
    invoice_no: str = Field(
        description="Reserved local per-store invoice number; not a Shopify order number."
    )
    total_paise: int = Field(
        description="Exact amount to confirm. Divide by 100 for INR."
    )
    tax_paise: int = Field(description="GST already included in total_paise.")
    offers: list[OfferDecisionSchema]
    status: str = Field(
        description="draft: no payment or source order has been created."
    )


class CheckoutStateSchema(BaseModel):
    checkout_id: str
    store_code: str
    customer_id: str | None
    status: str
    payment_ref: str | None
    payment_charge_id: str | None
    shopify_order_id: str | None
    invoice_no: str | None
    error_detail: str | None
    created_at: str
    updated_at: str
    checkout_elapsed_ms: float | None = None
    timing_recorded_at: str | None = None


class RefundPreviewSchema(BaseModel):
    refund_id: str
    checkout_id: str
    status: str
    amount_paise: int
    tax_reversed_paise: int
    frame_restocked_on_shopify_success: bool = Field(
        description="Intended behavior on completion; prepare has NOT restocked anything."
    )


class CheckoutEvidenceSchema(BaseModel):
    checkout: CheckoutStateSchema
    quote: dict[str, Any] | None = Field(
        description="Persisted quote. order_payload is the order body prepared for Shopify; lines show each wearer, HSN and tax. Completion adds transactions before sending."
    )
    order: dict[str, Any] | None = Field(
        description="Live GET of the source Shopify mock order after completion, including line IDs, transactions and refunds; null before an order exists."
    )
    refunds: list[dict[str, Any]] = Field(
        description="Local durable refund attempts, including prepared payload_json and source IDs."
    )
    invoice: dict[str, Any] | None = Field(default=None, description="Immutable issued invoice in SQLite; null for an unpaid draft.")
    refund_events: list[dict[str, Any]] = Field(default_factory=list, description="Append-only refund state changes, actor references and synchronization times.")


TAGS = [
    (
        "00 · Access",
        "Start with POST /auth/login. Swagger itself is sufficient; no frontend login is needed. Use provisioned credentials. The browser stores the HttpOnly cookie and Swagger automatically attaches the session CSRF token.",
    ),
    (
        "01 · Read source data",
        "Read customer/catalog/inventory before quoting. Shopify provides commercial data; prescriptions and staff come from the store-tool mock. Offers and GST rules are local configuration.",
    ),
    (
        "02 · Quote — no payment",
        "Validate inputs, calculate offers and tax, then persist a quote and reserve an invoice number locally. No charge or Shopify order yet.",
    ),
    (
        "03 · Confirm and inspect",
        "Payment confirmation is a separate write. Inspect the saved quote and source order to explain exactly what came back from Shopify.",
    ),
    (
        "04 · Refund and reconcile",
        "Preview first, then refund payment and write the source refund. Uncertain writes require inspection; they are not blindly repeated.",
    ),
    (
        "05 · Source reports",
        "Read Shopify orders/refunds back to produce reconciled reports. The new report uses IST and refund-event dates; the original day-end contract is preserved.",
    ),
    (
        "06 · Store operations",
        "Clinical entry, remakes, cash drawer, saved carts, register and audit APIs use the same permissions as the UI.",
    ),
    (
        "07 · Demo evidence",
        "Coverage, local performance evidence and basic application health.",
    ),
]

DOCUMENTED = {
    "/auth/login": (
        "00 · Access",
        "1. Sign in directly in Swagger",
        "Authenticates a provisioned account and sets an HttpOnly session cookie. Use manager / S108 for the HSR examples, or admin. Credentials are never embedded in the schema.",
    ),
    "/auth/me": (
        "00 · Access",
        "Inspect the signed-in role and store",
        "Returns the authenticated identity and CSRF token. Swagger uses this automatically for write requests.",
    ),
    "/api/bootstrap": (
        "01 · Read source data",
        "2a. Discover stores, products and variant IDs",
        "Reads Shopify mock locations and products plus SMT staff. The customer search directory is a local synthetic fixture; /api/customers performs the live source lookup.",
    ),
    "/api/customers": (
        "01 · Read source data",
        "2b. Fetch the customer and prescriptions",
        "Existing-customer lookup, not registration. Supply phone in a JSON body; it is normalized to +91 plus ten digits. The standard demo runner uses body-based /eluno/customer-lookup and /eluno/prescription-lookup extensions in its durable mock wrapper. Explicit legacy adapter mode uses the original exercise GET contracts, which put phone in upstream URLs. Local clinician records are merged with source prescriptions; sale preparation chooses the latest valid one. Requires session and CSRF.",
    ),
    "/api/inventory": (
        "01 · Read source data",
        "2c. Check stock at the billing store",
        "Reads Shopify location mapping and inventory_levels.json. Keep inventory_item_id separate from variant_id. Note a frame’s quantity now and compare after sale/refund.",
    ),
    "/api/draft": (
        "01 · Durable local records",
        "Resume the latest cashier draft",
        "GET returns the current user's resumable draft. PUT saves an append-only cart_snapshots version with draft_id, actor username/staff ID, created/saved timestamps and time since the prior save. The drafts table is only the latest resume pointer; history is available from /api/drafts/history.",
    ),
    "/api/draft/metadata": (
        "01 · Durable local records",
        "Read the active draft ID and timestamps",
        "Returns lifecycle and actor metadata separately so the existing GET /api/draft cart payload contract remains unchanged.",
    ),
    "/api/drafts/history": (
        "01 · Durable local records",
        "Inspect all saved draft versions",
        "Reads SQLite cart_snapshots joined to checkouts and the returned Shopify order reference. The listing omits cart contents and phone numbers; full payloads remain in the local SQLite database and cart_tracking view.",
    ),
    "/api/prescriptions": (
        "01 · Durable local records",
        "Record a clinician-authored prescription",
        "Writes the Rx ID, normalized customer phone, authenticated username, staff ID, store and creation time into SQLite prescriptions. Local clinical additions are merged into customer prescription lookup.",
    ),
    "/api/prescriptions/history": (
        "01 · Durable local records",
        "Inspect prescription authorship",
        "Returns Rx ID, customer ID, valid-through date, author, staff ID, store and timestamp without disclosing phone numbers.",
    ),
    "/sales/prepare": (
        "02 · Quote — no payment",
        "3. Prepare a validated quote",
        "Reads customer, variants, billing location and stock from Shopify; staff and wearer prescriptions from SMT/local clinical records. A wearer can bill frame/lens pairs, ready-to-wear or prescription sunglasses, or lens-only pairs through lens_only_variant_ids. Every lens is validated against that wearer's prescription and carried on its Shopify line; standalone lens pairs have no frame pair_ref and do not affect frame inventory. Calculates effective-date HSN GST and discounts from local data. No coupon is applied unless selected_offer_id is supplied; then the server rechecks dates and cart/customer conditions and applies only that coupon. No manager discount is applied unless both override_bps and reason_code are provided with an authorized identity. Manager discount is exclusive of a coupon. Saves quote/order_payload in SQLite and reserves a store invoice number. Returns checkout_id. It does NOT charge payment, create a Shopify order or reserve physical inventory.",
    ),
    "/sales/{checkout_id}/complete": (
        "03 · Confirm and inspect",
        "4. Confirm payment and create the source order",
        "For UPI/card: POST terminal /terminal/charges, persist charge reference, then POST Shopify orders.json with the saved lines, discounts, tax, location, invoice/checkout metadata and a successful payment transaction. Shopify creates the order and decrements tracked stock at that store. Cash and zero-charge remakes use their own local payment handling. A successful repeat returns the same order. An uncertain result is blocked for investigation.",
    ),
    "/checkouts/{checkout_id}": (
        "03 · Confirm and inspect",
        "Inspect durable local checkout state",
        "Reads SQLite only. Shows which financial stage finished, external references and completion duration stored directly on the checkout row; this does not fetch the source order.",
    ),
    "/api/checkouts/{identifier}/detail": (
        "03 · Confirm and inspect",
        "5. Compare prepared payload with the source order",
        "Reads local checkout/quote/refund_attempts and GETs Shopify orders/{id}.json when an order ID exists. Checkout duration is on the checkout row. Expand quote.order_payload for prepared source fields; completion additionally sends transactions. Expand order for the actual returned source record. order.refunds proves the Shopify refund exists; compare it with the local refund attempt and IDs.",
    ),
    "/refunds/prepare": (
        "04 · Refund and reconcile",
        "6a. Preview original-line refund and tax",
        "GETs the original Shopify order, then POSTs refunds/calculate.json to obtain refundable lines/tax/maximum amount. Saves a local refund attempt. A calculation POST is not a financial refund: no terminal refund or restock occurs yet. Returns refund_id.",
    ),
    "/refunds/{refund_id}/complete": (
        "04 · Refund and reconcile",
        "6b. Refund payment and write back to Shopify",
        "For electronic payment: POST terminal /terminal/refunds, persist its reference, then POST Shopify orders/{id}/refunds.json. Physical frames use return at the original billing location; lenses use no_restock. The source refund reverses the original line tax. Cash refunds require an open drawer.",
    ),
    "/sales/{checkout_id}/reconcile-order": (
        "04 · Refund and reconcile",
        "Recover an uncertain order without posting again",
        "Searches source orders for the saved checkout identifier. It never automatically recharges or reposts an order.",
    ),
    "/refunds/{refund_id}/reconcile-shopify": (
        "04 · Refund and reconcile",
        "Recover an uncertain source refund without refunding twice",
        "GETs the original source order and matches eluno_refund_id. It does not repeat the terminal refund or source write.",
    ),
    "/api/till/{action}": (
        "05 · Source reports",
        "Open, record paid-in or expense, and close a drawer",
        "Actions: open, paid-in, expense (paid-out), close. Amounts are integer paise. Paid-ins/expenses require a positive amount and a reason of at least three characters; they record the authenticated actor. Expected cash includes paid-ins without treating them as sales revenue. Close requires manager/admin and rejects unresolved financial operations.",
    ),
    "/api/reports": (
        "05 · Source reports",
        "7. Read Shopify back and reconcile the result",
        "Reads source orders and nested refunds. Uses Asia/Kolkata order-day sales and refund-event-day collections, with channel attribution and payment-to-order deltas. Compare before and after refund. Not calculated merely from local checkout rows.",
    ),
    "/api/reports/export": (
        "05 · Source reports",
        "Download the selected date as a CSV",
        "Shopify-derived bill count, gross, taxable, tax, discount, refunds and cash/card/UPI totals. basis=day_end matches the original order-date report, including all refunds on those orders. basis=daily matches the website's refund-event-date collection summary. Store roles are restricted to their own store; central roles can download all seven stores and combined totals.",
    ),
    "/reports/day-end": (
        "05 · Source reports",
        "Original order-day report contract",
        "Preserved API: counts refunds on orders from the selected order date regardless of refund date. Use /api/reports for the newer refund-event-date view.",
    ),
}


# Add ordered groups, request examples and inspectable response schemas without changing API results.
def install_api_documentation(app):
    """Build OpenAPI as an independently usable technical presentation of the UI's backend."""
    app.openapi_tags = [
        {"name": name, "description": description} for name, description in TAGS
    ]
    app.description = """## Two clients, one backend
The frontend at `/` and this Swagger UI call the same FastAPI services and share the same records.
You can complete the whole demonstration here without opening the frontend.

**Route through the demo:** login → source customer/catalog/stock → prepare → complete → detail → refund prepare/complete → source report.

**Data ownership:** Shopify mock = customers, catalog, stock, orders and refunds; SMT mock = prescriptions and staff; local configuration = offers and GST; SQLite = saved quotes, invoice series, financial state, sessions, clinical additions, cash and audit.

**Important:** this is a supplied Shopify-shaped mock, not a live Shopify store. All amounts named `_paise` are integer paise. Read source inventory before and after completion to prove the stock effect.

For every operation, expand the description, inspect the request **Schema**, then inspect the returned **Response body**. Copy returned checkout/refund IDs into later steps. Under detail, compare `quote.order_payload` with `order`.
"""
    for route in app.routes:
        if not getattr(route, "include_in_schema", False):
            continue
        if route.path in DOCUMENTED:
            tag, summary, description = DOCUMENTED[route.path]
            route.tags, route.summary, route.description = [tag], summary, description
        else:
            tag = (
                "00 · Access"
                if route.path.startswith("/auth/")
                else "04 · Refund and reconcile"
                if route.path.startswith("/refunds/")
                else "05 · Source reports"
                if route.path.startswith("/api/reports")
                else "07 · Demo evidence"
                if route.path in {"/health", "/api/evidence"}
                else "06 · Store operations"
            )
            route.tags = [tag]

    # Enrich generated schema once while leaving endpoint behavior and financial writes unchanged.
    def documented_openapi():
        """Attach named request examples and reusable response contracts to the generated schema."""
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
            tags=app.openapi_tags,
        )
        components = schema.setdefault("components", {}).setdefault("schemas", {})
        for model in (
            QuoteResult,
            CheckoutStateSchema,
            RefundPreviewSchema,
            CheckoutEvidenceSchema,
        ):
            contract = model.model_json_schema(
                ref_template="#/components/schemas/{model}"
            )
            components.update(contract.pop("$defs", {}))
            components[model.__name__] = contract
        response_models = {
            ("/sales/prepare", "post"): "QuoteResult",
            ("/sales/{checkout_id}/complete", "post"): "CheckoutStateSchema",
            ("/checkouts/{checkout_id}", "get"): "CheckoutStateSchema",
            ("/refunds/prepare", "post"): "RefundPreviewSchema",
            ("/api/checkouts/{identifier}/detail", "get"): "CheckoutEvidenceSchema",
        }
        for (path, method), model_name in response_models.items():
            schema["paths"][path][method]["responses"]["200"]["content"][
                "application/json"
            ]["schema"] = {"$ref": "#/components/schemas/" + model_name}
        sample = {
            "phone": "+919000000004",
            "store_code": "HSR",
            "staff_id": "S108",
            "variant_ids": [91000003, 91000083],
            "payment_method": "upi",
            "channel": "walk_in",
        }
        coupon_sample = {**sample, "selected_offer_id": "FESTIVE10"}
        schema["paths"]["/sales/prepare"]["post"]["requestBody"]["content"][
            "application/json"
        ]["examples"] = {
            "single_pair": {
                "summary": "One customer / one pair — manager S108",
                "value": sample,
            },
            "one_selected_coupon": {
                "summary": "Apply only the selected coupon",
                "value": coupon_sample,
            },
            "lens_only_pair": {
                "summary": "Sell one prescription lens pair without a frame",
                "value": {
                    **sample,
                    "variant_ids": [],
                    "members": [
                        {
                            "phone": "+919000000004",
                            "variant_ids": [],
                            "lens_only_variant_ids": [91000083],
                        }
                    ],
                },
            },
            "exact_manager_discount": {
                "summary": "Apply the entered 5% manager discount only",
                "value": {
                    **sample,
                    "override_bps": 500,
                    "reason_code": "walk_out_retention",
                    "selected_offer_id": "MANAGER_OVERRIDE",
                },
            },
            "family": {
                "summary": "Three wearers / three prescriptions / one invoice",
                "value": {
                    **sample,
                    "variant_ids": [],
                    "members": [
                        {"phone": phone, "variant_ids": variants}
                        for phone, variants in [
                            ("+919000000013", [91000003, 91000083]),
                            ("+919000000004", [91000005, 91000083]),
                            ("+919000000015", [91000006, 91000083]),
                        ]
                    ],
                },
            },
        }
        schema["paths"]["/refunds/prepare"]["post"]["requestBody"]["content"][
            "application/json"
        ]["example"] = {
            "checkout_id": "PASTE_RETURNED_CHECKOUT_ID",
            "reason": "customer_return",
        }
        for path, operations in schema["paths"].items():
            for method, operation in operations.items():
                if method not in {"get", "post", "put", "delete", "patch"}:
                    continue
                for parameter in operation.get("parameters", []):
                    if parameter["name"] == "phone":
                        parameter["example"] = "+919000000004"
                    if parameter["name"] == "store_code":
                        parameter["example"] = "HSR"
                if path not in {"/health", "/auth/login"}:
                    operation["responses"].setdefault(
                        "401", {"description": "Sign in using POST /auth/login first."}
                    )
                    operation["responses"].setdefault(
                        "403",
                        {
                            "description": "Role/store access or CSRF check rejected the request."
                        },
                    )
        app.openapi_schema = schema
        return schema

    app.openapi_schema = None
    app.openapi = documented_openapi
