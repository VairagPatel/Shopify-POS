/* Eluno Store Studio: same-origin browser client. Money is always integer paise. */
'use strict';
const state = {user:null, csrf:'', data:null, store:'HSR', page:'overview', category:'frame', search:'', activeWearer:0, pendingFrameId:null,
  cart:{members:[],payment_method:'upi',channel:'walk_in'}, quote:null, stock:{}, customerCache:{}, transactions:[]};
const root = document.querySelector('#app');
const modal = document.querySelector('#modal');
const navItems = [['overview','◫','Overview'],['billing','⊕','New sale'],['transactions','▤','Bills & returns'],['clinical','◎','Prescriptions'],['till','▣','Cash drawer'],['reports','↗','Daily reports'],['evidence','✓','Demo & coverage'],['outbox','✉','Report outbox'],['audit','≡','Audit trail']];

/** Escape every server/user string before inserting it into HTML. */
function escapeHtml(value) { return String(value ?? '').replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character])); }
/** Format integer paise as inclusive INR without arithmetic in display strings. */
function money(value) { return new Intl.NumberFormat('en-IN',{style:'currency',currency:'INR',maximumFractionDigits:2}).format((value||0)/100); }
/** Create a new stable identifier for a separate cashier draft session. */
function newDraftId() { return 'DR-'+(globalThis.crypto?.randomUUID?crypto.randomUUID():Date.now().toString(36)+'-'+Math.random().toString(36).slice(2)); }
/** Make authenticated API calls and preserve meaningful validation messages. */
async function api(path, options={}) {
  const response = await fetch(path,{credentials:'same-origin',...options,headers:{'Content-Type':'application/json','X-CSRF-Token':state.csrf,...options.headers}});
  const result = await response.json();
  if (!response.ok) {
    if (response.status===401 && path!=='/auth/login') { state.user=null; renderLogin(); }
    const detail=result.detail;
    const error=new Error(typeof detail==='string'?detail:Array.isArray(detail)?detail.map(item=>item.msg).join('\n'):JSON.stringify(detail||result));
    error.status=response.status;throw error;
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
  root.innerHTML=`<div class="layout"><aside class="sidebar"><div class="brand">eluno<i>.</i></div><div class="brand-sub">STORE STUDIO</div><div class="nav-label">Workspace</div><nav>${navigation.map(([id,icon,label])=>`<button class="nav-button ${state.page===id?'active':''}" data-page="${id}"><span class="icon">${icon}</span>${label}</button>`).join('')}</nav><div class="sidebar-footer"><div class="environment"><span class="dot"></span><strong>Demo environment</strong><br><span class="muted">Mock Shopify + payments<br>Real workflows. Synthetic data.</span></div></div></aside><section class="workspace"><header class="topbar"><div class="actions"><span class="muted">⌖</span>${central&&['reports','outbox'].includes(state.page)?'<span class="pill green">ALL STORES · CENTRAL VIEW</span>':`<select id="store-select" aria-label="Billing store">${state.data.stores.map(store=>`<option value="${escapeHtml(store.eluno.store_code)}" ${store.eluno.store_code===state.store?'selected':''}>${escapeHtml(store.name.replace('Eluno ',''))}</option>`).join('')}</select><span class="pill">STORE ${escapeHtml(state.store)}</span>`}</div><div class="account"><span class="muted">${escapeHtml(state.data.today)}</span><span class="avatar">${escapeHtml(state.user.display_name.slice(0,1))}</span><div>${escapeHtml(state.user.display_name)}<small>${escapeHtml(state.user.role)}</small></div><button class="button ghost" data-action="logout">Sign out</button></div></header><div id="network-status"></div><main class="main" id="main"></main></section></div>`;
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
    else if(page==='clinical') await clinicalPage(main);
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
function product(identifier) { return (state.data?.catalog||[]).find(item=>item.id===Number(identifier)); }
/** Cache customer/prescription reads during a cart editing session. */
async function loadCustomer(phone) { if(!state.customerCache[phone]) {const record=await post('/api/customers',{phone});state.customerCache[phone]=record;state.customerCache[record.customer.phone]=record;}return state.customerCache[phone]; }
/** Persist cart edits locally first, then to the authenticated draft endpoint. */
async function persistCart() {
  state.cart.quote_id=state.quote?.checkout_id||null;
  const snapshot={...state.cart,store_code:state.store};
  localStorage.setItem('eluno-cart-'+state.user.username,JSON.stringify(snapshot));
  try { const saved=await api('/api/draft',{method:'PUT',body:JSON.stringify(snapshot)});state.cart.draft_id=saved.draft_id;state.cart.created_at=saved.created_at;state.cart.updated_at=saved.updated_at;localStorage.setItem('eluno-cart-'+state.user.username,JSON.stringify({...snapshot,...saved})); } catch(error) { toast('Cart saved on this device. '+error.message); }
}
/** Invalidate an old quote whenever cart inputs change. */
function invalidateQuote() { state.quote=null;delete state.cart.quote_id; }
/** Render billing with wearer-specific cart lines and a real server quote. */
async function billing(main) {
  if(!['cashier','manager','admin'].includes(state.user.role)) { main.innerHTML=heading('BILLING','Sales workspace','Your role can review records but cannot create sales.')+'<div class="card empty">Sign in with a cashier or manager account to create a bill.</div>'; return; }
  const inventory=await api('/api/inventory?store_code='+state.store);
  state.stock=Object.fromEntries(inventory.inventory_levels.map(item=>[item.inventory_item_id,item.available]));
  for(const member of state.cart.members) {normalizeCartMember(member);const record=await loadCustomer(member.phone);member.phone=record.customer.phone;}
  main.innerHTML=heading('A BETTER WAY TO BILL','Let’s find their next pair.','One customer or the whole family. Every prescription stays with its wearer.','<button class="button light" data-action="guided-demo">Load sample customer</button>')+
    `<div class="steps"><span class="step active"><b>1</b>Customer & Rx</span><span class="step-arrow">→</span><span class="step ${state.cart.members.length?'active':''}"><b>2</b>Choose products</span><span class="step-arrow">→</span><span class="step"><b>3</b>Configure lens</span><span class="step-arrow">→</span><span class="step ${state.quote?'active':''}"><b>4</b>Review & pay</span></div><div class="billing-grid"><div><section class="card"><div class="card-head"><h2>Who are we helping?</h2><span class="pill">${state.cart.members.length} WEARER${state.cart.members.length===1?'':'S'}</span></div><form id="customer-form"><div class="actions"><label class="field" style="flex:1;margin:0">Find an existing customer<input name="phone" list="customers" placeholder="Phone number or choose a sample" required><datalist id="customers">${state.data.customers.map(customer=>`<option value="${escapeHtml(customer.phone)}">${escapeHtml(customer.first_name+' '+customer.last_name)}</option>`).join('')}</datalist></label><button class="button light" style="margin-top:19px">Add wearer ＋</button></div></form>${wearerPanel()}</section><div class="catalog-tools"><div class="tabs">${[['frame','Frames'],['lens','Lenses'],['sunglasses','Sunglasses']].map(([category,label])=>`<button class="tab ${state.category===category?'active':''}" data-category="${category}">${label}</button>`).join('')}</div>${state.category!=='lens'?`<input class="search" id="product-search" placeholder="Search name / SKU" value="${escapeHtml(state.search)}" aria-label="Search catalog">`:''}</div><div class="products" id="products">${productCards()}</div><p class="muted" style="font-size:10px;margin-top:12px">${state.category==='lens'?'Each catalogue lens is sold as a pair. Choose a frame destination above, or buy lenses alone.':'Add frames independently, then use Lenses to attach a prescription pair. Ready-to-wear sunglasses need no prescription.'}</p></div><aside class="card bill-panel" id="bill-panel">${billPanel()}</aside></div>`;
  if(state.category==='lens')initializeLensSection();
}
/** Display each family member and the latest valid prescription. */
function wearerPanel() {
  if(!state.cart.members.length) return '<div class="empty">Start with a customer.<br>Their prescription and priority flags will appear here.</div>';
  state.activeWearer=Math.min(state.activeWearer,state.cart.members.length-1);
  const member=state.cart.members[state.activeWearer], data=state.customerCache[member.phone], customer=data.customer;
  const valid=data.prescriptions.filter(rx=>rx.valid_until>=state.data.today).sort((left,right)=>right.date.localeCompare(left.date))[0];
  const productLines=wearerProductLines(member),productCount=productLines.pairs.length+productLines.readyFrames.length+productLines.invalidLenses.length+productLines.lensOnly.length+productLines.standaloneFrames.length;
  return `<div class="wearer-tabs">${state.cart.members.map((wearer,index)=>`<button class="wearer-tab ${index===state.activeWearer?'active':''}" data-wearer="${index}">${escapeHtml(state.customerCache[wearer.phone].customer.first_name)} · ${index+1}</button>`).join('')}</div><div class="customer-summary"><span class="avatar">${escapeHtml(customer.first_name[0])}</span><div style="flex:1"><h3>${escapeHtml(customer.first_name+' '+customer.last_name)}</h3><small>${escapeHtml(customer.phone)}</small></div><button class="button ghost" data-action="remove-wearer">Remove</button></div><div class="actions">${customer.tags.split(',').filter(Boolean).map(tag=>`<span class="pill ${tag==='priority'?'orange':'green'}">${escapeHtml(tag.replace('campaign:','Campaign · '))}</span>`).join('')}${valid?'<span class="pill green">Current prescription</span>':'<span class="pill red">No current prescription</span>'}</div>${valid?`<div class="rx-grid"><span>RIGHT · SPH / CYL<b>${valid.od.sph} / ${valid.od.cyl}</b></span><span>LEFT · SPH / CYL<b>${valid.os.sph} / ${valid.os.cyl}</b></span><span>AXIS · R / L<b>${valid.od.axis??'—'}° / ${valid.os.axis??'—'}°</b></span><span>VALID THROUGH<b>${escapeHtml(valid.valid_until)}</b></span></div>`:'<div class="notice">An optometrist must record a current prescription before a lens can be billed.</div>'}<div class="bill-line"><small>Selected for this wearer</small><strong>${productCount} selection(s)</strong></div>`;
}
/** Show independent frame, lens and sunglasses sections using the same cart. */
function productCards() {
  const member=state.cart.members[state.activeWearer];
  if(state.category==='lens')return '<section class="card lens-section"><div class="eyebrow">LENSES</div><h2>Choose a lens pair</h2><p class="muted">Choose the lens type, then index and coating. Buy lenses alone or attach them to a frame already in your cart.</p><div id="lens-configurator"></div></section>';
  const items=state.data.catalog.filter(item=>item.eluno.line_type==='frame'&&(state.category==='sunglasses'?item.eluno.category==='sunglasses':item.eluno.category!=='sunglasses')&&(item.product_title+' '+item.sku+' '+item.title).toLowerCase().includes(state.search.toLowerCase()));
  items.sort((left,right)=>Number((state.stock[right.inventory_item_id]||0)>0)-Number((state.stock[left.inventory_item_id]||0)>0)||left.product_title.localeCompare(right.product_title));
  return items.map((item,index)=>{
    const selected=[...(member?.variant_ids||[]),...(member?.frame_only_variant_ids||[])].includes(item.id);
    const stock=item.inventory_item_id?state.stock[item.inventory_item_id]||0:null;
    const disabled=!member||stock===0;
    return `<button class="product ${selected?'selected':''}" data-product="${item.id}" ${disabled?'disabled':''}><div class="product-art" style="background:${['#eef0e8','#f0ece5','#ecefed'][index%3]}"><span class="stock">${stock===null?'MADE TO ORDER':stock===0?'OUT OF STOCK':stock+' IN STORE'}</span>${glasses(state.category==='sunglasses'?'sunglasses':'frame',item.title.toLowerCase().includes('gold')?'#8f784a':'#444b3d',index)}</div><div class="product-info"><h3>${escapeHtml(item.product_title)}</h3><small>${escapeHtml(item.title)} · ${escapeHtml(item.sku)}</small><div class="product-price">${money(Math.round(Number(item.price)*100))}<span>${disabled?'Unavailable':selected?'Add another':'Add to cart →'}</span></div></div></button>`;
  }).join('')||'<div class="empty">No matching products.</div>';
}
/** Read paired products and explicit standalone lines without combining their prices. */
function wearerProductLines(member) {
  const pairs=[],readyFrames=[],invalidLenses=[],ids=member.variant_ids||[];
  for(let index=0;index<ids.length;index++) {
    const item=product(ids[index]);if(!item)continue;
    if(item.eluno.line_type==='frame') {
      const lens=product(ids[index+1]);
      if(lens?.eluno.line_type==='lens'){pairs.push({frame:item,lens,frameIndex:index});index++;}
      else readyFrames.push({...item,cart_index:index});
    } else if(item.eluno.line_type==='lens')invalidLenses.push(item);
  }
  const lensOnly=(member.lens_only_variant_ids||[]).map(id=>product(id)).filter(Boolean);
  const standaloneFrames=(member.frame_only_variant_ids||[]).map((id,index)=>({frame:product(id),index})).filter(item=>item.frame);
  return {pairs,readyFrames,invalidLenses,lensOnly,standaloneFrames};
}
/** Recover old grouped drafts while preserving every selected product. */
function normalizeCartMember(member) {
  member.variant_ids||=[];member.lens_only_variant_ids||=[];member.frame_only_variant_ids||=[];
  const ids=member.variant_ids,frames=[],lenses=[];
  ids.forEach((id,index)=>{const item=product(id);if(item?.eluno.line_type==='frame')frames.push(index);else if(item?.eluno.line_type==='lens')lenses.push(index);});
  const adjacent=frames.filter(index=>lenses.includes(index+1));
  if(adjacent.length===lenses.length&&frames.every(index=>product(ids[index]).eluno.category==='sunglasses'||adjacent.includes(index)))return;
  const optical=frames.filter(index=>product(ids[index]).eluno.category!=='sunglasses');
  const optional=frames.filter(index=>product(ids[index]).eluno.category==='sunglasses'&&product(ids[index]).eluno.rx_able);
  const pairedFrames=[...optical,...optional.slice(0,Math.max(0,lenses.length-optical.length))].sort((a,b)=>a-b);
  const match=new Map(pairedFrames.slice(0,lenses.length).map((frame,index)=>[frame,lenses[index]]));
  const normalized=[];
  for(const index of frames){if(match.has(index))normalized.push(ids[index],ids[match.get(index)]);else if(product(ids[index]).eluno.category==='sunglasses')normalized.push(ids[index]);else member.frame_only_variant_ids.push(ids[index]);}
  for(const index of lenses)if(![...match.values()].includes(index))member.lens_only_variant_ids.push(ids[index]);
  for(const id of ids)if(!product(id))normalized.push(id);
  member.variant_ids=normalized;
}
/** Offer each unpaired frame plus a separate lens-only purchase destination. */
function lensTargets(member) {
  if(!member)return [];
  const lines=wearerProductLines(member);
  return [...lines.standaloneFrames.map(({frame,index})=>({key:'standalone:'+index,frame})),
    ...lines.readyFrames.filter(frame=>frame.eluno.category!=='sunglasses').map(frame=>({key:'legacy:'+frame.cart_index,frame}))];
}
/** Start a standalone frame line; the cashier can then choose whether to add a lens. */
function addStandaloneFrame(frame) {
  const member=state.cart.members[state.activeWearer];
  if(!member)throw new Error('Add a wearer first.');
  const all=state.cart.members.flatMap(wearer=>[...(wearer.variant_ids||[]),...(wearer.frame_only_variant_ids||[])]);
  const demand=all.filter(id=>product(id)?.inventory_item_id===frame.inventory_item_id).length;
  if(frame.inventory_item_id&&demand>=(state.stock[frame.inventory_item_id]||0))throw new Error('All available units of this frame are already in the cart.');
  if(member.variant_ids.length+member.lens_only_variant_ids.length+member.frame_only_variant_ids.length>=30)throw new Error('Maximum 30 units per wearer.');
  member.frame_only_variant_ids.push(frame.id);
  state.lensTarget='standalone:'+(member.frame_only_variant_ids.length-1);state.category='lens';
}
/** Find the latest current prescription for the selected wearer. */
function currentPrescription(member) {
  return (state.customerCache[member.phone]?.prescriptions||[]).filter(rx=>rx.valid_until>=state.data.today).sort((left,right)=>String(right.date).localeCompare(String(left.date)))[0]||null;
}
/** Explain clinical incompatibility before the cashier adds a lens or reviews the cart. */
function lensValidationReasons(member,lens) {
  const rx=currentPrescription(member), reasons=[];
  if(!rx)return ['No current prescription is available; ask an optometrist to record one.'];
  const limits=lens.eluno.rx_limits||{};
  for(const [name,eye] of [['Right',rx.od],['Left',rx.os]]) {
    const numeric=value=>value===null||value===undefined||value===''?NaN:Number(value);
    const sphere=numeric(eye.sph),cylinder=numeric(eye.cyl),axis=numeric(eye.axis),add=numeric(eye.add);
    if(!Number.isFinite(sphere)||sphere<Number(limits.sph_min)||sphere>Number(limits.sph_max))reasons.push(`${name} sphere is outside this lens range (${limits.sph_min} to ${limits.sph_max}); choose another index/lens.`);
    if(!Number.isFinite(cylinder)||Math.abs(cylinder)>Number(limits.cyl_abs_max))reasons.push(`${name} cylinder exceeds this lens limit (±${limits.cyl_abs_max}); choose another lens.`);
    if(!Number.isInteger(axis)||axis<0||axis>180||axis%5)reasons.push(`${name} axis must be present and in 5° steps; ask the optometrist to verify it.`);
    if(limits.add_required&&(!Number.isFinite(add)||add<Number(limits.add_min??0)||add>Number(limits.add_max??5)))reasons.push(`${name} ADD is missing or outside the supported range for this lens; confirm the prescription.`);
  }
  return reasons;
}
/** Open the standalone lens section using its selected frame destination, if any. */
function initializeLensSection() {
  const member=state.cart.members[state.activeWearer],container=document.querySelector('#lens-configurator');
  if(!member){container.innerHTML='<div class="empty">Add a wearer to choose lenses.</div>';return;}
  const target=lensTargets(member).find(item=>item.key===state.lensTarget);
  openLensConfigurator(target?.frame.id??null,target?.key||'lens_only',true);
}
/** Use the same catalogue-backed dropdowns for standalone lenses and prescription sunglasses. */
function openLensConfigurator(frameId=null,target=null,inline=false) {
  state.pendingFrameId=frameId;state.lensTarget=target;state.lensInline=inline;
  const lenses=state.data.catalog.filter(item=>item.eluno.line_type==='lens'),member=state.cart.members[state.activeWearer];
  const ranked=lenses.slice().sort((left,right)=>Number(lensValidationReasons(member,left).length>0)-Number(lensValidationReasons(member,right).length>0)||Number(left.eluno.index)-Number(right.eluno.index));
  const preferred=ranked[0];
  state.lensChoice={lens_type:preferred?.eluno.lens_type||'single_vision',index:String(preferred?.eluno.index??''),coating:preferred?.eluno.coating||'standard'};
  renderLensConfigurator();
}
/** Filter index and coating by the selected lens type and validate both eyes. */
function renderLensConfigurator() {
  const inline=state.lensInline,frame=state.pendingFrameId===null?null:product(state.pendingFrameId),member=state.cart.members[state.activeWearer];
  const lenses=state.data.catalog.filter(item=>item.eluno.line_type==='lens');
  const compatible=item=>lensValidationReasons(member,item).length===0&&(!frame||frame.eluno.rx_able);
  const types=[...new Set(lenses.map(item=>item.eluno.lens_type))].sort((left,right)=>Number(!lenses.some(item=>item.eluno.lens_type===left&&compatible(item)))-Number(!lenses.some(item=>item.eluno.lens_type===right&&compatible(item)))||left.localeCompare(right));
  const type=state.lensChoice.lens_type,byType=lenses.filter(item=>item.eluno.lens_type===type);
  const indices=[...new Set(byType.map(item=>String(item.eluno.index)))].sort((left,right)=>Number(!byType.some(item=>String(item.eluno.index)===left&&compatible(item)))-Number(!byType.some(item=>String(item.eluno.index)===right&&compatible(item)))||Number(left)-Number(right));
  if(!indices.includes(state.lensChoice.index))state.lensChoice.index=indices[0]||'';
  const byIndex=byType.filter(item=>String(item.eluno.index)===state.lensChoice.index);
  const coatings=[...new Set(byIndex.map(item=>item.eluno.coating))].sort((left,right)=>Number(!byIndex.some(item=>item.eluno.coating===left&&compatible(item)))-Number(!byIndex.some(item=>item.eluno.coating===right&&compatible(item)))||left.localeCompare(right));
  if(!coatings.includes(state.lensChoice.coating))state.lensChoice.coating=coatings[0]||'';
  const selected=byIndex.find(item=>item.eluno.coating===state.lensChoice.coating)||null;
  const reasons=selected?lensValidationReasons(member,selected):['This configuration is not in the catalogue.'];
  if(frame&&!frame.eluno.rx_able)reasons.unshift('This frame cannot accept prescription lenses. Choose another frame or a lens-only purchase.');
  const available=selected&&reasons.length===0,lensPrice=selected?Math.round(Number(selected.price)*100):0;
  const price=lensPrice+(!inline&&frame?Math.round(Number(frame.price)*100):0);
  const targets=lensTargets(member);
  const content=`${inline?`<label class="field spacer">Add lenses for<select id="lens-target"><option value="lens_only" ${state.lensTarget==='lens_only'?'selected':''}>Lenses only · customer’s own frame</option>${targets.map(target=>`<option value="${target.key}" ${state.lensTarget===target.key?'selected':''}>${escapeHtml(target.frame.sku+' · '+target.frame.product_title)}</option>`).join('')}</select><small>${frame?'The frame is already in your cart. Adding this lens creates one linked pair.':'This adds one standalone prescription lens pair.'}</small></label>`:`<div class="modal-header"><h2>Configure a lens pair</h2><button class="button light" data-action="close-modal">Close</button></div>`}
    <div class="fields spacer"><label class="field">Lens type<select id="lens-type">${types.map(value=>`<option value="${escapeHtml(value)}" ${type===value?'selected':''}>${escapeHtml(value.replaceAll('_',' '))}${lenses.some(item=>item.eluno.lens_type===value&&compatible(item))?'':' · unavailable for this prescription'}</option>`).join('')}</select></label>
    <label class="field">Index<select id="lens-index">${indices.map(value=>`<option value="${value}" ${state.lensChoice.index===value?'selected':''}>${value}${byType.some(item=>String(item.eluno.index)===value&&compatible(item))?'':' · unavailable'}</option>`).join('')}</select></label>
    <label class="field">Coating<select id="lens-coating">${coatings.map(value=>`<option value="${escapeHtml(value)}" ${state.lensChoice.coating===value?'selected':''}>${escapeHtml(value==='blue_cut'?'Blue cut':value.replaceAll('_',' '))}${byIndex.some(item=>item.eluno.coating===value&&compatible(item))?'':' · unavailable'}</option>`).join('')}</select></label></div>
    <div class="lens-result spacer">${glasses('lens')}<div><h3>${selected?escapeHtml(selected.product_title):'No matching lens'}</h3><p>${selected?escapeHtml(selected.sku+' · '+selected.title):''}</p><strong>${money(lensPrice)}</strong><small>One pair · GST inclusive</small></div></div>
    ${reasons.length?`<div class="notice"><strong>Prescription needs attention</strong><ul>${reasons.map(reason=>`<li>${escapeHtml(reason)}</li>`).join('')}</ul></div>`:'<div class="notice green">The selected lens is compatible with both eyes. We check again before payment.</div>'}
    <div class="actions"><button class="button orange" data-action="${frame?'add-configured-pair':'add-lens-only'}" ${available?'':'disabled'}>${inline?'Add lens to cart':frame?'Add frame + lens pair':'Add lens pair only'} · ${money(price)}</button>${inline?'':'<button class="button light" data-action="close-modal">Back to products</button>'}</div>`;
  if(inline)document.querySelector('#lens-configurator').innerHTML=content;
  else {modal.innerHTML=content;if(!modal.open)modal.showModal();}
}
/** Offer a ready-to-wear or prescription option for each selected sunglasses frame. */
function openSunglassesChoice(frameId) {
  const frame=product(frameId);state.pendingFrameId=frameId;
  modal.innerHTML=`<div class="modal-header"><div><div class="eyebrow">SUNGLASSES · ${escapeHtml(frame.sku)}</div><h2>How will these be worn?</h2></div><button class="button light" data-action="close-modal">Close</button></div><p class="muted">Ready-to-wear sunglasses are sold without prescription lenses. Choose Rx to configure a validated lens pair for this frame.</p><div class="actions spacer"><button class="button light" data-action="add-ready-sunglasses">Ready-to-wear · ${money(Math.round(Number(frame.price)*100))}</button><button class="button orange" data-action="configure-sunglasses-rx">Configure with prescription →</button></div>`;
  if(!modal.open)modal.showModal();
}
/** Return offers active today whose cart, wearer, and lens conditions match the current cart. */
function availableCoupons() {
  if(!state.data||!state.cart.members.length)return [];
  const offers=state.data.offers||[],paired=[],readyFrames=[],lensOnly=[],otherLenses=[];
  for(const member of state.cart.members) {
    const ids=member.variant_ids||[];
    for(let index=0;index<ids.length;index++) {
      const item=product(ids[index]);if(!item)continue;
      if(item.eluno.line_type==='frame') {
        const lens=product(ids[index+1]);
        if(lens?.eluno.line_type==='lens'){paired.push({frame:item,lens});index++;}
        else readyFrames.push(item);
      } else if(item.eluno.line_type==='lens') otherLenses.push(item);
    }
    for(const id of member.lens_only_variant_ids||[]) {const lens=product(id);if(lens)lensOnly.push(lens);}
    for(const id of member.frame_only_variant_ids||[]) {const frame=product(id);if(frame)readyFrames.push(frame);}
  }
  const frames=[...paired.map(pair=>pair.frame),...readyFrames],lenses=[...paired.map(pair=>pair.lens),...otherLenses,...lensOnly],lines=[...frames,...lenses],pairLines=paired.flatMap(pair=>[pair.frame,pair.lens]),pairCount=paired.length+lensOnly.length;
  const customer=state.customerCache[state.cart.members[0].phone]?.customer;
  const tags=new Set(String(customer?.tags||'').split(',').map(tag=>tag.trim()).filter(Boolean));
  const hasPair=paired.length>0;
  return offers.filter(offer=>{
    if(!offer.active||offer.offer_id==='MANAGER_OVERRIDE'||state.data.today<offer.valid_from||state.data.today>offer.valid_to)return false;
    const rule=offer.rule||{},condition=rule.condition||{},target=rule.applies_to;
    const targetLines=target==='frame'?frames:target==='lens'?lenses:target==='pair'?pairLines:target==='cart'?lines:[];
    if(!targetLines.length)return false;
    if(condition.customer_tag&&!tags.has(condition.customer_tag))return false;
    if(condition.min_pairs_in_cart&&pairCount<condition.min_pairs_in_cart)return false;
    if(condition.has_frame_and_lens&&!hasPair)return false;
    if((condition.lens_type||condition.coating||condition.index_min)&&!targetLines.some(item=>
      item.eluno.line_type==='lens'&&
      (!condition.lens_type||item.eluno.lens_type===condition.lens_type)&&
      (!condition.coating||item.eluno.coating===condition.coating)&&
      (!condition.index_min||Number(item.eluno.index)>=Number(condition.index_min))
    ))return false;
    return true;
  });
}
/** Display the coupon's configured value without calculating a discount in the browser. */
function couponLabel(offer) {
  const discount=offer.rule.discount;
  if(discount.type==='percent'){const cap=offer.rule.max_discount_paise??discount.max_discount_paise;return `${(Number(discount.value_bps||discount.value_bps_max)/100).toFixed(0)}% off${cap!=null?' · max '+money(cap):''}`;}
  return `${money(Number(discount.value_paise||0))} off`;
}
/** Return the display name for an offer or its stable ID when metadata is missing. */
function offerName(offerId) { return (state.data?.offers||[]).find(offer=>offer.offer_id===offerId)?.name||offerId; }

/** Make coupon selection and its server-calculated application visible as separate steps. */
function couponControls(coupons, invalid) {
  const selected=state.cart.offer_id||'';
  const applied=(state.quote?.offers||[]).find(offer=>offer.offer_id===selected&&offer.applied);
  return `<label class="field">Coupon / offer<select id="offer-code"><option value="">No coupon selected</option>${coupons.map(offer=>`<option value="${escapeHtml(offer.offer_id)}" ${selected===offer.offer_id?'selected':''}>${escapeHtml(offer.offer_id+' · '+offer.name)} · ${escapeHtml(couponLabel(offer))}</option>`).join('')}</select><small>${coupons.length?'Choose an eligible coupon, then click Apply coupon to see the calculated discount.':'No coupons match today’s date and cart.'}</small></label>${selected?`<button class="button light" data-action="apply-coupon" ${invalid.length?'disabled':''}>Apply coupon & review bill</button>`:''}<p id="coupon-status" class="info" aria-live="polite">${applied?'Applied '+escapeHtml(selected)+' · − '+money(applied.amount_paise):selected?'Selected '+escapeHtml(selected)+' · apply it to calculate the discount.':'No coupon discount. Coupons are never applied automatically.'}</p>`;
}

/** Show every frame and lens as its own line, with a visible link for configured pairs. */
function billPanel() {
  const members=state.cart.members,coupons=availableCoupons();
  if(state.cart.offer_id&&!coupons.some(offer=>offer.offer_id===state.cart.offer_id)){state.cart.offer_id='';invalidateQuote();}
  const ids=members.flatMap(member=>[...(member.variant_ids||[]),...(member.lens_only_variant_ids||[]),...(member.frame_only_variant_ids||[])]);
  const gross=ids.reduce((sum,id)=>sum+Math.round(Number(product(id)?.price||0)*100),0),invalid=[];
  const wearerLines=members.map((member,memberIndex)=>{
    const {pairs,readyFrames,invalidLenses,lensOnly,standaloneFrames}=wearerProductLines(member),lines=[];
    const units=[...(member.variant_ids||[]),...(member.lens_only_variant_ids||[]),...(member.frame_only_variant_ids||[])];
    if(!units.length)invalid.push('Add a frame, sunglasses or a lens pair for '+(state.customerCache[member.phone]?.customer.first_name||'this wearer')+'.');
    for(const id of units)if(!product(id))invalid.push('Product '+id+' is no longer in the catalogue. Remove it before checkout.');
    for(const {frame,lens,frameIndex} of pairs){
      const reasons=lensValidationReasons(member,lens);if(reasons.length)invalid.push(lens.sku+': '+reasons.join(' '));
      lines.push(`<div class="cart-pair"><div class="bill-line"><span><strong>${escapeHtml(frame.product_title)}</strong><small>${escapeHtml(frame.sku)} · Frame</small></span><strong>${money(Math.round(Number(frame.price)*100))}</strong></div><div class="bill-line"><span><strong>${escapeHtml(lens.product_title)}</strong><small>${escapeHtml(lens.sku)} · Lens pair for ${escapeHtml(frame.sku)}</small></span><strong>${money(Math.round(Number(lens.price)*100))}</strong></div><div class="actions"><button class="button ghost" data-remove-pair="${frameIndex}" data-member="${memberIndex}">Remove pair</button><button class="button ghost" data-remove-pair-lens="${frameIndex}" data-member="${memberIndex}">Remove lens only</button></div></div>`);
    }
    for(const frame of readyFrames){
      const sunglasses=frame.eluno.category==='sunglasses';
      if(!sunglasses)invalid.push(frame.sku+': configure a lens or move this legacy frame to a frame-only purchase.');
      lines.push(`<div class="bill-line"><span><strong>${escapeHtml(frame.product_title)}</strong><small>${escapeHtml(frame.sku)} · ${sunglasses?'Ready-to-wear sunglasses':'Lens required'}</small>${sunglasses?'':`<button class="button ghost" data-configure-frame="${frame.cart_index}" data-frame-source="legacy" data-member="${memberIndex}">Add lens</button>`}<button class="button ghost" data-remove-pair="${frame.cart_index}" data-member="${memberIndex}">Remove</button></span><strong>${money(Math.round(Number(frame.price)*100))}</strong></div>`);
    }
    for(const {frame,index} of standaloneFrames)lines.push(`<div class="bill-line"><span><strong>${escapeHtml(frame.product_title)}</strong><small>${escapeHtml(frame.sku)} · Frame only</small><button class="button ghost" data-configure-frame="${index}" data-frame-source="standalone" data-member="${memberIndex}">Add lens</button><button class="button ghost" data-remove-frame-only="${index}" data-member="${memberIndex}">Remove frame</button></span><strong>${money(Math.round(Number(frame.price)*100))}</strong></div>`);
    for(const lens of invalidLenses)invalid.push(lens.sku+': move this item to the Lenses section.');
    for(const [lensIndex,lens] of lensOnly.entries()){
      const reasons=lensValidationReasons(member,lens);if(reasons.length)invalid.push(lens.sku+': '+reasons.join(' '));
      lines.push(`<div class="bill-line"><span><strong>${escapeHtml(lens.product_title)}</strong><small>${escapeHtml(lens.sku)} · Lenses only</small><button class="button ghost" data-remove-lens-only="${lensIndex}" data-member="${memberIndex}">Remove lens</button></span><strong>${money(Math.round(Number(lens.price)*100))}</strong></div>`);
    }
    return `<div class="bill-line"><strong>${escapeHtml(state.customerCache[member.phone]?.customer.first_name||member.phone)}</strong><small>Wearer</small></div>${lines.join('')}`;
  }).join('');
  if(invalid.length)state.quote=null;
  const quote=state.quote,decisions=quote?.offers||quote?.offer_decisions||[];
  const manager=['admin','manager'].includes(state.user.role);
  return `<div class="card-head"><h2>The bill</h2><span class="pill orange">${quote?'REVIEWED':'DRAFT'}</span></div>${wearerLines||'<div class="empty">Add a wearer, then select frames, lenses or sunglasses.</div>'}
    <div class="divider"></div><label class="field">Sale source<select id="channel">${[['walk_in','Walk-in'],['whatsapp','WhatsApp booked'],['online_pickup','Online pickup']].map(([value,label])=>`<option value="${value}" ${state.cart.channel===value?'selected':''}>${label}</option>`).join('')}</select></label>
    <label class="field">Payment method<select id="payment-method">${['upi','card','cash'].map(method=>`<option value="${method}" ${state.cart.payment_method===method?'selected':''}>${method.toUpperCase()}</option>`).join('')}</select></label>
    ${couponControls(coupons,invalid)}
    ${manager?`<details ${state.cart.override_percent||state.cart.reason_code?'open':''}><summary>Manager discount</summary><label class="field">Discount % · maximum 10<input id="override-percent" type="number" min="0" max="10" step="0.1" value="${escapeHtml(state.cart.override_percent||'')}"></label><label class="field">Reason code<select id="discount-reason"><option value="">Choose a reason</option>${['walk_out_retention','service_recovery','price_match'].map(reason=>`<option value="${reason}" ${state.cart.reason_code===reason?'selected':''}>${reason.replaceAll('_',' ')}</option>`).join('')}</select></label><small>Enter both a percentage and reason, then review the bill. The exact percentage replaces any coupon. Approved by ${escapeHtml(state.user.display_name)}.</small>${state.cart.override_percent&&!state.cart.reason_code?'<p class="info">Choose a reason to apply the manager discount.</p>':''}</details>`:''}
    <div class="bill-line"><span>MRP total</span><strong>${money(gross)}</strong></div>
    ${quote?`<div class="bill-line"><span>Offers & discounts</span><strong style="color:var(--green)">− ${money(gross-quote.total_paise)}</strong></div><div class="bill-line"><span>Taxable value</span><strong>${money(quote.total_paise-quote.tax_paise)}</strong></div><div class="bill-line"><span>Included GST</span><strong>${money(quote.tax_paise)}</strong></div>`:''}
    <div class="bill-line total-row"><span>${quote?'Amount due':'Before discounts'}</span><strong class="total">${money(quote?quote.total_paise:gross)}</strong></div>
    ${invalid.length?`<div class="notice"><strong>Cart needs attention</strong><ul>${invalid.map(reason=>`<li>${escapeHtml(reason)}</li>`).join('')}</ul></div>`:''}
    ${quote?`<button class="button orange" data-action="complete-sale">Confirm ${state.cart.payment_method.toUpperCase()} · ${money(quote.total_paise)} →</button><button class="button light" data-detail="${quote.checkout_id}">View quote details</button><p class="info">${escapeHtml(quote.invoice_no)} · Confirm payment to create the order and invoice.</p><details><summary>Why these offers?</summary>${decisions.map(offer=>`<p class="info"><b>${escapeHtml(offerName(offer.offer_id))}</b> · ${offer.applied?money(offer.amount_paise):'Not applied'}<br>${escapeHtml(offer.reason)}</p>`).join('')}</details>`:`<button class="button orange" data-action="prepare-sale" ${!members.length||invalid.length?'disabled':''}>Review offers & GST →</button><p class="info">Frames and lenses can be purchased separately. Each attached frame has one lens pair. All lens prescriptions are checked again at checkout.</p>`}`;
}
/** Remove the exact selected occurrence, including its attached lens. */
function removeCartPair(memberIndex,frameIndex) {
  const ids=state.cart.members[memberIndex]?.variant_ids||[];
  if(frameIndex<0||frameIndex>=ids.length)return;
  ids.splice(frameIndex,product(ids[frameIndex+1])?.eluno.line_type==='lens'?2:1);
}
/** Remove a lens while keeping its frame as an explicit frame-only purchase. */
function removePairedLens(memberIndex,frameIndex) {
  const member=state.cart.members[memberIndex];
  if(product(member?.variant_ids[frameIndex+1])?.eluno.line_type!=='lens')return;
  const removed=member.variant_ids.splice(frameIndex,2);member.frame_only_variant_ids.push(removed[0]);
}
/** Remove exactly one standalone lens pair without affecting another frame. */
function removeLensOnly(memberIndex,lensIndex) {
  const selected=state.cart.members[memberIndex]?.lens_only_variant_ids||[];
  if(lensIndex>=0&&lensIndex<selected.length)selected.splice(lensIndex,1);
}

/** List transaction states without presenting an uncertain payment as a completed sale. */
function transactionTable(records) { return records.length?`<div class="table-wrap"><table><thead><tr><th>INVOICE / CUSTOMER</th><th>STATUS</th><th>AMOUNT</th><th></th></tr></thead><tbody>${records.map(record=>`<tr><td>${escapeHtml(record.invoice_no||'Unallocated')}<small>${escapeHtml(record.customer_name||record.customer_id)}${record.remake?' · Remake':''}</small></td><td>${badge(record.status)}${record.refund_status?`<small>Refund: ${escapeHtml(record.refund_status.replaceAll('_',' '))}</small>`:''}</td><td>${money(record.total_paise)}<small>${escapeHtml(record.method?.toUpperCase())}</small></td><td class="right"><button class="button light small" data-detail="${record.checkout_id}">Open ↗</button></td></tr>`).join('')}</tbody></table></div>`:'<div class="empty">No bills yet. Start a sale to see the full process here.</div>'; }
/** Present searchable transaction history and an auditable invoice register. */
async function transactionsPage(main) {
  const [records,register,drafts]=await Promise.all([api('/api/transactions?store_code='+state.store),api('/api/register?store_code='+state.store),api('/api/drafts/history?store_code='+state.store)]);state.transactions=records;
  main.innerHTML=heading('EVERY BILL HAS A STORY','Bills, returns & remakes','Inspect source orders, refund records, checkout timing and every saved draft version.','<button class="button orange" data-action="new-sale">＋ New sale</button>')+`<section class="card section-gap">${transactionTable(records)}</section><section class="card section-gap"><div class="card-head"><h2>Draft history</h2><span class="pill">${drafts.length} SAVED VERSIONS</span></div><p class="muted" style="font-size:12px">Each save is retained with a draft ID, actor, store, timestamp and time since the previous save. Full cart snapshots remain in SQLite.</p><div class="table-wrap"><table><thead><tr><th>DRAFT ID / CHECKOUT</th><th>STATUS</th><th>CREATED BY</th><th>CREATED</th><th>SAVED</th><th>TIME SINCE PRIOR SAVE</th><th>SHOPIFY ORDER</th></tr></thead><tbody>${drafts.map(item=>`<tr><td>${escapeHtml(item.draft_id||'Legacy')}<small>${escapeHtml(item.checkout_id||'Cart not quoted')}</small></td><td>${badge(item.checkout_status||item.status)}</td><td>${escapeHtml(item.created_by||item.username)}<small>${escapeHtml(item.created_by_staff_id||'Staff ID unavailable')}</small></td><td>${escapeHtml(item.created_at||'Legacy record')}</td><td>${escapeHtml(item.saved_at)}</td><td>${item.elapsed_ms===null?'—':(item.elapsed_ms/1000).toFixed(2)+' s'}</td><td>${escapeHtml(item.shopify_order_id||'Not created')}</td></tr>`).join('')||'<tr><td colspan="7">No saved draft versions yet.</td></tr>'}</tbody></table></div></section><section class="card"><div class="card-head"><h2>Invoice register</h2><span class="pill">${register.length} ALLOCATIONS</span></div><p class="muted" style="font-size:12px">Reserved and cancelled numbers stay visible. Numbers are never reused.</p><div class="table-wrap"><table><thead><tr><th>SEQUENCE</th><th>INVOICE</th><th>STATUS</th><th>ALLOCATED AT</th></tr></thead><tbody>${register.map(item=>`<tr><td>${item.serial_number}</td><td>${escapeHtml(item.invoice_no)}</td><td>${badge(item.status)}</td><td>${escapeHtml(new Date(item.allocated_at).toLocaleString('en-IN'))}</td></tr>`).join('')}</tbody></table></div></section>`;
}
/** Render source-linked invoice and credit-note documents as printable HTML. */
function receiptHtml(detail, credit=false) {
  const quote=detail?.quote, checkout=detail?.checkout, refunds=Array.isArray(detail?.refunds)?detail.refunds:[], refund=refunds.find(item=>item.status==='recorded');
  if(!quote||!checkout)throw new Error('Bill details are incomplete: the saved quote or checkout record is missing. Refresh Bills & returns and inspect the source record.');
  const sourceLines=quote.order_payload?.line_items||[];
  const lines=Array.isArray(quote.lines)?quote.lines:sourceLines.map(line=>({title:line.variant_id,hsn:(Array.isArray(line.properties)?line.properties:[]).find(item=>item.name==='hsn')?.value,gross_paise:Math.round(Number(line.price)*100),discount_paise:Math.round(Number(line.total_discount)*100),cgst_paise:Math.round(Number(line.tax_lines?.[0]?.price||0)*100),sgst_paise:Math.round(Number(line.tax_lines?.[1]?.price||0)*100)}));
  const sign=credit?-1:1;
  return `<article class="receipt"><div class="receipt-brand"><div><div class="brand">eluno<i>.</i></div><small>STORE STUDIO · ${escapeHtml(checkout.store_code)}</small></div><div class="right"><h2>${credit?'Credit note':'Tax invoice'}</h2><p>${escapeHtml(credit?'CN/'+checkout.invoice_no:checkout.invoice_no)}</p><small>${credit?'Original invoice: '+escapeHtml(checkout.invoice_no):escapeHtml(new Date(checkout.created_at).toLocaleDateString('en-IN'))}</small></div></div><div class="notice">Demo document · synthetic customer data · not a legally issued tax document.</div><p><strong>${escapeHtml(quote.customer?.first_name||'Customer')} ${escapeHtml(quote.customer?.last_name||'')}</strong> · ${escapeHtml(quote.customer?.phone||checkout.customer_id)}</p><div class="table-wrap"><table><thead><tr><th>ITEM / WEARER / HSN</th><th>MRP</th><th>DISCOUNT</th><th>TAXABLE</th><th>CGST</th><th>SGST</th></tr></thead><tbody>${lines.map(line=>`<tr><td>${escapeHtml(line.title||line.variant_id)}<small>${escapeHtml(line.wearer_phone||'')} · ${escapeHtml(line.hsn)}${line.rx_id?' · '+escapeHtml(line.rx_id):''}</small></td><td>${money(sign*line.gross_paise)}</td><td>${money(sign*line.discount_paise)}</td><td>${money(sign*(line.gross_paise-line.discount_paise-line.cgst_paise-line.sgst_paise))}</td><td>${money(sign*line.cgst_paise)}</td><td>${money(sign*line.sgst_paise)}</td></tr>`).join('')}</tbody></table></div><div class="bill-line total-row"><span>${credit?'Refunded total':'Total · GST inclusive'}</span><strong class="total">${money(sign*quote.total_paise)}</strong></div><div class="receipt-footer">${credit?'Shopify refund: '+escapeHtml(refund?.shopify_refund_id):'Shopify order: '+escapeHtml(checkout.shopify_order_id||'Pending — quote only')}<br>Payment: ${escapeHtml(quote.method.toUpperCase())} · Checkout: ${escapeHtml(checkout.checkout_id)}${quote.remake?'<br>Remake of '+escapeHtml(quote.remake.original_invoice)+' · Cost owner: '+escapeHtml(quote.remake.cost_owner):''}<br>Thank you for seeing the world with Eluno.</div></article>`;
}
/** Open the detail drawer with real next actions for the persisted state. */
async function showDetail(identifier) {
  const detail=await api('/api/checkouts/'+encodeURIComponent(identifier)+'/detail'); state.detail=detail;
  const checkout=detail.checkout, manager=['manager','admin'].includes(state.user.role), seller=['cashier','manager','admin'].includes(state.user.role), refunds=Array.isArray(detail.refunds)?detail.refunds:[], refund=refunds[0], sourceRefunds=Array.isArray(detail.order?.refunds)?detail.order.refunds:[];
  modal.innerHTML=`<div class="modal-header"><div><div class="eyebrow">BILL DETAILS</div><h2>${escapeHtml(checkout.invoice_no)}</h2></div><button class="button light" data-action="close-modal">Close ✕</button></div><div class="actions no-print section-gap">${badge(checkout.status)}${refund?badge('refund '+refund.status):''}<button class="button light small" data-action="print">Print invoice</button>${refund?.status==='recorded'?'<button class="button light small" data-action="credit-note">Credit note</button>':''}${checkout.status==='draft'&&seller?'<button class="button orange small" data-action="complete-detail">Confirm payment</button><button class="button danger small" data-action="cancel-bill">Cancel draft</button>':''}${checkout.status==='order_recorded'&&manager&&!refund?'<button class="button light small" data-action="refund-dialog">Full refund</button><button class="button light small" data-action="remake-dialog">Remake lens</button>':''}${refund?.status==='prepared'&&manager?'<button class="button orange small" data-action="complete-refund">Confirm refund</button>':''}${checkout.status==='order_uncertain'&&manager?'<button class="button orange small" data-action="reconcile-order">Reconcile order</button>':''}${refund?.status==='shopify_uncertain'&&manager?'<button class="button orange small" data-action="reconcile-refund">Reconcile refund</button>':''}</div>${checkout.error_detail?'<div class="notice no-print">'+escapeHtml(checkout.error_detail)+'</div>':''}${receiptHtml(detail)}<div class="timeline no-print"><p>Quote saved · Invoice number reserved</p><p>${checkout.payment_charge_id?'Payment reference recorded: '+escapeHtml(checkout.payment_charge_id):'Payment has not been confirmed'}</p><p>${checkout.shopify_order_id?'Shopify order recorded: '+escapeHtml(checkout.shopify_order_id):'Shopify order not yet recorded'}</p><p>${checkout.checkout_elapsed_ms==null?'Checkout timing not recorded':'Checkout API timing: '+Number(checkout.checkout_elapsed_ms).toFixed(2)+' ms · '+escapeHtml(checkout.timing_recorded_at||'')}</p>${refund?'<p>SQLite refund_attempts: '+escapeHtml(refund.refund_id)+' · '+escapeHtml(refund.status)+' · terminal '+escapeHtml(refund.terminal_refund_id||'pending')+' · Shopify refund '+escapeHtml(refund.shopify_refund_id||'pending')+'</p>':'<p>No local SQLite refund attempt exists for this bill.</p>'}<p>Shopify source order refund records: ${sourceRefunds.map(item=>escapeHtml(String(item.id))).join(', ')||'none'}.</p></div><details class="no-print"><summary>Technical evidence · SQLite attempt + Shopify source state</summary><p>Local refund progress is stored in eluno.sqlite3 → refund_attempts. The Shopify mock order and its refunds are returned by GET /api/checkouts/{id}/detail.</p><pre>${escapeHtml(JSON.stringify(detail,null,2))}</pre></details>`;
  if(!modal.open) modal.showModal();
}
/** Render open/expense/close drawer controls and explain the variance calculation. */
async function tillPage(main) {
  const till=await api('/api/till?store_code='+state.store);state.till=till;
  const seller=['cashier','manager','admin'].includes(state.user.role),manager=['manager','admin'].includes(state.user.role);
  main.innerHTML=heading('THE LITTLE THINGS ADD UP','Cash drawer','Opening float + cash sales + paid-ins − cash refunds − expenses = expected cash.')+
    (till.open?`<div class="grid stats">${stat('Opening float',money(till.opening_paise),'Recorded at drawer open')}${stat('Cash sales',money(till.cash_sales_paise),'From Shopify transactions')}${stat('Paid-ins',money(till.paid_ins_paise||0),'Reasoned cash added')}${stat('Expenses',money(till.expenses_paise),'Every cash-out has a reason')}${stat('Expected in drawer',money(till.expected_paise),'After sales, refunds and expenses')}</div><div class="grid two-col"><section class="card"><h2>Record a cash movement</h2><form id="expense-form" class="spacer"><label class="field">Movement<select name="direction"><option value="expense">Paid-out / expense</option><option value="paid-in">Paid-in / add cash</option></select></label><div class="fields"><label class="field">Amount · INR<input name="amount" type="number" min="0.01" step="0.01" required></label><label class="field">Reason<input name="reason" placeholder="Courier, tea, supplies…" minlength="3" required></label></div><button class="button light" ${seller?'':'disabled'}>Record cash movement</button></form><div class="divider"></div>${[...till.expenses,...(till.paid_ins||[]).map(item=>({...item,reason:'Paid-in: '+item.reason}))].map(item=>`<div class="bill-line"><span>${escapeHtml(item.reason)}<br><small>${escapeHtml(item.actor)}</small></span><strong>${money(item.amount_paise)}</strong></div>`).join('')||'<p class="muted">No expenses recorded.</p>'}</section><section class="card"><h2>Count & close</h2><p class="muted spacer" style="font-size:12px">Enter the physical cash count. A variance above ₹200 queues a finance notification.</p><form id="close-till-form" class="spacer"><label class="field">Counted cash · INR<input name="amount" type="number" min="0" step="0.01" required></label><button class="button orange full-width" ${manager?'':'disabled'}>Reconcile & close drawer</button></form><p class="info muted spacer" style="font-size:11px">Manager permission required. The outbox shows notification delivery status.</p></section></div>`:`<section class="card" style="max-width:550px"><h2>Start with your opening float.</h2><p class="muted spacer">Open a drawer before recording a cash sale or refund.</p><form id="open-till-form" class="spacer"><label class="field">Opening cash · INR<input name="amount" type="number" min="0" step="0.01" value="2000" required></label><button class="button orange" ${seller?'':'disabled'}>Open drawer</button></form>${(till.history||[]).map(item=>`<div class="bill-line"><span>Previous close<small>${escapeHtml(item.closed_at)}</small></span><strong>Variance ${money(item.variance_paise)}</strong></div>`).join('')}</section>`);
}
/** Show all-store source-based reporting with channel comparison. */
async function reportsPage(main,day=state.data.today) {
  const report=await api('/api/reports?day='+encodeURIComponent(day));state.reportDay=day;
  const central=['admin','finance'].includes(state.user.role);
  const totals=report.stores.reduce((sum,item)=>({
    sales:sum.sales+item.sales_paise,gross:sum.gross+item.gross_paise,bills:sum.bills+item.bill_count,
    discounts:sum.discounts+item.discounts_paise,refunds:sum.refunds+item.refunds_paise,
    tax:sum.tax+item.tax_paise,taxable:sum.taxable+item.taxable_paise,
    net:sum.net+item.net_collected_paise,delta:sum.delta+item.reconciliation_delta_paise
  }),{sales:0,gross:0,bills:0,discounts:0,refunds:0,tax:0,taxable:0,net:0,delta:0});
  const average=totals.bills?Math.round(totals.sales/totals.bills):0;
  const channels={};report.stores.forEach(store=>Object.entries(store.channels).forEach(([key,value])=>channels[key]=(channels[key]||0)+value));
  const paymentMethods={};report.stores.forEach(store=>Object.entries(store.payment_methods||{}).forEach(([method,amount])=>paymentMethods[method]=(paymentMethods[method]||0)+amount));
  const scope=central?`All ${report.stores.length} stores combined`:'Your store · '+state.store;
  const mismatches=report.stores.filter(store=>store.reconciliation_delta_paise!==0);
  main.innerHTML=heading('DAILY BUSINESS SUMMARY','Total daily performance',`${scope} · ${day} · Asia/Kolkata`,
    `<div class="actions"><input type="date" id="report-date" class="search" value="${day}" aria-label="Report date"><button class="button orange" data-action="download-day-end">Download day-end CSV</button><button class="button light" data-action="download-daily">Download daily summary CSV</button></div>`)+`
    <section class="card daily-total section-gap" aria-label="Combined daily sales">
      <div><span class="pill orange">${scope}</span><h2>Total sales for the day</h2>
      <strong class="daily-sales" data-report="sales">${money(totals.sales)}</strong>
      <p class="muted">After discounts, including GST · before refunds</p></div>
      <div class="daily-highlights"><div><span>Total bills</span><strong data-report="bills">${totals.bills}</strong></div>
      <div><span>Average bill value</span><strong data-report="average">${money(average)}</strong></div>
      <div><span>Net collected</span><strong data-report="net">${money(totals.net)}</strong></div></div>
    </section>
    ${!totals.bills?'<div class="notice">No sales recorded for this date. Refunds on earlier bills may still appear below. Choose another date to review previous activity.</div>':''}
    <div class="grid finance-stats">${stat('Gross before discounts',money(totals.gross),'MRP inclusive of GST')}${stat('Discounts given',money(totals.discounts),'Already deducted from total sales')}${stat('Included GST',money(totals.tax),'Not an extra charge')}${stat('Taxable sales',money(totals.taxable),'Sales excluding GST')}${stat('Refunds issued',money(totals.refunds),'Refunds made on this date')}</div>
    <div class="grid two-col section-gap"><section class="card"><h2>Sales by channel · combined</h2>
      ${Object.entries(channels).map(([name,value])=>`<div class="bar-row"><span>${escapeHtml(name.replaceAll('_',' '))}</span><div class="bar-track"><div class="bar" style="width:${Math.max(0,Math.min(100,value/Math.max(totals.sales,1)*100))}%"></div></div><strong class="right">${money(value)}</strong></div>`).join('')||'<div class="empty">No channel sales for this date.</div>'}
    </section><section class="card"><h2>Daily reconciliation</h2><div class="bill-line"><span>Payments minus sales</span><strong>${money(totals.delta)}</strong></div>
      <p class="${mismatches.length?'error':'muted'}">${mismatches.length?`${mismatches.length} store(s) have a difference. Review the store details below, even if the combined difference is zero.`:'Recorded sale payments match order totals across this report.'}</p>
      <p class="info">Net collected = successful sale payments − refunds issued on this date, including returns of earlier bills. Average bill value = combined sales ÷ total bills. Cash drawer variance and bank settlement are separate checks.</p>
    </section></div>
    <section class="card section-gap"><h2>Successful sale payments</h2><div class="table-wrap"><table><thead><tr><th>PAYMENT METHOD</th><th>AMOUNT</th></tr></thead><tbody>${Object.entries(paymentMethods).map(([method,amount])=>`<tr><td>${escapeHtml(method.toUpperCase())}</td><td>${money(amount)}</td></tr>`).join('')||'<tr><td colspan="2">No payments on this date.</td></tr>'}</tbody></table></div><p class="info">Day-end CSV includes refunds on bills from the selected date. Daily summary CSV matches this screen and includes refunds actually issued on the selected date. Both are computed from Shopify orders.</p></section>
    <details class="card section-gap" id="store-breakdown"><summary>View store-by-store breakdown (${report.stores.length} stores)</summary>
      <div class="card-head spacer"><h2>Store performance</h2><span class="pill green">SHOPIFY SOURCE</span></div>
      <div class="table-wrap"><table><thead><tr><th>STORE</th><th>BILLS</th><th>SALES</th><th>AVG BILL</th><th>DISCOUNTS</th><th>NET COLLECTED</th><th>DELTA</th></tr></thead><tbody>
      ${report.stores.map(item=>`<tr><td>${escapeHtml(item.name)}</td><td>${item.bill_count}</td><td>${money(item.sales_paise)}</td><td>${money(item.average_bill_paise)}</td><td>${money(item.discounts_paise)}</td><td>${money(item.net_collected_paise)}</td><td><span class="pill ${item.reconciliation_delta_paise?'red':'green'}">${money(item.reconciliation_delta_paise)}</span></td></tr>`).join('')}
      </tbody></table></div></details><p class="info">Source: Shopify mock orders and transactions. This is a daily consolidated report, not a payment-gateway settlement statement.</p>`;
}
/** Download an authorized source report without changing any sales or refund data. */
async function downloadReport(basis) {
  const parameters=new URLSearchParams({day:state.reportDay||state.data.today,basis});
  if(!['admin','finance'].includes(state.user.role))parameters.set('store_code',state.store);
  const response=await fetch('/api/reports/export?'+parameters,{credentials:'same-origin'});
  if(!response.ok){const error=await response.json();throw new Error(error.detail||'The report could not be downloaded.');}
  const blob=await response.blob(),url=URL.createObjectURL(blob),link=document.createElement('a');
  link.href=url;link.download='eluno-'+basis+'-'+(state.reportDay||state.data.today)+'.csv';
  document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
/** Offer clinical entry only to optometrists and administrators. */
async function clinicalPage(main) {
  const allowed=['admin','optometrist'].includes(state.user.role);
  const history=allowed?await api('/api/prescriptions/history'+(state.user.role==='admin'?'':'?store_code='+state.store)):[];
  main.innerHTML=heading('EVERY LENS STARTS HERE','Prescription studio','Manual axis entry uses 5-degree steps. Local records receive an Rx ID, author and creation time.')+`<section class="card" style="max-width:850px"><form id="rx-form"><div class="fields"><label class="field">Customer phone<input name="phone" list="rx-customers" required><datalist id="rx-customers">${state.data.customers.map(item=>`<option value="${item.phone}">${escapeHtml(item.first_name+' '+item.last_name)}</option>`).join('')}</datalist></label><label class="field">Valid until<input name="valid_until" type="date" min="${state.data.today}" required></label></div>${['od','os'].map((side,index)=>`<h3 class="spacer">${index?'Left eye · OS':'Right eye · OD'}</h3><div class="fields spacer"><label class="field">Sphere<input name="${side}_sph" type="number" min="-30" max="30" step="0.25" value="0" required></label><label class="field">Cylinder<input name="${side}_cyl" type="number" min="-12" max="12" step="0.25" value="0" required></label><label class="field">Axis<select name="${side}_axis" required><option value="">Choose axis (0°–180°)</option>${Array.from({length:37},(_,number)=>`<option value="${number*5}">${number*5}°</option>`).join('')}</select></label><label class="field">ADD<input name="${side}_add" type="number" min="0" max="5" step="0.25" value="0" required></label></div>`).join('')}<div class="notice">Enter sphere, cylinder, axis and ADD for both eyes. Use 5° axis steps; enter 0.00 where ADD is not prescribed. Values are checked before saving and again during billing.</div><button class="button orange" ${allowed?'':'disabled'}>Save prescription</button>${allowed?'':'<p class="error">Your role cannot create clinical records.</p>'}</form></section><section class="card section-gap"><div class="card-head"><h2>Prescription records saved in this app</h2><span class="pill">${history.length} RECORDS</span></div><p class="muted">Database table: prescriptions. Phone numbers are left out of this audit view.</p><div class="table-wrap"><table><thead><tr><th>RX ID</th><th>CUSTOMER ID</th><th>VALID UNTIL</th><th>CREATED BY</th><th>STAFF ID</th><th>STORE / CREATED</th></tr></thead><tbody>${history.map(item=>`<tr><td>${escapeHtml(item.rx_id)}</td><td>${escapeHtml(item.customer_id||'—')}</td><td>${escapeHtml(item.valid_until||'—')}</td><td>${escapeHtml(item.created_by||'legacy')}</td><td>${escapeHtml(item.created_by_staff_id||'—')}</td><td>${escapeHtml(item.store_code||'—')}<small>${escapeHtml(item.created_at||'legacy')}</small></td></tr>`).join('')||'<tr><td colspan="6">No locally entered prescriptions.</td></tr>'}</tbody></table></div></section>`;
}
/** Connect stakeholder requests to explicit acceptance evidence and remaining limits. */
async function evidencePage(main) {
  const evidence=await api('/api/evidence');
  main.innerHTML=heading('BUILT TO BE EXPLAINED','The demo, end to end.','A requirement is complete only when the behavior and its evidence agree.','<button class="button orange" data-action="guided-demo">Run the sale walkthrough ↗</button>')+`<div class="grid stats">${stat('Requirements tracked',evidence.requirements.length,'Includes separate workstreams')}${stat('Completion samples',evidence.timings.samples,'Successful confirmation calls')}${stat('Observed p95',evidence.timings.p95_ms===null?'—':(evidence.timings.p95_ms/1000).toFixed(2)+'s','Local mock · not production SLA')}${stat('Target','< 10s','Customer confirmation → order result')}</div><div class="notice">Discounts are opt-in: one selected coupon, or a manager percentage with a reason. Coupon discounts do not auto-apply or stack. No live payments or real Shopify admin connection.</div><section class="card"><div class="card-head"><h2>Stakeholder acceptance map</h2><span class="pill">TECH LEAD VIEW</span></div>${evidence.requirements.map((item,index)=>`<div class="requirement"><span class="flow-number">${String(index+1).padStart(2,'0')}</span><div><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.behavior)}</p><small>${escapeHtml(item.owner)} · ${escapeHtml(item.evidence)}</small>${item.limit?'<p><strong>Boundary:</strong> '+escapeHtml(item.limit)+'</p>':''}</div>${badge(item.status)}</div>`).join('')}</section>`;
}
/** Display the report schedule and delivery status without faking sent email. */
async function outboxPage(main) {
  const result=await api('/api/outbox');
  const messages=result.messages;
  const queued=messages.filter(message=>message.status==='queued').length;
  const accepted=messages.filter(message=>message.status==='sent').length;
  const attention=messages.filter(message=>!['queued','sent'].includes(message.status)).length;
  main.innerHTML=heading('REPORT DELIVERY','Report outbox','Daily leadership reports and cash-drawer alerts, in one place.',
    '<button class="button orange" data-action="digest">Generate yesterday’s report</button>')+`
    <div class="outbox-settings section-gap"><div><span class="pill orange">DELIVERY</span><strong>${escapeHtml(result.delivery)}</strong><p>Queued reports are saved previews. “SMTP accepted” confirms server acceptance, not delivery to an inbox.</p></div><div><span class="pill">DAILY SCHEDULE</span><strong>10:00 AM IST</strong><p>Yesterday’s report · catches up after restart.<br>Generating again keeps the existing report for that day.</p></div></div>
    <div class="grid stats">${stat('Recent messages',messages.length,'Latest 50 messages')}${stat('Queued',queued,'Waiting for configured delivery')}${stat('SMTP accepted',accepted,'Accepted by the email server')}${stat('Needs review',attention,'Sending or uncertain outcome')}</div>
    <div class="outbox-list">${messages.map(message=>outboxMessage(message)).join('')||'<section class="card empty"><h2>Your outbox is empty</h2><p class="spacer">Generate yesterday’s report to preview the leadership email here. Cash-drawer alerts appear when closing variance exceeds ₹200.</p></section>'}</div>`;
}
/** Format a stored report as a readable table, preserving unknown message bodies safely. */
function outboxBody(message) {
  const lines=String(message.body||'').trim().split(/\r?\n/);
  const header=lines.findIndex(line=>line.trim()==='Store | Bills | Average bill | Discounts');
  const rows=header>=0?lines.slice(header+1).filter(line=>line.trim()).map(line=>line.split('|').map(cell=>cell.trim())):[];
  const valid=message.id.startsWith('digest-')&&rows.length>0&&rows.every(row=>row.length===4&&/^\d+$/.test(row[1])&&/^INR \d+\.\d{2}$/.test(row[2])&&/^INR \d+\.\d{2}$/.test(row[3]));
  if(!valid)return `<div class="outbox-body">${escapeHtml(message.body||'No message content.')}</div>`;
  return `<div class="outbox-report-heading"><h3>Store summary for this report</h3><span class="pill">${rows.length} stores</span></div><div class="table-wrap"><table class="outbox-table"><thead><tr><th>Store</th><th>Bills</th><th>Average bill value</th><th>Discounts given</th></tr></thead><tbody>${rows.map(row=>`<tr><td><strong>${escapeHtml((state.data?.stores||[]).find(store=>store.eluno.store_code===row[0])?.name||row[0])}</strong><small>${escapeHtml(row[0])}</small></td><td>${escapeHtml(row[1])}</td><td>${money(Math.round(Number(row[2].slice(4))*100))}</td><td>${money(Math.round(Number(row[3].slice(4))*100))}</td></tr>`).join('')}</tbody></table></div>`;
}
/** Present truthful delivery state, India-local creation time and original email evidence. */
function outboxMessage(message) {
  const digest=message.id.startsWith('digest-');
  const labels={queued:'Queued',sent:'SMTP accepted',sending:'Sending · check outcome',delivery_uncertain:'Delivery uncertain'};
  const descriptions={queued:'Saved in the outbox; not sent yet.',sent:'The configured SMTP server accepted this message.',sending:'Delivery was started. Inspect the outcome before sending again.',delivery_uncertain:'The delivery result is unknown. Review the error and mail server before any resend.'};
  const timestamp=new Date(message.created_at);
  const created=Number.isNaN(timestamp.getTime())?message.created_at:new Intl.DateTimeFormat('en-IN',{timeZone:'Asia/Kolkata',day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'}).format(timestamp)+' IST';
  const color=message.status==='sent'?'green':message.status==='queued'?'orange':'red';
  return `<article class="card outbox-message" data-message-id="${escapeHtml(message.id)}"><div class="outbox-message-head"><div><div class="eyebrow">${digest?'LEADERSHIP REPORT':'OPERATIONS ALERT'}</div><h2>${escapeHtml(message.subject)}</h2></div><span class="pill ${color}">${escapeHtml(labels[message.status]||message.status)}</span></div>
    <div class="outbox-meta"><span><b>Created</b> ${escapeHtml(created)}</span><span><b>Intended audience</b> ${digest?'Founder / leadership':'Finance'}</span>${digest?`<span><b>Report date</b> ${escapeHtml(message.id.slice(7))}</span>`:''}</div>
    ${outboxBody(message)}<div class="outbox-delivery-note">${escapeHtml(descriptions[message.status]||'Review this delivery status.')}</div>
    ${message.error?`<div class="outbox-error"><strong>Delivery needs attention</strong><p>${escapeHtml(message.error)}</p></div>`:''}
    <details class="outbox-original"><summary>View original email text</summary><pre>${escapeHtml(message.body)}</pre><small>Message reference: ${escapeHtml(message.id)}</small></details></article>`;
}
/** Render central audit events with actor and result information. */
async function auditPage(main) { const entries=await api('/api/audit'); main.innerHTML=heading('ACCOUNTABILITY, BUILT IN','A traceable store.','Who acted, what changed, and when. Server-side permissions protect each action.')+`<section class="card table-wrap"><table><thead><tr><th>TIME</th><th>ACTOR</th><th>ACTION</th><th>RESULT</th></tr></thead><tbody>${entries.map(item=>`<tr><td>${escapeHtml(new Date(item.at).toLocaleString('en-IN'))}</td><td>${escapeHtml(item.actor)}</td><td class="code">${escapeHtml(item.action)}</td><td class="code">${escapeHtml(item.detail)}</td></tr>`).join('')}</tbody></table></section>`; }
/** Prepare a sample cart while keeping the customer-confirmation step explicit. */
async function guidedDemo() { const inventory=await api('/api/inventory?store_code='+state.store);const available=new Set((inventory.inventory_levels||[]).filter(item=>item.available>0).map(item=>item.inventory_item_id));const catalog=state.data?.catalog||[];const frame=catalog.find(item=>item.id===91000003&&available.has(item.inventory_item_id))||catalog.find(item=>item.eluno.line_type==='frame'&&item.eluno.rx_able&&available.has(item.inventory_item_id));if(!frame)throw new Error('No prescription-compatible frames are available in this store.');state.cart={members:[{phone:'+919000000004',variant_ids:[frame.id,91000083]}],payment_method:'upi',channel:'walk_in',draft_id:newDraftId()};state.activeWearer=0;state.quote=null;await persistCart();await navigate('billing');toast('Sample loaded. Review the prescription, then click Review offers & GST.'); }
/** Ask the server to price and validate the current family cart. */
async function prepareSale() {
  if(!state.cart.members.length||state.cart.members.some(member=>!(member.variant_ids||[]).length&&!(member.lens_only_variant_ids||[]).length&&!(member.frame_only_variant_ids||[]).length)) throw new Error('Add a frame or a lens-only pair for every wearer.');
  const staff=state.user.role==='admin'?(state.data?.staff||[]).find(item=>item.store_code===state.store&&item.can_override_discount)?.staff_id:state.user.staff_id;
  const payload={phone:state.cart.members[0].phone,store_code:state.store,staff_id:staff,variant_ids:[],members:state.cart.members,payment_method:state.cart.payment_method,channel:state.cart.channel};
  if(state.cart.override_percent&&Number(state.cart.override_percent)>0&&state.cart.reason_code) {payload.override_bps=Math.round(Number(state.cart.override_percent)*100);payload.reason_code=state.cart.reason_code;payload.selected_offer_id='MANAGER_OVERRIDE';}
  else if(state.cart.offer_id)payload.selected_offer_id=state.cart.offer_id;
  state.quote=await post('/sales/prepare',payload);await persistCart();document.querySelector('#bill-panel').innerHTML=billPanel();toast('Quote saved. Review the exact amount before confirming payment.');
}
/** Complete a saved bill once and then display its durable source-linked result. */
async function completeSale(identifier) {
  try { await post('/sales/'+identifier+'/complete'); }
  catch(error) { toast('Payment result needs inspection: '+error.message);await showDetail(identifier);return; }
  if(state.quote?.checkout_id===identifier||state.cart.quote_id===identifier){state.cart={members:[],payment_method:'upi',channel:'walk_in',draft_id:newDraftId()};state.quote=null;await persistCart();}
  await navigate('transactions');await showDetail(identifier);toast('Bill recorded. Invoice and Shopify order are ready.');
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
  if(!['action','page','detail','category','wearer','product','quantity','removePair','removeLensOnly','removeFrameOnly','removePairLens','configureFrame'].some(key=>key in button.dataset))return;
  if(state.busy)return;
  setBusy(true);
  const action=button.dataset.action;
  button.disabled=true;
  try {
    if(button.dataset.page) await navigate(button.dataset.page);
    else if(button.dataset.detail) await showDetail(button.dataset.detail);
    else if(button.dataset.category) {state.category=button.dataset.category;await billing(document.querySelector('#main'));}
    else if(button.dataset.wearer!==undefined) {state.activeWearer=Number(button.dataset.wearer);state.lensTarget='lens_only';await billing(document.querySelector('#main'));}
    else if(button.dataset.quantity) {
      changeQuantity(Number(button.dataset.member),Number(button.dataset.variant),Number(button.dataset.quantity));
      invalidateQuote();await persistCart();await billing(document.querySelector('#main'));
    }
    else if(button.dataset.removePair!==undefined) {removeCartPair(Number(button.dataset.member),Number(button.dataset.removePair));invalidateQuote();await persistCart();await billing(document.querySelector('#main'));}
    else if(button.dataset.removeLensOnly!==undefined) {removeLensOnly(Number(button.dataset.member),Number(button.dataset.removeLensOnly));invalidateQuote();await persistCart();await billing(document.querySelector('#main'));}
    else if(button.dataset.configureFrame!==undefined) {state.activeWearer=Number(button.dataset.member);state.lensTarget=button.dataset.frameSource+':'+button.dataset.configureFrame;state.category='lens';await billing(document.querySelector('#main'));}
    else if(button.dataset.removeFrameOnly!==undefined) {state.cart.members[Number(button.dataset.member)].frame_only_variant_ids.splice(Number(button.dataset.removeFrameOnly),1);state.lensTarget='lens_only';invalidateQuote();await persistCart();await billing(document.querySelector('#main'));}
    else if(button.dataset.removePairLens!==undefined) {removePairedLens(Number(button.dataset.member),Number(button.dataset.removePairLens));invalidateQuote();await persistCart();await billing(document.querySelector('#main'));}
    else if(button.dataset.product) {const frame=product(Number(button.dataset.product));if(!frame)throw new Error('This product is no longer available.');if(frame.eluno.category==='sunglasses')openSunglassesChoice(frame.id);else {addStandaloneFrame(frame);invalidateQuote();await persistCart();await billing(document.querySelector('#main'));}}
    else if(action==='configure-lens-only') openLensConfigurator();
    else if(action==='add-ready-sunglasses') {const member=state.cart.members[state.activeWearer],frame=product(state.pendingFrameId);member.variant_ids.push(frame.id);modal.close();invalidateQuote();await persistCart();await billing(document.querySelector('#main'));}
    else if(action==='configure-sunglasses-rx') openLensConfigurator(state.pendingFrameId);
    else if(action==='add-configured-pair'||action==='add-lens-only') {
      const member=state.cart.members[state.activeWearer];if(!member)throw new Error('Choose a wearer first.');
      const lens=state.data.catalog.find(item=>item.eluno.line_type==='lens'&&item.eluno.lens_type===state.lensChoice.lens_type&&String(item.eluno.index)===state.lensChoice.index&&item.eluno.coating===state.lensChoice.coating);
      if(!lens)throw new Error('That lens configuration is not in the catalogue.');
      const reasons=lensValidationReasons(member,lens);if(reasons.length)throw new Error(reasons.join('\n'));
      const units=member.variant_ids.length+member.lens_only_variant_ids.length+member.frame_only_variant_ids.length;
      if(units>=30)throw new Error('Maximum 30 units per wearer.');
      if(action==='add-lens-only')member.lens_only_variant_ids.push(lens.id);
      else {
        const frame=product(state.pendingFrameId);if(!frame?.eluno.rx_able)throw new Error('This frame cannot accept a prescription lens.');
        const [source,indexText]=String(state.lensTarget||'').split(':'),index=Number(indexText);
        if(source==='standalone') {
          if(member.frame_only_variant_ids[index]!==frame.id)throw new Error('This frame selection changed. Select the frame again.');
          member.frame_only_variant_ids.splice(index,1);member.variant_ids.push(frame.id,lens.id);
        } else if(source==='legacy') {
          if(member.variant_ids[index]!==frame.id||product(member.variant_ids[index+1])?.eluno.line_type==='lens')throw new Error('This frame already has a lens. Select another frame.');
          member.variant_ids.splice(index+1,0,lens.id);
        } else {
          const demand=state.cart.members.flatMap(wearer=>[...wearer.variant_ids,...wearer.frame_only_variant_ids]).filter(id=>product(id)?.inventory_item_id===frame.inventory_item_id).length;
          if(frame.inventory_item_id&&demand>=(state.stock[frame.inventory_item_id]||0))throw new Error('No frame stock remains at this store.');
          if(units+2>30)throw new Error('Maximum 30 units per wearer.');
          member.variant_ids.push(frame.id,lens.id);
        }
      }
      if(modal.open)modal.close();state.lensTarget='lens_only';invalidateQuote();await persistCart();await billing(document.querySelector('#main'));toast('Lens added. Review the cart before payment.');
    }
    else if(action==='logout') {await post('/auth/logout');state.user=null;state.csrf='';modal.close();renderLogin();}
    else if(action==='guided-demo') await guidedDemo();
    else if(action==='new-sale') {state.quote=null;state.category='frame';state.activeWearer=0;state.customerCache={};state.lensTarget='lens_only';state.cart={members:[],payment_method:'upi',channel:'walk_in',draft_id:newDraftId()};await persistCart();await navigate('billing');}
    else if(action==='retry-workspace') await initializeWorkspace();
    else if(action==='remove-wearer') {state.cart.members.splice(state.activeWearer,1);invalidateQuote();await persistCart();await billing(document.querySelector('#main'));}
    else if(action==='prepare-sale'||action==='apply-coupon') await prepareSale();
    else if(action==='complete-sale') await completeSale(state.quote.checkout_id);
    else if(action==='complete-detail') await completeSale(state.detail.checkout.checkout_id);
    else if(action==='close-modal') modal.close();
    else if(action==='print') window.print();
    else if(action==='credit-note') {modal.querySelector('.receipt').outerHTML=receiptHtml(state.detail,true);toast('Credit note ready. Use Print invoice to print this document.');}
    else if(action==='cancel-bill') {modal.innerHTML=`<div class="modal-header"><h2>Cancel this draft</h2><button class="button light" data-action="close-modal">Close</button></div><p>The number stays in the invoice register.</p><form id="cancel-form" class="spacer"><label class="field">Reason<input name="reason" minlength="3" required></label><button class="button danger">Cancel unpaid bill</button></form>`;}
    else if(action==='refund-dialog') refundDialog();
    else if(action==='remake-dialog') remakeDialog();
    else if(action==='complete-refund') {const identifier=state.detail.checkout.checkout_id;await post('/refunds/'+state.detail.refunds[0].refund_id+'/complete');await navigate('transactions');await showDetail(identifier);toast('Refund recorded in Shopify and SQLite. The credit note is ready.');}
    else if(action==='reconcile-order') {await post('/sales/'+state.detail.checkout.checkout_id+'/reconcile-order');await showDetail(state.detail.checkout.checkout_id);}
    else if(action==='reconcile-refund') {await post('/refunds/'+state.detail.refunds[0].refund_id+'/reconcile-shopify');await showDetail(state.detail.checkout.checkout_id);}
    else if(action==='download-day-end') await downloadReport('day_end');
    else if(action==='download-daily') await downloadReport('daily');
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
    else if(form.id==='customer-form') {const record=await loadCustomer(values.phone);if(state.cart.members.length>=10)throw new Error('Maximum ten wearers per demo bill.');state.cart.members.push({phone:record.customer.phone,variant_ids:[],lens_only_variant_ids:[],frame_only_variant_ids:[]});state.activeWearer=state.cart.members.length-1;invalidateQuote();await persistCart();await billing(document.querySelector('#main'));}
    else if(['open-till-form','expense-form','close-till-form'].includes(form.id)) {const action={'open-till-form':'open','expense-form':values.direction||'expense','close-till-form':'close'}[form.id];const result=await post('/api/till/'+action,{store_code:state.store,amount_paise:Math.round(Number(values.amount)*100),reason:values.reason||''});await navigate('till');toast(action==='close'?'Drawer closed. Variance '+money(result.variance_paise)+(result.flagged?' · Finance notification queued.':''):'Drawer updated.');}
    else if(form.id==='rx-form') {const body={phone:values.phone,valid_until:values.valid_until,store_code:state.store};for(const side of ['od','os'])body[side]={sph:Number(values[side+'_sph']),cyl:Number(values[side+'_cyl']),axis:Number(values[side+'_axis']),add:Number(values[side+'_add'])};const saved=await post('/api/prescriptions',body);state.customerCache={};toast('Prescription '+saved.rx_id+' recorded by '+state.user.username+'.');await clinicalPage(document.querySelector('#main'));}
    else if(form.id==='refund-form') {const refund=await post('/refunds/prepare',{checkout_id:state.detail.checkout.checkout_id,reason:values.reason});await showDetail(state.detail.checkout.checkout_id);toast('Refund prepared: '+money(refund.amount_paise)+'. Confirm refund to move money.');}
    else if(form.id==='cancel-form') {const identifier=state.detail.checkout.checkout_id;await post('/api/checkouts/'+identifier+'/cancel',values);if(state.quote?.checkout_id===identifier){invalidateQuote();await persistCart();}await navigate('transactions');await showDetail(identifier);}
    else if(form.id==='remake-form') {const result=await post('/api/remakes/prepare',{checkout_id:state.detail.checkout.checkout_id,lens_variant_id:Number(values.lens_variant_id),wearer_phone:values.wearer_phone,reason:values.reason,cost_owner:values.cost_owner,lab_cost_paise:Math.round(Number(values.lab_cost)*100)});await showDetail(result.checkout_id);toast('Lens-only remake prepared. Confirm to create the linked order.');}
  } catch(error) {if(form.id==='login-form'){const loginError=document.querySelector('#login-error');if(state.user)renderStartupError(error);else if(loginError)loginError.textContent=error.message;else toast(error.message);}else toast(error.message);} finally {if(button)button.disabled=false;setBusy(false);}
}
/** Apply selection changes and invalidate pricing when commercial inputs change. */
async function handleChange(event) {
  if(state.busy)return;setBusy(true);
  try {
    const element=event.target;
    if(element.id==='store-select') {state.store=element.value;state.quote=null;state.cart={members:[],payment_method:'upi',channel:'walk_in',draft_id:newDraftId()};await persistCart();await navigate(state.page);}
    else if(['channel','payment-method','override-percent','discount-reason','offer-code'].includes(element.id)) {const key={'channel':'channel','payment-method':'payment_method','override-percent':'override_percent','discount-reason':'reason_code','offer-code':'offer_id'}[element.id];state.cart[key]=element.value;if(element.id==='offer-code'){state.cart.override_percent='';state.cart.reason_code='';}if(['override-percent','discount-reason'].includes(element.id)&&Number(state.cart.override_percent)>0&&state.cart.reason_code)state.cart.offer_id='';invalidateQuote();await persistCart();document.querySelector('#bill-panel').innerHTML=billPanel();}
    else if(element.id==='report-date') await reportsPage(document.querySelector('#main'),element.value);
    else if(element.id==='lens-target'){const target=lensTargets(state.cart.members[state.activeWearer]).find(item=>item.key===element.value);openLensConfigurator(target?.frame.id??null,target?.key||'lens_only',true);}
    else if(['lens-type','lens-index','lens-coating'].includes(element.id)){const key={'lens-type':'lens_type','lens-index':'index','lens-coating':'coating'}[element.id];state.lensChoice[key]=element.value;renderLensConfigurator();}
  } catch(error) {toast(error.message);} finally {setBusy(false);}
}
/** Restore server/browser drafts and load the authenticated workspace. */
async function initializeWorkspace() {
  state.cart={members:[],payment_method:'upi',channel:'walk_in',draft_id:newDraftId()};state.quote=null;state.customerCache={};state.activeWearer=0;
  state.data=await api('/api/bootstrap');state.store=state.data.stores.some(item=>item.eluno.store_code===state.user.store_code)?state.user.store_code:'HSR';
  const savedCart=await api('/api/draft');let savedMeta={};
  try{savedMeta=await api('/api/draft/metadata');}catch(error){if(error.status!==404)throw error;}
  let saved={...savedCart,...savedMeta};
  try {const local=JSON.parse(localStorage.getItem('eluno-cart-'+state.user.username)||'null');if(local)saved={...local,...savedMeta};} catch(error) {localStorage.removeItem('eluno-cart-'+state.user.username);}
  if(saved.members) {state.cart=saved;for(const member of state.cart.members)normalizeCartMember(member);if(state.data.stores.some(item=>item.eluno.store_code===saved.store_code))state.store=saved.store_code;if(saved.quote_id){try{const detail=await api('/api/checkouts/'+saved.quote_id+'/detail');if(detail.checkout.status==='draft')state.quote={...detail.quote,offers:detail.quote.offer_decisions};}catch(error){state.quote=null;}}}
  if(state.quote){
    const selected=Number(state.cart.override_percent)>0&&state.cart.reason_code?'MANAGER_OVERRIDE':state.cart.offer_id||null;
    if((state.quote.offers||[]).some(offer=>offer.applied&&offer.offer_id!==selected))invalidateQuote();
  }
  await navigate('overview');
}
/** Restore an existing login without exposing credentials or inventing demo state. */
async function boot() {
  try {state.user=await api('/auth/me');state.csrf=state.user.csrf;}
  catch(error){if(error.status===401){renderLogin();return;}renderStartupError(error);return;}
  try{await initializeWorkspace();}catch(error){renderStartupError(error);}
}
/** Keep an authenticated workspace failure distinct from an incorrect password. */
function renderStartupError(error) {
  root.innerHTML=`<section class="card" style="margin:8vh auto;max-width:640px"><h1>We couldn’t open your workspace.</h1><p class="spacer">${escapeHtml(error.message)}</p><div class="actions spacer"><button class="button orange" data-action="retry-workspace">Retry loading</button><button class="button light" data-action="logout">Sign out</button></div></section>`;
}
document.addEventListener('click',handleClick);
document.addEventListener('submit',handleSubmit);
document.addEventListener('change',handleChange);
// Filter the catalog locally without round trips or losing input focus.
document.addEventListener('input',event=>{if(event.target.id==='product-search'){state.search=event.target.value;document.querySelector('#products').innerHTML=productCards();}});
window.addEventListener('online',networkStatus);
window.addEventListener('offline',networkStatus);
boot();

