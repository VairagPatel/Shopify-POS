# Tech-lead walkthrough

## Opening: 30 seconds

“This is a working store-till demo. Shopify remains the source through the supplied mock. The UI makes the workflow visible, and the backend protects each financial transition. I'll show the input, the calculation, the source record and the resulting report.”

Sign in as admin. Point out **Demo environment**, the store selector and daily metrics. Do not call a mock order a live Shopify admin order.

## Sale and evidence: 2 minutes

1. Click **Start guided sale**: Karthik Reddy, phone `+919000000005`, frame `FR-0003`, lens `LN-0043`.
2. Show priority and campaign badges, prescription and store stock.
3. Click **Review offers & GST**. Explain that this validates and saves a quote; it has not charged anything.
4. Expand **Why these offers?**. Explain decisions, discounts, taxable value and included GST.
5. Confirm UPI. The invoice dialog shows the invoice number, payment reference and source order ID. Open **Technical evidence** to inspect the actual source payload.
6. Print the invoice if desired. Show HSN, wearer Rx, discount and tax per line.

## Family bill: 90 seconds

Create a new bill. Add three wearers:

| Wearer phone | Suggested frame | Suggested lens |
|---|---|---|
| `+919000000005` | `FR-0003` | `LN-0043` / variant `91000083` |
| `+919000000004` | `FR-0005` | Same lens variant |
| `+919000000007` | `FR-0006` | Same lens variant |

Click each wearer tab before selecting their items. The same lens SKU is allowed across different people; their prescription references remain distinct. Review, confirm and inspect the six lines on one order. If inventory has been consumed in repeated demos, select an available Rx-compatible frame or refund the earlier demo sale.

## Return and remake: 2 minutes

On a completed unrefunded bill:

- **Remake lens**: choose the original wearer, a compatible replacement lens, reason, cost owner and lab cost. Choose Eluno as cost owner to demonstrate zero customer charge. Confirm the new lens-only order. The frame is neither rebilled nor moved. Customer-funded remakes use catalog price/offer rules; external-cost recovery is only recorded.
- Return to the original bill and choose **Full refund**. Enter a reason; preview first, then confirm. Open the **Credit note**. It references the original invoice and reverses original tax. Source refund lines show the billing-store frame restock and `no_restock` for lenses.

## Roles and clinical guardrails: 1 minute

Sign out and sign in as cashier. The manager override is unavailable, refunds are not offered, and direct protected API requests return 403. Explain that the server guard enforces this independently of the buttons.

Sign in as optometrist to show manual axis options in five-degree steps. Existing issued Rx records are preserved. A lens outside the wearer's range is rejected before payment.

## Cash and reports: 90 seconds

As manager/admin, open a drawer with ₹2,000. Make a cash sale, then record a ₹50 courier expense. Count and close the drawer. A variance above ₹200 queues a finance message; exactly ₹200 does not.

Show **Store reports** and change the date if needed. The report uses Asia/Kolkata, source sales, channel attribution and refund-event-date collections. Show the payment-to-order delta and explain that cash variance is separate.

Show **Report outbox**. Generate yesterday's founder digest. It contains bills, average bill and discounts per store. Without SMTP it is a preview, not a sent email.

## Technical review: 1 minute

- Open **Demo & coverage** for the requirement map, acceptance evidence and limits.
- Open the invoice register: cancelled numbers remain, new bills get the next number.
- Explain the saved checkout → payment pending → captured → order pending → recorded states. Unknown writes are not blindly retried.
- Cite the test suite for lost-response behavior, authorization and stock/tax correctness.
- Show `Dockerfile`, CI, persistent mock wrapper and the supplied mock left unchanged.

Close with remaining production gates: real integration credentials and guarantees, finance/clinical policy sign-off, device/network pilot, measured p95 latency, pagination/settlement and operational security review. Beverage-question and camera fixes belong to their own owners.
