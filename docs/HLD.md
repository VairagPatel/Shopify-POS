# Eluno billing platform — detailed problem-led HLD

Snapshot: 26 October 2026. Final submission updates and test evidence: docs/FINAL_REQUIREMENT_AUDIT.md. Audience: founder, product, tech lead, retail, optometry, finance and operations. IMPLEMENTED means tested demo behavior against supplied mocks. PROPOSED means a production design or policy that has not been implemented or approved. OPEN means stakeholder input is required.

## 1. Problem statement

Eluno must replace the app at the till while retaining Shopify as its system of record. The brief describes seven Bengaluru stores, about 350–400 daily walk-ins across them, about 120 bills and an average bill near ₹5,400. Frames are stocked by location; prescription lenses are made to order. The website and finance continue to rely on Shopify.

Current pain points are manual discounts, clinical mistakes, multiple family bills, weak drawer tracking, unclear sales channels and unreliable reconciliation. Interruptions can leave staff unsure whether a payment or order succeeded. The solution must improve the whole transaction, not only the screen.

Success means a clinically valid and correctly priced bill becomes a traceable payment and source order; returns reverse the correct money, tax and stock; staff can recover safely; finance and leadership see consistent results. The requested 15 November launch is a business deadline, not evidence that live readiness has been achieved.

## 2. Proposed solution and scope

Use one modular billing application shared by the frontend and Swagger. It reads customers/catalog/stock from the Shopify mock, prescriptions/staff from the store tool, applies local rules, persists intent, charges the terminal and writes the order/transaction back to Shopify. Reporting reads source orders and refunds rather than treating local checkout rows as the financial ledger.

Exercise Must scope: customer and valid Rx lookup; validated frame/lens cart; configured offers; inclusive GST by line; payment then source order with store invoice; full refund with correct tax/restock; store day-end from source orders. UI is optional in the exercise but useful for explaining the process. The newer assignment email's 72-hour submission window supersedes the older pack's 48 hours.

Implemented extensions include family billing, roles, local clinical entry, manager controls, lens-only sales and remakes, cash expenses/close, central reports, printable documents, audit and notification outbox. Lens-only sales still require the wearer's current compatible prescription and never reserve frame stock. Deferred work includes live integrations, customer registration, partial refunds, full online-pickup fulfilment, guaranteed offline payment, queue-tool edits and camera repair. A selected sales-channel label does not implement an entire omnichannel order lifecycle.

## 3. Stakeholder requirement map

Founder: retain Shopify, show priority/campaign context, complete billing quickly, roll out seven stores and send the 10 am digest. Design response: source write-back, source context on billing, measured workflow timings, central reporting and durable notification jobs. Live performance and rollout are not proven by the demo.

Retail: stack offers, authorize up to 10% manager discount without a slow approval chain, bill a family together, report channels and record drawer expenses. Design response: configured pricing engine, authenticated manager identity/reason, wearer-specific lines, order channel metadata and local cash records. Exact offer stacking still requires agreement.

Optometry: block incompatible lens choices, use five-degree entry increments and support remakes without a frame charge. Design response: server-side clinical checks before payment, validated new entry and lens-only remake flow. Historical prescriptions must not be silently rounded.

Finance: HSN/effective-date tax, inclusive MRP, separate store invoice series, auditable discounts, source refunds and day-end reconciliation. Design response: integer-paise calculations, line snapshots, durable invoice register, original-tax reversal and source-derived reports. Legal documents and production finance policy still need approval.

Ops: restore returned frames to the original store, never restock custom lenses, avoid frame stock changes on remake, survive interrupted bills without duplicates. Design response: location-aware refund payloads, lens-only transactions and persisted pending/uncertain states. Seamless recovery from every terminal outcome is not implemented.

Separate owners: the beverage question belongs to the queue-tool team; the camera issue belongs to facilities/vendor support. Track them explicitly without presenting them as POS completion.

## 4. Conflicts and policy decisions

Speed versus audit: an authorized manager approves directly within the limit using their session and a reason. No separate approval chain is necessary, but a cashier cannot supply a manager's name as authorization.

Stacking versus margin: Meena and Vikram must approve the eligible items, application order, caps, second-pair definition and manager interaction for festive 10%, second-pair 50% and priority ₹500. The current engine follows supplied rules; it does not promise every offer always combines.

Ten seconds versus dependency time: agree what starts and stops the clock. A proposed p95 under ten seconds for an already prepared cart is a measurement proposal, not the same as an absolute ten-second promise. Report tail latency and failures, and agree whether customer terminal interaction counts.

Gapless invoices versus abandoned bills: retain reserved, issued and cancelled allocations, never recycle numbers. Finance must approve fiscal resets and document rules. Counting only successful sales cannot demonstrate a complete invoice series.

Clinical convenience versus exact records: five-degree input must not rewrite imported clinical facts. Dr. Iyer decides historical Rx handling, validity and remake approval. Customer registration, family-shared phones and phone changes also need explicit identity policy.

## 5. Actors and system boundaries

Cashier: build and complete permitted store bills. Manager: controlled overrides and remakes. Optometrist: clinical entry. Finance: reporting, registers and reconciliation. Admin: central administration. Store access is enforced in the backend, even when callers edit request bodies or URLs. A future founder-only read role should not automatically receive admin powers.

The customer is not a staff account. One payer can pay for several wearers. Every lens must keep its wearer's Rx association, rather than inheriting the payer's prescription.

Browser UI / Swagger → API authentication, CSRF and role/store checks → business services → persistence and external ports → Shopify, store tool and terminal adapters. A scheduler reads/writes the email outbox and sends through configured SMTP. The browser and every external response are validation boundaries.

## 6. Logical architecture

Presentation: frontend cart, clinical selection, invoice, report and exception views. Swagger demonstrates the same contracts. Clients display results; they do not authoritatively calculate the final price or grant roles.

Application layer: sale preparation/completion, refund, remake, till and reporting use cases. It orders side effects and records recoverable state. Pure domain functions handle clinical suitability, offers and tax without network calls.

Ports: SaleGateway, RefundGateway, ReportingGateway, CommerceGateway, StoreToolGateway and TerminalGateway define the methods actually available to orchestration. MockHTTP implements transport; OperationsGateway adds locally authored clinical records. Constructor injection lets tests supply an alternate implementation.

Persistence: SQLite stores workflow state, quotes, invoice allocation, authentication, local clinical records, till operations, audit and outbox. The demo does not use separate independently deployed microservices or distributed databases.

Current architecture qualification: gateway methods still exchange provider-shaped dictionaries, and some services assemble source payloads or access persistence details. These are active adapter contracts, not full provider independence. Proposed next step: typed domain DTOs plus explicit persistence ports and move provider serialization entirely into adapters.

## 7. Data ownership and synchronization

Shopify owns source customer identifiers, catalog, location inventory, orders, recorded payment transactions and refunds. The store tool owns existing source prescriptions and staff records. The terminal executes payments. Our application owns local workflow state, offers/tax configuration, store invoice allocation, cash operations and notification jobs. Locally entered Rx currently forms an overlay; its eventual clinical system of record is an open integration decision.

Synchronization means read source context → validate/calculate locally → execute payment → write source order → read source order for receipt/report/refund. It is not a full continuous mirror of Shopify. No generic bidirectional customer synchronization or production webhook processing is claimed.

Proposed live synchronization uses authenticated provider events, deduplication, processing checkpoints and scheduled reconciliation. Specify pagination, update ordering, freshness and deletion policies. A source event should trigger verified processing, not override local financial state without checks.

## 8. Conceptual information model

Customer payer → checkout → quote lines → wearer / frame-lens pair / prescription. Checkout → store invoice allocation, payment reference, Shopify order reference and full refund attempt. Store → till session → expenses and closing count. User → sessions, saved draft and audit. Outbox → message state and delivery result.

Different identifiers answer different questions: customer_id identifies a source person; rx_id a clinical record; checkout_id a workflow; payment_ref a payment attempt context; invoice_no a store document; shopify_order_id a source sale; refund_id a local reversal. Keep these separately linked. Conceptual links are not a claim that every relationship is a SQL foreign key.

The current database has 16 table declarations and stores some snapshots as JSON. It does not normalize all Shopify masters into local tables. A complete schema/endpoint inventory is available in the companion API/schema guide.

## 9. Customer and phone flow

POST /api/customers receives a JSON phone body, never a phone query from the current frontend. Supported ten-digit, +91, 91-prefixed and domestic-zero input formats normalize to one +91 representation. Existing-customer lookup returns customer plus source/local prescriptions; no match returns 404. The retired GET method returns 405.

The default upstream wrapper also uses body-based lookup. These are demo extensions, not official Shopify routes. Explicit legacy adapter mode still uses upstream query parameters and is not privacy-equivalent. A live provider needs an approved contract; a URL change alone is not a live integration.

Normalization solves formatting differences, not identity ownership. Historical imports are not silently rewritten. Shared family numbers, duplicate profiles, phone changes and OTP policy require design. Customer creation remains proposed, as requested. Phone remains sensitive in authorized responses/storage; TLS, restricted body logs and retention controls are production work.

## 10. Family cart and prescription flow

Resolve payer and each wearer; select source variants; identify the latest valid prescription for each lens; validate sphere/cylinder/ADD and expiry; associate wearer, Rx and pair with the correct line; block invalid combinations before payment with an actionable message.

Example: one parent pays for three family members. The bill has three pairs, with three distinct Rx associations. A progressive lens lacking required ADD is rejected even if the other wearers are valid. Changing the lens requires a new validated quote, not a local screen-only total change.

Frame stock is location-specific; lens metadata determines compatibility. A saved cart or quote is not an inventory reservation. Stock must be rechecked before payment, and production must address concurrent store/website demand rather than assuming a recheck is an atomic lock.

## 11. Pricing and tax flow

Read GST-inclusive source MRP → evaluate dated offers and stacking → validate any manager override → allocate discounts to lines → apply effective HSN rate → split taxable amount and CGST/SGST → persist totals and source payload before payment.

Invariant: each line's taxable + CGST + SGST equals line payable exactly; invoice payable equals summed lines. Integer paise and deterministic rounding avoid binary float money errors. Rate/offer data remains in configuration rather than constants; central constants describe application policies, not current GST rates.

Illustrative arithmetic only: ₹2,240 inclusive at an assumed 12% plus ₹1,180 at an assumed 18% gives ₹3,420 payable, ₹3,000 taxable and ₹420 tax. A permitted 10% on both becomes ₹3,078 payable, ₹2,700 taxable and ₹378 tax. Actual rates come from configured HSN data; these are teaching inputs, not tax advice or fixture claims.

Proposed production controls: approved promotion examples, configuration versioning, change review, quote expiry and explicit repricing rules. Refunds use original line tax, not today's rate.

## 12. Payment and order sequence

Prepare: resolve source records, validate cart and clinical rules, compute prices, reserve store invoice, persist quote and return checkout ID. Complete: load quote, recheck stock, save payment intent, claim the draft state, charge terminal or record cash, persist payment result, create Shopify order/transaction, save source ID, mark completed and present receipt.

Normal state path is draft → payment_pending → payment_captured → order_pending → order_recorded. Payment captured is not a completed source sale. Repeating completion of an already recorded checkout returns saved state; other started states require inspection instead of a second charge.

Source order includes line items, tax, discounts, clinical line properties, source location, invoice and checkout references, channel, staff and successful payment transaction. Multiple local writes and provider calls are involved; there is no distributed atomic transaction. A crash between steps can leave a pending state requiring recovery.

## 13. Failure and recovery architecture

Read failure before payment: stop safely and retry supported transient GET failures within bounded limits. The current private lookup POST is read-like but is not automatically retried by the generic GET-only retry policy.

Charge timeout: payment_uncertain; block automatic recharge. Order timeout after capture: order_uncertain; search source orders by checkout reference. One match resolves, none remains uncertain, several require manual review. Browser disconnect: reload checkout state rather than inventing a replacement sale.

Source refund timeout: reconcile by refund reference without repeating terminal refund. SMTP uncertainty: mark for review rather than blindly send twice. Process crash: use durable references and states; some repairs remain operational rather than fully automatic.

The supplied terminal does not guarantee idempotency just because a reference is supplied. Proposed live recovery requires provider-supported idempotency and status lookup, signed outcome events, aging-state monitoring and an approved staff runbook. Do not claim exactly-once behavior across all systems from local uniqueness constraints alone.

## 14. Invoice allocation and refund design

Reserve store invoice numbers under a serialized local transaction. Reuse the same allocation for the same checkout; never recycle numbers. Preserve reserved/issued/cancelled entries. Finance approves fiscal-year series, issuance timing, cancellation reasons, credit-note numbering and immutable document details. Issuance and source completion occur in separate steps, so recovery must verify both.

Full refund: read original recorded source order, calculate refund lines/tax, verify amount, persist attempt, refund terminal/cash, create source refund and save references. Frames return to the original billing location; custom lenses use no-restock. An HSR sale must not send frame stock to HQ by default. Original tax is reversed even after rates change.

The demo supports one full refund attempt per checkout; partial returns require a remaining-line-quantity/amount model. Refund-day collections and original-sale cohort views must be labelled separately. Shopify reconciliation does not replace bank/terminal settlement comparison.

## 15. Remake and lab boundary

Resolve original sale and wearer, capture reason/replacement lens/cost owner, validate the replacement Rx and prepare a lens-only transaction. Do not create a frame line or reserve frame stock. Recording an external optometrist as cost owner is not automatic collection from that party.

Clinical, ops and finance must agree reason-specific approvals, customer contribution, lab instructions, disposal and zero-charge document treatment. Full lab/QC/dispatch orchestration belongs to its own system; the till carries the necessary references and approved instruction data.

## 16. Cash drawer and store close

Open with counted float, account for cash sales/refunds and recorded paid-out expenses, calculate expected drawer balance and compare with physical count. Absolute variance over ₹200 queues finance notification. Exactly ₹200 is not over the threshold. Reasoned paid-ins now have their own additive table, API action and frontend movement selector, with regression tests.

Unresolved financial states block a misleading close in the demo. Proposed operations assign a manager to investigation and finance to approval of corrections. No adjustment should fabricate a balanced drawer without actor/reason evidence.

Reconcile the same location, Asia/Kolkata business day, refund-date definition and payment-method population. Agree treatment of late source records and post-close corrections. Source matching does not prove bank settlement, fees or chargebacks have reconciled.

## 17. Central reporting and email

Display combined totals as well as store breakdowns. Sum amounts and bill counts. Compute combined average bill value as combined sales divided by combined count, not an unweighted average of store averages. Two bills worth ₹10,000 in one store and one worth ₹8,000 elsewhere produce ₹18,000, three bills and ₹6,000 average.

The demo reads source orders and refuses to certify a report when the bounded mock order cap is reached. Proposed production needs full pagination or a reconciled reporting store, freshness timestamps and missing-store warnings. Missing data is not zero sales.

The daily digest targets 10:00 Asia/Kolkata and can catch up after that time when its process runs. Outbox delivery requires configured sender, recipients and SMTP. SMTP acceptance is not proof of inbox arrival. Production needs worker coordination, delivery monitoring and an agreed escalation policy.

## 18. Security and deployment

Implemented: password hashing, sessions, login throttling, CSRF and server-side role/store checks. Proposed: production TLS/cookie settings, secret rotation, minimum integration scopes, privileged-user policy, restricted backups, retention and body/APM log controls. Keep runtime credentials and sensitive snapshots out of Git.

Current deployment is one laptop/browser, one FastAPI application and scheduler, SQLite and local durable mocks. Proposed deployment is seven store clients and central users accessing a shared application/database, external adapters and coordinated workers. PostgreSQL is a possible future database, not an existing dependency.

Do not run independent local databases and call them a centralized multi-store system. In-process locks do not coordinate multiple workers. Multi-instance deployment needs shared transaction/state claims, scheduler ownership and tested invoice allocation. Keep the monolith modular until scale justifies additional services.

## 19. Performance, observability and support

Daily averages do not define peak capacity. Measure simultaneous confirmations, cart sizes, provider latency and website stock competition. Break timing into preparation, final validation, terminal interaction, source order and receipt. Prefetch stable data with freshness policies, but do not display a completed sale before its outcome is known just to improve timing.

Proposed telemetry correlates checkout, payment, invoice, store and source IDs without broad phone/clinical logs. Alert on aging pending/uncertain states, unmatched orders/refunds, invoice-register differences, stale reports and notification failures. Availability, recovery-time and recovery-point objectives remain business decisions, not measured promises.

Runbooks must name owners: store manager handles the customer, finance reconciles money/documents, ops resolves stock/lab issues and engineering investigates integrations. Never resolve unknown payment by deleting its checkout and charging again. Backup readiness requires a restore drill preserving state and invoice history together.

## 20. SOLID and ports-and-adapters assessment

Single responsibility: tax, offers, clinical validation, transport, shared money and shared errors have clear modules. The web module and sale orchestration still have multiple responsibilities; extraction of mapping and repository operations is the next improvement.

Open/closed: configured rates/offers change without ordinary code edits, and injected gateways allow alternate implementations. New offer families or providers can still require changes; this is not unlimited plug-in capability.

Liskov substitution: active Protocol contracts match adapter method names and are checked by tests. Runtime Protocol checks only verify member presence, not full behavior or type correctness. Alternate adapters must pass semantic contract tests for retries, money and uncertainty.

Interface segregation: sale, refund and reporting ports expose different required capabilities. Dependency inversion: services use those ports and domain errors rather than importing HTTP/SQLite error implementations. Complete hexagonal separation is still pending because provider-shaped dictionaries and concrete persistence access remain.

Naming means clear domain terms, not guessing whether a name looks AI-generated. Price-loop variables now identify variants, decisions, properties and line positions. Avoid cosmetic renaming of stable external fields or database columns without migration. Shared policy constants have one module; tax/offer records remain their own configuration data.

## 21. Delivery lifecycle and work packages

Requirements: map every stakeholder request, identify conflicts and assign decision owners. Design: document authority, APIs, states, invariants and failure recovery. Implementation: deliver the Must vertical flow, then justified extras. Verification: unit math/clinical tests, adapter tests, API authorization, browser/Swagger journeys and fault cases. Release: review changes, regenerate docs, provision secrets and prove deployment. Operations: monitor, reconcile, patch and restore-test.

Proposed work packages are scope/policy; source contracts; identity/access; clinical family cart; pricing/tax; payment/invoice; refund/remake; till/reconciliation; reports/email; recovery/observability; pilot; expansion. These are planning divisions, not a claim that historical Jira tickets exist. Each package needs an owner, acceptance examples and evidence.

Definition of done: documented behavior and known gaps, relevant passing tests, reviewed API/schema changes, no new privacy leak, repeatable run instructions, approved financial side effects and observable errors. Production done additionally needs live sandbox contracts, security/restore checks, business UAT and support ownership. Do not label a mock test as live-provider certification.

## 22. Validation and rollout gates

Demonstrate family bill with separate Rx, invalid lens rejection, denied cashier override, valid manager reason, exact tax rounding, repeated confirmation, interruption after charge, refund to original store, lens-only remake, cancelled invoice, drawer variance and central totals. Test no-phone URLs and equal results across supported phone formats. Include store isolation and source-report cap failures.

The previous recorded full suite passed 333 tests plus a private-wrapper browser check. The current refactor has its own test record in engineering review notes; these are demo evidence, not production latency or legal certification.

Pilot entry requires approved policies, real mappings and integration contracts, observable failures, trained users and a recovery runbook. Pilot exit requires an agreed observation period with no unexplained payments/orders, invoice positions or reconciliation differences. Thresholds and duration must be agreed rather than invented.

Expand store by store. Rollback routes new sales to an agreed fallback while preserving and resolving in-flight operations. It must not restore an old database over captured money or erase invoice history. Finance and ops coordinate old/new till usage to avoid duplicate billing.

## 23. Open decisions and presentation path

Rohan/Priya own timing definition and rollout gates; Meena/Vikram own stacking and overrides; finance owns fiscal documents, reporting cutoff and settlement; Dr. Iyer owns clinical rules and remake authorization; ops owns lab and stock procedures; integration owners confirm live API/payment guarantees; security/operations own privacy, retention, devices, recipients and recovery objectives.

Presentation: start with the broken store workflow; show source customer and Rx; show clinical/cart/offer/tax decisions; confirm payment and connect local checkout, invoice and source order; demonstrate refund and correct stock; show combined reporting; finish with uncertain recovery and remaining live work. Use Swagger to show the same backend flow without the frontend.

References: exercise-pack/brief/CANDIDATE_BRIEF.md, exercise-pack/brief/STAKEHOLDER_THREAD.md, the assignment email, STAKEHOLDER_REPLY.md, docs/LLD.md, docs/EXERCISE_MUST_AUDIT.md and the API/schema guide. This HLD is an explanation and proposal, not stakeholder sign-off.
