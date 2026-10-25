# DECISIONS.md — Eluno POS Engineering Decision Log

> Historical API-first planning log. The working UI and expanded scope now supersede the initial status below. See the current [README](README.md), [code review notes](docs/CODE_REVIEW.md), [acceptance checklist](docs/ACCEPTANCE.md) and [validation results](FINAL_AUDIT.md).

**Status:** PLANNING LOCKED on 24 Oct 2026. No application code has been implemented. Decisions are approved for the exercise plan, but technical assertions must be validated during implementation.

**User-selected constraints:** FastAPI + SQLite; staged workflow with review gates; no frontend until Must is working and tested; plan against 48 hours from email; Must only.

**Deadline caveat:** the covering email says 72 hours while both pack documents say 48. Use the shorter window to plan and request written confirmation. The actual deadline clock starts from the email timestamp, which is not provided here.

**Decision states:** ACCEPTED (planning), VERIFYING, IMPLEMENTED, TESTED, REVISED, DEFERRED. Never label an unbuilt feature tested.

## Format for every future decision
- **ID / Date / Status** — Proposed | Confirmed | Revised | Rejected
- **Question / context** — which stakeholder or constraint created it?
- **Options considered** — at least two and real trade-offs
- **Decision and rationale** — why it serves v1
- **Consequences and risks** — which behavior can still fail?
- **Validation evidence** — test name / mock request / example once implemented
- **Founder one-liner** — plain-English explanation

## D-001 — Build Must before Should (ACCEPTED — planning)
- **Options:** polished frontend + multiple features, or narrow verified checkout.
- **Decision:** Must checkout/refund/day-end first. CLI/API; no browser UI.
- **Why:** brief explicitly scores completeness and accepts stopping cleanly; UI is not scored.
- **Risk:** no visual staff-facing experience. **Proof:** integration demo and tests.
- **Founder one-liner:** 'I optimized for a billing workflow that can be trusted before polishing the interface.'

## D-002 — Domain separated from Shopify adapter (ACCEPTED — planning)
- **Options:** Shopify-shaped objects throughout, or internal clean models with boundary mapping.
- **Decision:** separate cart, Rx, discounts, tax and invoice from Shopify payloads through interfaces.
- **Why:** explicit assignment constraint and platform portability.
- **Risk:** more mapping code. **Proof:** core unit tests with no mock server.
- **Founder one-liner:** 'If we move platforms in 2027, business rules survive.'

## D-003 — Integer paise and effective-date HSN tax data (ACCEPTED — planning)
- **Decision:** all arithmetic as integers; effective tax rates read from JSON; rounding per line and CGST/SGST reconciliation.
- **Why:** prevents floating-point errors and enables tax changes without deployment.
- **Risk:** order-level GST totals must equal sum of line items. **Proof:** seeded invoice fixtures.
- **Founder one-liner:** 'Tax and discount totals match down to the last paisa.'

## D-004 — Offer rules deterministic, not LLM-driven (ACCEPTED — planning)
- **Decision:** evaluate eligibility/dates/stackable/priority deterministically. Record candidate decisions and show chosen combination; define tie-break by maximum lawful customer benefit subject to rule constraints (pending stakeholder signoff).
- **Why:** repeatable and auditable. **Risk:** stacking semantics and eligibility need approval.
- **Founder one-liner:** 'Staff get the same valid offer every time, with a clear reason.'

## D-005 — Stable checkout identity and persisted state (ACCEPTED — planning)
- **Decision:** save stable checkout_id and order_ref with state transitions before charge; never blind-retry non-idempotent Shopify order POST; reconcile by external marker and order listing.
- **Why:** real payment/order uncertainty on bad Wi-Fi.
- **Risk:** mock's terminal does NOT implement claimed charge idempotency; cannot guarantee safe automatic retry after unknown 503. Need manual/pending recovery or a documented adapter/mock correction.
- **Founder one-liner:** 'A slow network should not become two orders or two charges.'

## D-006 — Per-store invoice series with cancelled/void allocations (ACCEPTED — planning)
- **Decision:** store-specific transactional counter; allocate unique number at controlled checkout transition; mark failed/cancelled allocation as void, never reuse silently.
- **Why:** Shopify order_number is global; finance wants traceability and gapless accounted sequence.
- **Risk:** 'no gaps' requires agreement that voided numbers appear in register and are not hidden; request Vikram approval.
- **Founder one-liner:** 'Each store has a traceable invoice series—even failed bills are accounted for.'

## D-007 — Shopify is authoritative for day-end (ACCEPTED — planning)
- **Decision:** report from Shopify orders/refunds, plus separate local reconciliation exceptions and pending charges.
- **Why:** finance reconciles Shopify; locally computed success metrics alone could mislead.
- **Risk:** date/time, pagination, refund-date attribution and sample orders might skew results; explicitly define reporting period.
- **Founder one-liner:** 'The report uses the same ledger finance trusts, and separately flags exceptions.'

## D-008 — Protect clinical / stock constraints (ACCEPTED — planning)
- **Decision:** latest valid RX from SMT, both-eye limits and ADD validation; frame decrement only on order; frame restock only at originating store; lens never restocked.
- **Why:** fewer remakes and correct inventory.
- **Risk:** axis policy vs external prescriptions, remake cost ownership need clinical decision.
- **Founder one-liner:** 'Billing cannot quietly send an invalid lens order to the lab.'

## D-009 — Role-based manager adjustments and audit (DEFERRED)
- **Decision:** avoid manual override button without approver identity and reason code; store audit event when implemented.
- **Why:** direct conflict with finance compliance requirements.
- **Risk:** store flexibility reduced until approved workflow exists.
- **Founder one-liner:** 'Speed cannot remove discount accountability.'

## D-010 — Deployment pathway (ACCEPTED — planning)
- **Decision:** deliver one-command local prototype; real rollout requires pilot, Shopify permissions and reconciliation tests, terminal integrations, staff training and measured latency.
- **Why:** mock tests aren't a 7-store production rollout.
- **Risk:** operational dependencies outside candidate exercise.
- **Founder one-liner:** 'The assignment is proof of a workflow, not a claim that seven stores are production-ready.'

## Decision ledger to update DURING implementation
| ID | Decision made | Reason | Code location | Test/evidence | Status |
|---|---|---|---|---|---|
| TBD | | | | | |


## D-011 — FastAPI with SQLite (ACCEPTED — planning)
- **Context:** evaluator accepts CLI or HTTP API, and no UI is scored.
- **Alternatives:** Python CLI with sqlite3; FastAPI with SQLite; Node/TypeScript.
- **Decision:** FastAPI HTTP API as the thin interface, SQLite for durable checkout/invoice state, pytest for tests; prefer simple sqlite3 to avoid unnecessary infrastructure.
- **Reason:** maps to user's current backend skills; easy to demonstrate through Swagger/curl without a frontend.
- **Trade-off:** more setup than CLI; for a real seven-store rollout SQLite would need a stronger multi-node transactional data store.
- **Validation:** one-command start, HTTP health check, SQLite state survives app restart.
- **Founder explanation:** 'I chose the smallest web API that makes the flow easy to test while preserving transaction state.'

## D-012 — Staged implementation with review gates (ACCEPTED — planning)
- **Decision:** finish and review Part A before writing application code; pause after mock baseline, domain/pricing, sale, refund/report, and reliability; update this log with actual test evidence at each gate.
- **Reason:** avoids AI-generated uncontrolled scope drift and ensures the candidate can explain every decision.
- **Validation:** checkpoints in EXECUTION_ROADMAP.md.
- **Founder explanation:** 'I tested the riskier assumptions early instead of polishing an unproven implementation.'

## D-013 — No frontend unless Must + tests done (ACCEPTED — planning)
- **Decision:** FastAPI OpenAPI and curl are enough for the exercise. Frontend is explicitly deferred, even if unused time remains, until Must is complete and tested and review approves it.
- **Founder explanation:** 'The exercise scores billing correctness, not screens.'

## D-014 — 48-hour conservative submission window (ACCEPTED — planning; awaiting external confirmation)
- **Evidence:** START_HERE and brief say 48 hours; covering message says 72.
- **Decision:** schedule as if 48 hours applies; ask recruiter to clarify as early as possible. Do not claim they confirmed it.
- **Founder explanation:** 'I took the earlier documented deadline rather than risk a late delivery.'

## D-015 — Refund sequencing and unknown outcomes (TO VERIFY)
- **Options:** terminal-first, Shopify-first, reconciled state machine.
- **Decision target:** model terminal and Shopify refund recording as separate operations, with an explicit pending exception state if one succeeds and the other is uncertain. Confirm mock request shapes before locking ordering.
- **Risk:** no atomic transaction across payment gateway and Shopify. No unsupported guarantee of exactly-once side effects.
- **Validation:** test terminal failure/refund failure and inspect Shopify's captured amount/parent transaction link.

## Engineering update protocol
Every implementation gate must add a dated entry: what changed, why this approach beat alternatives, precise code path, command/test output, known limits, and what was not built. Do not rewrite historical decisions to hide revisions.

---
## Stage 2 verification — 24 Oct 2026 (MOCK VALIDATED; application not started)

### D-016 — Baseline mock contracts (VERIFIED)
- **Observation:** `python3 validate_seed.py` passed: 8 locations, 28 staff, 30 customers, 47 prescriptions, 92 variants, 8 offers, 320 inventory rows, 12 sample orders, 2 till sessions.
- **Evidence:** `bash examples.sh` against `--no-flake` exited 0; charge ₹19,072.15 → paid order #1013; HSR stock 2→1; full refund restored stock 1→2; order marked refunded.
- **Decision:** Treat examples as interoperability fixtures, not POS implementation; only move to coding after review.
- **Founder one-liner:** 'I first proved the external contracts worked before building logic on top.'

### D-017 — Terminal idempotency discrepancy (VERIFIED, BLOCKING AUTO-RETRY)
- **Documented expectation:** same `order_ref` safely retryable.
- **Actual server behavior:** charge records stored by generated `charge_id`, without `order_ref` dedupe. Same `order_ref` returned `201 chg_99000001`, then `503`, then `201 chg_99000002` in a flaky-mode probe.
- **Decision:** No blind automatic retry after uncertain terminal charge outcome. Persist state and use reconciliation/manual-review path; optionally ask exercise team about intended semantics. Do not silently patch supplied mock.
- **Trade-off:** some bills require staff assistance rather than automatic recovery, but double charge risk is unacceptable.
- **Founder one-liner:** 'The mock's written guarantee and code disagree; I chose not to risk charging a customer twice.'

### D-018 — 429 and Shopify create uncertainty (VERIFIED / DESIGN REQUIRED)
- **Evidence:** 35 invalid Shopify writes in flaky mode produced 8 HTTP 429 with `Retry-After: 1.0`; other 27 were validly rejected with 422. The mock's `POST /orders.json` has no idempotency key or uniqueness enforcement.
- **Decision:** bound retries for explicit pre-operation rate limits; unique POS marker and read-first reconciliation for uncertain order creation, with pending exception if inconclusive.
- **Limit:** scanning orders is not atomic and cannot guarantee exactly-once writes if requests race; document as a real-system integration requirement.
- **Founder one-liner:** 'We can recover from throttling, but we must not manufacture duplicate orders after ambiguous timeouts.'

### D-019 — Billing exercise scope from runnable baseline (VERIFIED)
- **Decision:** keep source mock unchanged, use its documented Shopify/SMT/terminal boundaries; no UI or application code until Stage 3 approval.
- **Evidence and detailed reproducibility:** `STAGE2_MOCK_VALIDATION.md` generated on 24 Oct 2026.
- **Founder one-liner:** 'I used the provided contract as a test fixture and separated mock quirks from production guarantees.'

---
## Stage 3 implementation — 24 Oct 2026 (FOUNDATION IMPLEMENTED, REVIEW REQUIRED)

### D-020 — Core models are independent of Shopify (IMPLEMENTED)
- **Why:** Shopify may be replaced; prescriptions, cart lines, store invoices and checkout states belong to Eluno's business domain.
- **Implemented:** `app/domain/models.py` defines immutable Customer, Prescription/EyePower, LensConfiguration, CartLine/Cart, Offer, Invoice, Refund, TillSession and CheckoutStatus. Paise is an integer alias; no financial computation is included at this gate.
- **Alternative:** directly use Shopify REST JSON in service functions. Rejected to avoid coupling.
- **Evidence:** `tests/test_foundation.py::test_domain_guardrails` validates local quantity/money invariants.
- **Caveat:** modelling alone is not lens validation, offer evaluation or full domain behavior.
- **Founder explanation:** 'If the commerce platform changes, the checkout vocabulary remains ours.'

### D-021 — Explicit external gateway ports without premature integration (IMPLEMENTED)
- **Why:** keep commerce, clinical/store, and terminal concerns separate; don't entangle checkout domain with API schemas.
- **Implemented:** `app/gateways/contracts.py` defines `CommerceGateway`, `StoreToolGateway`, and `TerminalGateway` Protocols.
- **Alternative:** build HTTP calls directly into FastAPI endpoints. Rejected because they are hard to swap and test.
- **Evidence:** import-time contract declarations; adapters intentionally not implemented in Stage 3.
- **Risk:** return types and gateway granularity will be refined against the mock during implementation.
- **Founder explanation:** 'The boundaries are explicit before any integration code is written.'

### D-022 — SQLite compare-and-set checkout state (IMPLEMENTED)
- **Why:** uncertain terminal/order outcomes require durable recording; prevent overlapping workers from silently overwriting status.
- **Implemented:** `app/persistence/sqlite.py` (`SQLiteStore`, `change_status`, `record_external_ref`); persisted checkout states and unique reference constraints.
- **Evidence:** `tests/test_foundation.py::test_checkout_is_durable`, `test_checkout_compare_and_set`, `test_ref_unique_and_immutable`.
- **Trade-off:** the current state-change method prevents stale writes but does not yet enforce an allowed transition graph or guarantee exactly-once external operations.
- **Founder explanation:** 'Uncertain payment outcomes survive restarts, and conflicting updates are rejected.'

### D-023 — Transactional invoice allocation with auditable reservations (IMPLEMENTED)
- **Why:** Shopify order numbers are global; Eluno needs distinct series per store without silent reuse.
- **Implemented:** `app/persistence/sqlite.py::reserve_invoice` uses `BEGIN IMMEDIATE`, store-specific `next_number`, unique checkout allocation, and immutable prefix. A retry for the same checkout returns its existing invoice. An unused invoice remains an allocated record rather than silently disappearing.
- **Evidence:** `tests/test_foundation.py::test_invoice_per_store_repeat_and_restart` passed.
- **Trade-off:** allocation reservation records are continuous, but not every reserved number necessarily becomes a final tax invoice. Voided-number policy needs Finance sign-off. Sequence formatting assumes a suitable prefix and starts from 1 for each new store.
- **Founder explanation:** 'We can explain every number, including one reserved for a sale that later failed.'

### D-024 — Read-only FastAPI review surface (IMPLEMENTED)
- **Why:** Stage 3 should be runnable and inspectable without accidentally initiating charges or creating Shopify orders.
- **Implemented:** `app/main.py` offers `GET /health` and `GET /checkouts/{checkout_id}` only; no public mutate endpoints.
- **Evidence:** `tests/test_foundation.py::test_health` passed; `GET /health` returns `checkout_enabled: false`.
- **Risk:** there is no authorization scheme because this stage exposes only local development inspection; must add one before production or enabling sensitive endpoints.
- **Founder explanation:** 'I verified the foundation before exposing workflows that move money.'

### D-025 — Stage 3 test evidence and intentionally unbuilt items (VERIFIED)
- **Run:** `cd /mnt/data/eluno_stage3/eluno-pos && python -m pytest -q`
- **Result:** **6 passed** (24 Oct 2026). App and tests run in the current environment; dependencies documented in `requirements.txt`.
- **Not built:** real HTTP gateway implementations, cart pricing, tax calculations, offers, prescription validation, charge, order creation, refunds, reports, or frontend.
- **Upcoming risk:** Mock's terminal charge idempotency mismatch remains unresolved (D-017). Never silently retry an ambiguous terminal call.
- **Review gate:** stop here until explicit Stage 3 approval.

---
## Stage 4 implementation — 24 Oct 2026 (PRICING CORE IMPLEMENTED; awaiting review)

### D-026 — Prescription checks are explicit and staff-actionable (TESTED)
- **Implemented:** `app/services/prescriptions.py::validate_lens` validates expiry, variant configuration consistency, both eyes' sphere/cylinder against variant `rx_limits`, axis when cylinder is nonzero, and required ADD for progressive/bifocal lenses.
- **Why:** optical safety rules must block invalid configurations before an external sale; an LLM must not approve prescription limits.
- **Alternative:** rely on Shopify accepting a variant (rejected; it does not enforce clinical suitability).
- **Evidence:** `tests/test_stage4.py::test_rx_valid_boundaries`, `test_rx_rejects_expired_and_outside_limits`, `test_rx_requires_add_for_progressive`, `test_rx_rejects_variant_mismatch`, `test_catalog_real_seed_lens_validation`.
- **Caveat:** The exercise only specifies sphere/cylinder and ADD validity; no PD fitting or full clinical sign-off workflow is included. `latest_valid_prescription` works on already normalized prescriptions; API parsing is future work.
- **Founder explanation:** 'The billing app does not let a cashier sell a lens outside the patient's prescription and catalog limits.'

### D-027 — Offer rules from JSON, deterministic decisions (TESTED; policy to confirm)
- **Implemented:** `app/services/offers.py::evaluate_offers` consumes `offers.json`, checks active dates, tags, lens type/index/coating, `pair_ref`, second pair, and manager role/reason/maximum discount. Every offer gets a reason and line-level allocation in paise. No executable rules or AI-generated discount values.
- **Policy assumption:** Compare (a) the priority-ordered stackable offers, individually capped to remaining line values, against (b) the first priority-ranked eligible nonstackable offer. Select the higher saving. Offer `priority` is ascending (smaller number wins for exclusive offers). Stable tie-break favors the stackable set. **Eluno has not signed off on this interpretation.**
- **Additional assumption:** `SECONDPAIR50` discounts the cheapest eligible lens once, even if more than two pairs. Flat cart/pair discounts split proportionally across eligible lines with exact-paisa remainder allocation. `MANAGER_OVERRIDE` requires explicit role, reason, and user-specified override bps (never auto-assumed).
- **Evidence:** `tests/test_stage4.py::test_seed_festive_exclusive`, `test_stack_priority_bundle_and_tag`, `test_second_pair_eligible_and_single_pair_rejected`, `test_expired_offer_and_manager_requires_approval`, `test_discount_never_exceeds_gross_and_reconciles`.
- **Known caveat:** Offer conflict, per-pair discount multiplicity, discount tax-allocation policy and manager identity verification require stakeholder confirmation. This is a pure rules engine, **not** proof that API staff identity is authenticated.
- **Founder explanation:** 'Offers are data-driven, repeatable, and explain why they applied or were rejected; finance can audit every paisa.'

### D-028 — Inclusive GST reverses tax from discounted line total (TESTED)
- **Implemented:** `app/services/taxes.py::inclusive_tax_line` computes line gross = qty × unit price, subtracts allocated discount, extracts taxable value using `round_half_up(total × 10000 / (10000 + rate_bps))`, then splits the tax remainder into CGST and SGST with deterministic odd-paisa allocation. `TaxCatalog.rate_for` rejects missing or overlapping active rates and selects by effective date. `invoice_totals` sums rounded line values.
- **Why:** All inputs and results are integer paise. Reconcile `taxable + CGST + SGST = charged inclusive total` on every line and overall.
- **Alternative:** binary floating point then round invoice totals (rejected due to line-level reconciliation errors).
- **Evidence:** `tests/test_stage4.py::test_rate_effective_dates`, `test_tax_reconcile_paisa`, `test_tax_discount_and_multiline`.
- **Caveat:** On an odd-paisa tax split, the extra paisa goes to CGST. Finance should confirm presentation/rounding preference; this is the exercise's intra-state CGST+SGST model, not legal tax advice. Existing sample invoice illustrates separate split rounding, so a one-paisa difference may occur in sample fixtures; the chosen invariant prioritizes exact reconciliation.
- **Founder explanation:** 'Every invoice line balances to the last paisa, even with a discount or an odd tax amount.'

### D-029 — Exercise JSON is a read-only configuration source at Stage 4 (TESTED)
- **Implemented:** `app/services/catalog.py` reads bundled `tax_rates.json`, `offers.json`, and `products.json` without changing the mock. Catalog selection is based on variant `eluno` metadata.
- **Why:** Exercise requires offers and tax rates to change without code edits; keep future Shopify adapter separate from domain calculations.
- **Risk:** Direct JSON loads are suitable for the exercise and snapshots, not a production synchronization strategy.
- **Founder explanation:** 'The cashier's calculations depend on business data, not hard-coded sales campaigns or tax rates.'

### D-030 — Test status, red/green correction and stopping boundary (VERIFIED)
- **Run:** `cd /mnt/data/eluno_stage4/eluno-pos && python -m pytest -q`
- **Final result:** **20 passed** (6 foundation + 14 Stage 4), 24 Oct 2026.
- **During implementation:** initial run was **19 passed, 1 failed**; manager rule `value_bps_max` did not have `value_bps`. Fixed separate manager handling in `app/services/offers.py`, reran to 20 passed. Recorded to demonstrate a real feedback loop rather than hide the error.
- **Not built:** live Shopify/store/terminal adapters, pricing HTTP API, payment/checkout orchestration, refunds, reports, UI. No charge or order was triggered. Gateway contracts and Stage 3 state remain untouched.
- **Open policy concerns:** discount stacking and prioritization, audit/approval semantics for manual discounts, and tax split presentation. Stage 5 must use an immutable computed quote and must not recalculate an altered total after payment.
- **Review checkpoint:** Stop here before payment or checkout integration.

## Stage 5 — sale integrations (implemented; review checkpoint)

### D-031 — Quote before external side effects
- **Decision:** `app/services/sale.py:SaleService.prepare` loads customers/variants/prescriptions and store stock through `app/gateways/http.py`, calculates offers and GST using Stage 4 services, and persists a quote in `checkout_quotes` before issuing a charge.
- **Why:** The user can inspect a stable total; a successful charge must not be followed by price recalculation. `app/persistence/sqlite.py:save_quote/load_quote` preserves the quote across restarts.
- **Trade-off:** Quote stock is checked when prepared, not reserved. Shopify decrements on order creation and may reject if stock disappears between prepare and order; requires manual compensation of a captured charge. No false claim of atomic stock reservation.
- **Evidence:** `tests/test_stage5.py::test_sale_mock_roundtrip_and_stock`, `test_persist_across_restart_and_refuse_duplicate`. Successful mock checkout created one paid Shopify order and reduced frame inventory by one.
- **Founder explanation:** "We save the amount and the sale details before asking the terminal to collect money. That prevents the application from changing the charged price after payment."

### D-032 — One-shot unsafe external writes
- **Decision:** `MockHTTP.request` retries read-only GET only. Terminal charge and Shopify order creation POST are performed at most once; a failure moves the checkout to `payment_uncertain` or `order_uncertain` in `SaleService.complete/_record_order`.
- **Why:** The terminal mock does NOT enforce its documented `order_ref` idempotency. An HTTP timeout does not establish that no charge happened. Shopify orders lack a native idempotency key in the exercise mock.
- **Trade-off:** Some recoverable failures require human action; this favors avoiding duplicate charges over unattended retries. A crash between a successful external call and local recording also remains a manual reconciliation case.
- **Evidence:** `test_uncertain_charge_never_repeated`, `test_uncertain_order_never_reposted` both pass. Duplicate `/complete` on successful sales returns the saved checkout without reposting.
- **Founder explanation:** "When we don't know whether a card was charged, we stop and reconcile rather than charge the customer again."

### D-033 — Traceable Shopify order and read-only reconciliation
- **Decision:** `checkout_id` and `invoice_no` are stored in Shopify `note_attributes`; Shopify line properties contain lens prescription reference, HSN, and lens selection. `reconcile_order` can find an existing order after response loss by scanning the mock's orders list. No automatic re-post if none is found.
- **Why:** The local state and Shopify record need a common correlation key. Recovery must not create a second order.
- **Trade-off:** The mock only supplies a limited `orders.json` list; scanning up to 250 orders is not proof of nonexistence at scale. A production adapter would require proper pagination/search and operator reconciliation tooling.
- **Evidence:** `test_reconcile_existing_order_after_lost_response` passes, resolving one matching Shopify order without repeating order creation.
- **Founder explanation:** "Every Shopify order has our unique checkout identifier. If the connection drops after we create an order, we look it up instead of blindly creating another."

### D-034 — Deliberate single-pair Stage 5 slice
- **Decision:** `SaleService.prepare` accepts zero or one frame and zero or one lens, each quantity one. Full multi-pair/family billing is not implemented in this milestone. Store-specific staff lookup and inventory checks run before payment.
- **Why:** A small complete and testable vertical slice is more valuable than a partially implemented large cart. The exercise Must tier still requires broader cart coverage; this is a known gap, not claimed complete.
- **Trade-off:** Multi-pair offer conditions cannot be exercised through the API yet. Stage 4's pure offer engine supports them, but sale orchestration needs generalization.
- **Evidence:** `tests/test_stage5.py` exercises one complete pair, stock rejection and invalid staff; 27 total tests passed, including 20 Stage 3/4 tests.
- **Founder explanation:** "I got one full sale working reliably first, then I can extend the cart size without changing pricing or integration boundaries."

### D-035 — Mock-scoped resilience, not a production payment guarantee
- **Decision:** Return clear 409 for already-started checkouts, 502 for gateway failures, and preserve error details in SQLite. No background retries of terminal charges or Shopify order POST. All stage 5 paths are synchronous.
- **Why:** The exercise mock is not a reliable charge-reconciliation service; `GET /terminal/charges/{id}` needs a charge id, which may be lost with the HTTP response.
- **Trade-off:** `payment_uncertain`, `payment_captured`, `order_pending`, and unresolved `order_uncertain` require explicit operations follow-up. Persisted state prevents *automatic* duplicate writes, not every failure/recovery risk. No performance guarantee of under 10 seconds has been established.
- **Evidence:** Stage 5 integration tests pass against unmodified `--no-flake` mock; simulated charge timeout and lost order response are tested. 429/retry behavior under flaky mock remains a follow-up acceptance test.
- **Founder explanation:** "A correct billing app must preserve ambiguous financial events, even if doing so means temporarily stopping a sale for reconciliation."

## Stage 6 — full refunds and day-end reporting (implemented; review checkpoint)

### D-036 — Shopify refund calculation is authoritative (TESTED)
- **Implementation:** `app/services/refunds.py::RefundService.prepare` reads the completed Shopify order, classifies persisted line properties, constructs full-quantity refund lines, then calls `app/gateways/http.py::MockHTTP.refund_calculate` (`POST /orders/{id}/refunds/calculate.json`). Refuses a refund if suggested amount does not equal full original order total, exceeds refundable balance, or calculated tax reversal differs from line taxes.
- **Reason:** Refund tax/discount arithmetic must match Shopify rather than a second local pricing engine.
- **Trade-off:** Stage 6 deliberately supports **full refund only** of sales created by this app. Existing Shopify refunds, unknown item types, mismatched calculations, and sample orders not linked to local checkouts require manual handling. Calculation endpoint is a POST but has no mock side effects; it is not automatically retried by our HTTP adapter.
- **Evidence:** `tests/test_stage6.py::test_full_refund_amount_tax_and_stock` checks refund amount equals charged amount, tax reversed equals original GST, and Shopify state.
- **Founder explanation:** "Before moving money, I ask Shopify to calculate the refund, then verify the complete amount and tax. This keeps our refund records aligned with finance's source of truth."

### D-037 — Refund the terminal first, then register the Shopify refund (TESTED, failure boundary documented)
- **Implementation:** `app/services/refunds.py::RefundService.complete` uses SQLite `refund_attempts` to persist `prepared → terminal_pending → terminal_refunded → shopify_pending → recorded`, with `terminal_uncertain` and `shopify_uncertain` branches. `app/persistence/sqlite.py::initiate_refund/refund_transition` compare-and-set statuses prevent duplicate outward calls on repeated requests. The original terminal `payment_charge_id` identifies the charge; the refund reason is mandatory.
- **Reason:** The physical payment refund must be recorded and Shopify must reflect the corresponding financial reversal and restock. Neither terminal refund nor Shopify refund is safe to automatically retry after uncertain response; the mock provides no refund-idempotency contract.
- **Trade-off:** A successful terminal refund followed by failed Shopify creation leaves a mismatch requiring reconciliation. Reversing the order would leave an equivalent reverse failure risk. A crash after the external side effect but before saving response also requires manual intervention. No distributed transaction claimed.
- **Evidence:** `test_terminal_refund_uncertain_is_not_retried` and `test_lost_shopify_refund_response_reconciles` pass. Shopify reconciliation uses persisted `eluno_refund_id` in refund `note_attributes`, and never reissues a POST.
- **Founder explanation:** "We record exactly what we attempted. If the response disappears, we stop rather than risking a second refund, and inspect Shopify before letting an operator resolve the case."

### D-038 — Only frames return to shelf stock (TESTED)
- **Implementation:** `RefundService.prepare` uses the original Shopify line's `line_type` property. Frame `restock_type='return'` plus the order's billing `location_id`; lens `restock_type='no_restock'`. Shopify's refund POST applies inventory mutation, not our app's own inventory adjustment.
- **Reason:** Prescription lenses are made to order and cannot be offered as new shelf stock. Frames should return only to the store originally billed.
- **Evidence:** `test_full_refund_amount_tax_and_stock` checks exact one-unit frame restoration and refund line types. No lens restock request is sent.
- **Founder explanation:** "A returned frame becomes available at the original store. A custom prescription lens is never treated as reusable inventory."

### D-039 — Day-end derives exclusively from Shopify orders (TESTED, timing limitations explicit)
- **Implementation:** `app/services/reporting.py::DayEndService.report` queries `MockHTTP.locations/orders`, filters `created_at` date and billing location, computes bill count, gross, taxable, total line tax, discounts, Shopify refund transactions, and Shopify sale transactions grouped by saved `payment_method` (fallback gateway). Monetary computations use `paise` decimal strings via `Decimal`; local checkout SQLite is not a financial report source. `GET /reports/day-end` is exposed in `app/main.py`.
- **Reason:** Finance already reconciles from Shopify, so our till must not show different numbers from a local shadow ledger.
- **Trade-off:** The mock offers no pagination and `orders.json` defaults to a bounded list; the report refuses a 250-record cap but could still miss remote records in less obvious conditions. The report groups refunds **by original sale date**, even if the refund happened later; this is not a refund-event-date cash settlement report. The API does not infer unrecorded terminal payments or cash drawer counts. Production needs pagination, timezone/cut-off rules, refund-event date reporting and reconciliation across settlement batches.
- **Evidence:** `test_report_from_shopify_after_refund` verifies totals reconcile, new refunds decrease net, and order is included.
- **Founder explanation:** "The day-end reads finance's source of truth. I show its accounting basis clearly, instead of promising a cash-settlement report that our mock cannot support."

### D-040 — Stage 6 verification and stop boundary (VERIFIED)
- **Actual command:** `cd /mnt/data/eluno_stage6/eluno-pos && python -m pytest -q`
- **Actual result:** **32 passed in 12.43s** on 24 Oct 2026, including 27 existing Stage 3–5 tests and 5 new Stage 6 tests with the unmodified mock running `--no-flake`.
- **Files changed:** `app/gateways/http.py`, `app/persistence/sqlite.py`, `app/main.py`; created `app/services/refunds.py`, `app/services/reporting.py`, `tests/test_stage6.py`. No changes to starter-kit mock or Stage 3–5 domain pricing logic.
- **Scope boundary:** Full refunds and Shopify-order-derived day-end reporting completed for the Stage 5 single-frame/single-lens sale flow; **no frontend, no partial refunds, no cash drawer, no final repo submission**, and no new multi-pair/family checkout flow. A separate production-readiness review is needed for 429/503 fault coverage, external refunds between quotes, payment mismatches, report pagination and operational recovery.
- **Review checkpoint:** Stop now and wait for user approval before final submission.

- **Final regression note:** Changing the health `stage` from 5 to 6 caused one expected assertion failure in `tests/test_foundation.py::test_health` (31 passed, 1 failed). Updated the assertion to reflect the new version and reran the suite.

## Final audit — decisions D-041 through D-044 (24 October 2026)

### D-041 — Report the Must coverage precisely, not as a complete retail POS (AUDITED)
- **Decision:** Keep single-pair checkout and order-date reporting limitations visible in `README.md` and `FINAL_AUDIT.md`; do not claim all Must variants are complete.
- **Reason:** Multi-pair offers exist in fixtures, but `app/services/sale.py::SaleService.prepare` rejects more than one frame/lens, so the till cannot exercise all seeded offer situations. The reporting source is correct but refund timing is not a real settlement ledger.
- **Evidence:** Source audit of `app/services/sale.py` and `app/services/reporting.py`, plus 32/32 tests passing for implemented paths.
- **Founder explanation:** "I finished and tested a thin end-to-end billing slice. I deliberately show the parts still needed for family billing and production finance rather than describing a prototype as a complete system."

### D-042 — Preserve conservative behavior on uncertain money movement (RECONFIRMED)
- **Decision:** Do not retry terminal charge/refund or Shopify order/refund POST automatically on ambiguous failures; keep persisted states and read-only reconciliation.
- **Reason:** The mock's advertised terminal idempotency differs from behavior seen in Stage 2; duplicate financial operations are worse than an operator intervention.
- **Evidence:** `app/services/sale.py`, `app/services/refunds.py`, `app/persistence/sqlite.py`; Stage 5–6 failure tests included in fresh-copy **32 passed** run.
- **Founder explanation:** "When an API times out, I don't assume payment failed. I save the uncertain state and reconcile before permitting further money movement."

### D-043 — Verify through both tests and a real HTTP smoke walkthrough (VERIFIED)
- **Decision:** Validate a fresh project copy with isolated mock-backed unit/integration tests and a separately launched app+mock HTTP walkthrough.
- **Reason:** In-process tests may miss routing/method mistakes or actual runtime configuration problems.
- **Evidence:** `FINAL_AUDIT.md` and audit-only `smoke_check.py`: 32/32 pytest; valid seed; external HTTP prepare/complete/refund/report **SMOKE PASS**. First smoke run used wrong method for completion and got 405; corrected audit script (application code unchanged).
- **Caveat:** Fresh dependency installation in fully isolated virtualenv was not verified; existing runtime packages used. Two processes must be launched; strict one-command start is not implemented.
- **Founder explanation:** "I tested business rules and then exercised the entire local HTTP boundary. I kept the first smoke-script error and the dependency-install limitation in the record."

### D-044 — Stop before submission and record known risks and next actions (APPROVED WORKFLOW)
- **Decision:** Improve documentation and Loom plan; leave Git push, Loom recording, emails, and scope expansion for explicit final approval.
- **Reason:** User requested a review gate, and the code still has Must-tier breadth/reconciliation limitations worth discussing.
- **Evidence:** `README.md`, `FINAL_AUDIT.md`, `LOOM_SCRIPT.md`; no remote repository operations performed.
- **Founder explanation:** "I keep decisions, test evidence, open gaps, and final release approval separate so the handoff is traceable."


## Must-tier gap closure — D-045 to D-047 (24 October 2026)

### D-045 — Accept multiple complete frame/lens pairs using positional pairing (TESTED)
- **Code:** `app/services/sale.py::SaleService.prepare`; `app/main.py` retains the existing `variant_ids` API contract. Separate frame and lens selections retain their original order; the Nth frame pairs with the Nth lens. Each pair receives a stable `pair_ref` saved on both Shopify line items. Each selected lens is independently validated against the customer's latest valid prescription.
- **Reason:** The original one-frame/one-lens restriction blocked seeded second-pair offers; accepting multiple distinct pairs closes this meaningful Must-tier coverage gap without a new API schema or UI.
- **Alternative rejected:** Assume consecutive frame/lens order or silently pair unmatched items; both are error-prone. Explicit customer-controlled pair IDs would be more flexible but bigger in scope.
- **Boundary:** A multi-line sale requires equal numbers of frames and lenses; one frame-only or lens-only sale still works. Repeated variant IDs are rejected (no quantity model), and all pairs use one customer's prescription. Thus we support multi-pair, **not multiple distinct wearers within a family**.
- **Evidence:** `tests/test_multi_pair.py::test_two_pairs_prescription_offer_order_and_full_refund` verifies 4 Shopify lines, matching pair refs, second-pair discount, stock reduction for both frames, and refund of every line with lens no-restock.
- **Founder explanation:** "I removed the one-pair limit while keeping pairing deterministic. I reject ambiguous carts instead of guessing whose lens belongs to which frame."

### D-046 — Reuse existing pricing and refund engines for arbitrary distinct cart lines (TESTED)
- **Code:** `app/services/sale.py` builds `CartLine`, lens checks, taxes, discounts, and Shopify properties in loops indexed by selected variant. `app/services/offers.py` already supports multi-line allocations and `SECONDPAIR50`; `app/services/refunds.py` already loops over original Shopify order lines. These two services required **no changes**.
- **Reason:** Minimal changes avoid a second financial algorithm. Shopify remains responsible for authoritative order inventory decrement and refund restock.
- **Evidence:** Multi-pair end-to-end integration asserts `SECONDPAIR50` applies; full refund returns the two frames to stock, excludes lens restocking, and the previous 32 tests remain green.
- **Founder explanation:** "The tax, offer and refund engines were designed around cart lines already, so only sale preparation needed generalizing."

### D-047 — Stop after focused Must improvements with verified regression (TESTED)
- **Command:** `cd eluno-pos && python -m pytest -q`
- **Actual output:** `35 passed in 12.55s` (32 existing + 3 new) with the supplied mock unmodified, using non-flaky mode in integration tests.
- **Known remaining gaps:** Different customers' prescriptions in a family bill; repeated SKUs and quantities; atomic stock reservation; uncertain payment reconciliation; store-local settlement reporting/pagination; strict one-command start. No external push, email or Loom submission performed.
- **Founder explanation:** "I closed the second-pair promotion gap with three new tests, kept all existing sale/refund tests passing, and stopped rather than broadening into an untested UI or settlement system."
