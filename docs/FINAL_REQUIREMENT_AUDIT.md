# Final submission audit — 26 October 2026

Authoritative scope for this pass: **Must + constraints + cash paid-ins**. The user explicitly chose to defer partial refunds and all Stretch options. This is a local mock exercise, not a live Shopify rollout. Changes are saved locally; publishing the latest work and recording the Loom are separate remaining submission actions.

## Seven Must flows

| Requirement | Implementation | Verification / result |
| --- | --- | --- |
| Customer + latest valid Rx | POST body lookup, canonical phone, source customer, source/local Rx overlay, latest-valid selector | Phone privacy/clinical tests; implemented |
| Frame/lens matrix + Rx validation | Variant type/index/coating, sphere/cylinder/ADD checks, wearer-specific line associations | Foundation, multi-pair and clinical cases; implemented |
| offers.json rules | Dates, eligibility, stackability and deterministic allocations | Stage 4 cases; implemented under documented policy |
| Inclusive GST by HSN | Effective-date config, integer paise, line taxable/CGST/SGST, exact totals | Tax and rounding cases; implemented |
| Terminal then source order + invoice | Persisted quote, charge, adapter-serialized paid order, clinical properties and store series | Stage 5 roundtrip/recovery; implemented |
| Full source refund | Original line tax, parent transaction, billing-store physical restock, no lens restock | Stage 6 refund/restock/repeat tests; implemented |
| Store/date source day-end | Gross, taxable, tax, discounts, refunds, method split, explicit capped-source failure | Stage 6 plus India midnight boundary; implemented |

The Must day-end reports refunds on the selected original-sale cohort, regardless of refund date, and labels that policy. The central analytics API also provides refund-event-date collection metrics. These are different questions, not silently interchangeable totals.

## Should / Stretch

| Item | Final state |
| --- | --- |
| Cash float, sales/refunds, paid-ins/paid-outs, count/variance | Implemented, including new paid-in API/UI with reason, actor and positive amount validation |
| Channel attribution/report by store | Implemented. Online pickup is a channel label, not full web-order fulfilment orchestration |
| Partial refund | Deliberately deferred with user approval |
| Printable invoice | HTML print support; production legal approval not claimed |
| Audit | Authenticated action logging and reasoned overrides/cash movements; not a formal tamper-proof external audit ledger |
| All three Stretch choices | Not implemented; at most one is allowed and none is required |

## Constraints and qualifications

One-command launch: **implemented and checked** with `python start.py`. A fresh isolated copy created a new virtual environment, installed dependencies, provisioned accounts, started app/mock and served health/OpenAPI. A repeat preserved generated account credentials. Python 3.13 is tested; app minimum is 3.10, distinct from mock minimum 3.8.

Provider-independent domain / explicit adapter: **implemented for sale, full-refund and Must-report workflows**. `BillingAdapter` projects customer/product/store/order/refund records into `app/domain/records.py` contracts and prescriptions into domain objects. Provider serialization and original snapshot decoding live behind the adapter. Services receive gateway and repository ports; invoice SQL now belongs to SQLiteStore. A replacement-provider test runs the same sale, refund and report services with different opaque write shapes and no Shopify record fields. The raw frontend bootstrap/operational inspection endpoints and legacy database names still describe the current integration; replacing the whole product also requires adapting those views and migrating source IDs. Do not confuse domain independence with an automatic whole-system migration.

Data-driven rates/offers: implemented. Money arithmetic: integer paise with decimal-string conversion; tax-rate fractions at the source boundary are rates, not money amounts. Safe reads: bounded GET retries for transport failures and 429/503. Private body lookup POSTs are not automatically retried by that GET-only policy. Writes are attempted once and persisted uncertainty blocks blind duplicates. There is no universal exactly-once guarantee or automatic recovery from every crash/terminal outcome.

Math tests: present for tax, discounts and refunds. No live Shopify account/payment is required for this exercise. Under-ten-second production performance, seven-store deployment, production invoices and actual SMTP delivery remain outside demonstrated readiness.

## New fixes in this pass

- Added standard-library one-command bootstrap, preserving existing accounts/data and honoring isolated runtime paths.
- Added durable `paid_ins`, API action, frontend movement selector, totals, positive-amount/reason checks and authorization matrix coverage.
- Corrected Must day-end filtering to convert source timestamps to the India business date; regression test covers UTC evening crossing local midnight.
- Moved source order/refund mapping and record projection behind BillingAdapter, introduced neutral record contracts and repository ports, preserved existing write snapshot format, and added a replacement-provider roundtrip test.
- Rewrote Part A as a scoped planning reply; preserved the previous version in `docs/STAKEHOLDER_REPLY_PRE_SUBMISSION.md`. Its historical before-code ordering cannot be recreated by editing a file now.
- Added offline per-requirement diagrams, class relationships, sequence/state diagrams and an explanation script.

## Evidence

Full run: **346 passed**, one third-party Starlette/httpx deprecation warning, 188.05 seconds. Command: `.venv\Scripts\python.exe -m pytest tests -q --tb=short`. Log: ignored `runtime/submission-suite.txt`.

Fresh-copy bootstrap and app/mock startup passed; log: ignored `runtime/bootstrap-check.txt`. No reviewer credentials were printed in chat. Original exercise mock files and the existing runtime database/snapshot were preserved. JavaScript syntax check passed.

## What remains before sending the submission

Review the integration migration boundaries above; review Part A for the under-two-page target in the chosen rendering; record and time the ≤8-minute Loom; verify reviewer access to the repository and video; commit/push the current changes when ready. Do not send a stale repository revision while showing the local latest demo.

The functional Must tier and its core provider boundary are verified. Production rollout and live-provider acceptance remain separate from exercise completion.
