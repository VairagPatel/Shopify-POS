"""Generate a self-contained schema guide with the actual current OpenAPI inventory."""
import html
import json
import re
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.main import app


# Keep examples readable without allowing embedded data to become HTML.
def code(value):
    text = value if isinstance(value,str) else json.dumps(value,indent=2,ensure_ascii=False)
    return '<pre><code>'+html.escape(text)+'</code></pre>'


# Render comparison rows using authored HTML and escaped source values where needed.
def table(headers, rows):
    return '<div class="table-wrap"><table><thead><tr>'+''.join('<th>'+h+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+cell+'</td>' for cell in row)+'</tr>' for row in rows)+'</tbody></table></div>'


# Build a stable chapter anchor for the offline navigation.
def section(identifier, title, body):
    return f'<section id="{identifier}"><h2>{title}</h2>{body}</section>'


# Embed current schemas, source examples and operational boundaries in one reading artifact.
def main():
    schema=app.openapi()
    (ROOT/'docs/openapi-contract.json').write_text(json.dumps(schema,indent=2,ensure_ascii=False),encoding='utf-8')
    original=(ROOT/'app/static/founder-brief.html').read_text(encoding='utf-8')
    css=re.search(r'<style>(.*?)</style>',original,re.S).group(1)
    css+='pre{padding:20px;background:#23372e;color:#f4f5ea;border-radius:8px;white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;line-height:1.7;max-height:650px;overflow:auto}pre code{background:none;color:inherit;padding:0}.field{font-family:monospace;font-size:12px}summary{overflow-wrap:anywhere}.data-search[hidden]{display:none!important}@media print{pre{max-height:none;overflow:visible;background:#edf1e8;color:#23372e}pre code{color:inherit}.search-panel{display:none}}'
    parts=[]
    parts.append(section('start','1. Customer lookup is not customer creation', '''
    <p class="intro">The current “Add wearer” action adds an existing person to a bill. It does not create a new Shopify customer.</p>
    <p>We now call <code>POST /api/customers</code> with a JSON body. This remains a lookup despite using POST: the phone is private request input, so it should not appear in a query string.</p>
    '''+code({'phone':'9000000005'})+'''
    <div class="flow"><span>Enter phone</span><b>→</b><span>Normalize to +91</span><b>→</b><span>Find source customer</span><b>→</b><span>Read source + local Rx</span><b>→</b><span>Add wearer to bill</span></div>
    <p>A missing source customer returns <strong>404</strong>. The app does not invent a local customer or create a source account automatically. New-customer registration is described in chapter 6 as proposed work, as requested.</p>
    <div class="note">The previous <code>GET /api/customers?phone=...</code> contract is retired. It now returns 405. This is an intentional API compatibility change for privacy. Swagger, frontend lookup and automated callers were updated.</div>
    <p>A schema describes fields, types and validation. An API is the action that accepts or returns those fields. A database table is where selected records are stored. They are related but not interchangeable.</p>
    '''))
    parts.append(section('phone','2. One phone format everywhere',table(['Input example','Stored / used for lookup'],[
      ('9000000005','+919000000005'),('+919000000005','+919000000005'),('919000000005','+919000000005'),('09000000005','+919000000005'),('+91 90000-00005','+919000000005'),('(90000) 00005','+919000000005')
    ])+'''
    <p><strong>Rule:</strong> this demo accepts Indian mobile numbers only. Keep phone as a string, remove permitted formatting spaces/brackets/hyphens, recognize +91 / 91 / a leading domestic 0, then require ten digits beginning with 6–9. Store and compare the result as <code>+91</code> plus those ten digits.</p>
    <p>Reject missing values, numeric JSON values, letters, unsupported country codes, extra digits and non-ASCII digit lookalikes. We do not silently guess the country. Formatting is not proof that a phone belongs to the customer; no OTP verification is implemented.</p>
    '''+table(['Boundary','Current normalization'],[
      ('POST /api/customers','Typed CustomerLookupRequest → PhoneNumber → source lookup. Customer response uses the same normalized format.'),
      ('POST /sales/prepare','Normalize payer phone and every member phone, including direct SaleService calls.'),
      ('POST /api/prescriptions','Typed clinical request; save canonical phone alongside source customer_id.'),
      ('POST /api/remakes/prepare','Typed wearer_phone input uses the same rule.'),
      ('PUT /api/draft','Canonicalize wearer phone entries before saving the JSON draft.'),
      ('Source adapters / local Rx overlay','Normalize before querying source or the local prescriptions table.'),
      ('Browser cart','Use the normalized phone returned by the lookup, rather than saving the typed variation.')
    ])+'''
    <h3>Existing data is not silently rewritten</h3><p>The supplied seed already uses canonical phones. Saved historical orders, invoices and quotes are retained. This change is not a database-wide migration. If imported/old clinical records contain multiple formats, a controlled backfill and duplicate review is still needed; do not bulk-merge customers by phone without checking identity.</p>
    <h3>Use customer IDs as long-term identity</h3><p>A phone can change or be shared by a family. The source <code>customer.id</code> is a better long-term relationship key. The current exercise store-tool lookup is by phone; local clinical writes also retain <code>customer_id</code>. A production redesign should query/link prescriptions by customer ID and treat phone as a searchable contact field. That redesign is proposed, not implemented here.</p>
    '''))
    parts.append(section('privacy','3. Phone privacy: browser, adapter and logs', '''
    <div class="cards two"><article><span class="tag">Changed in this project</span><ul><li>Browser lookup uses POST JSON, no phone query parameter.</li><li>Standard runner enables body-based customer and prescription lookup extensions.</li><li>No automatic fallback to a phone-in-URL lookup.</li><li>Standard Uvicorn access logging strips query strings.</li><li>Durable mock wrapper logs only the request path, not query values.</li></ul></article><article><span class="tag amber">Still requires care</span><ul><li>POST is not encryption. Use HTTPS for deployed traffic.</li><li>Authorized users can inspect request/response bodies in browser tools.</li><li>Phone still exists in clinical/quote/source data, receipts, draft storage and permitted responses.</li><li>Proxy, tracing, error and analytics systems need their own redaction rules.</li><li>Bootstrap still returns the synthetic customer directory; production should minimize bulk exposure.</li></ul></article></div>
    <h3>Two external adapter modes—do not confuse them</h3>
    '''+table(['Mode','What is called','Meaning'],[
      ('Default application / run_demo.py','POST /eluno/customer-lookup<br>POST /eluno/prescription-lookup','JSON body contains the normalized phone. These are additive endpoints in our durable mock wrapper. They read the existing synthetic source records directly; no phone URL is constructed.'),
      ('Explicit legacy exercise mode','GET customers/search.json with query<br>GET /smt/prescriptions with phone','Original supplied mock contract. Opt in with ELUNO_PRIVATE_LOOKUP=0 only for compatibility/testing. It places phone upstream in the URL and does not meet the end-to-end no-phone-URL objective.'),
      ('Future live integration','Provider-approved body-based search or an approved privacy gateway','Not implemented. Our /eluno/* routes are not official Shopify APIs and must not be presented as such.')
    ])+'''
    <p>The supplied exercise mock file stays unchanged. Our wrapper adds the privacy routes and preserves the original routes. Direct <code>MockHTTP</code> defaults to the original exercise contract for low-level compatibility tests; <code>OperationsGateway</code>, used by the app, defaults to private lookup. A private lookup against an unextended source fails visibly; it does not fall back silently.</p>
    <p><strong>Limit of the guarantee:</strong> the updated app does not generate phone-bearing lookup URLs in private mode. We cannot prevent an obsolete client from manually sending a phone in any arbitrary URL, but the retired route rejects the old method and standard app/wrapper logs strip query values. Other infrastructure logs are outside this local change.</p>
    '''))
    parts.append(section('linkage','4. How a prescription gets attached to the customer and bill', '''
    <ol class="timeline"><li><strong>Resolve the customer.</strong><p>Phone input becomes <code>+919000000005</code>. Source lookup returns a stable customer ID, name, phone and tags.</p></li><li><strong>Read the prescription list.</strong><p>The adapter asks the store-tool source for records matching the canonical phone. OperationsGateway merges these with locally authored clinical records using that phone. Lookup returns the list; it does not attach every record to a bill.</p></li><li><strong>Create a clinical record if needed.</strong><p>An optometrist submits a typed prescription body. The backend resolves the source customer and adds <code>customer_id</code>, <code>rx_id</code>, issue timestamp and the authenticated optometrist identity. It saves this record locally. It does not send it to Shopify or write it back to the store tool.</p></li><li><strong>Select during sale preparation.</strong><p>For every lens, the backend finds the latest issued prescription whose <code>valid_until</code> has not passed. It checks both eyes, lens limits and required ADD. Source records are trusted as supplied; independent customer-ID consistency checking on imported source Rx records is not added by this change.</p></li><li><strong>Persist on the lens line.</strong><p>The quote stores the chosen <code>rx_id</code> and wearer phone. The source order lens line properties include <code>rx_id</code>, <code>wearer_phone</code> and lens configuration. Frame/lens pair references link items within a wearer.</p></li><li><strong>Keep historical evidence stable.</strong><p>A new prescription does not rewrite a completed invoice or its source order. A remake links to the original sale and creates a new lens-only checkout with the appropriate current validation.</p></li></ol>
    <div class="dependency">CustomerRecord.id → PrescriptionRecord.customer_id<br>Canonical phone → current source/local Rx lookup<br>PrescriptionRecord.rx_id → saved quote lens line → source order line properties</div>
    <h3>Clinical entry example</h3>
    '''+code({'phone':'9000000005','od':{'sph':'-2.00','cyl':'-0.50','axis':90,'add':'1.50'},'os':{'sph':'-1.75','cyl':'0.00','axis':90,'add':'1.50'},'valid_until':'2027-04-01'})+'''
    <p>Send to <code>POST /api/prescriptions</code>. <code>od</code> is right eye; <code>os</code> is left eye. Sphere, cylinder, axis and ADD are required for both eyes. Sphere, cylinder and ADD use quarter-diopter steps; axis is an integer from 5° to 180° in five-degree steps. Enter ADD as 0.00 when none is prescribed. The validity date must be today through two years ahead. The selected lens limits are checked again before the cart can be prepared.</p>
    <p>Do not send <code>customer_id</code> or an approver identity to impersonate another record: the current clinical handler determines those from the resolved source customer and authenticated user. The schema accepts only the documented input fields; existing source prescription records may contain extra fields such as PD and notes.</p>
    '''))
    customer=next(row for row in json.loads((ROOT/'exercise-pack/starter-kit/data/customers.json').read_text()) if row['phone']=='+919000000005')
    prescriptions=[row for row in json.loads((ROOT/'exercise-pack/starter-kit/data/prescriptions.json').read_text()) if row['phone']==customer['phone']]
    products=json.loads((ROOT/'exercise-pack/starter-kit/data/products.json').read_text())
    variants=[variant for product in products for variant in product['variants']]
    parts.append(section('records','5. Field-level records: what comes from where',table(['Record / important field','Source / type','Purpose'],[
      ('CustomerRecord.id','Source integer','Stable customer identity returned by customer lookup.'),('CustomerRecord.phone','Canonical string','Search/contact value; not a safe permanent person identifier.'),('CustomerRecord.tags','Comma-separated source string','Priority/campaign/offer tags; never assume they are a JSON array.'),('PrescriptionRecord.rx_id','Source or locally generated string','Identifies one issued prescription; referenced from sold lens lines.'),('PrescriptionRecord.customer_id / phone','Integer / canonical string','Clinical customer link and current lookup key.'),('PrescriptionRecord.od / os','Nested eye records','sph, cyl, axis and add; source values may be numbers or strings.'),('date / valid_until','Date or timestamp / date string','Issue-order selection and expiry check; date-only and aware issue timestamps are supported.'),('variant.id / inventory_item_id','Two distinct source integer IDs','Variant selects a sellable option; inventory item plus location identifies physical stock.'),('variant.eluno','Supplied custom metadata object','line_type, HSN, lens type/index/coating, Rx limits and frame compatibility.'),('Cart / CartLine','Internal domain objects','Customer, store, unit prices, quantity, pair reference and prescription ID used for rules.'),('TaxLine','Internal integer-paise fields','gross, discount, discounted total, taxable, CGST and SGST; not the source decimal-string payload.'),('checkout_id / invoice_no','Local generated strings','Operation tracking versus per-store invoice numbering.'),('payment_charge_id / shopify_order_id','External returned references','Link the local operation to actual terminal/source outcomes.'),('quote.order_payload','Saved source-shaped dictionary','Prepared order data before payment; completion adds the transaction.'),('Refund payload','Source-shaped dictionary','Original line IDs, return/no_restock, store location and refund transaction parent reference.')
    ])+'''
    <p>The examples below are supplied synthetic fixture records, not real customer data. They show actual source field names, including fields not directly used by billing. The source’s prescription list can include expired entries; the example is not a promise that it is the selected prescription today.</p>
    '''+''.join('<details><summary>'+name+'</summary>'+code(value)+'</details>' for name,value in [
      ('Customer source record',customer),('Prescription source record',prescriptions[0]),
      ('Frame variant record',next(row for row in variants if row['id']==91000003)),
      ('Lens variant record',next(row for row in variants if row['id']==91000083)),
      ('Lookup response shape',{'customer':{'id':customer['id'],'phone':customer['phone'],'first_name':customer['first_name'],'last_name':customer['last_name'],'tags':customer['tags']},'prescriptions':[{'rx_id':'SOURCE_OR_LOCAL_RX_ID','customer_id':customer['id'],'phone':customer['phone'],'date':'2026-10-25T10:00:00+05:30','valid_until':'2027-04-01','od':{'sph':'-2.00','cyl':'0.00','axis':None,'add':'1.50'},'os':{'sph':'-2.00','cyl':'0.00','axis':None,'add':'1.50'}}]})
    ])))
    parts.append(section('creation','6. Proposed new-customer registration — NOT IMPLEMENTED', '''
    <p>Current lookup returning 404 should lead to a clearly designed registration workflow, not a silent local insert. This is the proposed design for a future ticket; neither the endpoint nor the source create operation below is active.</p>
    <ol><li>Staff collects name, phone and any approved optional contact/consent fields.</li><li>Normalize phone and validate fields before attempting a source write.</li><li>Search for possible duplicates. A shared family phone is a business decision, not automatic proof of the same person.</li><li>Create the customer through the approved external customer-creation adapter using a body, stable request key and a reviewed duplicate/uncertain-response strategy.</li><li>Save/use the returned source customer ID. Do not report success when only a local record exists.</li><li>Then an optometrist creates/attaches a prescription using the stable customer ID and their own identity.</li><li>Only after that should lens billing proceed.</li></ol>
    <h3>Proposed body, not a current API contract</h3>
    '''+code({'proposed_endpoint':'POST /api/customer-registrations','implemented':False,'request_example':{'first_name':'Example','last_name':'Customer','phone':'9000000005','email':None,'accepts_marketing':False,'request_id':'CLIENT_GENERATED_UNIQUE_REGISTRATION_KEY'},'response_example':{'customer_id':'RETURNED_SOURCE_ID','phone':'+919000000005','created':True}})+'''
    <div class="note"><strong>Decisions before building:</strong> whether phone must be unique, whether family wearers share a payer contact, whether OTP is needed, which roles may create/edit, how phone changes propagate, required consent and how uncertain creates are reconciled. Do not claim a uniqueness guarantee without source and database enforcement.</div>
    <p>The supplied original mock has no customer-create route. A demo extension would have to be explicitly labelled and tested, just like our body-based lookup extension. Production creation would need a real provider contract.</p>
    '''))

    external=[
      ('POST /eluno/customer-lookup','Wrapper extension / default app','{phone: canonical string}','{customers: CustomerRecord[]}','Read source customer; none → empty list → app 404.'),
      ('POST /eluno/prescription-lookup','Wrapper extension / default app','{phone: canonical string}','{prescriptions: PrescriptionRecord[]}','Read source Rx list; local overlay merged by OperationsGateway.'),
      ('GET customers/search.json','Original exercise / legacy mode','query=phone:… in query string','{customers: CustomerRecord[]}','Privacy-incompatible upstream URL; original mock remains unchanged.'),
      ('GET /smt/prescriptions','Original exercise / legacy mode','phone in query string','{prescriptions: PrescriptionRecord[]}','Privacy-incompatible original store-tool read.'),
      ('GET locations.json','Source adapter','No body','{locations: [{id,name,eluno}]}','Store/location and invoice-prefix mapping; HQ is warehouse.'),
      ('GET products.json','Source adapter','limit query','{products: [{id,title,variants}]}','Bootstrap catalog; variants nested under product.'),
      ('GET variants/{id}.json','Source adapter','Variant ID path','{variant: {...}}','Authoritative price, inventory item ID, HSN and clinical metadata.'),
      ('GET inventory_levels.json','Source adapter','inventory_item_ids + location_ids','{inventory_levels: [{inventory_item_id,location_id,available}]}','Read availability; no stock reservation.'),
      ('GET /smt/staff','Store tool','store query','{staff: [{staff_id,store_code,can_override_discount,...}]}','Select/validate store staff.'),
      ('POST /terminal/charges','Terminal','{order_ref,amount_paise,method}','Charge record including charge_id','Financial write, sent once. UPI/card; cash bypasses terminal.'),
      ('GET /terminal/charges/{id}','Terminal adapter capability','Known charge ID path','Charge status record','Available adapter read; not a guarantee of automatic recovery if no charge ID was received.'),
      ('POST orders.json','Source adapter','{order: {customer,location_id,line_items,taxes_included,discount_applications,note_attributes,transactions,...}}','{order: source Order}','Paid sale and source stock decrement; local state links returned ID.'),
      ('GET orders.json','Source adapter','status=any, limit','{orders: Order[]}','Report/reconcile; report rejects capped results at 250.'),
      ('GET orders/{id}.json','Source adapter','Source order ID path','{order: Order}','Evidence and original refund/remake checks.'),
      ('POST orders/{id}/refunds/calculate.json','Source adapter','{refund: {refund_line_items}}','{refund: calculated lines and suggested transactions}','Prepare full amount/original-tax validation. Not the final refund write.'),
      ('POST /terminal/refunds','Terminal','{charge_id,amount_paise,reason}','Terminal refund record including refund_id','Returns electronic payment; do not blindly repeat uncertainty.'),
      ('POST orders/{id}/refunds.json','Source adapter','{refund: {refund_line_items,transactions,note,note_attributes}}','{refund: source Refund}','Record source reversal; frame return at original location, lens no_restock.')
    ]
    parts.append(section('external','7. Every external API used by the adapter', '<p>Unprefixed Shopify-style paths use <code>/admin/api/2026-10/</code> on the exercise mock. These are the routes used by our application/adapter, not an inventory of every unused mock-server capability. Request/response shapes below are compact; complete example records follow.</p>'+table(['Method/path','Boundary','Request','Response','Effect'],external)+'''
    <h3>Paid source order: important nested fields</h3>
    '''+code({'order':{'customer':{'id':80001005},'location_id':70000002,'taxes_included':True,'inventory_behaviour':'decrement_obeying_policy','source_name':'eluno-pos','line_items':[{'variant_id':91000083,'quantity':1,'price':'SOURCE_GROSS_PRICE_DECIMAL','total_discount':'LINE_DISCOUNT_DECIMAL','properties':[{'name':'line_type','value':'lens'},{'name':'hsn','value':'CONFIGURED_HSN'},{'name':'rx_id','value':'SELECTED_RX_ID'},{'name':'wearer_phone','value':'+919000000005'},{'name':'lens_config','value':'TYPE/INDEX/COATING'}],'tax_lines':[{'title':'CGST','rate':'HALF_RATE_FRACTION','price':'LINE_CGST_DECIMAL'},{'title':'SGST','rate':'HALF_RATE_FRACTION','price':'LINE_SGST_DECIMAL'}],'discount_allocations':[{'amount':'ALLOCATED_DECIMAL','discount_application_index':0}]}],'discount_applications':['APPLIED_SOURCE_DISCOUNT_OBJECTS'],'note_attributes':[{'name':'checkout_id','value':'LOCAL_CHECKOUT_UUID'},{'name':'invoice_no','value':'STORE_INVOICE_NUMBER'},{'name':'store_code','value':'HSR'},{'name':'staff_id','value':'S105'}],'transactions':[{'kind':'sale','status':'success','gateway':'razorpay_terminal','amount':'SAVED_TOTAL_DECIMAL','authorization':'CAPTURED_CHARGE_ID'}]}})+'''
    <p class="muted">Placeholders explain the mapping; this object is not executable sample pricing. Each actual item has calculated amounts and complete metadata. The prepared quote lacks the final payment transaction until completion. Phone remains in authorized order properties; removing phone from URLs does not remove it from the data model.</p>
    '''))

    policies=runpy.run_path(str(ROOT/'tests/endpoint_matrix.py'))['ENDPOINTS']
    policy={}
    for method,_,path,roles,_,_ in policies:
        policy.setdefault((method,path),set()).update(roles)
    inventory=''
    operation_count=0
    for path,operations in schema['paths'].items():
        for method,operation in operations.items():
            if method not in {'get','post','put','delete','patch'}:
                continue
            operation_count+=1
            roles=', '.join(sorted(policy.get((method.upper(),path),set()))) or ('Public' if path in {'/','/health','/auth/login'} else 'See route guard')
            inventory+=f'<details class="data-search"><summary><code>{method.upper()} {html.escape(path)}</code> — {html.escape(operation.get("summary",""))}</summary><p><b>Allowed roles:</b> {roles}</p><p>{html.escape(operation.get("description",""))}</p>'
            if path=='/api/till/{action}':
                inventory+='<p>Action-specific guard: open/expense allow cashier, manager, admin; close allows manager/admin. The union above does not grant cashier drawer close.</p>'
            inventory+='<h3>Parameters</h3>'+code(operation.get('parameters',[]))+'<h3>Request body</h3>'+code(operation.get('requestBody',{'body':'No request body declared'}))+'<h3>Responses</h3>'+code(operation.get('responses',{}))+'</details>'
    parts.append(section('internal','8. All internal app APIs: actual OpenAPI contracts','''
    <p>The following inventory is generated from <code>app.openapi()</code>. It includes each registered schema-visible method/path with its actual parameters, body and response schemas. Reusable <code>$ref</code> names resolve in chapter 9. Session cookie authentication and CSRF on every POST/PUT apply unless the route is public.</p>
    <p><strong>Documentation limit:</strong> some existing handlers return generic dictionaries and their response OpenAPI schema is empty/permissive. That is not a fully enforced output contract. We show the actual schema rather than inventing validation. Customer lookup and clinical inputs now have explicit nested models; other output contracts still need future tightening.</p><p>400/422 indicates invalid input; 401 no session; 403 permission/CSRF/store failure; 404 unknown record; 409 incompatible operation state; 502 upstream error. An HTTP error alone does not prove that an already-attempted external payment failed—inspect saved state.</p>
    <div class="search-panel tools"><label for="schema-search">Search API or schema</label><input id="schema-search" type="search" placeholder="customer, phone, refund, tax…"><button id="expand" type="button">Expand visible entries</button></div><p id="search-count" class="muted" aria-live="polite"></p>
    '''+inventory+'<p class="muted">Also available: /docs (Swagger), /openapi.json (machine-readable specification), /redoc (generated documentation route), /docs/oauth2-redirect and /static/* assets. These are framework/static routes rather than billing APIs; authorization follows the application’s public-path allowlist.</p>'))
    schemas=''
    for name,definition in sorted(schema['components']['schemas'].items()):
        required=definition.get('required',[])
        fields=[]
        for field,attributes in definition.get('properties',{}).items():
            shape=attributes.get('type') or attributes.get('$ref') or json.dumps(attributes.get('anyOf',{}))
            fields.append([html.escape(field),html.escape(str(shape)),'Yes' if field in required else 'No',html.escape(attributes.get('description',''))])
        schemas+=f'<details class="data-search" id="model-{name}"><summary>{html.escape(name)}</summary>'+table(['Field','Type/reference','Required','Meaning'],fields)+code(definition)+'</details>'
    parts.append(section('models','9. All reusable internal schema definitions',schemas))
    sql=[]
    for filename in ['app/persistence/sqlite.py','app/security.py']:
        text=(ROOT/filename).read_text()
        for match in re.finditer(r'CREATE TABLE IF NOT EXISTS\s+(\w+)\s*\(.*?\);',text,re.S):
            sql.append((match.group(1),match.group()))
    parts.append(section('database','10. Internal storage and relationships', '''
    <p>SQLite stores operational state, not a replacement copy of Shopify’s whole customer/product ledger. The SQL below is extracted from the current table definitions. Additional indexes and migrations are in the source files; the tills table also receives <code>baseline_json</code> through an additive migration.</p>
    '''+table(['Table/group','Relationship and meaning'],[
      ('users → sessions','Session username joins to provisioned account; token is stored hashed, with expiry and CSRF token. No phone is needed for staff login.'),
      ('prescriptions','rx_id identifies record; phone is canonical lookup key; payload JSON also contains customer_id and both eyes. No local customer table or enforced customer foreign key exists.'),
      ('drafts','One JSON cart per username; members contain canonical phone and selected variants. Not a source customer record.'),
      ('checkouts → checkout_quotes','checkout_id joins operation state to saved pricing/payload; customer_id links logically to the source customer.'),
      ('invoice_series → invoice_allocations','Store counter and checkout allocation preserve invoice numbers across reserved/issued/cancelled states.'),
      ('refunds','Links to checkout and source order; preserves amount, payload, state and external refund references.'),
      ('tills → expenses','Store drawer sessions, baseline source transaction IDs, counted/expected cash and reasoned expenses.'),
      ('audit / timings / outbox','Who acted and result metadata; completion measurements; saved notification body and status.')
    ])+''.join('<details class="data-search"><summary>'+html.escape(name)+'</summary>'+code(statement)+'</details>' for name,statement in sql)+'''
    <p><strong>Retention and data protection:</strong> current demo storage includes plaintext phone/clinical data in authorized payloads, browser drafts and the synthetic snapshot. Encryption at rest, retention/deletion policy, consent, staff access review and production-safe export rules are not implemented by moving lookup to POST.</p>
    '''))
    parts.append(section('verification','11. Verify and explain the change', '''
    <ol><li>Restart the runner so the backend, wrapper and Swagger schema load the new contract. Do not recreate the virtual environment.</li><li>Sign in, call <code>POST /api/customers</code> with <code>{"phone":"9000000005"}</code>. Confirm normalized phone and source customer ID.</li><li>Repeat with +91, 91 and leading-0 formats. The same customer and Rx list should return.</li><li>As optometrist, add a valid prescription using one format. As cashier, look up using another and prepare a lens bill. Verify chosen rx_id and wearer phone in saved quote/source payload.</li><li>Inspect browser Network: lookup URL contains only /api/customers; phone is in Request Payload. Private source calls use /eluno/* body routes.</li><li>Invalid/foreign number → 422; valid but unknown customer → 404; old GET customer route → 405; no session → 401; POST without CSRF → 403.</li><li>Check access logs contain paths without phone-bearing queries. Do not assume proxy/APM/body logging is redacted without its own verification.</li></ol>
    <h3>Run the application and targeted regression tests</h3>
    '''+code('.\\.venv\\Scripts\\python.exe run_demo.py --port 8001 --mock-port 8788\n.\\.venv\\Scripts\\python.exe -m pytest tests/test_phone_privacy.py tests/test_browser_roles.py -q')+'''
    <p>Regression cases cover canonical formats, invalid numbers, body-only wrapper requests, access-log redaction, same-customer clinical linkage and quote attachment. The wider role/endpoint suite protects the changed POST lookup and CSRF rules. See docs/PHONE_LOOKUP_CHANGE.md for the final recorded run result.</p>
    <div class="say"><span>Founder / tech-lead explanation</span><p>“We use a customer ID to identify the source record and a consistently formatted phone to find it. Prescriptions belong to that customer, and a specific Rx ID is attached to each sold lens. We moved phone lookup into request bodies; our demo wrapper supports the same privacy boundary without modifying the supplied exercise service.”</p></div>
    '''))
    nav=[('start','Lookup vs creation'),('phone','Phone standard'),('privacy','Privacy boundaries'),('linkage','Prescription attachment'),('records','Fields & examples'),('creation','Proposed registration'),('external','External API inventory'),('internal','Internal API inventory'),('models','All schema definitions'),('database','Database relationships'),('verification','Verification walkthrough')]
    javascript='''
    /** Search actual API/schema entries without changing the documented contract. */
    function filterSchemas(){const term=document.querySelector('#schema-search').value.toLowerCase();let count=0;document.querySelectorAll('.data-search').forEach(item=>{item.hidden=!item.textContent.toLowerCase().includes(term);if(!item.hidden)count++;});document.querySelector('#search-count').textContent=count+' API, model and table entries match.';}
    /** Expand contracts and clear filters for complete printing. */
    function preparePrint(){document.querySelector('#schema-search').value='';filterSchemas();document.querySelectorAll('details').forEach(item=>item.open=true);}
    document.querySelector('#schema-search').addEventListener('input',filterSchemas);
    document.querySelector('#expand').addEventListener('click',()=>document.querySelectorAll('.data-search:not([hidden])').forEach(item=>item.open=true));
    document.querySelector('#print').addEventListener('click',()=>{preparePrint();window.print();});window.addEventListener('beforeprint',preparePrint);filterSchemas();
    '''
    document='<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Eluno · API, schema and customer identity guide</title><style>'+css+'</style></head><body><aside><div class="brand">eluno<i>.</i></div><div class="eyebrow">API & schema guide</div><nav>'+''.join(f'<a href="#{anchor}">{i:02d} · {label}</a>' for i,(anchor,label) in enumerate(nav,1))+'</nav><button id="print">Print / save complete PDF</button></aside><main><header><span class="tag amber">IMPLEMENTATION + PROPOSED DESIGN</span><h1>One customer.<br><em>Clear identities.<br>Traceable records.</em></h1><p class="intro">Every lookup, phone format, prescription relationship and API boundary—explained with the actual schemas and source examples.</p><p>Snapshot: 25 October 2026 · '+str(operation_count)+' schema-visible operations · '+str(len(schema['components']['schemas']))+' reusable schemas · '+str(len(sql))+' table definitions.</p><div class="note">Existing-customer lookup and phone privacy are implemented changes. Customer registration and a full customer-ID-based clinical redesign are proposals. This guide labels the difference.</div></header>'+''.join(parts)+'<footer>Self-contained HTML. OpenAPI export: docs/openapi-contract.json. Source schemas: app/customer_schemas.py, app/phone.py, app/main.py, app/web.py and app/api_documentation.py. Generated by scripts/build_schema_guide.py.</footer></main><script>'+javascript+'</script></body></html>'
    (ROOT/'app/static/api-schema-guide.html').write_text(document,encoding='utf-8')
    print(f'Built schema guide: {operation_count} operations, {len(schema["components"]["schemas"])} schemas, {len(sql)} tables.')


if __name__=='__main__':
    main()
