# Eluno Store Studio — recording plan

Use the detailed steps in [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md). No recording or external submission has been made.

For an eight-minute recording:

| Time | Show | Explain |
|---|---|---|
| 0:00–0:35 | Scope and login | Replace the till; Shopify remains the record; supplied mocks satisfy exercise integration |
| 0:35–1:25 | Source customer, Rx, catalog and store stock | Must 1–2; briefly demonstrate an invalid lens rejection |
| 1:25–2:20 | Valid cart and prepared quote | Must 3–4; configured offer decisions, inclusive GST, taxable/CGST/SGST and invoice number |
| 2:20–3:20 | Confirm payment and inspect actual source order | Must 5; charge precedes source order, transaction/Rx/discount/tax properties and stock decrement |
| 3:20–4:20 | Full refund and source evidence | Must 6; original tax reversal, original transaction link, frame restored to billing store, lens not restocked |
| 4:20–5:05 | Store/date day-end endpoint | Must 7; source-derived count, gross, taxable, tax, discount, refund and payment split |
| 5:05–6:15 | Decisions and tests | Integer paise, persisted financial states/no blind retries, source-derived reconciliation; show latest audit |
| 6:15–6:55 | One decision to revisit | Move Shopify-shaped mapping out of sale/refund orchestration into adapters; explain current boundary honestly |
| 6:55–7:35 | AI disclosure and limits | Explain assistance and an incorrect assumption you actually verified; distinguish mock functionality from rollout readiness |

AI discussion prompts to personalize truthfully: AI assisted implementation, test scaffolding, investigation and documentation. The first AI-assisted cart implementation restricted each wearer to one frame/lens pair; the cashier review exposed that assumption, and regression tests plus browser checks drove the correction. Explain what you personally reviewed and understood. Do not claim independently authored code or personal checks you did not perform.

Keep optional family/remake/email demonstrations out of the core recording if they crowd out a Must item or the required discussion. Target 7:35 to leave room for transitions; the actual recording must remain under eight minutes.

Before recording, run the tests, verify available stock, open the coverage map and rehearse. Do not display generated passwords. Do not claim live Shopify, live terminal payments or actual email delivery when SMTP is unconfigured. Browser screenshots are stored locally in `runtime/screenshots`.
