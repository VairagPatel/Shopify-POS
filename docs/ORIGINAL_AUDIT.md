# Final Must-tier gap audit — 24 October 2026

## Source of requirements
`exercise-pack/START_HERE.md`, `exercise-pack/brief/CANDIDATE_BRIEF.md`, `exercise-pack/brief/STAKEHOLDER_THREAD.md` and mock documentation. Audited **the copied Stage 6 codebase**, not an imagined future solution.

## Verification commands and actual results

- Fresh source extraction/copied tree (no old runtime SQLite, caches or bytecode).
- `python -m pytest -q` → **32 passed in 13.06s**.
- `python exercise-pack/starter-kit/validate_seed.py` → **OK**, 8 locations, 30 customers, 47 prescriptions, 92 variants, 8 offers, 12 orders.
- Spawned the unchanged mock on port 18787 and the actual FastAPI server on port 18080 with a **fresh temporary SQLite**. `GET /health` returned 200. `POST /sales/prepare` returned a 1,869,700-paise quote; `POST /sales/{id}/complete` returned `order_recorded` and Shopify order ID `99000005`; repeated completion returned the same order reference. `POST /refunds/prepare` followed by `/refunds/{id}/complete` returned `recorded` for 1,869,700 paise. `GET /reports/day-end` returned Shopify source and included the refund. **SMOKE PASS**.
- The first standalone HTTP smoke run was **invalid** due to the audit script sending GET instead of POST for an empty-body completion request (405). Fixed the smoke script's method, reran, and passed. No application behavior was modified to correct this.
- A virtualenv was attempted but unavailable for a fully isolated install in this environment: `pip check` surfaced an unrelated preexisting `supervisor`/`setuptools` environment mismatch, and the created venv had no pytest installed. The verification therefore used preinstalled Python 3.13 packages. **Do not claim clean dependency installation was proven.**

## Coverage table

| Must | Status | Evidence / limitation |
|---|---|---|
| Customer phone + latest valid Rx | Tested | `SaleService.prepare`; single synthetic customer sample; invalid/stale Rx unit tests |
| Frame + lens, matrix limits | Partial | One frame + one lens at quantity one; broader multi-pair/family cart not exposed |
| Data offers | Partial | Pure engine tested for conditions/priority/stacking; manager policy and multi-pair in sale API incomplete |
| GST by HSN inclusive | Tested | Pure calculations and integration; paise reconciliation |
| Terminal charge + Shopify paid order + invoice | Tested | Live HTTP smoke; invoice stored independently; uncertainty/manual recovery limits |
| Full refund / frame restock / lens no-restock | Tested | Mock integration; only linked local sales; no automatic terminal reconciliation |
| Day-end by store/date Shopify | Partial | Report available, but original-order-date refund timing and pagination cap restrict financial completeness |

## Risks to disclose clearly at review

1. Mock idempotency differs from its documentation: same terminal `order_ref` was observed to generate distinct charges after a timeout in Stage 2. Avoid blind retries.
2. Presumed safe 429/503 retry only for reads; mutating calls stop on uncertain failures. True reliability with a terminal requires stronger reconciliation APIs.
3. Stock reservation is not atomic with payment. Stock may disappear after a charge but before Shopify order creation.
4. CLI/HTTP API only, no UI (explicitly permitted by brief).
5. Both mock + API need to be launched as separate commands after installing app dependencies; this **does not strictly satisfy** a literal “one command after cloning” expectation. Needs a launcher if Eluno interprets this strictly.
6. Test suite does not establish correctness against live Shopify, actual terminal, deployment security, or store-scale load.

## Submission checklist (NOT submitted)
- [x] Stakeholder reply exists at repo root.
- [x] Source/tests present and mock unchanged.
- [x] 32 tests pass; fresh HTTP bill/refund/report passes.
- [x] README and DECISIONS updated.
- [ ] Strict one-command launcher / isolated pip install verification.
- [ ] Decide whether to generalize cart or prominently keep Must gap disclosed.
- [ ] Record 8-minute Loom.
- [ ] Create/push repo, add reviewer if private, email links — **only after user approval**.


## Post-audit Must gap improvement (24 October 2026)
- Multi-pair checkout now handles multiple **distinct** frames and lenses paired positionally, sharing one customer's prescription. Seeded `SECONDPAIR50` can execute through an actual sale.
- End-to-end mock test includes four Shopify lines, both frame stock decrements, full refund with both frames restocked and both lenses not restocked.
- `python -m pytest -q`: **35 passed in 12.55s**. The earlier audit's 32/32 result remains historical evidence rather than the latest count.
- Outstanding: repeated SKUs/quantities, mixed-person family carts, uncertain terminal reconciliation, stock race, refund-event-date reporting and pagination.
- No git push or submission.
