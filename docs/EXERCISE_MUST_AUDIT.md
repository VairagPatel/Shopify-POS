# Audit against the original exercise — 25 October 2026

## Verdict

All seven functional Must flows are implemented and covered by tests against the supplied mocks. That is different from complete submission readiness or full architectural/production compliance. The remaining items below should be disclosed and resolved where practical before submitting.

Reviewed the original `C:/Users/vaira/OneDrive/Desktop/eluno-pos-exercise/START_HERE.md` and `brief/CANDIDATE_BRIEF.md`, plus the user's newer assignment email. The local copies of the candidate brief, stakeholder thread, mock server, offers and tax configuration match the originals byte-for-byte. The email's **72 hours** supersedes the pack's older 48-hour text; the actual deadline needs the email receipt timestamp. No live Shopify account, deployed website or frontend is required by the exercise.

## Seven Must requirements

| Must | Implementation evidence | Automated evidence | Assessment |
|---|---|---|---|
| 1. Customer by phone + latest valid prescription | `MockHTTP.customer`, store-tool prescription read, local overlay and `latest_valid_prescription` | Source sale roundtrip; clinical boundary and mixed-timestamp tests | Implemented. Existing customers; no customer-creation feature required. |
| 2. Frame/lens cart, matrix and Rx validation | Source variant lens type/index/coating and limits; both-eye validation; progressive/bifocal ADD; actionable errors | `test_rx_valid_boundaries`, expired/outside-limits, ADD and variant-mismatch tests | Implemented. Additional wearer/quantity cart extends the baseline. |
| 3. offers.json dates/conditions/stackability | `evaluate_offers` reads supplied configuration; tests tags, dates, pair eligibility, exclusivity and allocations | Stage 4 offer tests; standalone-frame eligibility regression | Implemented under documented policy. Stakeholder request to always combine offers is a separate unresolved business conflict, not the exercise's configured-rule requirement. |
| 4. HSN inclusive GST and invoice components | Effective-date tax catalog, integer-paise line arithmetic, taxable/CGST/SGST fields and printable invoice | Tax reconciliation, discount/multiline tests; browser invoice journey | Implemented. Production tax/document sign-off is outside mock certification. |
| 5. Terminal charge then Shopify order, full payload and per-store invoice | Durable quote/state; terminal charge first; source order with tax/discount/payment transaction/Rx properties; store invoice allocation | Source roundtrip and inventory, invoice repeat/restart/store series, lost-response and reconciliation tests | Implemented. Unknown terminal outcomes deliberately stop for investigation. |
| 6. Full source refund, original tax, store frame restock, no lens restock | Read original source order; calculate/verify amount and tax; terminal refund then source refund linked to original transaction | Full refund amount/tax/stock; prepare has no financial effects; terminal/source uncertainty and reconciliation tests | Implemented. Partial refunds are optional Should scope and remain absent. |
| 7. Source-derived store/date day-end report | `DayEndService.report` exposes bill count, gross, taxable, tax, discounts, refunds and payment-method totals from source orders | `test_report_from_shopify_after_refund`; source channel/refund detail tests | Implemented with an explicit bounded-data policy: reject at 250-order cap. Legacy report attributes refunds to selected order-day cohort; newer collection reports use refund event dates and IST. |

Fresh targeted run: **35 passed in 9.62 seconds**, one third-party Starlette/httpx deprecation warning. Command: `python -m pytest tests/test_foundation.py tests/test_stage4.py tests/test_stage5.py tests/test_stage6.py tests/test_multi_pair.py -q`. Previous full app/role/browser audit: **313 passed in 164.61 seconds**. The full suite was not rerun for this document-only audit.

## Exercise constraints: important qualifications

- **Core/adapter boundary: partial.** Domain models, Rx validation, offer evaluation and tax math are Shopify-independent, and external calls pass through an explicit HTTP adapter. However, `SaleService` and `RefundService` still consume/build Shopify-shaped dictionaries. Do not claim that replacing Shopify requires only swapping the HTTP client. Revisit mapping external records/payloads at the adapter boundary if explaining the architecture.
- **One-command launch after setup: yes; pristine-clone setup still required.** README documents creating the environment, installing dependencies, provisioning accounts and then `python run_demo.py`. A clean-machine clone/install/browser run has not been performed in this audit. Python 3.13 is the tested application runtime; 3.8 is the mock's minimum, not a promise about the whole app.
- **Data-driven offers/tax and integer paise: implemented.** Decimal money conversion happens at the external boundary. Pricing logic does not require code changes for ordinary configuration edits.
- **429/503 and duplicate safety: guarded, not automatic recovery of every outcome.** Safe reads retry supported transient failures. Writes are sent once; durable pending/uncertain states prevent blind duplicate order/payment/refund submission. Recovery can require manual investigation. Single-worker mutation serialization is an explicit limit.
- **Tax/discount/refund tests: present and passed.** Live integrations, load tests and seven-store rollout are not required to claim the exercise's mock Must flow works.

## Parts A and C, and the handoff

| Deliverable | Current state | Remaining action |
|---|---|---|
| Part A stakeholder reply | `STAKEHOLDER_REPLY.md` covers conflicts, named decision owners, scope and dependencies | Review for concise under-two-page presentation. It currently reads partly as a retrospective demo update; the brief asks for a planning reply before code. Do not claim the required ordering has been verified from repository evidence. |
| Part B repository | Source, tests, fixture pack and README are present locally | Create/push the repository, verify a clean clone and permissions, and supply a real URL. No remote has been submitted. |
| Part C Loom ≤8 minutes | Script exists and has been aligned to the Must flow, decisions and AI disclosure | Record, time it and verify reviewer access. A script is not a recording. |
| Submission email | Draft only | Insert verified repo and Loom URLs. If private, invite `kaustabh.ghosh@longivitate.in`. Send within 72 hours of the actual email. |

The stakeholder reply carries as much weight as code. Spend remaining submission time on its clarity, a repeatable Must demonstration and an honest Loom, rather than expanding optional UI features. Deployment is optional for this assignment.
