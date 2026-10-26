# Low-Level Design — Eluno Store Studio

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

Sale preparation selects the latest unexpired prescription and adapts it to Prescription/EyePower. Each lens CartLine carries prescription_id; wearer selections determine whose prescription is used. CartLine pair_ref associates a frame and lens within that wearer. Standalone lens pairs use the separate `lens_only_variant_ids` wearer field and have no frame pair_ref. Both paths retain the prescription on the source order lens line; lens-only lines do not read or change frame inventory. Historical records are not bulk-normalized by this change.

Proposed only: POST /api/customer-registrations, source customer creation, duplicate detection and eventual stable-customer-ID clinical joins. Shared-family-phone policy, phone changes and ownership verification need decisions before implementation.

## 3. Sale prepare algorithm
Normalize payer and wearer phones → resolve store location → verify customers and staff → validate variants and wearer pairing → check stock and prescriptions → evaluate offers and authorized override → calculate line tax/totals → reserve invoice and persist quote → return checkout identifier and calculated result.

PrepareRequest contains phone, store_code, staff_id, variant_ids, payment_method, channel, optional checkout_id/reason_code/override_bps and members. Each wearer has paired `variant_ids` plus optional `lens_only_variant_ids`; each lens-only variant is a prescribed lens pair. Payment methods are upi/card/cash. Channels are walk_in/whatsapp/online_pickup. Do not trust a client-supplied role or price. Existing server middleware and service checks enforce the actual user's access.

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
Billing: valid frame/lens cart, lens-only pair with wearer prescription, multi-wearer units, selected coupon exclusivity, authorized override/reason, stock changed before complete, double-click completion and concurrent invoice allocation.
Failures: terminal timeout does not lead to automatic recharge; source order timeout is reconciled by reference; duplicate matching orders require review; process interruption leaves inspectable persisted state.
Refund: correct tax reversal, original-store frame restock, no lens restock, repeated completion, uncertain source reconciliation.
Operations: role/store denial, central totals, cash expenses/variance, unresolved-state close guard and SMTP-uncertain behavior.

Recorded validation: 333 full-suite tests passed and the private-wrapper browser journey passed separately. Load, real-provider, backup-recovery and seven-store rollout tests remain separate production acceptance work.

## 10. API and database reference
The following appendix is generated from the saved OpenAPI contract and current CREATE TABLE declarations. These are actual project contracts, not proposed endpoint names. Full request/response bodies and external endpoints are in api-schema-guide.html and docs/openapi-contract.json. CREATE TABLE excerpts do not include every later ALTER TABLE migration or index; consult source for those details.


## Implemented API inventory

GET /health — Health
GET /checkouts/{checkout_id} — Inspect durable local checkout state
POST /sales/prepare — 3. Prepare a validated quote
POST /sales/{checkout_id}/complete — 4. Confirm payment and create the source order
POST /sales/{checkout_id}/reconcile-order — Recover an uncertain order without posting again
POST /refunds/prepare — 6a. Preview original-line refund and tax
GET /refunds/{refund_id} — Refund State
POST /refunds/{refund_id}/complete — 6b. Refund payment and write back to Shopify
POST /refunds/{refund_id}/reconcile-shopify — Recover an uncertain source refund without refunding twice
GET /reports/day-end — Original order-day report contract
GET / — Homepage
POST /auth/login — 1. Sign in directly in Swagger
GET /auth/me — Inspect the signed-in role and store
POST /auth/logout — Logout
GET /api/bootstrap — 2a. Discover stores, products and variant IDs
POST /api/customers — 2b. Fetch the customer and prescriptions
GET /api/inventory — 2c. Check stock at the billing store
GET /api/transactions — Transactions
GET /api/checkouts/{identifier}/detail — 5. Compare prepared payload with the source order
POST /api/checkouts/{identifier}/cancel — Cancel
GET /api/draft — Draft
PUT /api/draft — Save Draft
POST /api/prescriptions — Prescription
POST /api/remakes/prepare — Remake
GET /api/till — Till
POST /api/till/{action} — Open, record paid-in or expense, and close a drawer
GET /api/reports — 7. Read Shopify back and reconcile the result
GET /api/register — Register
GET /api/evidence — Evidence
GET /api/audit — Audit Log
GET /api/outbox — Outbox
POST /api/reports/digest — Digest

## Database table declarations

CREATE TABLE IF NOT EXISTS checkouts (
                  checkout_id TEXT PRIMARY KEY,
                  store_code TEXT NOT NULL,
                  customer_id TEXT,
                  status TEXT NOT NULL,
                  payment_ref TEXT UNIQUE,
                  payment_charge_id TEXT,
                  shopify_order_id TEXT UNIQUE,
                  invoice_no TEXT UNIQUE,
                  error_detail TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );

CREATE TABLE IF NOT EXISTS checkout_quotes (
                  checkout_id TEXT PRIMARY KEY REFERENCES checkouts(checkout_id),
                  quote_json TEXT NOT NULL
                );

CREATE TABLE IF NOT EXISTS invoice_series (
                  store_code TEXT PRIMARY KEY,
                  prefix TEXT NOT NULL,
                  next_number INTEGER NOT NULL CHECK (next_number > 0)
                );

CREATE TABLE IF NOT EXISTS invoice_allocations (
                  invoice_no TEXT PRIMARY KEY,
                  checkout_id TEXT NOT NULL UNIQUE REFERENCES checkouts(checkout_id),
                  store_code TEXT NOT NULL,
                  serial_number INTEGER NOT NULL,
                  allocated_at TEXT NOT NULL,
                  status TEXT NOT NULL DEFAULT 'reserved',
                  UNIQUE(store_code, serial_number)
                );

CREATE TABLE IF NOT EXISTS refund_attempts (
                  refund_id TEXT PRIMARY KEY,
                  checkout_id TEXT NOT NULL UNIQUE REFERENCES checkouts(checkout_id),
                  shopify_order_id TEXT NOT NULL,
                  amount_paise INTEGER NOT NULL,
                  payload_json TEXT NOT NULL,
                  status TEXT NOT NULL,
                  terminal_refund_id TEXT,
                  shopify_refund_id TEXT,
                  error_detail TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );

CREATE TABLE IF NOT EXISTS users(username TEXT PRIMARY KEY, password_hash TEXT NOT NULL,
          role TEXT NOT NULL, store_code TEXT NOT NULL, staff_id TEXT NOT NULL, display_name TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, username TEXT NOT NULL,
          csrf TEXT NOT NULL, expires REAL NOT NULL);

CREATE TABLE IF NOT EXISTS login_attempts(username TEXT PRIMARY KEY, attempts INTEGER NOT NULL, since REAL NOT NULL);

CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL,
          actor TEXT NOT NULL, action TEXT NOT NULL, reference TEXT NOT NULL, detail TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS drafts(username TEXT PRIMARY KEY, payload TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS prescriptions(rx_id TEXT PRIMARY KEY, phone TEXT NOT NULL, payload TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS tills(id TEXT PRIMARY KEY, store_code TEXT NOT NULL, opened_at TEXT NOT NULL,
          closed_at TEXT, opening_paise INTEGER NOT NULL, counted_paise INTEGER, expected_paise INTEGER, variance_paise INTEGER);

CREATE TABLE IF NOT EXISTS expenses(id TEXT PRIMARY KEY, till_id TEXT NOT NULL, amount_paise INTEGER NOT NULL,
          reason TEXT NOT NULL, actor TEXT NOT NULL, at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS paid_ins(id TEXT PRIMARY KEY, till_id TEXT NOT NULL, amount_paise INTEGER NOT NULL CHECK(amount_paise > 0),
          reason TEXT NOT NULL, actor TEXT NOT NULL, at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS outbox(id TEXT PRIMARY KEY, created_at TEXT NOT NULL, subject TEXT NOT NULL,
          body TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued', error TEXT);

CREATE TABLE IF NOT EXISTS timings(checkout_id TEXT PRIMARY KEY, elapsed_ms REAL NOT NULL, at TEXT NOT NULL);
