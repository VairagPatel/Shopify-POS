# Acceptance checklist

Run these in the authenticated UI. Each operation uses synthetic data; no live money moves. Automated references are under `tests/` and the in-app coverage map is `app/requirements.json`.

- [ ] Anonymous access to business APIs returns 401; login works and logout revokes the cookie.
- [ ] Missing CSRF returns 403; cashier cannot request manager discounts, refunds, clinical writes or cross-store records.
- [ ] HSR guided customer shows priority/campaign tags and a valid prescription.
- [ ] A valid frame/lens quote shows applied and rejected offers before payment.
- [ ] A lens outside the prescription range is rejected before any charge.
- [ ] Three family wearers yield three Rx references on one six-line order and one invoice.
- [ ] Repeated successful completion returns the same order ID; uncertain completion is not blindly retried.
- [ ] Manager override rejects above 10% or missing reason; approved staff/reason persist on the order.
- [ ] A physical sunglass item bills with its configured HSN/GST without requiring an Rx.
- [ ] Invoice line taxable value + CGST + SGST equals discounted line total exactly.
- [ ] Cancelled drafts cannot be charged; their numbers remain in the register and are never reused.
- [ ] Full refund amount/tax match the original sale; frames return to the billing store and lenses do not restock.
- [ ] Credit note references the original invoice and source refund.
- [ ] Remake contains only a lens, preserves frame inventory, records original invoice/cost owner/lab cost/approver.
- [ ] Only a clinician/admin can enter new Rx; axis 91 fails and axis 90 succeeds.
- [ ] Cash sale without an open drawer fails; float + sales − refunds − expenses reconciles to expected cash.
- [ ] Only manager/admin closes a drawer; absolute variance >₹200 queues finance, exactly ₹200 does not.
- [ ] Store/channel report reads source orders; refunded money appears on refund event day in IST.
- [ ] Repeated founder digest generation creates one outbox entry for that date.
- [ ] SMTP-unconfigured UI says preview/queued, never sent; configured delivery has explicit status.
- [ ] Browser reload restores draft; app/mock restart preserves saved orders and inventory together.
- [ ] Completion samples/p95 are labeled local-mock measurements, not a production SLA.
- [ ] Role-bound store reads and linked checkout/refund endpoints reject cross-store access.
- [ ] GitHub submission contains no runtime credentials, databases, snapshots or environment secrets.

Production-only acceptance: real Shopify/terminal integration, terminal idempotency/status contract, settlement feeds, pagination, real invoice/credit-note approval, device/Wi-Fi pilot and seven-store rollout sign-off. Queue/camera requests remain separate workstreams.
