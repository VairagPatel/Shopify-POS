"""Build offline visual explanations and GitHub-readable diagrams for the final review."""

import html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = [
    ("M1", "Customer and latest valid prescription", "A phone entered with or without +91 must identify the same existing person. Clinical selection must use the newest unexpired Rx, not just the first source row.",
     ["Cashier enters phone", "POST /api/customers", "Canonical +91 phone", "Shopify customer + SMT Rx", "Merge local clinical Rx", "Select latest valid Rx"],
     "CustomerLookupRequest → PhoneNumber → CustomerLookupResponse. Sale preparation uses Prescription/EyePower and latest_valid_prescription.",
     "Customer comes from the Shopify mock; source prescriptions from the store tool; newly entered clinical records from SQLite. Phone is in the request body. Wrapper extensions keep upstream lookup private; they are not official Shopify APIs.",
     "Unknown customer: 404. Invalid phone: 422. No valid Rx blocks lens billing. Example: 9000000005 and +919000000005 normalize identically; validity/issue date decides which Rx is used.",
     "Explain: We fetch existing identity and clinical data; we do not create a customer when Add wearer is clicked. Tests: test_phone_privacy.py, test_foundation.py."),
    ("M2", "Frame + lens selection and clinical validation", "A configured lens is a product variant selected by type, index and coating. A valid variant can still be clinically wrong for this wearer.",
     ["Choose frame + lens", "Resolve source variants", "Attach wearer / pair", "Load lens limits", "Validate sphere/cylinder/ADD", "Accept or block with reason"],
     "POST /sales/prepare: PrepareRequest and WearerSelection → Cart/CartLine, Prescription, LensConfiguration → ValidationResult.",
     "Source variant metadata supplies lens type/index/coating, HSN and Rx limits. Inventory is checked at the billing location. Every family lens retains its own wearer and rx_id.",
     "Reject out-of-range sphere/cylinder, expired Rx, missing progressive/bifocal ADD, incompatible frame or insufficient stock before money moves. Three family wearers may share one payer and invoice, not one prescription.",
     "Explain: The server validates clinical compatibility, so bypassing the screen does not bypass the rule. Tests: test_foundation.py, test_multi_pair.py."),
    ("M3", "Offers, dates, conditions and stackability", "Discounts must follow configured rules rather than cashier guesses. The stakeholder's desired universal stacking still needs business agreement.",
     ["Read offers.json", "Check active/date/tag/pair", "Evaluate eligible rules", "Compare allowed combinations", "Allocate exact line discounts", "Persist decision + reason"],
     "SaleService → evaluate_offers(Cart, Customer, rule data) → OfferResult / OfferDecision.",
     "Rules come from exercise-pack/starter-kit/data/offers.json. Normal changes to dates, amounts and conditions are data changes. New rule families may need code. Manager authorization and mandatory reason are independently enforced.",
     "Example: an expired promotion is rejected even if the customer expects it. The current documented policy compares eligible stackable discounts with the highest-priority eligible non-stackable option. Approval of exact stacking examples remains a business decision.",
     "Explain: We show why each offer applied or did not apply, and preserve allocations for tax/refunds. Tests: test_stage4.py."),
    ("M4", "Inclusive GST and exact line arithmetic", "MRP already includes GST. The invoice separates the discounted price into taxable value, CGST and SGST without losing a paisa.",
     ["Gross MRP in paise", "Subtract line discount", "HSN + effective date", "Extract taxable amount", "Split tax deterministically", "Sum invoice invariants"],
     "TaxCatalog.rate_for → inclusive_tax_line → TaxLine → invoice_totals.",
     "HSN and billing date select one effective rate from tax_rates.json. Internal money is integer paise; decimal currency strings are created at provider boundaries.",
     "Illustrative rate, not a legal rate claim: ₹112 payable at 12% gives ₹100 taxable and ₹12 tax. If tax is an odd number of paise, assign the remainder deterministically so taxable + CGST + SGST still equals payable. Missing/overlapping effective rates fail validation.",
     "Explain: We do not add GST on top of an already inclusive price. Refunds reverse original values. Tests: test_stage4.py."),
    ("M5", "Payment, source order and store invoice", "One bill must connect local workflow, terminal outcome, source order and a store-specific invoice number. A payment alone is not a completed source sale.",
     ["Persist quote + invoice", "Recheck stock", "Claim payment_pending", "Charge terminal / cash", "POST source order", "Save order ID + receipt"],
     "POST /sales/prepare → POST /sales/{checkout_id}/complete → GET /checkouts/{checkout_id}. SaleGateway delegates provider payload assembly to the Shopify mapping adapter.",
     "Order write contains items, taxes, discounts, successful transaction, lens Rx properties, store location and invoice/checkout references. Invoice series belongs to our DB; source order number belongs to Shopify. They are different identifiers.",
     "Charge timeout → payment_uncertain. Order timeout → order_uncertain. Do not press a new charge action to recover an unknown result. A repeated completion after order_recorded returns the saved result.",
     "Explain: The state is saved before external writes. We never claim a cross-system atomic transaction. Tests: test_stage5.py, test_production_matrix.py."),
    ("M6", "Full refund, original tax and correct stock", "Refund the original sale and record it in Shopify. A frame returns to the store that billed it; made-to-order lenses are not restocked.",
     ["Read original source sale", "Calculate full reversal", "Verify amount + original tax", "Persist refund attempt", "Refund terminal / cash", "Record source refund"],
     "POST /refunds/prepare → POST /refunds/{refund_id}/complete. RefundGateway calls source calculation, terminal reversal and source refund recording.",
     "The payload links the sale transaction and local refund reference. Original source line tax is used rather than today's rate. A linked printable credit-note context is available; production document approval remains separate.",
     "Example: an HSR frame return restores HSR inventory, never HQ by default. Lens stock does not increase. Source refund timeout is reconciled by refund reference, not a second terminal refund. Partial returns are explicitly deferred in the agreed scope.",
     "Explain: Payment reversal and source inventory/tax recording are distinct steps with persisted progress. Tests: test_stage6.py."),
    ("M7", "Store/date day-end and central totals", "Finance needs a report derived from source orders, not merely local success screens. Leadership also needs the combined total.",
     ["Choose store + India date", "Read source orders", "Filter valid store sales", "Sum gross/discount/tax", "Sum refunds + methods", "Return reconciled report"],
     "GET /reports/day-end (see live Swagger for parameters) uses DayEndService; GET /api/reports uses central/store analytics. Confirm the route name against the endpoint appendix.",
     "Output includes bill count, gross, taxable, tax, discounts, refunds and payment-method totals. India timezone conversion now handles an evening UTC transaction belonging to the following local day. The mock's bounded order cap fails explicitly rather than silently truncating a certified report.",
     "The Must report includes refunds on the selected sale cohort, regardless of refund day, and labels that policy. Cash-event-date analytics answers a different question. Combined average = summed sales / summed bill count, not average of store averages.",
     "Explain: Two stores with ₹10,000/2 bills and ₹8,000/1 bill give ₹18,000, 3 bills, ₹6,000 average. Tests: test_stage6.py, test_submission_gaps.py."),
    ("S1", "Cash till, paid-ins, paid-outs and close", "Physical cash must be explainable independently of card/UPI totals.",
     ["Open with float", "Record cash sales/refunds", "Add reasoned paid-in", "Record reasoned paid-out", "Count physical cash", "Close + variance alert"],
     "POST /api/till/open, /api/till/paid-in, /api/till/expense, /api/till/close; GET /api/till. Positive movement amounts and reasons are required; store/role guards apply.",
     "Expected = opening + cash sales + paid-ins − cash refunds − paid-outs. Movements retain actor and time. Paid-ins use an additive table; existing expenses/data are preserved.",
     "₹1,000 opening + ₹500 paid-in − ₹100 courier = ₹1,400 expected. Count ₹1,400 → zero variance. Absolute variance over ₹200 queues notification. Unresolved financial operations block close.",
     "Explain: A cash top-up is not a sale and must not inflate revenue. Tests: test_submission_gaps.py and endpoint authorization matrix."),
]

CLASS_GROUPS = [
    ("Customer", ["customer_id, phone, tags"], "Identity used by cart and offers"),
    ("Prescription", ["prescription_id, customer_phone", "right / left: EyePower", "valid_until, issued_at"], "Selected for each lens wearer"),
    ("LensConfiguration", ["lens_type, index, coating", "variant_id"], "Validated against Rx and metadata"),
    ("Cart", ["customer_id, store_code", "lines: tuple[CartLine]"], "Contains 1..many lines"),
    ("CartLine", ["variant_id, quantity, unit_price_paise", "product_kind, pair_ref", "prescription_id"], "Connects product, pair and wearer Rx"),
    ("TaxLine / OfferResult", ["taxable, CGST, SGST, discount", "OfferDecision + allocations"], "Pure rule calculation results"),
    ("SaleService", ["prepare(), complete()", "reconcile_order()"], "Uses SaleGateway + SQLiteStore"),
    ("RefundService", ["prepare(), complete()", "reconcile_shopify()"], "Uses RefundGateway + SQLiteStore"),
    ("DayEndService", ["report(store_code, day)"], "Uses ReportingGateway"),
    ("Gateway Protocols", ["Sale / Refund / Reporting", "Commerce / StoreTool / Terminal"], "Injected operation capabilities"),
    ("MockHTTP / OperationsGateway", ["HTTP reads/writes", "local Rx overlay", "build_order_payload()"], "Raw source transport; BillingAdapter projects neutral records"),
    ("SQLiteStore", ["save_quote(), change_status()", "reserve_invoice(), get_refund()"], "Durable state and invoice allocation"),
]


# Escape all content embedded in generated HTML/SVG.
def escape(value):
    return html.escape(str(value))


# Draw a readable left-to-right flow with each step individually numbered.
def flow_svg(nodes, title):
    width = 1140
    parts = [f'<svg viewBox="0 0 {width} 180" role="img" aria-label="{escape(title)}"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="#bd6126"/></marker></defs>']
    import textwrap
    for index, label in enumerate(nodes):
        x = 8 + index * 190
        if index:
            parts.append(f'<path d="M{x-20} 90 H{x-3}" stroke="#bd6126" stroke-width="2" marker-end="url(#arrow)"/>')
        parts.append(f'<rect x="{x}" y="25" width="168" height="125" rx="10" fill="#edf0e6" stroke="#adb9aa"/><text x="{x+14}" y="52" fill="#ad541d" font-size="17" font-weight="700">{index+1:02}</text>')
        for line, text in enumerate(textwrap.wrap(label, 20)):
            parts.append(f'<text x="{x+14}" y="{78+line*20}" font-size="13" fill="#203b35">{escape(text)}</text>')
    return ''.join(parts)+'</svg>'


# Draw actual domain associations with field lists and labelled relationships.
def class_svg():
    nodes = [
        (20, 20, 'Customer', ['customer_id : str', 'phone : str', 'tags : tuple']),
        (390, 20, 'Cart', ['customer_id : str', 'store_code : str', 'lines : tuple[CartLine]']),
        (760, 20, 'CartLine', ['variant_id, quantity, price', 'pair_ref, product_kind', 'prescription_id : optional']),
        (760, 280, 'Prescription', ['prescription_id, phone', 'right, left : EyePower', 'valid_until, issued_at']),
        (390, 280, 'EyePower', ['sphere, cylinder', 'axis : optional', 'add : optional']),
        (20, 280, 'LensConfiguration', ['lens_type, index, coating', 'variant_id']),
    ]
    output = ['<svg viewBox="0 0 1080 490" role="img" aria-label="Domain class diagram"><defs><marker id="classarrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0 L8 4 L0 8" fill="#bd6126"/></marker></defs>']
    for x,y,name,fields in nodes:
        output.append(f'<rect x="{x}" y="{y}" width="290" height="155" rx="6" fill="white" stroke="#203b35"/><path d="M{x} {y+40} H{x+290}" stroke="#203b35"/><text x="{x+14}" y="{y+27}" font-weight="700" font-size="18">{name}</text>')
        for index,field in enumerate(fields):
            output.append(f'<text x="{x+14}" y="{y+69+index*25}" font-size="14">{escape(field)}</text>')
    for path in ['M310 90 H385', 'M680 90 H755', 'M905 175 V275', 'M760 355 H685']:
        output.append(f'<path d="{path}" fill="none" stroke="#bd6126" stroke-width="2" marker-end="url(#classarrow)"/>')
    for x,y,label in [(320,77,'payer'),(690,77,'1..many'),(916,224,'Rx ID'),(687,343,'2 eyes')]:
        output.append(f'<text x="{x}" y="{y}" font-size="13">{label}</text>')
    output.append('<text x="20" y="220" font-size="15">LensConfiguration + Prescription + lens metadata → validate_lens() → ValidationResult</text>')
    output.append('<text x="20" y="475" font-size="14">ID relationships describe linkage; they are not all nested objects or enforced SQL foreign keys.</text></svg>')
    return ''.join(output)


# Build an offline presentation and actual Mermaid class/sequence sources for GitHub.
def main():
    mermaid = '''# Submission diagrams — current implementation

These diagrams describe the implemented demo. Core services use BillingAdapter neutral records and repository ports; operational UI projections still describe the current integration. Not all database relationships are enforced foreign keys.

## Class relationships

```mermaid
classDiagram
Customer "1" --> "0..*" Cart : payer
Cart "1" *-- "1..*" CartLine : lines
CartLine --> Prescription : optional Rx ID
Prescription *-- EyePower : right and left
CartLine --> LensConfiguration : lens variant
SaleService ..> Cart : builds
SaleService ..> TaxLine : calculates
SaleService ..> OfferResult : evaluates
SaleService --> SaleGateway : injected
RefundService --> RefundGateway : injected
DayEndService --> ReportingGateway : injected
SaleService --> SQLiteStore : saves intent
RefundService --> SQLiteStore : saves reversal
BillingAdapter ..|> SaleGateway : structural protocol
BillingAdapter ..|> RefundGateway : structural protocol
BillingAdapter ..|> ReportingGateway : structural protocol
OperationsGateway --|> MockHTTP : clinical overlay
BillingAdapter --> ShopifyMapping : serialization
BillingAdapter --> MockHTTP : source transport
SaleService --> SaleRepository : durable port
RefundService --> RefundRepository : durable port
SQLiteStore ..|> SaleRepository
SQLiteStore ..|> RefundRepository
class SaleService {
  prepare()
  complete(checkout_id)
  reconcile_order(checkout_id)
}
class RefundService {
  prepare()
  complete(refund_id)
  reconcile_shopify(refund_id)
}
class SQLiteStore {
  save_quote()
  change_status()
  reserve_invoice()
}
```

## Payment/order sequence

```mermaid
sequenceDiagram
actor Cashier
participant API
participant SaleService
participant DB as SQLiteStore
participant Terminal
participant Shopify
Cashier->>API: POST /sales/prepare
API->>SaleService: authenticated preparation
SaleService->>Shopify: read customer, variant, store, stock
Note over SaleService: Rx from store tool; validate offers and tax
SaleService->>DB: persist quote and invoice allocation
API-->>Cashier: checkout_id and totals
Cashier->>API: POST /sales/{id}/complete
SaleService->>Shopify: recheck inventory
SaleService->>DB: claim payment_pending
SaleService->>Terminal: one charge
alt definite result
Terminal-->>SaleService: charge_id
SaleService->>DB: persist captured state
SaleService->>Shopify: create paid order
Shopify-->>SaleService: order_id
SaleService->>DB: record source ID and completion
API-->>Cashier: invoice
else timeout
SaleService->>DB: uncertain state
API-->>Cashier: inspect/reconcile, do not recharge
end
```

## Recovery states

```mermaid
stateDiagram-v2
[*] --> draft
draft --> payment_pending
payment_pending --> payment_captured
payment_pending --> payment_uncertain
payment_captured --> order_pending
order_pending --> order_recorded
order_pending --> order_uncertain
order_uncertain --> order_recorded: one source match
order_uncertain --> reconciliation_required: duplicate matches
```
'''
    for key, title, _, nodes, *_ in STEPS:
        mermaid += f'\n## {key}: {title}\n\n```mermaid\nflowchart LR\n'
        mermaid += '\n'.join(f'  n{i}["{label}"]' for i,label in enumerate(nodes))+'\n'
        mermaid += '\n'.join(f'  n{i} --> n{i+1}' for i in range(len(nodes)-1))+'\n```\n'
    (ROOT/'docs/SYSTEM_DIAGRAMS.md').write_text(mermaid,encoding='utf-8')
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Eluno · submission walkthrough</title><style>
*{box-sizing:border-box}body{margin:0;background:#f7f5ed;color:#203b35;font:17px/1.7 system-ui}header{background:#203b35;color:#fff;padding:50px max(24px,calc((100% - 1180px)/2))}h1{font-size:clamp(32px,4vw,52px);line-height:1.2}nav{background:#e9edde;padding:16px;display:flex;gap:15px;flex-wrap:wrap;position:sticky;top:0;z-index:1}a{color:#a84e17}main{max-width:1180px;margin:auto;padding:24px}section{padding:25px 0;border-bottom:1px solid #ccd2c3;scroll-margin-top:110px}h2{font-size:30px}h3{margin-bottom:6px}.diagram{overflow:auto}.diagram svg{min-width:950px;width:100%;font-family:system-ui}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.card{background:#fff;padding:18px;border:1px solid #cbd2c4;border-radius:9px}.card h3{margin-top:0}.note{border-left:5px solid #f88e2b;background:#fff0dc;padding:18px}button{border:0;background:#b65a1e;color:white;padding:10px;cursor:pointer}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#213b35;color:white;padding:20px;font:14px/1.7 monospace}details{margin:14px 0}summary{cursor:pointer;font-weight:700}.columns{display:grid;grid-template-columns:1fr 1fr;gap:20px}@media(max-width:700px){.grid,.columns{grid-template-columns:1fr}nav{position:static}h2{font-size:26px}}@media print{nav,button{display:none}header{background:white;color:#203b35;padding:0}body{font-size:11pt;background:white}.diagram svg{min-width:0}.diagram{overflow:visible}section{break-before:page}.card{break-inside:avoid}h2,h3{break-after:avoid}main{padding:0}}
</style><header><small>FINAL REVIEW · 26 OCTOBER 2026</small><h1>Explain every requirement.<br>Follow every important step.</h1><p>System view · classes · seven Must journeys · cash controls · interview answers</p></header><nav><a href="#system">System</a><a href="#classes">Classes</a>'''
    page += ''.join(f'<a href="#{key}">{key}</a>' for key,*_ in STEPS)
    page += '<a href="#recovery">Recovery</a><button onclick="document.querySelectorAll(\'details\').forEach(x=>x.open=true);window.print()">Print / Save PDF</button></nav><main><p class="note">Scope agreed: Must + constraints + cash paid-ins. Partial refunds and Stretch are deferred. Local mocks demonstrate provider behavior; no real money moves. Core workflows use provider-neutral records. Legacy source snapshots and UI integration views remain documented migration concerns.</p>'
    page += '<section id="system"><h2>1. Start with the problem and system</h2><p>Replace Shopify POS at the till, while Shopify remains the source for orders, transactions, inventory and refunds. The store tool supplies clinical context. Our backend validates and coordinates the work; both frontend and Swagger call it.</p>'+flow_svg(['Frontend / Swagger','Authenticated API','Domain rules + workflows','Local durable state','Provider adapters','Shopify / SMT / terminal'],'System boundaries')+'<p>The arrows summarize responsibilities, not a literal serial call to every component. Source reads happen before payment; database writes surround external side effects. Email scheduling is a separate outbox workflow.</p></section>'
    page += '<section id="classes"><h2>2. Classes and relationships</h2><div class="diagram">'+class_svg()+'</div><div class="grid">'
    for name,fields,relationship in CLASS_GROUPS:
        page += f'<article class="card"><h3>{escape(name)}</h3><code>{"<br>".join(escape(f) for f in fields)}</code><p>{escape(relationship)}</p></article>'
    page += '</div><pre>Customer ──payer──► Cart ──contains 1..many──► CartLine\nPrescription ──contains──► EyePower (right and left)\nCartLine ──Rx identifier──► Prescription\nSaleService ──uses──► SaleGateway ◄──implemented by── BillingAdapter\nRefundService ──uses──► RefundGateway ◄──implemented by── BillingAdapter\nDayEndService ──uses──► ReportingGateway\nOperationsGateway ──inherits──► MockHTTP\nSaleService / RefundService ──persist through──► SQLiteStore</pre><p>The class cards describe real classes. The CartLine links are identifier relationships, not nested object composition. Protocol implementation is structural. ShopifyMapping in the GitHub diagram represents the mapping module, not a runtime class.</p></section>'
    for key,title,problem,nodes,contract,source,failure,pitch in STEPS:
        page += f'<section id="{key}"><small>REQUIREMENT {key}</small><h2>{escape(title)}</h2><p>{escape(problem)}</p><div class="diagram">{flow_svg(nodes,title)}</div><div class="columns"><div><h3>API and classes</h3><p>{escape(contract)}</p><h3>Where data comes from / goes</h3><p>{escape(source)}</p></div><div><h3>Example and failure scenarios</h3><p>{escape(failure)}</p><h3>What to say in the interview</h3><p>{escape(pitch)}</p></div></div></section>'
    page += '<section id="recovery"><h2>Recovery, constraints and reviewer questions</h2><pre>draft → payment_pending → payment_captured → order_pending → order_recorded\n                ↓                                 ↓\n        payment_uncertain                  order_uncertain\n        investigate terminal               read source by checkout reference\n                                           1 match: recorded\n                                           0 matches: remain uncertain\n                                           many: manual reconciliation</pre><p>There is no distributed transaction. A saved reference does not create a provider idempotency guarantee. Safe GET retries and durable operation claims prevent blind repeats; uncertain writes require verification.</p><details open><summary>If Shopify is replaced in 2027?</summary><p>Pure clinical, offer and tax rules remain. Replace integration calls and mappings, migrate source identifiers and rerun contract/reconciliation tests. The final core boundary uses neutral records and repository ports. A replacement-provider sale/refund/report test proves the business workflows can stay unchanged. Whole-product replacement also needs data migration and updating source-specific UI projections; it is not just changing a URL.</p></details><details open><summary>How do we prove the features?</summary><p>Run the automated suite, then show a valid sale, rejected lens, dated/stacking offer, exact line tax, source order, repeated completion, full refund with original-store restock, date report and cash movement. Use fresh isolated data for tests. Final counts and commands are in FINAL_REQUIREMENT_AUDIT.md.</p></details><details open><summary>What is intentionally deferred?</summary><p>Partial refunds and all three Stretch options. A screen is optional. Real Shopify onboarding, payment production approval, seven-store rollout and guaranteed ten-second production billing are not exercise completion claims. Record the Loom and check repository access separately.</p></details></section></main></html>'
    (ROOT/'app/static/submission-walkthrough.html').write_text(page,encoding='utf-8')
    print('Built offline walkthrough: 8 requirement flows, 12 class cards, GitHub Mermaid diagrams.')


if __name__ == '__main__':
    main()
