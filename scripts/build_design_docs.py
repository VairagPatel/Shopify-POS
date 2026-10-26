"""Generate readable HLD/LLD documents and an offline HTML presentation."""

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

HLD = (ROOT / "docs/PROBLEM_HLD.md").read_text(encoding="utf-8")

LLD = """# Low-Level Design — Eluno Store Studio

Read the HLD first. This document maps the design to current modules and persisted contracts. The generated API/schema guide is the companion field-level reference.

## 1. Module responsibilities
app/main.py: FastAPI setup, request models and sale/refund orchestration routes.
app/web.py: frontend, authentication routes, operational APIs and authorization middleware.
app/security.py: password hashing, session validation, user provisioning, role/store guards and operational table initialization.
app/services/sale.py: prepare, complete, source-order write and order reconciliation.
app/services/refunds.py: full-refund preparation, completion and source reconciliation.
app/services/prescriptions.py: latest valid Rx selection and lens compatibility checks.
app/services/offers.py and taxes.py: offer evaluation and inclusive-GST arithmetic.
app/services/reporting.py and app/operations.py: source-based reporting, local Rx overlay, tills, audit and digest construction.
app/persistence/sqlite.py: durable state, compare-and-set transitions and serialized invoice reservation.
app/gateways/http.py: mock HTTP contracts and GatewayError classification.
app/customer_schemas.py and phone.py: typed customer/clinical inputs and canonical phone validation.
app/scheduler.py: digest scheduling and email outbox delivery.
app/static/app.js: browser workflow; it calls APIs rather than owning authoritative pricing.
scripts/persistent_mock.py: durable source snapshot and private lookup extensions.

## 2. Identity and prescription linkage
POST /api/customers accepts {"phone":"9000000005"}. CustomerLookupRequest applies PhoneNumber validation. normalize_phone returns +919000000005. Accepted forms include ten local digits, 91-prefixed digits, +91 and a leading domestic zero with supported separators. Non-string JSON, foreign or malformed numbers are rejected.

The handler uses OperationsGateway: the source customer lookup returns CustomerRecord; prescriptions are source records plus the local clinical overlay. CustomerLookupResponse contains customer and prescriptions. No source match returns 404. GET /api/customers is retired and returns 405.

Source/local prescription records retain rx_id, customer_id, canonical phone, issue date, valid_until and right/left eye values (od/os). The current lookup association is phone-based; it is not a normalized customer foreign-key design. Clinical creation is POST /api/prescriptions and requires the optometrist role (admin override follows the shared guard). EyeInput validates sphere/cylinder bounds, axis five-degree steps and ADD bounds.

Sale preparation selects the latest unexpired prescription and adapts it to Prescription/EyePower. Each lens CartLine carries prescription_id; wearer selections determine whose prescription is used. CartLine pair_ref associates a frame and lens within that wearer. Source order line properties carry the billing/clinical trace information. Historical records are not bulk-normalized by this change.

Proposed only: POST /api/customer-registrations, source customer creation, duplicate detection and eventual stable-customer-ID clinical joins. Shared-family-phone policy, phone changes and ownership verification need decisions before implementation.

## 3. Sale prepare algorithm
Normalize payer and wearer phones → resolve store location → verify customers and staff → validate variants and wearer pairing → check stock and prescriptions → evaluate offers and authorized override → calculate line tax/totals → reserve invoice and persist quote → return checkout identifier and calculated result.

PrepareRequest contains phone, store_code, staff_id, variant_ids, payment_method, channel, optional checkout_id/reason_code/override_bps and members. Payment methods are upi/card/cash. Channels are walk_in/whatsapp/online_pickup. Do not trust a client-supplied role or price. Existing server middleware and service checks enforce the actual user's access.

Money is represented in integer paise; basis points express percentage inputs. Source decimal money strings convert through Decimal. Inclusive-tax splitting separates taxable value and tax from discounted gross; invoice totals sum the line results. Offer priority and stackability follow implemented rule data, not unrestricted stacking of every stakeholder example.

The persisted quote contains the source order payload and payment amount/method. Completion loads this quote rather than accepting a new client price. A quote does not reserve source stock.

## 4. Checkout state machine and side effects
Normal: draft → payment_pending → payment_captured → order_pending → order_recorded.
Charge GatewayError: payment_pending → payment_uncertain.
Order GatewayError: order_pending → order_uncertain.
Order reconciliation: one reference match → order_recorded; multiple → reconciliation_required; zero → remain order_uncertain.
Cancellation is a guarded operational action; do not treat every non-final state as safely cancellable.

complete(checkout_id) returns saved state when already order_recorded; any other non-draft state is blocked for inspection. Before payment, it rechecks aggregate inventory demand. It persists payment_ref = elu-checkout-<checkout_id> and changes draft to payment_pending conditionally. Cash uses a cash reference; a zero amount uses a no-charge reference; otherwise the terminal receives a charge call.

After capture it stores payment_charge_id, records payment_captured, changes to order_pending and sends a source order payload with the successful transaction. It saves shopify_order_id, marks order_recorded and updates the invoice allocation to issued. These are several durable steps, not one cross-system atomic commit; a crash between them can require reconciliation or repair.

reconcile_order reads source orders and matches note_attributes.checkout_id. It never automatically POSTs another order. The payment reference helps tracing but cannot manufacture provider-side exactly-once guarantees. Unknown terminal results require investigation; the current demo has no universal automatic payment recovery path.

## 5. Invoice and concurrency design
invoice_series holds store_code, prefix and next_number. reserve_invoice uses BEGIN IMMEDIATE to serialize allocation, reuses an existing checkout allocation, inserts invoice_allocations and advances the sequence in one local transaction. Unique store/serial and checkout constraints prevent duplicate allocation. Reserved or cancelled numbers remain auditable and are not recycled.

change_status updates only WHERE checkout_id=? AND status=<expected>. A lost concurrent claim becomes StateConflict. Unique payment_ref and shopify_order_id prevent conflicting local reference assignment. This protects local state; it does not lock external inventory or create a distributed transaction. SQLite connections use a 15-second busy timeout. Declared SQL relationships must not be confused with complete cross-system referential enforcement.

## 6. Full-refund state machine
prepared → terminal_pending → terminal_refunded → shopify_pending → recorded.
Terminal GatewayError → terminal_uncertain. Source refund GatewayError → shopify_uncertain.
Source reconciliation: one eluno_refund_id match → recorded; several → manual_review; none → remain uncertain.

prepare requires an order_recorded checkout and reads its original source order. It builds full refund lines and asks the source for the calculation. refund_attempts persists amount and payload before refunding. Its unique checkout_id restricts this model to one full refund attempt per checkout. complete returns an already-recorded result but blocks blindly repeating an attempted refund.

Frame reversal uses the billing location; lenses use the non-restock path. The source refund represents the line tax reversal and the credit-note context references the original invoice. Real finance approval remains required. Remakes use the separate lens-only prepare flow; they are not a frame refund/rebuy shortcut.

## 7. Reports, drawer and outbox
analytics reads source orders/refunds and aggregates by business day and optional store. Central totals sum sales and bills and calculate average bill value from the combined amount/count, not an unweighted average of store averages. Local operations attach opening cash, recorded expenses and counted cash to till records. The one_open_till partial unique index prevents two open sessions for one store.

Digest and variance messages enter outbox. Delivery claims queued → sending; successful SMTP submission records sent, while uncertain delivery records delivery_uncertain. Do not automatically resend an uncertain message and risk duplicates. Delivery requires SMTP configuration and an active scheduler process. The outbox is an email queue, not a general Shopify synchronization queue.

## 8. Errors and validation
401 means no valid session; 403 means forbidden role/store/CSRF context. 404 identifies missing records, 405 the retired lookup method, 422 invalid business/input data, 409 a state conflict and 502 a provider failure. Exact response bodies come from each route/exception handler. Some schemas still expose generic object responses; the design guide does not imply every dictionary field has runtime type validation.

Session tokens are stored hashed. Passwords use PBKDF2-HMAC-SHA256 with 600,000 iterations and a per-password salt. Mutation requests require the session's CSRF context. Browser/Swagger share backend authorization. Logs strip URL query strings, but body logging by a future proxy/APM needs its own controls.

## 9. Verification scenarios
Lookup: bare number and +91 format resolve the same customer; invalid input fails; unknown customer is 404; no phone appears in default request URLs; old GET is 405.
Clinical: latest unexpired Rx selected; incompatible lens blocked; invalid axis rejected; progressive lens requires suitable ADD; family members retain distinct Rx associations.
Billing: valid frame/lens cart, multiple wearer units, authorized override/reason, stock changed before complete, double-click completion and concurrent invoice allocation.
Failures: terminal timeout does not lead to automatic recharge; source order timeout is reconciled by reference; duplicate matching orders require review; process interruption leaves inspectable persisted state.
Refund: correct tax reversal, original-store frame restock, no lens restock, repeated completion, uncertain source reconciliation.
Operations: role/store denial, central totals, cash expenses/variance, unresolved-state close guard and SMTP-uncertain behavior.

Recorded validation: 333 full-suite tests passed and the private-wrapper browser journey passed separately. Load, real-provider, backup-recovery and seven-store rollout tests remain separate production acceptance work.

## 10. API and database reference
The following appendix is generated from the saved OpenAPI contract and current CREATE TABLE declarations. These are actual project contracts, not proposed endpoint names. Full request/response bodies and external endpoints are in api-schema-guide.html and docs/openapi-contract.json. CREATE TABLE excerpts do not include every later ALTER TABLE migration or index; consult source for those details.
"""


# Render the small documentation format without external packages or remote assets.
def render(text):
    blocks = []
    for paragraph in text.strip().split("\n\n"):
        if paragraph.startswith("# "):
            blocks.append("<h1>" + html.escape(paragraph[2:]) + "</h1>")
        elif paragraph.startswith("## "):
            blocks.append("<h2>" + html.escape(paragraph[3:]) + "</h2>")
        else:
            blocks.append("<p>" + html.escape(paragraph).replace("\n", "<br>") + "</p>")
    return "\n".join(blocks)


# Write both Markdown deliverables and the offline presentation from shared content.
def main():
    spec = json.loads((ROOT / "docs/openapi-contract.json").read_text(encoding="utf-8"))
    endpoints = []
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            if method in {"get", "post", "put", "delete", "patch"}:
                endpoints.append(
                    f"{method.upper()} {path} — {operation.get('summary', '')}"
                )
    tables = []
    for filename in ["app/persistence/sqlite.py", "app/security.py"]:
        source = (ROOT / filename).read_text(encoding="utf-8")
        tables.extend(re.findall(r"CREATE TABLE IF NOT EXISTS\s+.*?;", source, re.S))
    appendix = "\n\n## Implemented API inventory\n\n" + "\n".join(endpoints)
    appendix += "\n\n## Database table declarations\n\n" + "\n\n".join(tables)
    (ROOT / "docs/HLD.md").write_text(HLD, encoding="utf-8")
    (ROOT / "docs/LLD.md").write_text(LLD + appendix, encoding="utf-8")
    diagram = '<div class="diagram"><div>Frontend / Swagger</div><b>↓ Same API contracts</b><div>FastAPI · Authentication · Role/store checks</div><b>↓</b><div>Sale · Clinical · Offers · Tax · Refund · Reports</div><b>↙ Durable state &nbsp; ↘ External calls</b><div>SQLite &nbsp; | &nbsp; OperationsGateway → Shopify / SMT / Terminal mocks</div></div>'
    document = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Eluno — HLD & LLD</title><style>
    *{box-sizing:border-box}body{margin:0;background:#f7f5ed;color:#213b35;font:17px/1.75 system-ui,sans-serif}header{background:#213b35;color:#fff;padding:48px max(24px,calc((100% - 1080px)/2))}header p{color:#e6e8da}nav{position:sticky;top:0;background:#edf0e5;padding:14px 24px;display:flex;gap:24px;flex-wrap:wrap;border-bottom:1px solid #ccd3c5}a{color:#ad541d}main{max-width:1080px;margin:auto;padding:28px 24px}h1{font-size:clamp(28px,4vw,46px);line-height:1.2}h2{margin-top:40px;border-top:1px solid #d4d8ca;padding-top:24px;font-size:25px}p{overflow-wrap:anywhere}section{scroll-margin-top:85px}button{background:#b95d21;color:white;border:0;padding:10px 18px;cursor:pointer}.diagram{padding:24px;background:#e9ede2;text-align:center;margin:28px 0}.diagram div{background:white;padding:14px;border:1px solid #c7cebd;border-radius:6px}.diagram b{display:block;margin:8px}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#203a34;color:#fff;padding:20px;font:13px/1.65 monospace}details{border:1px solid #c7cebd;padding:18px;margin:20px 0}summary{cursor:pointer;font-weight:700}.note{border-left:5px solid #f88e2b;padding:14px 22px;background:#fff0dc}@media print{nav,button{display:none}body{background:white;font-size:11pt}header{padding:12px;background:white;color:#213b35}header p{color:#213b35}main{padding:0}h2{break-after:avoid}pre{background:#eee;color:black}section{break-before:page}}
    </style><header><small>ELUNO STORE STUDIO · TECHNICAL DESIGN</small><h1>How the system fits together.<br>How each operation works.</h1><p>HLD for the system view. LLD for the implementation view.<br>Problem-led design · 26 October 2026</p></header><nav><a href="#hld">High-Level Design</a><a href="#lld">Low-Level Design</a><a href="api-schema-guide.html">Detailed API schemas</a><button onclick="document.querySelectorAll('details').forEach(x=>x.open=true);window.print()">Print / Save PDF</button></nav><main><p class="note">Implemented evaluation demo using local mocks. Production proposals and limitations are explicitly labelled. Customer registration remains proposed.</p>"""
    document += (
        diagram
        + '<section id="hld">'
        + render(HLD)
        + '</section><section id="lld">'
        + render(LLD)
    )
    document += (
        "<details open><summary>Implemented API inventory</summary><pre>"
        + html.escape("\n".join(endpoints))
        + "</pre></details>"
    )
    document += (
        "<details><summary>Database table declarations</summary><pre>"
        + html.escape("\n\n".join(tables))
        + "</pre></details></section></main></html>"
    )
    (ROOT / "app/static/design-guide.html").write_text(document, encoding="utf-8")
    print(
        f"Generated HLD, LLD and HTML: {len(endpoints)} operations, {len(tables)} tables"
    )


if __name__ == "__main__":
    main()
