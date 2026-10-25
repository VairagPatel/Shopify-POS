# STAKEHOLDER_REPLY.md

**Subject:** Re: Replace Shopify POS — proposed v1 and decisions needed

Hi Rohan, Meena, Dr. Iyer, Vikram, Farhan and Priya,

Thanks for sharing the problems from each team. I suggest a staged v1: replace the till flow while keeping **Shopify as the source of truth** for orders, payments, inventory and refunds, and the store tool as the source for prescriptions. My priority is a quick billing experience that also remains correct and recoverable when a store network fails.

**Decisions and questions before implementation**

- **Rohan / Priya — speed and rollout:** Does “under 10 seconds” start when the customer approves the prepared cart, or at the beginning of lookup? I propose loading customer, prescription and inventory earlier, measuring final-confirmation-to-result p95, and starting with one-store pilot and reconciliation checks before a seven-store 15 November rollout. If Shopify or the terminal is unavailable, the sale should show **pending**, not falsely promise success.
- **Meena + Vikram — offers and manager discounts:** Should festive, second-pair and priority offers combine only when their configured rules allow, and is there a cap? I propose a deterministic offer engine with visible applied discounts and reasons for rejected offers. For any manual manager override, could an authorized manager ID and reason be mandatory, without a separate approval chain for an allowed amount? This preserves speed and finance's audit requirement.
- **Dr. Iyer — prescription, axis and remakes:** Should external or expired prescriptions require optometrist confirmation? Does the 5-degree axis grid apply to staff input only, rather than invalidating an already issued external prescription? I would always block an out-of-range lens or progressive/bifocal without an ADD, with an actionable message. For remakes, who decides the cost owner and authorizes it? Remake orders should refer to the original bill without charging or deducting the frame again.
- **Vikram — invoices and reporting:** Do we agree that cancelled/reserved numbers remain in a per-store invoice register as cancelled rather than disappearing? Shopify order numbers cannot be that series. Please confirm store-local reporting day, refund-date attribution and credit-note format. Day-end totals should be calculated from Shopify, with a separate exception list for payments not yet matched to an order.
- **Farhan — stock and outages:** Can we confirm that every physical frame is deducted from the billing store location and only that frame is returned there on refund? Custom lenses should never be restocked. I propose a saved checkout ID and reconciliation state for Wi-Fi failures; no automatic second charge or Shopify create while the first outcome is unknown.

**Exercise v1 (Must):** customer lookup, latest valid prescription, frame/lens compatibility, rule-based offers, inclusive HSN GST to the paisa, terminal charge and Shopify order with store invoice number, complete Shopify refund with correct tax/stock treatment, and Shopify-derived store/day report. I will prove these with tests and a thin API rather than spend time on screens.

**Deferred for a later release:** family billing, cash drawer flows, sales-channel dashboards, manager discount UI, printable invoices, automatic 10am founder emails and full remake handling. Priority/campaign tags exist in customer data, but displaying them on a till screen requires the later UI. Beverage-question removal and the Indiranagar footfall camera are separate workstreams, not POS scope. These items should enter a prioritized backlog, not disappear.

**Needed to ship in real stores:** API access and scopes, Shopify inventory/location mapping, terminal payment-status/reconciliation guarantees, store-tool permissions, invoice and credit-note sign-off, cashier/manager authorization rules, operational Wi-Fi/device testing, and store pilot owners. I would expand rollout only after duplicate/order/refund correctness and store-day reconciliation are demonstrated.

If this scope and the proposed defaults sound reasonable, Priya can capture decisions and we can start with the highest-risk checkout flow.

Thanks,
Vairag
