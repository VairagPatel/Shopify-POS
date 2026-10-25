**Subject: Re: Replace Shopify POS — scoped release, working demo and decisions needed**

Hi Rohan, Meena, Dr. Iyer, Vikram, Farhan and Priya,

I propose replacing the store-facing till while keeping Shopify authoritative for orders, payments, inventory and refunds. We now have a working demo that shows the whole process: customer and prescription → wearer-specific cart → offers and tax → payment → Shopify order and store invoice → return/remake → store reconciliation.

The demo uses the supplied mocks and synthetic data. It is evidence of the implemented workflows, not approval to replace the live tills in all seven stores.

**Proposed release scope**

- Family billing on one invoice, with separate prescription validation for every wearer; priority/campaign tags visible before billing.
- Configured offers, a visible explanation of applied/rejected discounts, and a manager override up to 10% with authenticated approver identity and a mandatory reason.
- HSN/effective-date GST from configuration, GST-inclusive MRP, taxable/tax breakdown, per-store invoice allocation and a register retaining cancelled numbers.
- Full refunds in Shopify, reversal of original line tax, and a linked printable credit note. Physical frames return to the billing location; custom lenses are not restocked.
- Lens-only remakes linked to the original bill, with reason, approver, lab cost and cost owner; no duplicate frame billing or stock movement.
- Store-local day-end and channel reporting, cash expenses, physical drawer count and a finance notification when absolute variance exceeds ₹200.
- A 10:00 Asia/Kolkata founder report with yesterday's bills, average bill value and discounts per store.
- Saved carts and persisted financial states, with explicit pending/uncertain outcomes and reconciliation rather than blind retries.

**Decisions we need to settle**

1. **Meena + Vikram — offer stacking.** The demo follows supplied stackable/non-stackable configuration. Please confirm whether festive 10%, second-pair 50% and priority ₹500 always combine, what “second pair” discounts, the calculation order, maximum discount and how manager overrides interact. We should approve example bills before freezing the rules.
2. **Meena + Vikram — manager approval.** My proposal reconciles speed and auditability: an authorized manager approves directly within the limit using their identity and a reason; no separate approval chain. Cashiers cannot impersonate a manager through the API.
3. **Dr. Iyer — axis and remakes.** New manual axes use five-degree choices; already-issued prescriptions are preserved. Please confirm clinical validity rules and who authorizes remake cost ownership. External-optometrist costs are recorded for recovery, not automatically charged to that party.
4. **Vikram — invoice and credit-note sign-off.** Every allocated number remains visible, including reserved/cancelled bills. Please approve the fiscal-year series, legal document fields and credit-note numbering before real issuance. The current printable documents are explicitly demo documents.
5. **Rohan + Priya — performance and rollout.** Measure from confirmation of an already-prepared cart to final order result, with a proposed p95 target below ten seconds. Local mock timings are visible, but production latency, outages and devices still need validation. Start with one pilot store; expand only after payment/order/refund reconciliation passes. I cannot responsibly commit all seven stores by 15 November without those gates and integration access.
6. **Finance + Ops — operating details.** Please confirm drawer-close ownership, finance/founder email recipients, the report cutoff and exception escalation. Reports use Asia/Kolkata; new collection reports attribute refunds to the actual refund day. A queued email is not claimed as delivered until SMTP accepts it.

**Separate workstreams**

The queue-tool beverage question should go to its product/engineering owner. The Indiranagar camera should be triaged with facilities and the camera vendor. Both remain explicitly tracked; neither is hidden inside POS completion.

**Acceptance and rollout**

Priya can use the attached requirement-to-test checklist and the demo's coverage view to distinguish verified behavior, assumptions and production dependencies. The tech review should include a family sale, incompatible lens rejection, denied cashier override, full refund/restock, remake without frame movement, cancelled invoice, drawer variance and an uncertain-response reconciliation.

Before a pilot we need real Shopify scopes/location mappings, terminal status/idempotency guarantees, store-tool access, finance/clinical sign-off, actual notification configuration and an operating runbook. Then we can agree a credible rollout date against measured evidence.

Thanks,  
Vairag
