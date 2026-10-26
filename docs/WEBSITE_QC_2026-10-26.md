# Website QC — 26 October 2026

The complete suite passed **414 tests**. Final targeted reruns passed another 4 browser/API checks and 17 clinical, invoice, refund and export checks. They cover the last restored-coupon, duplicate-frame, compound-eligibility, prescription-sunglasses and admin prescription-store corrections. These checks overlap the complete suite.

## Verified sales flow

1. Sign in with the existing account. Workspace failures are shown separately from incorrect passwords; the live server must expose `/api/draft/metadata`.
2. Add an existing wearer by phone. Numbers normalize to the same +91 format; lookup uses JSON bodies.
3. **Frames:** add a frame as a frame-only line. Open **Lenses** to attach one lens pair if required.
4. **Lenses:** choose the destination, then **type → index → coating → Add lens to cart**. The destination can be the customer's own frame for a standalone lens purchase.
5. **Sunglasses:** ready-to-wear and prescription-compatible options both work. The catalogue's Rx compatibility is enforced.
6. Review separately priced frame and lens lines. Remove a lens without losing its frame, remove the exact occurrence of a repeated frame, or remove an entire pair.
7. Coupons start blank. Select a currently eligible code and click **Apply coupon & review bill**. Only the selected coupon applies.
8. A manager discount needs both the entered percentage and a reason. A percentage alone gives no manager discount. Selecting a coupon clears the manager override.
9. Review GST and confirm UPI, card or cash. Cash requires an open drawer; a blocked cash confirmation leaves the unpaid bill recoverable.
10. The terminal result is saved first, then the Shopify mock order is created with lines, GST, discounts, sale transaction, store invoice reference and lens Rx ID plus clinical snapshot. The issued invoice is saved in SQLite. Repeated confirmation cannot duplicate it.
11. A full return creates a terminal refund and Shopify refund, returns the frame to its billing store, leaves lenses unstocked, records local synchronization time and keeps the original invoice available.

## Prescription axis

Both the entry schema and billing validation accept **0°, 5°, 10° … 180°**. Missing axes, off-grid values, negative values and values above 180° are rejected. Zero remains visible as 0° in the customer panel and is carried into the Shopify lens prescription snapshot.

## Coupon QC amounts

For a ₹10,998 frame and ₹9,499 progressive 1.60 blue-cut lens pair, gross is **₹20,497**. The priority/campaign checks use a customer with those tags and a clinician-confirmed prescription.

| Selection | Discount | Amount payable |
| --- | ---: | ---: |
| No coupon / no complete manager discount | ₹0.00 | ₹20,497.00 |
| FESTIVE10 | ₹1,099.80 | ₹19,397.20 |
| PRIORITY500 | ₹500.00 | ₹19,997.00 |
| PGX_CAMPAIGN15 | ₹1,424.85 | ₹19,072.15 |
| FREE_BLUECUT_PGX | ₹1,000.00 | ₹19,497.00 |
| BUNDLE300 | ₹300.00 | ₹20,197.00 |
| Manager 5% with reason | ₹1,024.85 | ₹19,472.15 |

SECONDPAIR50 is unavailable for one pair. With the tested two-pair ₹39,994 bill it discounts the cheaper ₹9,499 lens by **₹4,749.50**, leaving **₹35,244.50**. FESTIVE10 respects its configured **₹2,000 cap**. MONSOON20 stays unavailable. Type, index and coating must match the same lens; conditions cannot be satisfied by different cart lines. No coupon is applied implicitly, including when an older saved quote is restored.

## SQLite records

Open the existing `runtime/eluno.sqlite3` in this project. Refresh the SQLite browser after activity; do not create another empty file.

| Object | What it contains |
| --- | --- |
| `drafts` | Latest resumable cart per account |
| `cart_snapshots` / `cart_tracking` | All saved versions, draft ID, actor/staff ID, timestamps and checkout/source references |
| `checkouts` | Payment/order status, references and completion duration |
| `checkout_quotes` | Approved line prices, tax, offers, wearers and Rx references |
| `order_submissions` | Exact final order request, including sale transaction, saved before sending |
| `invoice_allocations` | Complete per-store reserved/issued/cancelled numbering register |
| `invoices` | One durable issued invoice per successfully recorded POS order |
| `invoice_lines` | Browsable invoice line, HSN, discount, GST and Rx fields |
| `refund_attempts` | Refund intent, submitted payload, state, terminal/source IDs and `synced_at` |
| `refund_events` | Append-only refund state transitions; old records have an explicitly migrated current-state event |
| `prescriptions` | Rx ID, normalized phone, clinical payload, author username/staff ID, store and timestamp |

The issued invoice count is the number of completed POS orders. Reserved drafts are not issued invoices, and seeded or external Shopify orders do not acquire invented POS invoice numbers. Existing completed POS records are backfilled from their saved quotes. Historical exact submitted requests remain unavailable where an older app never captured them; new requests are stored explicitly.

## Day-end and downloads

The report page shows bills, gross MRP, taxable value, GST, discounts, refunds, collections and successful sale-payment splits. Source data is Shopify mock orders, not merely local checkout counts.

- **Download day-end CSV:** the original exercise policy, selected store/order date with refunds on those orders regardless of refund date.
- **Download daily summary CSV:** the website collection view, with refunds issued on the selected date, including returns of earlier bills.

The accounting basis is stated in both exports. Store roles are restricted to their own store; admin/finance can download all seven stores and a combined total. CSV money uses exact INR decimal strings. Browser QC downloaded the file and verified its payment-method and bill totals. Failed refund transactions are excluded.

## Bugs addressed

- Admin-authored prescriptions now retain the selected clinical store, and admin history includes older global entries.
- Stale backend caused metadata 404s and apparent login failure after successful authentication.
- Generic checkout blocking read the temporary button-disabled state.
- Unsafe array lookups caused receipt/detail rendering errors.
- Grouped frame/lens API carts and mixed sunglasses/prescription carts lost their association.
- Removing a repeated frame could target the first occurrence instead of the selected line.
- Clearing a coupon or restoring an old quote could leave misleading discount state.
- The festive cap was read from the wrong JSON location; lens eligibility tested conditions on different lenses.
- Manager percentage editing collapsed its reason input.
- Finished/cancelled/refunded flows could leave stale cart or list controls visible.
- Store-role coverage queries generated an invalid SQL WHERE clause.
- Reconciled source orders could retain a reserved invoice allocation.
- Issued invoices and refund synchronization were difficult to inspect directly in SQLite.

## QC evidence and scope

The suite covers all five roles, every registered API policy, browser page navigation, cart changes, frame-only/lens-only/paired/sunglasses sales, clinical validation, offer/tax/refund math, payment and source uncertainty, invoice uniqueness, cash reconciliation, source reports and CSV authorization. Test data and processes are isolated from the user's demo database.

Artifacts are generated locally under `runtime/qc/`: `website-final.xml`, `downloaded-day-end.csv`, `screenshots/sales-lens-dropdowns.png`, and `screenshots/lens-only-invoice.png`. Earlier SQLite and mock-state backups are retained there. The supplied archive was inspected as a reference and was not modified.

These results validate the exercise's local Shopify/store-tool/payment mocks. Live-provider onboarding and production deployment validation remain separate.

## Live handover check

The actual app at `http://127.0.0.1:8001` was restarted with the current build and checked in Chrome using the existing admin credentials. All nine pages loaded; zero-degree axis options were present; there were no JavaScript errors or missing API endpoints. The seven-store day-end CSV downloaded successfully. No sales or prescriptions were created by this final live check.

At this verification point, the active database contained **13 issued invoices**, **34 invoice lines**, and **4 recorded refund attempts**. All four had synchronization timestamps and source refund IDs matching the Shopify mock snapshot. The issued invoice count matched the count of successfully recorded POS checkouts. These counts increase as the demo is used. Refresh or reopen the existing SQLite file in the database viewer to see new rows.
