# Production-oriented test audit — 25 October 2026

Scope: the existing authenticated demo, its browser UI, Swagger contracts, local persistence and supplied Shopify/store/terminal mocks. This is not a production-readiness certificate.

## Executed evidence

- Initial endpoint/security run: **225 passed, 12 failed**. Eleven failures exposed application input handling defects; one exposed an omitted public `/` route exemption in the test manifest.
- Initial cart regression run: **2 passed, 5 failed**. It reproduced multi-frame/repeated-unit restrictions and the completed-cash-refund retry defect. The stale-quote test initially stopped at the cart-size restriction.
- After fixes: **244 endpoint/security/cart checks passed**.
- Additional auth/discount/outbox boundary run: **17 passed**.
- Real Chrome acceptance: **passed** for all five role logins/navigation and a cashier multi-frame sale, quantity removal, reload, invoice and source order. No JavaScript page errors. This found a missing quantity event-handler entry and misleading sale actions for non-selling roles; both were fixed and retested.
- Full-suite result: **313 passed in 164.61 seconds**, with one third-party Starlette/httpx test-client deprecation warning. No failed or skipped tests.
- JavaScript syntax and supplied seed validator: passed.
- Python undefined-name/error checks (`ruff --select F --ignore F401,F811`): passed. The ignored categories cover imports, including pytest fixture registration. The broader repository style scan is **not clean**; it reports import ordering, modernization and other existing lint findings, so this audit does not claim a clean full Ruff run.
- GitHub Actions now installs browser test dependencies and Chromium. The hosted workflow itself has not been run here.

## Defects corrected

| Finding | Correction | Regression evidence |
|---|---|---|
| Selecting a second frame silently replaced the first | Additive cart with visible quantity and +/− controls | `test_browser_roles.py`, `test_multi_item_sale_and_refund` |
| Wearer API allowed only one item or one frame/lens pair | Up to 30 unit selections per wearer; repeated IDs represent quantity | `test_cart_regressions.py` |
| A standalone wearer's item was assigned a pair reference | References only for matched frame/lens units within each wearer | `test_standalone_frames_are_not_offer_pairs` |
| Clinical frame compatibility was checked against lenses elsewhere in a family cart | Check compatibility only for paired frames in wearer carts | `test_family_sunglasses_and_prescription_pair` |
| Stock could change after quote preparation | Recheck aggregate unit demand before charging | `test_stale_quote_cannot_charge_after_stock_consumed` |
| Malformed/null/list request bodies caused middleware 500s | Validate JSON object shape before reading fields | `test_production_matrix.py` malformed-body cases |
| GET on the sale preparation route tried to parse JSON | Apply preparation parsing only to POST | `test_wrong_method_does_not_crash` |
| Invalid manager basis points caused type errors | Require bounded integer input | `test_discount_input_boundaries` |
| Boolean money values were accepted as paise | Strict integer money fields | `test_cash_amount_requires_bounded_integer_paise` |
| Retrying an already-recorded cash refund required an open drawer | Drawer precondition applies to a prepared refund only | `test_completed_cash_refund_repeat_after_close` |
| Finance/optometrist screens offered unusable sale actions | Show sale actions only to selling roles | `test_browser_roles.py` |

No endpoint was removed and no migration rewrites existing bills. Legacy flat cart requests keep their original contract. Wearer-based carts power the extended UI and Swagger quantity flow.

## Coverage and practical limits

The independent manifest has 31 concrete endpoint/action cases, each checked against all five roles, plus anonymous requests and CSRF checks for writes. A schema coverage test fails when a new business method/path lacks a policy case. Public entry points and login have separate tests. Some allowed-role matrix cases deliberately expect 404/409/422 to test authorization before business preconditions; they are not substitutes for successful transaction scenarios.

Existing scenario tests also cover prescriptions, tax/offer arithmetic, cancellations, family billing, remakes, refunds, till reconciliation, source reports and uncertain payment/order/refund outcomes. The new tests add multi-unit source effects, same-checkout concurrent completion, stale-stock rejection, session rotation/throttling and simulated SMTP outcomes.

The test plan is broader than current automation. **Still manual or incomplete:** exhaustive field/archived-product validation; every rapid-click/offline UI combination; competing independent carts and cross-process contention; all SMTP scheduler clock/restart boundaries; exact variance boundary combinations; load/soak and p95/p99 latency; process-kill/disk-full/backup restore; actual SMTP delivery; hosted CI; real Shopify/terminal contracts and inventory races with other channels. Local mutation serialization assumes the documented single application worker. A source inventory recheck is not a cross-system stock reservation.

Production requirements also need approved offer/prescription/invoice policies, deployment security review and operational sign-off. These limits remain explicit rather than being marked complete because a demo test passed.

See `PRODUCTION_TEST_PLAN.md` for the broader case catalogue and `CASHIER_ACCEPTANCE.md` for reproducible frontend/Swagger steps and commands.
