# Eluno Store POS — evaluation implementation

A small FastAPI till application that replaces the **store-facing billing flow**, while Shopify remains the source of truth for customers, inventory, orders, payments and refunds. Built against the **unmodified, local mock** provided with the exercise; **not production-ready**. Part A is [`STAKEHOLDER_REPLY.md`](STAKEHOLDER_REPLY.md); architecture and trade-offs are in [`DECISIONS.md`](DECISIONS.md).

## Requirements and run locally

- Python **3.10+** for this application (the supplied mock uses Python 3.8+). Python 3.13 was used for the final audit.
- From the repository root, install the application dependencies:

```bash
python -m pip install -r requirements.txt
```

Start **two local processes** in separate terminals (there are no external accounts or credentials):

```bash
# Terminal A — exercise mock; reset its in-memory state on every restart
python exercise-pack/starter-kit/mock-apis/mock_server.py --no-flake

# Terminal B — POS app
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs`, or run the documented requests below. Run `python -m pytest -q` for automated tests; they start their **own isolated mock server** as needed. Verify source fixtures with `python exercise-pack/starter-kit/validate_seed.py`.

You may set `ELUNO_MOCK_URL` (default `http://127.0.0.1:8787`) and `ELUNO_DB_PATH` (default `runtime/eluno.sqlite3`). **Use a new SQLite file for each fresh mock session**; the mock resets on restart while local SQLite does not. Do not delete the local database to recover a real ambiguous charge; reconcile the charge first.

## Demo: one complete sale and refund

Run these requests from the repo root with the mock and POS app both running:

```bash
# 1. Prepare a HSR bill for an existing synthetic customer
curl -sS -X POST http://127.0.0.1:8000/sales/prepare \
  -H 'Content-Type: application/json' \
  -d '{"phone":"+919000000005","store_code":"HSR","staff_id":"S105","variant_ids":[91000003,91000083],"payment_method":"upi"}'
# Record checkout_id and check the quote before authorizing payment.

# 2. Charge terminal and create Shopify order (POST has no request body)
curl -sS -X POST http://127.0.0.1:8000/sales/<CHECKOUT_ID>/complete

# 3. Prepare a full refund without moving money yet
curl -sS -X POST http://127.0.0.1:8000/refunds/prepare \
  -H 'Content-Type: application/json' \
  -d '{"checkout_id":"<CHECKOUT_ID>","reason":"customer_return"}'

# 4. Carry out terminal + Shopify refund; do not repeat if uncertain
curl -sS -X POST http://127.0.0.1:8000/refunds/<REFUND_ID>/complete

# 5. View Shopify-sourced store/date report (choose actual sale date)
curl -sS 'http://127.0.0.1:8000/reports/day-end?store_code=HSR&date=2026-10-24'
```

Use `GET /checkouts/{checkout_id}` or `GET /refunds/{refund_id}` to inspect persisted status. Read-only recovery endpoints: `POST /sales/{checkout_id}/reconcile-order` and `POST /refunds/{refund_id}/reconcile-shopify`. Swagger UI at `/docs` shows request shapes.

## Must-tier coverage (accurate scope)

| Requirement | Implemented and demonstrated | Limits |
|---|---|---|
| Shopify customer lookup + latest valid prescription | Yes | Existing customers only; lens choices require valid Rx |
| Frame + lens, Rx range validation | Yes | Multiple distinct frame/lens pairs supported (one frame + one lens per pair); positional pairing and one shared prescription per customer; no repeated variant IDs or mixed-person prescriptions |
| Data-driven offers | Yes, pricing core | Stacking / manager override semantics are assumptions awaiting stakeholder confirmation; SECONDPAIR50 can be exercised in a two-pair sale; offer-stacking semantics remain provisional |
| Inclusive GST, HSN/date-dependent rates | Yes | Paise arithmetic and per-line CGST/SGST reconciliation tested |
| Terminal charge → Shopify paid order, invoice no. | Yes | Uncertain charges/orders halt for investigation, not blind retry; mock-specific integration |
| Full Shopify refund / tax reversal / frame-only restock | Yes | App-created, locally linked sales only; manual handling may be required after uncertain terminal outcome |
| Store/date report from Shopify orders | Yes | **Order-date** report, not refund-event-date settlement; no pagination once result cap is reached |

**Should/Stretch:** no cash till, channel report, partial refunds, printable invoice, audit-trail UI, or AI enhancements; a UI is intentionally omitted because the brief does not score one.

## Architecture and decisions

- `app/domain/models.py`: Shopify-independent cart, prescription, lens, checkout and invoice types.
- `app/services/prescriptions.py`, `offers.py`, `taxes.py`: pure business rules, independently tested.
- `app/services/sale.py`: quote creation and stateful sale orchestration.
- `app/services/refunds.py`: refund calculation, terminal refund, Shopify refund and guarded recovery.
- `app/services/reporting.py`: Shopify-sourced store/date report.
- `app/gateways/contracts.py`, `http.py`: integration boundary (Shopify/SMT/terminal mock).
- `app/persistence/sqlite.py`: checkout/refund states, references, per-store invoice sequences.
- `app/main.py`: FastAPI routes, request validation, HTTP errors.
- `tests/`: pure-rule, persistence, mock integration, and uncertainty cases.

We deliberately persist each attempted external side effect. The supplied terminal mock does **not** enforce the documented idempotency promise consistently. After a lost response, a second charge/refund POST may duplicate money movement. The app records uncertainty and blocks automatic repetition. That is safer than retrying blindly, but requires an operator runbook before real rollout. Shopify order reconciliation relies on a unique local checkout identifier in order note attributes and a bounded mock orders search.

## Multi-pair example (new Must-tier coverage)

Submit `POST /sales/prepare` with `variant_ids: [91000003, 91000005, 91000083, 91000084]` for the HSR fixture customer. The first frame pairs with the first lens and the second frame with the second lens; `pair_ref` 1/2 is saved on Shopify lines. `SECONDPAIR50` becomes eligible. Completing creates **one** paid Shopify order with four lines. A full refund restores both frames, not either prescription lens. See `tests/test_multi_pair.py`.

Current cart restrictions are explicit: all pairs use the same customer latest valid prescription; a variant may occur only once; each line has quantity one; lens and frame groups are positional; bills with unequal multi-pair frame/lens counts are rejected rather than guessed. This is multi-pair, **not** mixed-customer family billing.

## Validation evidence

Latest focused Must-gap run (24 Oct 2026): `python -m pytest -q` — **35 passed** (32 previous + 3 multi-pair tests). Prior fresh-copy audit: **32 passed**; `python exercise-pack/starter-kit/validate_seed.py` — **OK**. Separately launched actual HTTP mock + actual FastAPI app and ran prepare → paid Shopify order → full refund → Shopify day-end report: **passed**. See `FINAL_AUDIT.md` for exact evidence and boundaries. A truly isolated dependency installation was **not proven** because the execution environment did not have a working clean virtualenv setup for pytest; the existing runtime dependencies were used. The source copy and SQLite were fresh.

## Known risks and what I would do next

1. Extend multi-pair carts to allow repeated SKUs with explicit quantities, explicit pair grouping and different prescriptions/customers within a family bill. Current pairing is by the order of frames and lenses; frame/lens count must match when more than one line is present.
2. Add reconciliation tools for uncertain terminal payments/refunds, protected by cashier/manager roles; confirm real terminal idempotency contract.
3. Protect against stock races between availability check and order creation, including recovery after money capture.
4. Implement store-local date cut-offs, paginated Shopify order retrieval, refund-event-date totals and proper payment settlement reconciliation.
5. Add auth, audit logs, cashier usability, printing and operational monitoring prior to production use.

See [`DECISIONS.md`](DECISIONS.md) for trade-offs and the stakeholder reply for assumptions requiring sign-off. **This is an evaluation build, not a deployable live-payment system.**
