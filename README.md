# Eluno Store Studio

**Database access:** run `python scripts/view_data.py` and open http://127.0.0.1:8999 to inspect carts, all local tables and the source mock snapshot read-only. See [storage guide](docs/DATABASE_ACCESS.md).

**Final submission entry point:** [visual requirement-by-requirement walkthrough](app/static/submission-walkthrough.html), [class and sequence diagrams](docs/SYSTEM_DIAGRAMS.md), and [final requirement audit](docs/FINAL_REQUIREMENT_AUDIT.md). Latest full suite: **414 passed**; see [current website QC and manual review flow](docs/WEBSITE_QC_2026-10-26.md). Scope agreed: Must + constraints + cash paid-ins; partial refunds and Stretch are deferred. The core workflows now use neutral BillingAdapter records and repository ports; whole-system provider migration boundaries remain documented.

**Latest engineering review:** [phone privacy, API/schema traceability, SOLID, constants and adapters](docs/ENGINEERING_REVIEW.md). The shared-policy/port refactor passed **337 tests**. This earlier review is superseded by the final neutral-record boundary pass. [Detailed problem-led HLD](docs/PROBLEM_HLD.md) maps stakeholder needs to flows, ownership, recovery and rollout gates.

**Technical design:** [HLD](docs/HLD.md), [LLD](docs/LLD.md), and [styled offline design guide](app/static/design-guide.html). The guide includes architecture, data ownership, billing/refund state machines, module responsibilities, database declarations and the implemented API inventory. Regenerate with `python scripts/build_design_docs.py`.

**Customer identity and API schemas:** [open the detailed guide](app/static/api-schema-guide.html) or `/static/api-schema-guide.html` on the app. Customer lookup is now **POST `/api/customers` with a JSON phone body**, not a GET query. Indian mobile formats normalize to `+91` plus ten digits. The standard runner enables body-based lookup extensions in the durable mock wrapper; the supplied original mock is unchanged. `ELUNO_PRIVATE_LOOKUP=0` explicitly enables legacy upstream GET contracts and does not meet the no-phone-in-URL objective. See [change notes](docs/PHONE_LOOKUP_CHANGE.md) and [OpenAPI export](docs/openapi-contract.json). Customer registration is proposed, not implemented.

**Founder briefing:** open [the standalone HTML document](app/static/founder-brief.html), or `/static/founder-brief.html` on the running app. It explains the problem, retrospective ticket breakdown, implementation steps, source data, full billing/refund flow, decisions, test evidence and proposed rollout in simple English. It includes search, diagrams and print styling.

A working, authenticated store POS demo: family billing, clinical validation, offers, inclusive GST, payment/order orchestration, invoices, full refunds, lens remakes, cash reconciliation and store reports. The interface follows Eluno's orange (`#f88e2b`), black and white brand palette.

**This is an evaluation demo using the supplied Shopify, store-tool and terminal mocks. It does not connect to a real Shopify admin or move real money.** Production rollout and the remaining boundaries are explicit in the in-app **Demo & coverage** view.

Earlier architecture validation: **337 tests passed**, including phone normalization/privacy, five-role endpoint authorization and Chrome cashier multi-frame/quantity checks. The browser journey also passed separately against the private lookup wrapper. See [latest lookup verification](docs/PHONE_LOOKUP_CHANGE.md), [earlier test results and limits](docs/TEST_RESULTS.md), [production-oriented cases](docs/PRODUCTION_TEST_PLAN.md), and [cashier / Swagger acceptance walkthrough](docs/CASHIER_ACCEPTANCE.md).

For a visual, single-reading explanation, open **`/static/flow-guide.html`** on the running app, or open [the standalone HTML guide](app/static/flow-guide.html) directly. It includes architecture, the full source-to-sale-to-refund journey, a money example, role permissions, Swagger steps and generated scenario, endpoint and test inventories. Refresh the embedded inventories with `python scripts/build_guide_inventory.py` after changing tests or the plan.

## Start locally

From a fresh clone, use one command (Python 3.10+; 3.13 tested):

```powershell
python start.py
```

This creates `.venv` if needed, installs declared dependencies (internet required on first setup), provisions missing local demo accounts without replacing existing ones, and starts the app and durable mock. Read generated credentials locally in `runtime/demo-accounts.txt`. Optional ports: `python start.py --port 8001 --mock-port 8788`. An isolated fresh-venv copy was verified through setup, startup, health and the POST-only customer contract. The manual setup below remains available.

Python 3.13 is the tested runtime. No Node build or external database is required.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/setup_demo.py
.\.venv\Scripts\python.exe run_demo.py
```

On macOS/Linux, use `.venv/bin/python` instead of `.venv\Scripts\python.exe`.

Open **http://127.0.0.1:8000**. Generated passwords are in **`runtime/demo-accounts.txt`**, which is ignored by Git. The setup command never overwrites existing accounts. The default accounts are `admin`, `manager`, `cashier`, `finance` and `optometrist`; the three store roles belong to HSR.

If the earlier API-only demo still occupies port 8000:

```powershell
.\.venv\Scripts\python.exe run_demo.py --port 8001 --mock-port 8788
```

This serves the new UI at **http://127.0.0.1:8001**. The old session database is not deleted or overwritten.

## Present the demo

**Two presentation modes:** use the frontend at `/` or the independent Swagger flow at `/docs` on the same app/port. Both use the same backend and records. [The API/source-data walkthrough](docs/API_WALKTHROUGH.md) explains Shopify reads, local calculations, payment, order/refund write-back and report read-back, with a sequence diagram and exact requests. Swagger supports login directly and supplies the session CSRF token automatically.

1. Sign in as `admin` for the walkthrough, then use `cashier` to demonstrate enforced restrictions.
2. Select **Start guided sale**. It loads Karthik Reddy, a frame and a compatible progressive lens.
3. Show priority/campaign flags, the prescription, available stock and the wearer-specific cart.
4. Select **Review offers & GST**. Explain the calculated discount, taxable amount and included CGST/SGST.
5. Confirm payment. Show the saved invoice, payment reference, Shopify source order and line-level tax.
6. Prepare and confirm a full refund. Show the credit note, original invoice reference and updated report.
7. Demonstrate family billing, a lens-only remake, cash close and report outbox using [the full presentation script](docs/DEMO_SCRIPT.md).
8. Open **Demo & coverage** for requirement-by-requirement evidence and honest boundaries.

The fixture dates and offers were supplied for the 2026 exercise. Use a fresh clinician-entered prescription when a fixture expires. Expired offers should stop applying; the app does not silently freeze the business date.

## Features and boundaries

| Workflow | Implemented demo behavior | Boundary |
|---|---|---|
| Login | PBKDF2 passwords, HttpOnly sessions, CSRF, role/store enforcement, throttling | CLI account management; no production SSO |
| Family sale | Up to ten wearers, 30 units each, independent prescriptions, multiple frames/pairs and quantity controls | Existing synthetic customers; frame/lens units pair in selection order within each wearer |
| Offers | Only one explicitly selected eligible coupon applies; manager discount requires both percentage and reason | Coupon stacking is disabled per cashier workflow direction |
| Manager discount | At most 10%, authorized staff and reason recorded on order | Seeded offer eligibility rules still apply |
| Clinical | Rx range/ADD validation; optometrist-only entry; 5-degree manual axis steps | Issued external axes remain unchanged |
| Invoice | Inclusive MRP, HSN/date tax, store sequence, preserved cancellations, print | Demo document; requires finance sign-off for actual issuance |
| Refund | Full payment/tax reversal and printable linked credit note | No partial refunds; ambiguous terminal writes require investigation |
| Inventory | Source-store physical stock return; no custom-lens restock | No real reservation/stock concurrency integration |
| Remake | Original invoice link, lens only, cost owner and lab cost recorded | External cost recovery is not automatically collected |
| Cash | Float, sales, refunds, reasoned expenses, count, variance | Single-worker demo; no external payment settlement feed |
| Reports | IST store/day/channel, refund-event-date collection totals | Mock result cap below 250 orders; no live pagination |
| Email | Durable outbox, 10am IST founder digest, above-₹200 variance alert | SMTP required for delivery; app must run |
| Recovery | Local/server cart, durable state, no blind repeat writes, mock snapshots | No offline charging; unknown terminal outcomes remain manual |

Beverage-question removal and camera repair are separate tracked workstreams: their systems were not supplied. “All seven stores by 15 November” and “under 10 seconds in production” are rollout/performance acceptance gates, not claims a local mock can prove.

## Architecture

```text
Browser UI / Swagger
    → Authentication + CSRF + role/store guard
    → Sale / refund / clinical / cash / reporting services
    → SQLite (quotes, state, invoice register, identity, audit, outbox)
    → HTTP adapter → supplied Shopify / SMT / terminal mock
                       + additive durable-snapshot wrapper
```

- `app/static/`: buildless HTML/CSS/JavaScript UI; same origin as API.
- `app/main.py`: original route contracts, preserved with authentication now required.
- `app/web.py`: UI APIs and the security boundary for old and new endpoints.
- `app/security.py`: account provisioning, password/session handling and permissions.
- `app/operations.py`: clinical overlay, cash sessions, source-based reporting and outbox generation.
- `app/services/`: pricing, prescription validation and guarded financial state machines.
- `app/persistence/sqlite.py`: additive durable state and serialized invoice allocation.
- `scripts/persistent_mock.py`: persistence wrapper; the supplied mock source remains unchanged.
- `app/scheduler.py`: idempotent digest scheduling and optional SMTP delivery.

The app serializes authenticated mutations within its **single worker**. SQLite compare-and-set transitions protect financial state; uncertain payment/order/refund writes are not retried automatically. Do not deploy multiple app replicas against this demo.

## Verify

The complete suite includes Playwright browser tests. Install `requirements-dev.txt` and have Chrome available, or follow the Chromium setup in `docs/CASHIER_ACCEPTANCE.md`. For backend-only checks without browser dependencies, run `python -m pytest tests --ignore=tests/test_browser_roles.py -q`.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe exercise-pack/starter-kit/validate_seed.py
node --check app/static/app.js
```

Optional browser QA and formatting tools:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts/browser_smoke.py
```

The browser smoke script expects Chrome, the app at port 8001 and the local generated admin credentials. It creates a **synthetic sale and refund** and saves screenshots in `runtime/screenshots`. The GitHub Actions workflow runs the Python acceptance suite, fixture validation and JavaScript syntax check.

See [validation evidence](FINAL_AUDIT.md), [stakeholder reply](STAKEHOLDER_REPLY.md), [deployment guide](docs/DEPLOYMENT.md), [acceptance checklist](docs/ACCEPTANCE.md), and [code review notes](docs/CODE_REVIEW.md).

## Data and deployment

Keep `runtime/eluno.sqlite3` **and** `runtime/mock-state.json` together. Both are runtime data; neither belongs on GitHub. Do not reset one side independently while retaining the other. Existing original session databases are preserved separately; they cannot be safely reconciled against a freshly reset original in-memory mock.

For a private HTTPS deployment, use the included Dockerfile with a persistent `/data` volume and a long `ELUNO_ADMIN_PASSWORD` secret. See the deployment guide before publishing. No remote deployment or GitHub push is performed by the local setup.

Historical API-only notes are retained under `docs/ORIGINAL_*` and in `DECISIONS.md`; this README and the current acceptance map supersede their scope statements.

## Inspecting saved carts and completed bills

The current sale screen has separate **Frames**, **Lenses**, and **Sunglasses** tabs.
In Lenses, select **type → index → coating**, then **Add lens to cart**. Choose a frame already in the cart to attach exactly one lens pair, or choose **Lenses only · customer's own frame**. Frame-only purchases are explicit standalone lines. Axis entry accepts **0°, 5°, …, 180°**; a missing axis remains invalid.

Coupons start blank. Choose an eligible coupon and press **Apply coupon & review bill**. A manager discount requires both a percentage and reason; it replaces the coupon. Payment creates the source order and issues the invoice only after the terminal result is recorded.

Daily reports have **Download day-end CSV** and **Download daily summary CSV** buttons. The day-end export includes refunds on orders from the selected date, while the daily summary uses the actual refund event date and matches the website summary. Both include source-derived gross, taxable value, GST, discounts, refunds and payment-method totals.

The app stores its SQLite database at `runtime/eluno.sqlite3` (or the path in `ELUNO_DB_PATH`). Cart changes append a full payload snapshot to `cart_snapshots`; the latest editable cart is in `drafts`. Each new sale has its own draft ID, actor, staff ID and timestamps; the Bills & returns page lists every saved version. On migration, any existing draft without a matching snapshot is copied once into that history table. `cart_tracking` joins each snapshot to checkout status, invoice number and Shopify order ID. Checkout duration is stored on the checkout row. Refund progress is saved in `refund_attempts`; the Bills & returns detail view compares it with the source Shopify order refund. Locally entered Rx authorship is stored in `prescriptions`.

Open the existing file from PowerShell only after confirming it exists:

```powershell
if (Test-Path .\runtime\eluno.sqlite3) { sqlite3 .\runtime\eluno.sqlite3 } else { Write-Error "Existing app database not found; start the app first." }
```

Then run these SQL queries:

```sql
.tables
SELECT saved_at, username, store_code, saved_status, checkout_status,
       checkout_id, invoice_no, shopify_order_id, payload
FROM cart_tracking
ORDER BY saved_at DESC;

SELECT checkout_id, status, invoice_no, shopify_order_id, created_at, updated_at,
       checkout_elapsed_ms, timing_recorded_at
FROM checkouts
ORDER BY created_at DESC;

SELECT checkout_id, quote_json
FROM checkout_quotes
ORDER BY checkout_id;

SELECT refund_id, checkout_id, shopify_order_id, amount_paise, status,
       terminal_refund_id, shopify_refund_id, created_at, updated_at
FROM refund_attempts
ORDER BY created_at DESC;

SELECT rx_id, created_by, created_by_staff_id, store_code, created_at, payload
FROM prescriptions
ORDER BY created_at DESC;

SELECT invoice_no, checkout_id, store_code, shopify_order_id, total_paise,
       payment_method, payment_charge_id, issued_at
FROM invoices
ORDER BY issued_at DESC;

SELECT * FROM invoice_lines ORDER BY invoice_no, line_number;
SELECT refund_id, status, shopify_refund_id, synced_at FROM refund_attempts;
SELECT * FROM refund_events ORDER BY event_id DESC;
SELECT * FROM order_submissions ORDER BY created_at DESC;
```

A local draft has `saved_status = 'draft'` and no checkout link. A quoted snapshot has a `checkout_id`; `checkout_status` then advances through payment/order states and ends at `order_recorded` for a successful sale. `payload` contains wearer phone numbers and selected frame/lens variant IDs, so treat the file as sensitive demo data.
