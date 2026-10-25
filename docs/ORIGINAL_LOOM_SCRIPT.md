# Eluno POS — final Loom walkthrough (35 tests; max 8 minutes)

**Status:** Preparation script only. No Loom has been recorded or submitted. Aim for **7:30–7:45** so normal pauses do not push past the eight-minute limit.

## Before recording (do not count toward the video)

1. Open `README.md`, `STAKEHOLDER_REPLY.md`, `DECISIONS.md`, `app/services/sale.py`, `app/services/refunds.py` and Swagger at `http://127.0.0.1:8000/docs`.
2. Run `python -m pytest -q` and keep **35 passed** visible. Run `python exercise-pack/starter-kit/validate_seed.py` if desired.
3. Start fresh mock and FastAPI processes as in README. Set up fresh SQLite and mock state for the demo. **Don't erase an actual ambiguous payment record to reset production state.**
4. Pre-test a two-pair HSR sale with customer `+919000000005`, staff `S105`, variants `[91000003,91000005,91000083,91000084]`; confirm `SECONDPAIR50` is present in the quote. Retain IDs produced in the real demo; don't hardcode IDs in narration.
5. Keep the refund, report and status endpoint URLs ready; avoid displaying credentials, personal data, or unrelated desktop notifications.
6. Read the limitations below and rehearse the demonstration once without recording.

## Timed run of show

| Time | Show | What to explain in your own words |
|---|---|---|
| 0:00–0:35 | README and folder tree | “This is an evaluation till backend for seven stores. Shopify remains the source of truth for customers, orders, inventory and refunds; the store tool supplies prescriptions, and a separate terminal collects payment. This is not a production-ready POS.” |
| 0:35–1:20 | `STAKEHOLDER_REPLY.md` | “I wrote the stakeholder response first because store speed, clinical safety, promotion flexibility and finance reconciliation conflict. I clarified proposed v1 behavior and what needs stakeholder approval.” |
| 1:20–2:05 | Domain, services, gateway, SQLite | “I separated prescription rules, offer evaluation and GST from HTTP provider payloads. SQLite holds invoice sequences, quotes and uncertain external operation states. The gateway translates to mock Shopify, store-tool and terminal APIs.” |
| 2:05–3:45 | Swagger: `POST /sales/prepare` with two pairs, then `POST /sales/{id}/complete` | “I built a two-frame/two-lens cart, using positional pairing. The latest valid prescription checks each lens. `SECONDPAIR50` applies through seeded offer data; taxes reconcile to the paisa. We save an invoice and quote before payment. On completion the terminal charge is followed by the paid Shopify order with four lines.” Show actual quote, order ID, and stock results. |
| 3:45–4:50 | `POST /refunds/prepare`, `POST /refunds/{id}/complete`, Shopify result | “Shopify first calculates the refundable amount and tax reversal. Then the terminal refunds and Shopify records the reversal. Both frames restock at the billing location, but prescription lenses do not.” |
| 4:50–5:20 | `GET /reports/day-end?store_code=HSR&date=...` | “This report reads Shopify, not my SQLite workflow records. Refunds here are attributed to original order dates; it isn't a cash settlement report for refund-event dates.” |
| 5:20–6:25 | `DECISIONS.md` and implementation | “Three decisions: integer-paise inclusive GST and deterministic offers; persisted states around charge/order/refund calls to avoid blind retries; a provider boundary so business rules don't rely on Shopify response formats. The mock does not reliably honor the documented terminal idempotency promise, so uncertainty needs reconciliation.” |
| 6:25–6:55 | `python -m pytest -q` output | “I verified 35 tests, including three new tests for two-pair billing, invalid pair counts, and duplicate-variant rejection. The integration case checks `SECONDPAIR50`, four Shopify lines, both frame stock deductions, and full refund behavior.” |
| 6:55–7:35 | README limitations; finish | “For real stores I'd add different-wearer prescriptions, repeated SKU quantities, atomic inventory reservations, operator reconciliation, store-local refund-date settlement and a one-command launch. I deliberately didn't hide those gaps.” |

## AI tools (personalize truthfully)

Use this **only if it accurately describes your own workflow**: “I used AI assistance for planning, scaffolding and test scenarios; I inspected the provided mock, reviewed the generated behavior, and ran the tests myself. A useful lesson was not to trust documented terminal idempotency without checking the server behavior.” If you used different tools or did not perform a step personally, replace this with what you actually did. Don't invent an AI failure.

## Make these explicit if challenged

- Two pairs work **for one selected customer's prescription**; this is **not** mixed-person family billing. Pairing is positional, no repeated variants or quantity >1.
- HTTP API only, no cashier UI; the brief says no UI is required.
- Payment/order/refund side effects are persisted and uncertain cases stop; this is not true distributed atomicity or automatic terminal reconciliation.
- The current setup needs **two processes**, so the one-command startup constraint remains unmet. Name it as an improvement, don't falsely claim compliance.
- Shopify report groups refunds by original order date; no full pagination or settlement-date ledger.
- The 35 tests were run against the project on 24 Oct 2026; show the actual result from your recording environment.

## Backup if live demo fails

Do not repeatedly charge or refund after a timeout. Open the saved checkout/refund state, explain what is uncertain, and show test evidence. A safety stop is better than a demo that risks duplicate operations.
