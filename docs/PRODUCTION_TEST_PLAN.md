# Role, endpoint and transaction test plan

This is a production-oriented test plan for the supplied-mock application, not production certification. Tests run against isolated databases and mock processes; they must not charge real payments or change a live store. Expected outcomes below are written before implementation fixes.

## Release gates

1. Every registered business method/path has an explicit authorization case for cashier, manager, optometrist, finance and admin, plus anonymous and missing-CSRF checks.
2. Every financial flow verifies both local state and source order/payment/refund/inventory effects, including rejected and repeated requests.
3. Every discovered defect has a regression case. Failures are reported, not waived by reducing assertions.
4. Browser checks exercise actual controls for all five roles and the cashier's multi-item cart. API permissions are checked separately from hidden controls.
5. Passing local tests does not waive the separate integration, security, deployment, performance and recovery gates below.

## Permissions policy to verify

| Capability | Cashier | Manager | Optometrist | Finance | Admin |
|---|---|---|---|---|---|
| Sign in / out; read own session | Yes | Yes | Yes | Yes | Yes |
| Read store transactions/inventory/reports | Own store | Own store | Own store | All stores | All stores |
| Read shared customer/catalog directory | Yes | Yes | Yes | Yes | Yes |
| Prepare / complete / cancel sales; save cart | Yes | Yes | No | No | Yes |
| Manual discount | No | Own identity + reason, ≤10% | No | No | Valid staff + reason, ≤10% |
| Full refund / remake / uncertain-source reconciliation | No | Yes | No | No | Yes |
| Record prescription | No | No | Yes | No | Yes |
| Open drawer / record expenses | Yes | Yes | No | No | Yes |
| Close drawer | No | Yes | No | No | Yes |
| Cross-store audit / outbox / founder digest | No | No | No | Yes | Yes |

## Required test cases

| ID | Area | Case | Expected result |
|---|---|---|---|
| AUTH-01 | Login | Valid login for each role | Correct identity/store, HttpOnly session, no password hash returned |
| AUTH-02 | Login | Wrong/unknown credentials | Same 401 response; no session created |
| AUTH-03 | Session | Expired, tampered, revoked token | 401; no business effect |
| AUTH-04 | CSRF | Missing/wrong token on every write | 403; no business effect |
| AUTH-05 | Throttle | Repeated bad password and cooldown | Rate limited; succeeds after cooldown with correct password |
| RBAC-01 | All endpoints | Each role × every method/path | Allowed calls succeed or return the documented precondition error; denied calls return 403 |
| RBAC-02 | Ownership | Guess another store's checkout/refund/detail/cancel IDs | 403 regardless of knowing the identifier |
| RBAC-03 | Staff | Spoof manager/staff identity or store | 403; no quote/discount/payment |
| INPUT-01 | Bodies | Null, array, string, malformed JSON and wrong content type | Controlled 4xx, never an unhandled 500 |
| INPUT-02 | Fields | Booleans/fractions as money/IDs, negative/out-of-range values, whitespace reasons | 422 with no mutation |
| INPUT-03 | Clinical | Missing eye, malformed object, NaN/Infinity, invalid axes and date | 422; no clinical record |
| INPUT-04 | Catalog | Unknown/archived product; unknown store/customer | Controlled rejection before financial effects |
| CART-01 | Cashier | Add a second distinct frame for the same customer | Both remain in cart, quote and one source order |
| CART-02 | Quantity | Add two units of the same frame | Quantity visible; two unit lines or an equivalent quantity-bearing line; stock decreases by two |
| CART-03 | Quantity | Repeated SKU demand exceeds store stock, including across wearers | Rejected before payment |
| CART-04 | Pairing | Two frames + two compatible lenses for one wearer | Two complete pairs and correct offer eligibility |
| CART-05 | Mixed bill | One standalone sunglass wearer plus another prescription pair | Sunglass does not inherit another wearer's Rx restriction |
| CART-06 | Controls | Increment/decrement/remove and reload cart | Quantities/totals retained; no silent replacement or loss |
| CART-07 | Limits | Too many wearers/items; empty wearer | Actionable rejection; no partial payment/order. Unequal frame/lens counts use positional pairs with remaining units standalone. |
| SALE-01 | Quote | Prepare | Immutable stored quote, reserved invoice; zero terminal/order/stock writes |
| SALE-02 | Completion | Charge then source create | Exactly one charge and one paid order, exact paise/tax/discount totals |
| SALE-03 | Stale quote | Stock decreases after prepare | Recheck before charging; insufficient stock rejected with no charge |
| SALE-04 | Concurrency | Same checkout completed twice concurrently | One external charge/order and stable result |
| SALE-05 | Concurrency | Two prepared carts compete for last item | At most one completes; losing request does not charge |
| SALE-06 | Recovery | Lost charge response / lost order response / crash-pending state | Durable uncertain state; no blind repeat; source reconciliation only where possible |
| TAX-01 | Money | Boundary amounts/rates and discount caps | Taxable + CGST + SGST = discounted total in integer paise |
| TAX-02 | Offers | Dates, tags, full-pair count, manager limit/reason | Rule-specific eligibility; standalone frames do not count as complete pairs |
| INV-01 | Sequence | Concurrent reservations and cancellations | Unique monotonic store series; cancelled/reserved numbers retained |
| REF-01 | Full refund | Money, tax and location | Exact original amount/tax, source refund exists, frame restocked only at original store |
| REF-02 | Retry | Concurrent or repeated refund | One terminal refund and one source refund; no double restock |
| REF-03 | Cash retry | Repeat recorded cash refund after drawer closes | Returns recorded result without requiring another drawer or moving money |
| REF-04 | Recovery | Terminal/source refund response lost | Explicit uncertain state; no automatic repeated financial write |
| REMAKE-01 | Cost owner | Company, customer, external optometrist | Lens only; correct customer charge; original invoice, cost owner and approver retained |
| REMAKE-02 | Invalid | Frame replacement input, wrong wearer, refunded/unpaid original | Rejected; original stock/payment unchanged |
| CASH-01 | Reconciliation | Float + cash sales − refunds − expenses | Exact expected cash using source transaction IDs |
| CASH-02 | Lifecycle | Duplicate open, expense without open, double close | 409; no duplicate cash event |
| CASH-03 | Variance | ±₹200 and ±₹200.01 | Alert only strictly above absolute ₹200 |
| CASH-04 | Exceptions | Close while payment/refund unresolved | Block close pending investigation |
| REPORT-01 | Date | IST midnight and refund on later day | Sales on order day; refunds on refund event day in new report |
| REPORT-02 | Source | Source totals differ from local rows | Report reads source records; rejects incomplete capped source results |
| EMAIL-01 | Schedule | Before/after 10am IST, restart and duplicate ticks | One durable digest per day; configured delivery status accurate |
| EMAIL-02 | Delivery | SMTP success, failure/uncertainty, no configuration | Sent only after acceptance; uncertainty not blindly retried; no SMTP stays queued |
| WEB-01 | UI | All five role logins / nav / enabled actions | UI matches server permissions; no JavaScript errors |
| WEB-02 | UI | Cashier multiple frames/quantity/removal + review | Same items and exact total in browser, saved quote and source order |
| WEB-03 | UI | Rapid clicks, expired session, source timeout, reload | No silent cart change or duplicate submit; actionable state |
| API-01 | Swagger | Independent login/read/quote flow; schemas | All references resolve and actual examples run without frontend |

## Separate production-environment gates (not claimed by local tests)

- Real Shopify/terminal staging contract tests, credentials/scopes, pagination, inventory races with other channels, capture/refund status and idempotency guarantees.
- Sustained/concurrent load, p95/p99 end-to-end timing, seven-store device/network tests and dependency outages.
- Restart at each financial write boundary, coordinated backup/restore, disk-full/SQLite lock failures and monitored recovery.
- Independent security review, HTTPS/proxy/cookie deployment checks, account lifecycle/SSO, secret rotation and tenant/data access review.
- Actual SMTP acceptance/delivery and recipient approval; scheduler health and retry runbooks.
- Approved invoice/credit-note fields, clinical/business policies and operational sign-off.

Execution results and discovered defects will be recorded in `docs/TEST_RESULTS.md`. The automated endpoint manifest is kept alongside tests so a newly added endpoint cannot silently escape coverage.
