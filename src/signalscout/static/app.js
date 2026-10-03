const sourceLabels = {x:'X', web:'Web / news', hn:'Hacker News', reddit:'Reddit', github:'GitHub', rss:'RSS / API'};
const sourceKeys = Object.keys(sourceLabels);
const ruleLabels = {
  topics:['Topics','A topic to monitor'], include:['Include keywords','Add an include keyword'],
  exclude:['Exclude keywords','Add an exclude keyword'], competitors:['Competitors','Name, domain, or handle'],
  people:['Influential people','Name, handle, or profile URL']
};
let profile = null, currentView = 'feed', currentTab = 'all', currentPage = 1;
let currentItems = [], currentDetail = null, runs = [], detailFocus = null;
let toastTimer;
const $ = selector => document.querySelector(selector);
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));

function safeExternalUrl(value) {
  try { const url = new URL(value); return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : null; }
  catch { return null; }
}
function dateText(value) { return value ? new Date(value).toLocaleString() : 'Time unavailable'; }
function metricText(value, name) {
  if (value == null) return 'Metric unavailable';
  const unit=String(name||'');
  const displayUnit=value===1&&['points','stars','comments','likes','upvotes'].includes(unit)?unit.slice(0,-1):unit;
  return displayUnit?`${value} ${displayUnit}`:String(value);
}
function toast(message) { const el=$('#toast'); el.textContent=message; el.classList.add('show'); clearTimeout(toastTimer); toastTimer=setTimeout(()=>el.classList.remove('show'),3000); }
function errorText(detail) {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map(item => item.msg || String(item)).join('; ');
  return 'Request failed';
}
async function api(path, options={}) {
  const response = await fetch('/api'+path, {headers:{'Content-Type':'application/json'}, ...options});
  const body = await response.json().catch(()=>({}));
  if (!response.ok) throw new Error(errorText(body.detail));
  return body;
}

function switchView(view) {
  currentView=view;
  window.history.replaceState(null,'','#'+view+(view==='agent'&&typeof agentSessionId!=='undefined'&&agentSessionId?'/'+agentSessionId:'')+(view==='opportunities'&&typeof selectedOpportunityId!=='undefined'&&selectedOpportunityId?'/'+selectedOpportunityId:''));
  document.querySelectorAll('.view').forEach(el=>el.classList.toggle('active',el.id===view+'-view'));
  document.querySelectorAll('.nav [data-view]').forEach(el=>el.classList.toggle('active',el.dataset.view===view));
  $('#breadcrumb-view').textContent={feed:'Signal feed',monitoring:'Monitoring',collection:'Collection',opportunities:'Opportunities',company:'Company context',agent:'Agent workspace'}[view];
  window.scrollTo({top:0,behavior:'smooth'});
  if (view==='opportunities') loadIntelligence();
  if (view==='company') loadCompany();
  if (view==='agent') loadAgentWorkspace();
  if (view==='collection') loadRuns();
  if (view==='feed') { loadFeed(); loadSummary(true); }
}

function renderProfile() {
  if (!profile) return;
  $('#config-groups').innerHTML=Object.entries(ruleLabels).map(([key,[label,placeholder]])=>
    `<div class="config-group"><div class="config-head"><h3>${escapeHtml(label)}</h3><span>${profile[key].length} added</span></div>`+
    `<div class="chips">${profile[key].map((value,index)=>`<span class="chip">${escapeHtml(value)}`+
    `<button aria-label="Remove ${escapeHtml(value)}" data-remove-key="${key}" data-remove-index="${index}">×</button></span>`).join('')}</div>`+
    `<form class="inline-form" data-add-key="${key}"><input aria-label="${escapeHtml(placeholder)}" placeholder="${escapeHtml(placeholder)}" maxlength="100"><button class="button small" type="submit">Add</button></form>`+
    `<div class="error-text" data-error-for="${key}" role="alert"></div></div>`).join('');
  $('#source-toggles').innerHTML=sourceKeys.map(key=>`<label class="source-toggle"><span>${escapeHtml(sourceLabels[key])}`+
    `<small>${key==='x'?'Recent posts':key==='web'?'Search and pages':key==='hn'?'Stories and comments':key==='reddit'?'Posts and comments':key==='github'?'Repos and issues':'Configured feeds'}</small></span>`+
    `<input type="checkbox" data-source-key="${key}" ${profile.sources[key]?'checked':''} aria-label="Enable ${escapeHtml(sourceLabels[key])}"></label>`).join('');
  $('#enabled-count').textContent=sourceKeys.filter(key=>profile.sources[key]).length+' sources selected';
  const selected=$('#topic-filter').value;
  $('#topic-filter').innerHTML='<option value="all">All topics</option>'+profile.topics.map(topic=>
    `<option value="${escapeHtml(topic)}">${escapeHtml(topic)}</option>`).join('');
  if (profile.topics.includes(selected)) $('#topic-filter').value=selected;
}
async function loadProfile() {
  try { profile=await api('/profile'); renderProfile(); $('#profile-saved').textContent='Saved profile loaded'; }
  catch(error) { $('#profile-saved').textContent=error.message; }
}
function markUnsaved() { $('#profile-saved').textContent='Unsaved changes'; }
function addRule(form) {
  const key=form.dataset.addKey, input=form.querySelector('input'), value=input.value.trim().replace(/\s+/g,' ');
  const error=$(`[data-error-for="${key}"]`);
  if (!value) { error.textContent='Enter a value.'; return; }
  if (profile[key].some(item=>item.toLocaleLowerCase()===value.toLocaleLowerCase())) { error.textContent='Already in this list.'; return; }
  if (value.length>100) { error.textContent='Use at most 100 characters.'; return; }
  profile[key].push(value); renderProfile(); markUnsaved();
}
async function saveProfile() {
  const note=$('#profile-saved'); note.textContent='Saving…';
  try {
    profile=await api('/profile',{method:'PUT',body:JSON.stringify({
      topics:profile.topics,include:profile.include,exclude:profile.exclude,
      competitors:profile.competitors,people:profile.people,sources:profile.sources})});
    renderProfile(); note.textContent='Saved'; toast('Monitoring profile saved'); loadRuns();
  } catch(error) { note.textContent=error.message; toast('Profile could not be saved'); }
}

function feedParams() {
  const params=new URLSearchParams({state:currentTab,page:String(currentPage),page_size:'20'});
  const source=$('#source-filter').value;
  if (source!=='all') params.set('source',sourceKeys.find(key=>sourceLabels[key]===source) || source);
  const topic=$('#topic-filter').value;
  if (topic!=='all') params.set('topic',topic);
  const hours=$('#date-filter').value;
  if (hours!=='all') params.set('from',new Date(Date.now()-Number(hours)*3600000).toISOString());
  const engagement=Number($('#engagement-filter').value);
  if (engagement>0) params.set('min_engagement',String(engagement));
  return params;
}
function renderFeed(data) {
  currentItems=data.items;
  $('#feed-count').textContent=`${data.total} ${data.total===1?'signal':'signals'}`;
  $('#signal-list').innerHTML=data.items.length?data.items.map(signal=>{
    const id=Number(signal.id), source=sourceLabels[signal.source_key]||signal.source_key;
    const metric=metricText(signal.metric_value, signal.metric_name);
    return `<article class="signal"><div class="signal-top"><span class="source"><i></i>${escapeHtml(source)}</span>`+
      `<span class="tag">${escapeHtml(signal.topics[0]||'Matched')}</span><span class="signal-time">${escapeHtml(dateText(signal.published_at))}</span></div>`+
      `<h3>${escapeHtml(signal.title)}</h3><p>${escapeHtml(signal.snippet)}</p><div class="signal-bottom"><div class="signal-meta">`+
      `<span>${escapeHtml(metric)}</span><span>${signal.source_count} ${signal.source_count===1?'source':'sources'} contributing</span></div>`+
      `<div class="signal-actions"><button data-detail="${id}">Details</button>`+
      `<button data-action="saved" data-id="${id}" class="${signal.saved?'on':''}">${signal.saved?'Saved':'Save'}</button>`+
      `<button data-action="interesting" data-id="${id}" class="${signal.interesting?'on':''}">${signal.interesting?'Interesting ✓':'Interesting'}</button>`+
      `<button data-action="dismissed" data-id="${id}" class="${signal.dismissed?'dismissed':''}">${signal.dismissed?'Restore':'Dismiss'}</button></div></div></article>`;
  }).join(''):'<div class="empty"><strong>No matching signals</strong><p>Try different filters or run collection after saving a monitoring profile.</p></div>';
  const pages=Math.ceil(data.total/data.page_size);
  $('#feed-pagination').innerHTML=pages>1?`<button data-page="previous" ${currentPage<=1?'disabled':''}>Previous</button>`+
    `<span>Page ${currentPage} of ${pages}</span><button data-page="next" ${currentPage>=pages?'disabled':''}>Next</button>`:'';
}
async function loadFeed() {
  try { renderFeed(await api('/signals?'+feedParams())); }
  catch(error) { $('#signal-list').innerHTML=`<div class="empty"><strong>Feed unavailable</strong><p>${escapeHtml(error.message)}</p></div>`; }
}
async function loadSummary(preserveNew=false) {
  try {
    const summary=await api('/summary');
    $('#found-count').textContent=summary.found;
    if (!preserveNew) $('#new-count').textContent=summary.new_since_last_visit;
    $('#duplicate-count').textContent=summary.grouped_duplicate_hits;
  } catch(error) { toast(error.message); }
}
async function updateState(action,id) {
  const signal=currentItems.find(item=>item.id===id) || currentDetail;
  if (!signal || !['saved','interesting','dismissed'].includes(action)) return;
  try {
    await api(`/signals/${id}/state`,{method:'PATCH',body:JSON.stringify({[action]:!signal[action]})});
    await loadFeed();
    if (currentDetail?.id===id) await openDetail(id,false);
  } catch(error) { toast(error.message); }
}
async function openDetail(id,rememberFocus=true) {
  try {
    const signal=await api(`/signals/${id}`);
    currentDetail=signal;
    if (rememberFocus) detailFocus=document.activeElement;
    const itemHtml=signal.source_items.map(item=>{
      const url=safeExternalUrl(item.source_url);
      const metric=metricText(item.metric_value, item.metric_name);
      return `<div class="drawer-section"><strong>${escapeHtml(sourceLabels[item.source_key]||item.source_key)}</strong>`+
        `<p>${escapeHtml(item.title)} · ${escapeHtml(metric)} · ${escapeHtml(dateText(item.published_at))}</p>`+
        (url?`<a class="source-link" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">Open original source ↗</a>`:'')+'</div>';
    }).join('');
    $('#detail-content').innerHTML=`<div class="signal-top"><span class="source">${escapeHtml(sourceLabels[signal.source_items[0]?.source_key]||'Signal')}</span>`+
      `<span class="signal-time">${escapeHtml(dateText(signal.published_at))}</span></div><h2 id="detail-title">${escapeHtml(signal.title)}</h2>`+
      `<p>${escapeHtml(signal.snippet)}</p><div class="drawer-actions">`+
      `<button class="button small ${signal.saved?'selected':''}" data-action="saved" data-id="${id}">${signal.saved?'Saved ✓':'Save'}</button>`+
      `<button class="button small ${signal.interesting?'selected':''}" data-action="interesting" data-id="${id}">${signal.interesting?'Interesting ✓':'Mark interesting'}</button>`+
      `<button class="button small ${signal.dismissed?'danger':''}" data-action="dismissed" data-id="${id}">${signal.dismissed?'Restore':'Dismiss'}</button></div>`+
      `<div class="drawer-section"><h3>Why this matched</h3><p>${escapeHtml(signal.matched_terms.join(', ')||'Matched monitoring rules')}</p>`+
      `<p>${escapeHtml(signal.topics.join(', '))}</p></div><div class="drawer-section"><h3>Sources in this group</h3>${itemHtml}</div>`;
    $('#detail-overlay').classList.add('open'); $('#close-detail').focus();
  } catch(error) { toast(error.message); }
}
function closeDetail() {
  const signalId=currentDetail?.id;
  $('#detail-overlay').classList.remove('open'); currentDetail=null;
  const target=detailFocus?.isConnected?detailFocus:
    (document.querySelector(`#signal-list [data-detail="${signalId}"]`) || $('#refresh-from-feed'));
  target?.focus();
}

function renderRuns() {
  const latest=runs[0];
  const notice=$('.collection-actions .notice'), health=$('.side-panel .notice');
  if (!latest) {
    $('#collection-time').textContent='No collection has run yet';
    $('#run-status').textContent='No runs yet';
    $('#collection-table tbody').innerHTML='<tr><td colspan="3">Save a profile or run collection to see source status.</td></tr>';
    $('#last-run-mini').textContent='No runs yet';
    notice.textContent='No collection results yet.'; health.textContent='No collection runs yet.';
    $('#run-history').innerHTML=''; return;
  }
  $('#collection-time').textContent=`${dateText(latest.queued_at)} · ${latest.trigger}`+
    (latest.finished_at?` · finished ${dateText(latest.finished_at)}`:'');
  const status=$('#run-status'); status.textContent=latest.status;
  status.className='run-status '+(latest.status==='partial'?'partial':latest.status==='queued'||latest.status==='running'?'running':'');
  $('#collection-table tbody').innerHTML=sourceKeys.map(key=>{
    const source=latest.sources.find(row=>row.source_key===key);
    return `<tr><td>${escapeHtml(sourceLabels[key])}</td><td>${source?`${source.accepted_count} accepted · ${source.hit_count} ${source.hit_count===1?'hit':'hits'}`:'Waiting'}</td>`+
      `<td><span class="badge">${escapeHtml(source?.status||'queued')}</span>`+
      (source?.error_message?`<div class="small-text">${escapeHtml(source.error_message)}</div>`:'')+'</td></tr>';
  }).join('');
  const failures=latest.sources.filter(row=>['failed','unavailable'].includes(row.status));
  const message=failures.length?`Latest run ${latest.status}. ${failures.map(row=>sourceLabels[row.source_key]+': '+row.error_message).join('; ')}. Earlier results remain visible with their original dates.`:
    latest.status==='queued'||latest.status==='running'?'Collection is in progress. Results update as sources finish.':'Latest run completed.';
  notice.textContent=message; health.textContent=message;
  const completed=runs.find(run=>run.finished_at);
  $('#last-run-mini').textContent=completed?dateText(completed.finished_at):'No completed run';
  $('#run-history').innerHTML=runs.length>1?'<strong>Recent runs</strong><br>'+runs.slice(1,6).map(run=>
    `<span>${escapeHtml(dateText(run.queued_at))} · ${escapeHtml(run.trigger)} · ${escapeHtml(run.status)}</span><br>`).join(''):'';
}
async function loadRuns() {
  try { runs=await api('/collection-runs'); renderRuns(); }
  catch(error) { $('#collection-time').textContent='Collection status unavailable: '+error.message; }
}
async function runCollection() {
  try { await api('/collection-runs',{method:'POST'}); switchView('collection'); await loadRuns(); toast('Collection queued'); }
  catch(error) { toast(error.message); }
}

document.addEventListener('click',event=>{
  const view=event.target.closest('[data-view]'); if(view){switchView(view.dataset.view);return;}
  const tab=event.target.closest('[data-feed-tab]'); if(tab){currentTab=tab.dataset.feedTab;currentPage=1;
    document.querySelectorAll('[data-feed-tab]').forEach(el=>{el.classList.toggle('active',el===tab);el.setAttribute('aria-selected',String(el===tab));});loadFeed();return;}
  const remove=event.target.closest('[data-remove-key]'); if(remove&&profile){profile[remove.dataset.removeKey].splice(Number(remove.dataset.removeIndex),1);renderProfile();markUnsaved();return;}
  const action=event.target.closest('[data-action]'); if(action){updateState(action.dataset.action,Number(action.dataset.id));return;}
  const detail=event.target.closest('[data-detail]'); if(detail){openDetail(Number(detail.dataset.detail));return;}
  const page=event.target.closest('[data-page]'); if(page){currentPage+=page.dataset.page==='next'?1:-1;loadFeed();return;}
});
document.addEventListener('submit',event=>{const form=event.target.closest('[data-add-key]');if(form){event.preventDefault();addRule(form);}});
document.addEventListener('change',event=>{
  if(event.target.matches('[data-source-key]')&&profile){profile.sources[event.target.dataset.sourceKey]=event.target.checked;$('#enabled-count').textContent=sourceKeys.filter(key=>profile.sources[key]).length+' sources selected';markUnsaved();}
  if(event.target.matches('#source-filter,#topic-filter,#date-filter,#engagement-filter')){currentPage=1;loadFeed();}
});
$('#engagement-filter').addEventListener('input',()=>{currentPage=1;loadFeed();});
$('#save-profile').addEventListener('click',saveProfile);
$('#refresh-from-feed').addEventListener('click',runCollection);
$('#refresh-from-collection').addEventListener('click',runCollection);
$('#close-detail').addEventListener('click',closeDetail);
$('#detail-overlay').addEventListener('click',event=>{if(event.target.id==='detail-overlay')closeDetail();});
document.addEventListener('keydown',event=>{
  const overlay=$('#detail-overlay');
  if (!overlay.classList.contains('open')) return;
  if (event.key==='Escape') { closeDetail(); return; }
  if (event.key==='Tab') {
    const controls=[...overlay.querySelectorAll('button:not([disabled]),a[href]')];
    if (!controls.length) return;
    const first=controls[0], last=controls[controls.length-1];
    if (event.shiftKey && document.activeElement===first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement===last) { event.preventDefault(); first.focus(); }
  }
});

async function initialize() {
  await loadProfile();
  await Promise.all([loadFeed(),loadSummary(),loadRuns()]);
  try { const review=await api('/feed-reviewed',{method:'POST'}); $('#new-count').textContent=review.new_since_last_visit; }
  catch(error) { toast(error.message); }
  setInterval(()=>{if(runs[0]&&['queued','running'].includes(runs[0].status)){loadRuns();loadFeed();loadSummary(true);}},8000);
}
initialize();
