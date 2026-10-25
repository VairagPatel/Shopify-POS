/* Eluno Store Studio: same-origin browser client. Money is always integer paise. */
'use strict';
const state = {user:null, csrf:'', data:null, store:'HSR', page:'overview', category:'frame', search:'', activeWearer:0,
  cart:{members:[],payment_method:'upi',channel:'walk_in'}, quote:null, stock:{}, customerCache:{}, transactions:[]};
const root = document.querySelector('#app');
const modal = document.querySelector('#modal');
const navItems = [['overview','◫','Overview'],['billing','⊕','New sale'],['transactions','▤','Bills & returns'],['clinical','◎','Prescriptions'],['till','▣','Cash drawer'],['reports','↗','Store reports'],['evidence','✓','Demo & coverage'],['outbox','✉','Report outbox'],['audit','≡','Audit trail']];

/** Escape every server/user string before inserting it into HTML. */
function escapeHtml(value) { return String(value ?? '').replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character])); }
/** Format integer paise as inclusive INR without arithmetic in display strings. */
function money(value) { return new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:2}).format((value||0)/100); }
/** Make authenticated API calls and preserve meaningful validation messages. */
async function api(path, options={}) {
  const response = await fetch(path,{credentials:'same-origin',...options,headers:{'Content-Type':'application/json','X-CSRF-Token':state.csrf,...options.headers}});
  const result = await response.json();
  if (!response.ok) {
    if (response.status===401 && path!=='/auth/login') { state.user=null; renderLogin(); }
    const detail=result.detail;
    throw new Error(typeof detail==='string'?detail:Array.isArray(detail)?detail.map(item=>item.msg).join('\n'):JSON.stringify(detail||result));
  }
  return result;
}
/** Submit a JSON mutation with the current session's CSRF token. */
function post(path, body={}) { return api(path,{method:'POST',body:JSON.stringify(body)}); }
/** Show a brief accessible status message. */
function toast(message) { const element=document.querySelector('#toast'); element.textContent=message; element.style.display='block'; clearTimeout(toast.timer); toast.timer=setTimeout(()=>element.style.display='none',6000); }
/** Serialize UI edits so a slow wearer lookup cannot redirect subsequent product clicks. */
function setBusy(value) { state.busy=value;root.inert=value;modal.inert=value;root.setAttribute('aria-busy',String(value));document.body.style.cursor=value?'progress':''; }
/** Render a stable status chip using a closed color mapping. */
function badge(status) { const color=['order_recorded','recorded','issued','sent','implemented'].includes(status)?'green':['draft','prepared','reserved','queued','partial'].includes(status)?'orange':['cancelled','delivery_uncertain'].includes(status)?'red':''; return `<span class="pill ${color}">${escapeHtml(status?.replaceAll('_',' ')||'pending')}</span>`; }
/** Draw a decorative product illustration; it does not claim to be a product photo. */
function glasses(kind='frame', color='#383b32', index=0) {
  if (kind==='lens') return '<svg viewBox="0 0 240 120" fill="none" aria-hidden="true"><ellipse cx="105" cy="63" rx="46" ry="46" fill="#dfe8e5" stroke="#9fb5b0"/><ellipse cx="135" cy="57" rx="46" ry="46" fill="#e8f0ed" fill-opacity=".7" stroke="#97b3ad"/><path d="M118 22c-18 6-27 19-29 35" stroke="white" stroke-width="4" stroke-linecap="round"/></svg>';
  const dark=kind.includes('sun');
  return `<svg viewBox="0 0 300 130" fill="none" aria-hidden="true"><path d="M42 50 18 19M257 50l25-31" stroke="${color}" stroke-width="5" stroke-linecap="round"/><path d="M31 48c20-12 68-12 90 0 9 12-4 48-18 51-19 5-48 4-58-8-9-10-16-30-14-43Z" fill="${dark?'#51564c':'#d6ded2'}" fill-opacity="${dark?'.9':'.38'}" stroke="${color}" stroke-width="${index%2?5:8}"/><path d="M179 48c20-12 68-12 90 0 2 13-4 33-14 43-10 12-39 13-58 8-14-3-27-39-18-51Z" fill="${dark?'#51564c':'#d6ded2'}" fill-opacity="${dark?'.9':'.38'}" stroke="${color}" stroke-width="${index%2?5:8}"/><path d="M123 51c16-7 38-7 54 0" stroke="${color}" stroke-width="6"/><path d="M49 49h8M243 49h8" stroke="#c5ab70" stroke-width="3"/></svg>`;
}
/** Render the credential form without embedding usable passwords in the client. */
function renderLogin() {
  root.innerHTML=`<div class="login"><section class="login-story"><div class="brand">eluno<i>.</i></div><div><div class="eyebrow">THE STORE, IN FOCUS</div><h1>Every pair.<br>Every person.<br><em>One thoughtful flow.</em></h1><div class="hero-art">${glasses('frame','#424938',1)}</div></div><small>STORE STUDIO &nbsp; / &nbsp; WORKING DEMO</small></section><section class="login-form"><div class="eyebrow">WELCOME TO YOUR STORE</div><h2>A clearer way to bill.</h2><p>Sign in to manage sales, prescriptions and the details that make a store work.</p><form id="login-form"><label class="field">Username<input name="username" autocomplete="username" required autofocus></label><label class="field">Password<input type="password" name="password" autocomplete="current-password" required></label><div id="login-error" class="error" role="alert"></div><button class="button orange" type="submit">Sign in to Store Studio <span>→</span></button></form><div class="login-note"><span class="dot"></span>Demo environment · Shopify and payments are simulated.<br>Accounts are provisioned by the demo owner. Permissions are enforced by the server.</div></section></div>`;
}
/** Render persistent navigation and the store/account controls. */
function shell() {
  const central=['admin','finance'].includes(state.user.role);
  const navigation=navItems.filter(item=>(central||!['outbox','audit'].includes(item[0]))&&(item[0]!=='billing'||['cashier','manager','admin'].includes(state.user.role)));
  root.innerHTML=`<div class="layout"><aside class="sidebar"><div class="brand">eluno<i>.</i></div><div class="brand-sub">STORE STUDIO</div><div class="nav-label">Workspace</div><nav>${navigation.map(([id,icon,label])=>`<button class="nav-button ${state.page===id?'active':''}" data-page="${id}"><span class="icon">${icon}</span>${label}</button>`).join('')}</nav><div class="sidebar-footer"><div class="environment"><span class="dot"></span><strong>Demo environment</strong><br><span class="muted">Mock Shopify + payments<br>Real workflows. Synthetic data.</span></div></div></aside><section class="workspace"><header class="topbar"><div class="actions"><span class="muted">⌖</span><select id="store-select" aria-label="Billing store">${state.data.stores.map(store=>`<option value="${escapeHtml(store.eluno.store_code)}" ${store.eluno.store_code===state.store?'selected':''}>${escapeHtml(store.name.replace('Eluno ',''))}</option>`).join('')}</select><span class="pill">STORE ${escapeHtml(state.store)}</span></div><div class="account"><span class="muted">${escapeHtml(state.data.today)}</span><span class="avatar">${escapeHtml(state.user.display_name.slice(0,1))}</span><div>${escapeHtml(state.user.display_name)}<small>${escapeHtml(state.user.role)}</small></div><button class="button ghost" data-action="logout">Sign out</button></div></header><div id="network-status"></div><main class="main" id="main"></main></section></div>`;
  networkStatus();
}
/** Explain connectivity loss without implying offline payment is supported. */
function networkStatus() { const element=document.querySelector('#network-status'); if(element) element.innerHTML=navigator.onLine?'':'<div class="offline">Connection lost. Your cart is saved on this device. Payments require a connection; inspect a pending bill before retrying.</div>'; }
/** Build a consistent heading with an optional page action. */
function heading(eyebrow,title,subtitle,action='') { return `<div class="page-heading"><div><div class="eyebrow">${eyebrow}</div><h1>${title}</h1><p>${subtitle}</p></div>${action}</div>`; }
/** Load the selected page and contain errors within the workspace. */
async function navigate(page) {
  state.page=page; shell();
  const main=document.querySelector('#main'); main.innerHTML='<div class="empty">Loading your store…</div>';
  try {
    if(page==='overview') await overview(main);
    else if(page==='billing') await billing(main);
    else if(page==='transactions') await transactionsPage(main);
    else if(page==='till') await tillPage(main);
    else if(page==='reports') await reportsPage(main);
    else if(page==='clinical') clinicalPage(main);
    else if(page==='evidence') await evidencePage(main);
    else if(page==='outbox') await outboxPage(main);
    else if(page==='audit') await auditPage(main);
  } catch(error) { main.innerHTML=`<div class="card"><h2>We couldn't load this view.</h2><p class="error">${escapeHtml(error.message)}</p><button class="button light" data-page="${page}">Try again</button></div>`; }
}
/** Present source-backed daily numbers and an understandable demo entry point. */
async function overview(main) {
  const [report,transactions]=await Promise.all([api(`/api/reports?day=${state.data.today}&store_code=${state.store}`),api(`/api/transactions?store_code=${state.store}`)]);
  state.transactions=transactions;
  const total=report.stores[0];
  main.innerHTML=heading('YOUR STORE, AT A GLANCE','Good to see you, '+escapeHtml(state.user.display_name.split(' ')[0])+'.','A little less admin. A lot more time for your customers.',['cashier','manager','admin'].includes(state.user.role)?'<button class="button orange" data-action="new-sale">＋ New sale</button>':'')+
  `<div class="grid stats">${stat('Sales today',money(total.sales_paise),'Inclusive of GST · Shopify source')}${stat('Bills created',total.bill_count,'One bill, even for a family')}${stat('Average bill',money(total.average_bill_paise),'Across today’s completed bills')}${stat('Reconciliation',money(total.reconciliation_delta_paise),total.reconciliation_delta_paise?'Needs review':'Payments match sales','green')}</div>
  <section class="card hero"><div><div class="eyebrow">FROM FIRST LOOK TO FINAL BILL</div><h2>Great eyewear.<br>An even better checkout.</h2><p>Walk through a real sale, see the prescription checks, and follow the result all the way to Shopify.</p>${['cashier','manager','admin'].includes(state.user.role)?'<button class="button" data-action="guided-demo">Start guided sale <span>↗</span></button>':'<button class="button" data-page="transactions">Review bills <span>↗</span></button>'}</div><div class="hero-art">${glasses('frame','#494e3c',1)}</div></section>
  <div class="grid two-col"><section class="card"><div class="card-head"><h2>Recent bills</h2><button class="button ghost" data-page="transactions">View all ↗</button></div>${transactionTable(transactions.slice(0,5))}</section><section class="card"><div class="card-head"><h2>One connected process</h2><span class="pill orange">LIVE DEMO</span></div><div class="flow-list">${[['Customer & prescription','Identify the wearer and check clinical compatibility.'],['Offers, tax & payment','Review the exact amount before confirming.'],['Order, invoice & stock','See the source order and store invoice together.'],['Return & reconciliation','Reverse payment and tax, then see the report change.']].map(([title,body],index)=>`<div class="flow-item"><span class="flow-number">${index+1}</span><div><h3>${title}</h3><p>${body}</p></div></div>`).join('')}</div></section></div>`;
}
/** Render a metric card with an explicit basis. */
function stat(label,value,foot,color='') { return `<div class="card"><div class="stat-label">${label}</div><div class="stat-value">${value}</div><div class="stat-foot ${color}">${foot}</div></div>`; }
/** Resolve product metadata from the loaded catalog. */
function product(identifier) { return state.data.catalog.find(item=>item.id===Number(identifier)); }
/** Cache customer/prescription reads during a cart editing session. */
async function loadCustomer(phone) { if(!state.customerCache[phone]) state.customerCache[phone]=await api('/api/customers?phone='+encodeURIComponent(phone)); return state.customerCache[phone]; }
/** Persist cart edits locally first, then to the authenticated draft endpoint. */
async function persistCart() {
  const snapshot={...state.cart,store_code:state.store,quote_id:state.quote?.checkout_id||null};
  localStorage.setItem('eluno-cart-'+state.user.username,JSON.stringify(snapshot));
  try { await api('/api/draft',{method:'PUT',body:JSON.stringify(snapshot)}); } catch(error) { toast('Cart saved on this device. '+error.message); }
}
/** Invalidate an old quote whenever cart inputs change. */
function invalidateQuote() { state.quote=null; }
/** Render billing with wearer-specific cart lines and a real server quote. */
async function billing(main) {
  if(!['cashier','manager','admin'].includes(state.user.role)) { main.innerHTML=heading('BILLING','Sales workspace','Your role can review records but cannot create sales.')+'<div class="card empty">Sign in with a cashier or manager account to create a bill.</div>'; return; }
  const inventory=await api('/api/inventory?store_code='+state.store);
  state.stock=Object.fromEntries(inventory.inventory_levels.map(item=>[item.inventory_item_id,item.available]));
  for(const member of state.cart.members) await loadCustomer(member.phone);
  main.innerHTML=heading('A BETTER WAY TO BILL','Let’s find their next pair.','One customer or the whole family. Every prescription stays with its wearer.','<button class="button light" data-action="guided-demo">Load sample customer</button>')+
    `<div class="steps"><span class="step active"><b>1</b>Customer & Rx</span><span class="step-arrow">→</span><span class="step ${state.cart.members.length?'active':''}"><b>2</b>Build the bill</span><span class="step-arrow">→</span><span class="step ${state.quote?'active':''}"><b>3</b>Review & pay</span><span class="step-arrow">→</span><span class="step"><b>4</b>Invoice & order</span></div><div class="billing-grid"><div><section class="card"><div class="card-head"><h2>Who are we helping?</h2><span class="pill">${state.cart.members.length} WEARER${state.cart.members.length===1?'':'S'}</span></div><form id="customer-form"><div class="actions"><label class="field" style="flex:1;margin:0">Find an existing customer<input name="phone" list="customers" placeholder="Phone number or choose a sample" required><datalist id="customers">${state.data.customers.map(customer=>`<option value="${escapeHtml(customer.phone)}">${escapeHtml(customer.first_name+' '+customer.last_name)}</option>`).join('')}</datalist></label><button class="button light" style="margin-top:19px">Add wearer ＋</button></div></form>${wearerPanel()}</section><div class="catalog-tools"><div class="tabs">${['frame','lens','sunglasses'].map(category=>`<button class="tab ${state.category===category?'active':''}" data-category="${category}">${category==='frame'?'Frames':category==='lens'?'Lenses':'Sunglasses'}</button>`).join('')}</div><input class="search" id="product-search" placeholder="Search name / SKU" value="${escapeHtml(state.search)}" aria-label="Search catalog"></div><div class="products" id="products">${productCards()}</div><p class="muted" style="font-size:10px;margin-top:12px">Catalog illustrations are representative. Prices and availability come from the mock catalog.</p></div><aside class="card bill-panel" id="bill-panel">${billPanel()}</aside></div>`;
}
/** Display each family member and the latest valid prescription. */
function wearerPanel() {
  if(!state.cart.members.length) return '<div class="empty">Start with a customer.<br>Their prescription and priority flags will appear here.</div>';
  state.activeWearer=Math.min(state.activeWearer,state.cart.members.length-1);
  const member=state.cart.members[state.activeWearer], data=state.customerCache[member.phone], customer=data.customer;
  const valid=data.prescriptions.filter(rx=>rx.valid_until>=state.data.today).sort((left,right)=>right.date.localeCompare(left.date))[0];
  return `<div class="wearer-tabs">${state.cart.members.map((wearer,index)=>`<button class="wearer-tab ${index===state.activeWearer?'active':''}" data-wearer="${index}">${escapeHtml(state.customerCache[wearer.phone].customer.first_name)} · ${index+1}</button>`).join('')}</div><div class="customer-summary"><span class="avatar">${escapeHtml(customer.first_name[0])}</span><div style="flex:1"><h3>${escapeHtml(customer.first_name+' '+customer.last_name)}</h3><small>${escapeHtml(customer.phone)}</small></div><button class="button ghost" data-action="remove-wearer">Remove</button></div><div class="actions">${customer.tags.split(',').filter(Boolean).map(tag=>`<span class="pill ${tag==='priority'?'orange':'green'}">${escapeHtml(tag.replace('campaign:','Campaign · '))}</span>`).join('')}${valid?'<span class="pill green">Valid prescription</span>':'<span class="pill red">No valid prescription</span>'}</div>${valid?`<div class="rx-grid"><span>RIGHT · SPH / CYL<b>${valid.od.sph} / ${valid.od.cyl}</b></span><span>LEFT · SPH / CYL<b>${valid.os.sph} / ${valid.os.cyl}</b></span><span>AXIS · R / L<b>${valid.od.axis||'—'}° / ${valid.os.axis||'—'}°</b></span><span>VALID THROUGH<b>${escapeHtml(valid.valid_until)}</b></span></div>`:'<div class="notice">An optometrist must record a valid prescription before a lens can be billed.</div>'}<div class="bill-line"><small>Selected for this wearer</small><strong>${member.variant_ids.length} item(s)</strong></div>`;
}
/** Build stock-aware catalog cards for the active wearer. */
function productCards() {
  const member=state.cart.members[state.activeWearer];
  const items=state.data.catalog.filter(item=>(state.category==='sunglasses'?item.eluno.category==='sunglasses'||item.eluno.line_type.includes('sun'):item.eluno.line_type===state.category && item.eluno.category!=='sunglasses') && (item.product_title+' '+item.sku+' '+item.title).toLowerCase().includes(state.search.toLowerCase()));
  return items.map((item,index)=>{const selected=member?.variant_ids.filter(id=>id===item.id).length||0, stock=item.inventory_item_id?state.stock[item.inventory_item_id]||0:null; return `<button class="product ${selected?'selected':''}" data-product="${item.id}" ${!member||stock===0?'disabled':''}><div class="product-art" style="background:${['#eef0e8','#f0ece5','#ecefed'][index%3]}"><span class="stock">${stock===null?'MADE TO ORDER':stock+' IN STORE'}</span>${glasses(item.eluno.line_type,item.title.toLowerCase().includes('gold')?'#8f784a':'#444b3d',index)}</div><div class="product-info"><h3>${escapeHtml(item.product_title)}</h3><small>${escapeHtml(item.title)} · ${escapeHtml(item.sku)}</small><div class="product-price">${money(Math.round(Number(item.price)*100))}<span>${selected?'＋ · '+selected:'＋'}</span></div></div></button>`;}).join('')||'<div class="empty">No matching products.</div>';
}
/** Show editable payment details and exact quote totals before confirmation. */
function billPanel() {
  const quote=state.quote, members=state.cart.members;
  const gross=members.flatMap(member=>member.variant_ids).reduce((sum,id)=>sum+Math.round(Number(product(id).price)*100),0);
  return `<div class="card-head"><h2>The bill</h2><span class="pill orange">${quote?'REVIEWED':'DRAFT'}</span></div>${members.map((member,memberIndex)=>`<div class="bill-line"><strong>${escapeHtml(state.customerCache[member.phone]?.customer.first_name||member.phone)}</strong><small>Wearer</small></div>${[...new Set(member.variant_ids)].map(id=>{const quantity=member.variant_ids.filter(value=>value===id).length;return `<div class="bill-line"><span>${escapeHtml(product(id).product_title)}<br><small>${escapeHtml(product(id).sku)} · Qty ${quantity}</small><br><button class="button ghost" data-quantity="-1" data-member="${memberIndex}" data-variant="${id}" aria-label="Remove one ${escapeHtml(product(id).sku)}">−</button><button class="button ghost" data-quantity="1" data-member="${memberIndex}" data-variant="${id}" aria-label="Add one ${escapeHtml(product(id).sku)}">＋</button></span><strong>${money(Math.round(Number(product(id).price)*100)*quantity)}</strong></div>`;}).join('')}`).join('')||'<div class="empty">Your bill starts here.</div>'}<div class="divider"></div><label class="field">Sale source<select id="channel">${[['walk_in','Walk-in'],['whatsapp','WhatsApp booked'],['online_pickup','Online pickup']].map(([value,label])=>`<option value="${value}" ${state.cart.channel===value?'selected':''}>${label}</option>`).join('')}</select></label><label class="field">Payment method<select id="payment-method">${['upi','card','cash'].map(method=>`<option value="${method}" ${state.cart.payment_method===method?'selected':''}>${method.toUpperCase()}</option>`).join('')}</select></label>${['admin','manager'].includes(state.user.role)?`<details><summary>Manager discount</summary><label class="field">Discount % · maximum 10<input id="override-percent" type="number" min="0" max="10" step="0.1" value="${state.cart.override_percent||''}"></label><label class="field">Reason code<select id="discount-reason"><option value="">Choose a reason</option>${['walk_out_retention','service_recovery','price_match'].map(reason=>`<option ${state.cart.reason_code===reason?'selected':''} value="${reason}">${reason.replaceAll('_',' ')}</option>`).join('')}</select></label><small>Approved by ${escapeHtml(state.user.display_name)}. Recorded on the order.</small></details>`:''}<div class="bill-line"><span>MRP total</span><strong>${money(gross)}</strong></div>${quote?`<div class="bill-line"><span>Offers & discounts</span><strong style="color:var(--green)">− ${money(gross-quote.total_paise)}</strong></div><div class="bill-line"><span>Taxable value</span><strong>${money(quote.total_paise-quote.tax_paise)}</strong></div><div class="bill-line"><span>Included GST</span><strong>${money(quote.tax_paise)}</strong></div>`:''}<div class="bill-line total-row"><span>${quote?'Amount due':'Before offers'}</span><strong class="total">${money(quote?quote.total_paise:gross)}</strong></div>${quote?`<button class="button orange" data-action="complete-sale">Confirm ${state.cart.payment_method.toUpperCase()} · ${money(quote.total_paise)} →</button><button class="button light" data-detail="${quote.checkout_id}">View quote details</button><div class="info">${escapeHtml(quote.invoice_no)}<br>Confirming records the demo payment and creates the Shopify order.</div><details><summary>Why these offers?</summary>${quote.offers.map(offer=>`<p class="info"><b>${escapeHtml(offer.offer_id)}</b> · ${offer.applied?money(offer.amount_paise):'Not applied'}<br>${escapeHtml(offer.reason)}</p>`).join('')}</details>`:`<button class="button orange" data-action="prepare-sale" ${!members.length?'disabled':''}>Review offers & GST →</button><p class="info">Add multiple items or use + / − to adjust quantities. Within each wearer, frames and lenses pair in selection order; extra items are standalone. The server validates stock, prescriptions and offers before payment.</p>`}`;
}
/** Add/remove one unit while checking the whole family's displayed stock. */
function changeQuantity(memberIndex, variantId, delta) {
  const member=state.cart.members[memberIndex],item=product(variantId);
  if(delta<0) {const index=member.variant_ids.indexOf(variantId);if(index>=0)member.variant_ids.splice(index,1);return;}
  if(member.variant_ids.length>=30)throw new Error('Maximum 30 units per wearer.');
  const demand=state.cart.members.flatMap(wearer=>wearer.variant_ids).filter(id=>product(id).inventory_item_id===item.inventory_item_id).length;
  if(item.inventory_item_id&&demand>=(state.stock[item.inventory_item_id]||0))throw new Error('All available units are already in this bill.');
  member.variant_ids.push(variantId);
}

/** List transaction states without presenting an uncertain payment as a completed sale. */
function transactionTable(records) { return records.length?`<div class="table-wrap"><table><thead><tr><th>INVOICE / CUSTOMER</th><th>STATUS</th><th>AMOUNT</th><th></th></tr></thead><tbody>${records.map(record=>`<tr><td>${escapeHtml(record.invoice_no||'Unallocated')}<small>${escapeHtml(record.customer_name||record.customer_id)}${record.remake?' · Remake':''}</small></td><td>${badge(record.status)}</td><td>${money(record.total_paise)}<small>${escapeHtml(record.method?.toUpperCase())}</small></td><td class="right"><button class="button light small" data-detail="${record.checkout_id}">Open ↗</button></td></tr>`).join('')}</tbody></table></div>`:'<div class="empty">No bills yet. Start a sale to see the full process here.</div>'; }
/** Present searchable transaction history and an auditable invoice register. */
async function transactionsPage(main) {
  const [records,register]=await Promise.all([api('/api/transactions?store_code='+state.store),api('/api/register?store_code='+state.store)]);state.transactions=records;
  main.innerHTML=heading('EVERY BILL HAS A STORY','Bills, returns & remakes','Pick a bill to inspect its source order, print an invoice or start a return.','<button class="button orange" data-action="new-sale">＋ New sale</button>')+`<section class="card section-gap">${transactionTable(records)}</section><section class="card"><div class="card-head"><h2>Invoice register</h2><span class="pill">${register.length} ALLOCATIONS</span></div><p class="muted" style="font-size:12px">Reserved and cancelled numbers stay visible. Numbers are never reused.</p><div class="table-wrap"><table><thead><tr><th>SEQUENCE</th><th>INVOICE</th><th>STATUS</th><th>ALLOCATED AT</th></tr></thead><tbody>${register.map(item=>`<tr><td>${item.serial_number}</td><td>${escapeHtml(item.invoice_no)}</td><td>${badge(item.status)}</td><td>${escapeHtml(new Date(item.allocated_at).toLocaleString('en-IN'))}</td></tr>`).join('')}</tbody></table></div></section>`;
}
/** Render source-linked invoice and credit-note documents as printable HTML. */
function receiptHtml(detail, credit=false) {
  const quote=detail.quote, checkout=detail.checkout, refund=detail.refunds.find(item=>item.status==='recorded');
  const lines=quote.lines||quote.order_payload.line_items.map(line=>({title:line.variant_id,hsn:line.properties.find(item=>item.name==='hsn')?.value,gross_paise:Math.round(Number(line.price)*100),discount_paise:Math.round(Number(line.total_discount)*100),cgst_paise:Math.round(Number(line.tax_lines[0]?.price||0)*100),sgst_paise:Math.round(Number(line.tax_lines[1]?.price||0)*100)}));
  const sign=credit?-1:1;
  return `<article class="receipt"><div class="receipt-brand"><div><div class="brand">eluno<i>.</i></div><small>STORE STUDIO · ${escapeHtml(checkout.store_code)}</small></div><div class="right"><h2>${credit?'Credit note':'Tax invoice'}</h2><p>${escapeHtml(credit?'CN/'+checkout.invoice_no:checkout.invoice_no)}</p><small>${credit?'Original invoice: '+escapeHtml(checkout.invoice_no):escapeHtml(new Date(checkout.created_at).toLocaleDateString('en-IN'))}</small></div></div><div class="notice">Demo document · synthetic customer data · not a legally issued tax document.</div><p><strong>${escapeHtml(quote.customer?.first_name||'Customer')} ${escapeHtml(quote.customer?.last_name||'')}</strong> · ${escapeHtml(quote.customer?.phone||checkout.customer_id)}</p><div class="table-wrap"><table><thead><tr><th>ITEM / WEARER / HSN</th><th>MRP</th><th>DISCOUNT</th><th>TAXABLE</th><th>CGST</th><th>SGST</th></tr></thead><tbody>${lines.map(line=>`<tr><td>${escapeHtml(line.title||line.variant_id)}<small>${escapeHtml(line.wearer_phone||'')} · ${escapeHtml(line.hsn)}${line.rx_id?' · '+escapeHtml(line.rx_id):''}</small></td><td>${money(sign*line.gross_paise)}</td><td>${money(sign*line.discount_paise)}</td><td>${money(sign*(line.gross_paise-line.discount_paise-line.cgst_paise-line.sgst_paise))}</td><td>${money(sign*line.cgst_paise)}</td><td>${money(sign*line.sgst_paise)}</td></tr>`).join('')}</tbody></table></div><div class="bill-line total-row"><span>${credit?'Refunded total':'Total · GST inclusive'}</span><strong class="total">${money(sign*quote.total_paise)}</strong></div><div class="receipt-footer">${credit?'Shopify refund: '+escapeHtml(refund?.shopify_refund_id):'Shopify order: '+escapeHtml(checkout.shopify_order_id||'Pending — quote only')}<br>Payment: ${escapeHtml(quote.method.toUpperCase())} · Checkout: ${escapeHtml(checkout.checkout_id)}${quote.remake?'<br>Remake of '+escapeHtml(quote.remake.original_invoice)+' · Cost owner: '+escapeHtml(quote.remake.cost_owner):''}<br>Thank you for seeing the world with Eluno.</div></article>`;
}
/** Open the detail drawer with real next actions for the persisted state. */
async function showDetail(identifier) {
  const detail=await api('/api/checkouts/'+encodeURIComponent(identifier)+'/detail'); state.detail=detail;
  const checkout=detail.checkout, manager=['manager','admin'].includes(state.user.role), seller=['cashier','manager','admin'].includes(state.user.role), refund=detail.refunds[0];
  modal.innerHTML=`<div class="modal-header"><div><div class="eyebrow">BILL DETAILS</div><h2>${escapeHtml(checkout.invoice_no)}</h2></div><button class="button light" data-action="close-modal">Close ✕</button></div><div class="actions no-print section-gap">${badge(checkout.status)}${refund?badge('refund '+refund.status):''}<button class="button light small" data-action="print">Print invoice</button>${refund?.status==='recorded'?'<button class="button light small" data-action="credit-note">Credit note</button>':''}${checkout.status==='draft'&&seller?'<button class="button orange small" data-action="complete-detail">Confirm payment</button><button class="button danger small" data-action="cancel-bill">Cancel draft</button>':''}${checkout.status==='order_recorded'&&manager&&!refund?'<button class="button light small" data-action="refund-dialog">Full refund</button><button class="button light small" data-action="remake-dialog">Remake lens</button>':''}${refund?.status==='prepared'&&manager?'<button class="button orange small" data-action="complete-refund">Confirm refund</button>':''}${checkout.status==='order_uncertain'&&manager?'<button class="button orange small" data-action="reconcile-order">Reconcile order</button>':''}${refund?.status==='shopify_uncertain'&&manager?'<button class="button orange small" data-action="reconcile-refund">Reconcile refund</button>':''}</div>${checkout.error_detail?'<div class="notice no-print">'+escapeHtml(checkout.error_detail)+'</div>':''}${receiptHtml(detail)}<div class="timeline no-print"><p>Quote saved · Invoice number reserved</p><p>${checkout.payment_charge_id?'Payment reference recorded: '+escapeHtml(checkout.payment_charge_id):'Payment has not been confirmed'}</p><p>${checkout.shopify_order_id?'Shopify order recorded: '+escapeHtml(checkout.shopify_order_id):'Shopify order not yet recorded'}</p>${refund?'<p>Refund: '+escapeHtml(refund.status)+'</p>':''}</div><details class="no-print"><summary>Technical evidence · source order & saved state</summary><pre>${escapeHtml(JSON.stringify(detail,null,2))}</pre></details>`;
  if(!modal.open) modal.showModal();
}
/** Render open/expense/close drawer controls and explain the variance calculation. */
async function tillPage(main) {
  const till=await api('/api/till?store_code='+state.store);state.till=till;
  const seller=['cashier','manager','admin'].includes(state.user.role),manager=['manager','admin'].includes(state.user.role);
  main.innerHTML=heading('THE LITTLE THINGS ADD UP','Cash drawer','Opening float + cash sales − cash refunds − expenses = expected cash.')+
    (till.open?`<div class="grid stats">${stat('Opening float',money(till.opening_paise),'Recorded at drawer open')}${stat('Cash sales',money(till.cash_sales_paise),'From Shopify transactions')}${stat('Expenses',money(till.expenses_paise),'Every cash-out has a reason')}${stat('Expected in drawer',money(till.expected_paise),'After sales, refunds and expenses')}</div><div class="grid two-col"><section class="card"><h2>Record a cash expense</h2><form id="expense-form" class="spacer"><div class="fields"><label class="field">Amount · INR<input name="amount" type="number" min="0.01" step="0.01" required></label><label class="field">Reason<input name="reason" placeholder="Courier, tea, supplies…" minlength="3" required></label></div><button class="button light" ${seller?'':'disabled'}>Record cash out</button></form><div class="divider"></div>${till.expenses.map(item=>`<div class="bill-line"><span>${escapeHtml(item.reason)}<br><small>${escapeHtml(item.actor)}</small></span><strong>${money(item.amount_paise)}</strong></div>`).join('')||'<p class="muted">No expenses recorded.</p>'}</section><section class="card"><h2>Count & close</h2><p class="muted spacer" style="font-size:12px">Enter the physical cash count. A variance above ₹200 queues a finance notification.</p><form id="close-till-form" class="spacer"><label class="field">Counted cash · INR<input name="amount" type="number" min="0" step="0.01" required></label><button class="button orange full-width" ${manager?'':'disabled'}>Reconcile & close drawer</button></form><p class="info muted spacer" style="font-size:11px">Manager permission required. The outbox shows notification delivery status.</p></section></div>`:`<section class="card" style="max-width:550px"><h2>Start with your opening float.</h2><p class="muted spacer">Open a drawer before recording a cash sale or refund.</p><form id="open-till-form" class="spacer"><label class="field">Opening cash · INR<input name="amount" type="number" min="0" step="0.01" value="2000" required></label><button class="button orange" ${seller?'':'disabled'}>Open drawer</button></form>${(till.history||[]).map(item=>`<div class="bill-line"><span>Previous close<small>${escapeHtml(item.closed_at)}</small></span><strong>Variance ${money(item.variance_paise)}</strong></div>`).join('')}</section>`);
}
/** Show all-store source-based reporting with channel comparison. */
async function reportsPage(main,day=state.data.today) {
  const report=await api('/api/reports?day='+day);
  const totals=report.stores.reduce((sum,item)=>({sales:sum.sales+item.sales_paise,bills:sum.bills+item.bill_count,discounts:sum.discounts+item.discounts_paise,refunds:sum.refunds+item.refunds_paise}),{sales:0,bills:0,discounts:0,refunds:0});
  const channels={};report.stores.forEach(store=>Object.entries(store.channels).forEach(([key,value])=>channels[key]=(channels[key]||0)+value));
  main.innerHTML=heading('THE NUMBERS, RECONCILED','A clear view of the day.','Shopify source · Asia/Kolkata · Refunds attributed to their actual event date.',`<input type="date" id="report-date" class="search" value="${day}" aria-label="Report date">`)+`<div class="grid stats">${stat('Sales',money(totals.sales),'GST inclusive')}${stat('Bills',totals.bills,'Across permitted stores')}${stat('Discounts',money(totals.discounts),'Recorded on order lines')}${stat('Refunds',money(totals.refunds),'Refund event date')}</div><section class="card section-gap"><div class="card-head"><h2>Store performance</h2><span class="pill green">SHOPIFY SOURCE</span></div><div class="table-wrap"><table><thead><tr><th>STORE</th><th>BILLS</th><th>SALES</th><th>AVG BILL</th><th>DISCOUNTS</th><th>NET COLLECTED</th><th>DELTA</th></tr></thead><tbody>${report.stores.map(item=>`<tr><td>${escapeHtml(item.name)}</td><td>${item.bill_count}</td><td>${money(item.sales_paise)}</td><td>${money(item.average_bill_paise)}</td><td>${money(item.discounts_paise)}</td><td>${money(item.net_collected_paise)}</td><td><span class="pill ${item.reconciliation_delta_paise?'red':'green'}">${money(item.reconciliation_delta_paise)}</span></td></tr>`).join('')}</tbody></table></div></section><div class="grid two-col"><section class="card"><h2>Where bills came from</h2>${Object.entries(channels).map(([name,value])=>`<div class="bar-row"><span>${escapeHtml(name.replaceAll('_',' '))}</span><div class="bar-track"><div class="bar" style="width:${Math.max(0,Math.min(100,value/Math.max(totals.sales,1)*100))}%"></div></div><strong class="right">${money(value)}</strong></div>`).join('')||'<div class="empty">Complete a bill to see channel totals.</div>'}</section><section class="card"><h2>What does “match” mean?</h2><p class="muted spacer" style="font-size:12px">Delta is successful sale payments minus order totals. Net collected subtracts refunds made on this day, including refunds on earlier bills. Cash drawer variance is reconciled separately.</p><p class="notice">This demo measures mock transactions. Payment gateway settlement and real Shopify pagination require live integration work.</p></section></div>`;
}
/** Offer clinical entry only to optometrists and administrators. */
function clinicalPage(main) {
  const allowed=['admin','optometrist'].includes(state.user.role);
  main.innerHTML=heading('EVERY LENS STARTS HERE','Prescription studio','Manual axis entry uses 5-degree steps. Existing issued prescriptions are preserved.')+`<section class="card" style="max-width:850px"><form id="rx-form"><div class="fields"><label class="field">Customer phone<input name="phone" list="rx-customers" required><datalist id="rx-customers">${state.data.customers.map(item=>`<option value="${item.phone}">${escapeHtml(item.first_name+' '+item.last_name)}</option>`).join('')}</datalist></label><label class="field">Valid until<input name="valid_until" type="date" min="${state.data.today}" required></label></div>${['od','os'].map((side,index)=>`<h3 class="spacer">${index?'Left eye · OS':'Right eye · OD'}</h3><div class="fields spacer"><label class="field">Sphere<input name="${side}_sph" type="number" min="-30" max="30" step="0.25" value="0" required></label><label class="field">Cylinder<input name="${side}_cyl" type="number" min="-12" max="12" step="0.25" value="0" required></label><label class="field">Axis<select name="${side}_axis"><option value="">Not applicable</option>${Array.from({length:36},(_,number)=>`<option value="${(number+1)*5}">${(number+1)*5}°</option>`).join('')}</select></label><label class="field">ADD<input name="${side}_add" type="number" min="0" max="5" step="0.25" placeholder="If prescribed"></label></div>`).join('')}<div class="notice">Clinical values must be entered by an authorized optometrist. Lens compatibility is revalidated at quote preparation.</div><button class="button orange" ${allowed?'':'disabled'}>Save prescription</button>${allowed?'':'<p class="error">Your role cannot create clinical records.</p>'}</form></section>`;
}
/** Connect stakeholder requests to explicit acceptance evidence and remaining limits. */
async function evidencePage(main) {
  const evidence=await api('/api/evidence');
  main.innerHTML=heading('BUILT TO BE EXPLAINED','The demo, end to end.','A requirement is complete only when the behavior and its evidence agree.','<button class="button orange" data-action="guided-demo">Run the sale walkthrough ↗</button>')+`<div class="grid stats">${stat('Requirements tracked',evidence.requirements.length,'Includes separate workstreams')}${stat('Completion samples',evidence.timings.samples,'Successful confirmation calls')}${stat('Observed p95',evidence.timings.p95_ms===null?'—':(evidence.timings.p95_ms/1000).toFixed(2)+'s','Local mock · not production SLA')}${stat('Target','< 10s','Customer confirmation → order result')}</div><div class="notice">Demo assumptions: configured offer stacking; immediate manager approval with reason; external remake costs recorded for later recovery. No live payments or real Shopify admin connection.</div><section class="card"><div class="card-head"><h2>Stakeholder acceptance map</h2><span class="pill">TECH LEAD VIEW</span></div>${evidence.requirements.map((item,index)=>`<div class="requirement"><span class="flow-number">${String(index+1).padStart(2,'0')}</span><div><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.behavior)}</p><small>${escapeHtml(item.owner)} · ${escapeHtml(item.evidence)}</small>${item.limit?'<p><strong>Boundary:</strong> '+escapeHtml(item.limit)+'</p>':''}</div>${badge(item.status)}</div>`).join('')}</section>`;
}
/** Display the report schedule and delivery status without faking sent email. */
async function outboxPage(main) {
  const result=await api('/api/outbox');
  main.innerHTML=heading('THE MORNING BRIEF','Reports, ready to send.',escapeHtml(result.schedule),'<button class="button light" data-action="digest">Generate yesterday’s report</button>')+`<div class="notice">${escapeHtml(result.delivery)}. Queued means prepared, not delivered.</div><section class="card">${result.messages.map(message=>`<div class="section-gap"><div class="card-head"><h3>${escapeHtml(message.subject)}</h3>${badge(message.status)}</div><small>${escapeHtml(message.created_at)}</small><pre>${escapeHtml(message.body)}</pre>${message.error?'<p class="error">'+escapeHtml(message.error)+'</p>':''}</div>`).join('')||'<div class="empty">No messages yet. Generate a report preview or close a drawer with a variance above ₹200.</div>'}</section>`;
}
/** Render central audit events with actor and result information. */
async function auditPage(main) { const entries=await api('/api/audit'); main.innerHTML=heading('ACCOUNTABILITY, BUILT IN','A traceable store.','Who acted, what changed, and when. Server-side permissions protect each action.')+`<section class="card table-wrap"><table><thead><tr><th>TIME</th><th>ACTOR</th><th>ACTION</th><th>RESULT</th></tr></thead><tbody>${entries.map(item=>`<tr><td>${escapeHtml(new Date(item.at).toLocaleString('en-IN'))}</td><td>${escapeHtml(item.actor)}</td><td class="code">${escapeHtml(item.action)}</td><td class="code">${escapeHtml(item.detail)}</td></tr>`).join('')}</tbody></table></section>`; }
/** Prepare a sample cart while keeping the customer-confirmation step explicit. */
async function guidedDemo() { const inventory=await api('/api/inventory?store_code='+state.store);const available=new Set(inventory.inventory_levels.filter(item=>item.available>0).map(item=>item.inventory_item_id));const frame=state.data.catalog.find(item=>item.id===91000003&&available.has(item.inventory_item_id))||state.data.catalog.find(item=>item.eluno.line_type==='frame'&&item.eluno.rx_able&&available.has(item.inventory_item_id));if(!frame)throw new Error('No prescription-compatible frames are available in this store.');state.cart={members:[{phone:'+919000000005',variant_ids:[frame.id,91000083]}],payment_method:'upi',channel:'walk_in'};state.activeWearer=0;state.quote=null;await persistCart();await navigate('billing');toast('Sample loaded. Review the prescription, then click Review offers & GST.'); }
/** Ask the server to price and validate the current family cart. */
async function prepareSale() {
  if(state.cart.members.some(member=>!member.variant_ids.length)) throw new Error('Select an item for every wearer.');
  const staff=state.user.role==='admin'?state.data.staff.find(item=>item.store_code===state.store&&item.can_override_discount)?.staff_id:state.user.staff_id;
  const payload={phone:state.cart.members[0].phone,store_code:state.store,staff_id:staff,variant_ids:[],members:state.cart.members,payment_method:state.cart.payment_method,channel:state.cart.channel};
  if(state.cart.override_percent) {payload.override_bps=Math.round(Number(state.cart.override_percent)*100);payload.reason_code=state.cart.reason_code;}
  state.quote=await post('/sales/prepare',payload);await persistCart();document.querySelector('#bill-panel').innerHTML=billPanel();toast('Quote saved. Review the exact amount before confirming payment.');
}
/** Complete a saved bill once and then display its durable source-linked result. */
async function completeSale(identifier) {
  try { await post('/sales/'+identifier+'/complete'); }
  catch(error) { toast('Payment result needs inspection: '+error.message);await showDetail(identifier);return; }
  state.cart={members:[],payment_method:'upi',channel:'walk_in'};state.quote=null;await persistCart();await showDetail(identifier);toast('Bill recorded. Invoice and Shopify order are ready.');
}
/** Collect a refund reason before showing a separate financial confirmation. */
function refundDialog() { modal.innerHTML=`<div class="modal-header"><h2>Prepare a full refund</h2><button class="button light" data-action="close-modal">Close</button></div><p>Original invoice: ${escapeHtml(state.detail.checkout.invoice_no)}</p><div class="notice">The frame returns to the billing store. Custom lenses are not restocked. GST is reversed from the original lines.</div><form id="refund-form"><label class="field">Reason<textarea name="reason" minlength="3" required placeholder="Customer return"></textarea></label><button class="button orange">Preview refund amount</button></form>`; }
/** Collect remake ownership and lens selection without adding a frame line. */
function remakeDialog() {
  const wearers=[...new Set(state.detail.quote.lines.map(line=>line.wearer_phone))];
  modal.innerHTML=`<div class="modal-header"><h2>A fresh lens. The same frame.</h2><button class="button light" data-action="close-modal">Close</button></div><p class="muted">Linked to ${escapeHtml(state.detail.checkout.invoice_no)}. Frame inventory stays untouched.</p><form id="remake-form" class="spacer"><div class="fields"><label class="field">Wearer<select name="wearer_phone">${wearers.map(phone=>`<option>${escapeHtml(phone)}</option>`).join('')}</select></label><label class="field">Replacement lens<select name="lens_variant_id">${state.data.catalog.filter(item=>item.eluno.line_type==='lens').map(item=>`<option value="${item.id}">${escapeHtml(item.product_title+' · '+item.title)}</option>`).join('')}</select></label><label class="field">Who bears the cost?<select name="cost_owner"><option value="company">Eluno</option><option value="customer">Customer</option><option value="external_optometrist">External optometrist</option></select></label><label class="field">Lab cost · INR<input name="lab_cost" type="number" min="0" step=".01" required></label></div><label class="field">Reason<textarea name="reason" minlength="3" required placeholder="Progressive adaptation / incorrect external prescription"></textarea></label><div class="notice">Customer-paid remakes use the replacement lens selling price and eligible offers. Other cost owners create a zero-customer-charge order; lab cost is tracked separately for recovery.</div><button class="button orange">Prepare remake</button></form>`;
}
/** Route button actions, disabling the clicked control while its request is pending. */
async function handleClick(event) {
  const button=event.target.closest('button,[data-detail]');if(!button)return;
  if(!['action','page','detail','category','wearer','product','quantity'].some(key=>key in button.dataset))return;
  if(state.busy)return;
  setBusy(true);
  const action=button.dataset.action;
  button.disabled=true;
  try {
    if(button.dataset.page) await navigate(button.dataset.page);
    else if(button.dataset.detail) await showDetail(button.dataset.detail);
    else if(button.dataset.category) {state.category=button.dataset.category;await billing(document.querySelector('#main'));}
    else if(button.dataset.wearer!==undefined) {state.activeWearer=Number(button.dataset.wearer);await billing(document.querySelector('#main'));}
    else if(button.dataset.quantity) {
      changeQuantity(Number(button.dataset.member),Number(button.dataset.variant),Number(button.dataset.quantity));
      invalidateQuote();await persistCart();await billing(document.querySelector('#main'));
    }
    else if(button.dataset.product) {
      changeQuantity(state.activeWearer,Number(button.dataset.product),1);
      invalidateQuote();await persistCart();await billing(document.querySelector('#main'));
    } else if(action==='logout') {await post('/auth/logout');state.user=null;state.csrf='';modal.close();renderLogin();}
    else if(action==='guided-demo') await guidedDemo();
    else if(action==='new-sale') {state.quote=null;state.cart={members:[],payment_method:'upi',channel:'walk_in'};await persistCart();await navigate('billing');}
    else if(action==='remove-wearer') {state.cart.members.splice(state.activeWearer,1);invalidateQuote();await persistCart();await billing(document.querySelector('#main'));}
    else if(action==='prepare-sale') await prepareSale();
    else if(action==='complete-sale') await completeSale(state.quote.checkout_id);
    else if(action==='complete-detail') await completeSale(state.detail.checkout.checkout_id);
    else if(action==='close-modal') modal.close();
    else if(action==='print') window.print();
    else if(action==='credit-note') {modal.querySelector('.receipt').outerHTML=receiptHtml(state.detail,true);toast('Credit note ready. Use Print invoice to print this document.');}
    else if(action==='cancel-bill') {modal.innerHTML=`<div class="modal-header"><h2>Cancel this draft</h2><button class="button light" data-action="close-modal">Close</button></div><p>The number stays in the invoice register.</p><form id="cancel-form" class="spacer"><label class="field">Reason<input name="reason" minlength="3" required></label><button class="button danger">Cancel unpaid bill</button></form>`;}
    else if(action==='refund-dialog') refundDialog();
    else if(action==='remake-dialog') remakeDialog();
    else if(action==='complete-refund') {await post('/refunds/'+state.detail.refunds[0].refund_id+'/complete');await showDetail(state.detail.checkout.checkout_id);toast('Refund recorded. Print the credit note and check the day-end report.');}
    else if(action==='reconcile-order') {await post('/sales/'+state.detail.checkout.checkout_id+'/reconcile-order');await showDetail(state.detail.checkout.checkout_id);}
    else if(action==='reconcile-refund') {await post('/refunds/'+state.detail.refunds[0].refund_id+'/reconcile-shopify');await showDetail(state.detail.checkout.checkout_id);}
    else if(action==='digest') {const yesterday=new Date(state.data.today+'T12:00:00Z');yesterday.setUTCDate(yesterday.getUTCDate()-1);await post('/api/reports/digest?day='+yesterday.toISOString().slice(0,10));await navigate('outbox');}
  } catch(error) {toast(error.message);} finally {button.disabled=false;setBusy(false);}
}
/** Handle forms with explicit request payloads and inline credential errors. */
async function handleSubmit(event) {
  const form=event.target;if(!(form instanceof HTMLFormElement))return;event.preventDefault();
  if(state.busy)return;setBusy(true);
  const values=Object.fromEntries(new FormData(form)),button=form.querySelector('button[type="submit"],button');if(button)button.disabled=true;
  try {
    if(form.id==='login-form') {const result=await post('/auth/login',values);state.user=result.user;state.csrf=result.csrf;await initializeWorkspace();}
    else if(form.id==='customer-form') {await loadCustomer(values.phone);if(state.cart.members.length>=10)throw new Error('Maximum ten wearers per demo bill.');state.cart.members.push({phone:values.phone,variant_ids:[]});state.activeWearer=state.cart.members.length-1;invalidateQuote();await persistCart();await billing(document.querySelector('#main'));}
    else if(['open-till-form','expense-form','close-till-form'].includes(form.id)) {const action={'open-till-form':'open','expense-form':'expense','close-till-form':'close'}[form.id];const result=await post('/api/till/'+action,{store_code:state.store,amount_paise:Math.round(Number(values.amount)*100),reason:values.reason||''});await navigate('till');toast(action==='close'?'Drawer closed. Variance '+money(result.variance_paise)+(result.flagged?' · Finance notification queued.':''):'Drawer updated.');}
    else if(form.id==='rx-form') {const body={phone:values.phone,valid_until:values.valid_until};for(const side of ['od','os'])body[side]={sph:Number(values[side+'_sph']),cyl:Number(values[side+'_cyl']),axis:values[side+'_axis']?Number(values[side+'_axis']):null,add:values[side+'_add']?Number(values[side+'_add']):null};await post('/api/prescriptions',body);delete state.customerCache[values.phone];toast('Prescription recorded with your clinical identity.');form.reset();}
    else if(form.id==='refund-form') {const refund=await post('/refunds/prepare',{checkout_id:state.detail.checkout.checkout_id,reason:values.reason});await showDetail(state.detail.checkout.checkout_id);toast('Refund prepared: '+money(refund.amount_paise)+'. Confirm refund to move money.');}
    else if(form.id==='cancel-form') {await post('/api/checkouts/'+state.detail.checkout.checkout_id+'/cancel',values);await showDetail(state.detail.checkout.checkout_id);}
    else if(form.id==='remake-form') {const result=await post('/api/remakes/prepare',{checkout_id:state.detail.checkout.checkout_id,lens_variant_id:Number(values.lens_variant_id),wearer_phone:values.wearer_phone,reason:values.reason,cost_owner:values.cost_owner,lab_cost_paise:Math.round(Number(values.lab_cost)*100)});await showDetail(result.checkout_id);toast('Lens-only remake prepared. Confirm to create the linked order.');}
  } catch(error) {if(form.id==='login-form')document.querySelector('#login-error').textContent=error.message;else toast(error.message);} finally {if(button)button.disabled=false;setBusy(false);}
}
/** Apply selection changes and invalidate pricing when commercial inputs change. */
async function handleChange(event) {
  if(state.busy)return;setBusy(true);
  try {
    const element=event.target;
    if(element.id==='store-select') {state.store=element.value;state.quote=null;state.cart={members:[],payment_method:'upi',channel:'walk_in'};await navigate(state.page);}
    else if(['channel','payment-method','override-percent','discount-reason'].includes(element.id)) {const key={'channel':'channel','payment-method':'payment_method','override-percent':'override_percent','discount-reason':'reason_code'}[element.id];state.cart[key]=element.value;invalidateQuote();await persistCart();document.querySelector('#bill-panel').innerHTML=billPanel();}
    else if(element.id==='report-date') await reportsPage(document.querySelector('#main'),element.value);
  } catch(error) {toast(error.message);} finally {setBusy(false);}
}
/** Restore server/browser drafts and load the authenticated workspace. */
async function initializeWorkspace() {
  state.cart={members:[],payment_method:'upi',channel:'walk_in'};state.quote=null;state.customerCache={};state.activeWearer=0;
  state.data=await api('/api/bootstrap');state.store=state.data.stores.some(item=>item.eluno.store_code===state.user.store_code)?state.user.store_code:'HSR';
  let saved=await api('/api/draft');
  try {const local=JSON.parse(localStorage.getItem('eluno-cart-'+state.user.username)||'null');if(local)saved=local;} catch(error) {localStorage.removeItem('eluno-cart-'+state.user.username);}
  if(saved.members) {state.cart=saved;if(state.data.stores.some(item=>item.eluno.store_code===saved.store_code))state.store=saved.store_code;if(saved.quote_id){try{const detail=await api('/api/checkouts/'+saved.quote_id+'/detail');if(detail.checkout.status==='draft')state.quote={...detail.quote,offers:detail.quote.offer_decisions};}catch(error){state.quote=null;}}}
  await navigate('overview');
}
/** Restore an existing login without exposing credentials or inventing demo state. */
async function boot() { try {state.user=await api('/auth/me');state.csrf=state.user.csrf;await initializeWorkspace();} catch(error) {renderLogin();} }
document.addEventListener('click',handleClick);
document.addEventListener('submit',handleSubmit);
document.addEventListener('change',handleChange);
// Filter the catalog locally without round trips or losing input focus.
document.addEventListener('input',event=>{if(event.target.id==='product-search'){state.search=event.target.value;document.querySelector('#products').innerHTML=productCards();}});
window.addEventListener('online',networkStatus);
window.addEventListener('offline',networkStatus);
boot();

