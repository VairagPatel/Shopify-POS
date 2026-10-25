# Eluno Store Studio

A working, authenticated store POS demo: family billing, clinical validation, offers, inclusive GST, payment/order orchestration, invoices, full refunds, lens remakes, cash reconciliation and store reports. The interface follows Eluno's orange (`#f88e2b`), black and white brand palette.

**This is an evaluation demo using the supplied Shopify, store-tool and terminal mocks. It does not connect to a real Shopify admin or move real money.** Production rollout and the remaining boundaries are explicit in the in-app **Demo & coverage** view.

Latest validation: **313 tests passed**, including five-role endpoint authorization and Chrome cashier multi-frame/quantity checks. See [test results and limits](docs/TEST_RESULTS.md), [production-oriented cases](docs/PRODUCTION_TEST_PLAN.md), and [cashier / Swagger acceptance walkthrough](docs/CASHIER_ACCEPTANCE.md).

For a visual, single-reading explanation, open **`/static/flow-guide.html`** on the running app, or open [the standalone HTML guide](app/static/flow-guide.html) directly. It includes architecture, the full source-to-sale-to-refund journey, a money example, role permissions, Swagger steps, all 46 planned scenarios, 31 endpoint actions and 75 automated test functions. Refresh the embedded inventories with `python scripts/build_guide_inventory.py` after changing tests or the plan.

## Start locally

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
| Offers | Configured stacking, priority and explicit rejection reasons | Business policy still needs approval |
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
