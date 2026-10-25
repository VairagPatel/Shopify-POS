# Expanded demo validation — 25 October 2026

**Latest role/endpoint/cart audit: 313 tests passed in 164.61 seconds**, including real Chrome checks for all five roles. The cashier now supports multiple frames and quantities. See [current results](docs/TEST_RESULTS.md), [test plan](docs/PRODUCTION_TEST_PLAN.md) and [frontend/Swagger acceptance steps](docs/CASHIER_ACCEPTANCE.md). The 50-test evidence below describes the earlier baseline, not the current total.

The original baseline passed **35 tests**. The latest expanded regression run passed **50 tests in 47.19 seconds**, including the readability review, HTTP-client cleanup, drawer consistency fixes, prescription timestamp coverage and OpenAPI contract checks. The only warning is a third-party Starlette/httpx test-client deprecation.

Additional checks passed: fixture validation, JavaScript syntax, Python undefined/unused-name checks, and a source scan confirming **233 Python functions with preceding purpose comments (zero missing)**.

Swagger was independently exercised in a fresh Chrome browser: direct `/auth/login`, source customer/prescription read and CSRF-protected quote preparation all passed without opening the frontend. The test draft was cancelled and its invoice allocation retained. OpenAPI now includes ordered flow groups, request examples, nested wearer schemas, response contracts and source/write-effect descriptions. See `docs/API_WALKTHROUGH.md`.

Actual headless Chrome completed the working browser journey:

1. Credential login and authenticated overview.
2. Guided customer/cart with prescription and tags.
3. Server quote with offers, taxable value and included GST.
4. Confirmed UPI mock payment and Shopify order.
5. Invoice view with source references.
6. Full refund preview and confirmation.
7. Credit-note view.
8. Source-based report and stakeholder coverage view.

**No JavaScript page errors** were reported in that run. Screenshots are stored locally under `runtime/screenshots` and are not committed as runtime data. The overview and quote screenshots were visually inspected for layout.

The extended Chrome run also passed: **three wearers / six invoice lines, a zero-customer-charge lens-only remake, cash expense and above-₹200 variance outbox, clinical entry with 36 five-degree axis options, and cashier UI restrictions**. It reported no JavaScript page errors. Browser QA found and fixed an overlapping-action race while adding wearers; the UI now serializes pending edits.

The local runner was restarted using its existing database and mock snapshot. Earlier persisted transactions remained available in the app; neither the original API-only database nor the exercise source was erased.

The final main browser journey passed again after clinical entry and restart. This caught and fixed mixed naive/aware prescription timestamp ordering; regression tests now cover both source shapes and preparing a bill immediately after creating a prescription.

Python acceptance tests cover existing money/state behavior plus real authentication, CSRF/logout, roles/store restrictions, three distinct family prescriptions, cancellation register, manager approval evidence, cash sale/expense/refund/close, variance notification, digest deduplication, clinician axis validation, zero-charge remake without frame stock change, channels/refund totals, sunglasses, draft restore, IST boundary and mock snapshot serialization.

Validation limits: no real Shopify, live terminal, actual SMTP delivery, public deployment, Docker build, seven-store pilot or production-latency certification has been performed. No repository remote was supplied and no GitHub push was attempted. A passing demo suite does not establish production readiness.
