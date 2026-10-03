// Guided intelligence workflow; all data comes from the main same-origin API.
let intelligenceStatus = {provider_available:false,has_brief:false,content_count:0};
let opportunityData = {run_id:null,opportunities:[]}, selectedOpportunity = null, selectedOpportunityId = null;
let opportunityPage = 1, intelligenceJobs = [], intelligencePoll = null, detailRequest = 0;
let companyLoaded = false, companyContent = [], companyDirty = false;
let knowledgeStatus = null, knowledgePoll = null;
const draftEdits = new Map();
const intelApi = (path, options={}) => api('/intelligence'+path, options);
const channelName = value => value === 'linkedin' ? 'LinkedIn' : 'X';
const opportunityCount = count => `${count} ${count===1?'opportunity':'opportunities'}`;
const activeIntelJob = () => intelligenceJobs.find(job=>['queued','running'].includes(job.status));

function sourceAnchor(url, label) {
  const safe=safeExternalUrl(url);
  return safe ? `<a class="source-link" href="${escapeHtml(safe)}" target="_blank" rel="noopener noreferrer">${escapeHtml(label||safe)} ↗</a>` : `<span>${escapeHtml(label||'Source URL unavailable')}</span>`;
}
function intelError(error) { $('#intelligence-error').textContent=error.message;$('#knowledge-error').textContent=error.message; }
function renderIntelligenceGuidance() {
  const notices=[];
  if (!intelligenceStatus.has_brief) notices.push('Add a company brief to assess POV fit and generate drafts.');
  if (!intelligenceStatus.content_count) notices.push('Add previous company content to assess novelty.');
  if (!intelligenceStatus.provider_available) notices.push('Gemini is unavailable. Analysis still works; research and drafting need a configured provider.');
  const setup=notices.length ? notices.map(escapeHtml).join(' ')+' <button class="link-button" data-view="company">Set up company context →</button>' : '';
  const signals=intelligenceStatus.signal_count===0 ? 'No signals collected yet. Add monitoring topics, then run collection. <button class="link-button" data-view="monitoring">Set up monitoring →</button> ' : '';
  $('#intelligence-guidance').innerHTML=signals+setup;
}
function renderIntelligenceJobs() {
  const job=activeIntelJob()||intelligenceJobs[0], el=$('#intelligence-job');
  if (!job) { el.textContent='';$('#company-intelligence-job').textContent='';document.querySelectorAll('#analyze-button,[data-research-opportunity],[data-generate-draft],[data-refine-angle],#knowledge-reindex,#knowledge-search-button').forEach(button=>button.disabled=false); return; }
  const names={analyze:'Signal analysis',research:'Topic research',draft:'Draft generation',index:'Knowledge indexing',search:'Knowledge search',refine_angle:'Angle refinement'};
  el.className='job-banner '+job.status;
  const result=job.status==='complete' && job.action==='analyze' ? ` · ${opportunityCount(job.result?.opportunity_count??0)}` : '';
  el.textContent=`${names[job.action]} · ${job.status}${result}${job.error_message?' · '+job.error_message:''}`;
  $('#company-intelligence-job').className=el.className;$('#company-intelligence-job').textContent=el.textContent;
  const active=!!activeIntelJob();
  document.querySelectorAll('#analyze-button,[data-research-opportunity],[data-generate-draft],[data-refine-angle],#knowledge-reindex,#knowledge-search-button').forEach(button=>button.disabled=active);
}
function renderOpportunities() {
  const items=opportunityData.opportunities, start=(opportunityPage-1)*20;
  $('#analysis-summary').textContent=opportunityData.run_id ? `${opportunityCount(items.length)} · analyzed ${dateText(opportunityData.analyzed_at)}` : 'Run analysis to find opportunities.';
  $('#opportunity-list').innerHTML=items.length ? items.slice(start,start+20).map(item=>
    `<button class="opportunity-card ${item.id===selectedOpportunityId?'selected':''}" data-opportunity="${Number(item.id)}" aria-pressed="${item.id===selectedOpportunityId}">`+
    `<div class="opportunity-score"><span>Rank ${Number(item.rank)} · ${item.signal_ids.length} signals</span><strong>${Number(item.total)}<span class="small-text"> /100</span></strong></div>`+
    `<h3>${escapeHtml(item.label)}</h3><p>${escapeHtml(item.angle)}</p><span class="small-text">${Math.round(item.confidence*100)}% score coverage · ${Object.values(item.components).filter(v=>v===null).length} unknown components</span></button>`
  ).join('') : '<div class="empty"><strong>No opportunities yet</strong><p>Collect signals, then select Analyze signals. Dismissed signals are excluded.</p><button class="button small" data-view="feed">View signal feed</button></div>';
  const pages=Math.ceil(items.length/20);
  $('#opportunity-pagination').innerHTML=pages>1 ? `<button data-opportunity-page="previous" ${opportunityPage===1?'disabled':''}>Previous</button><span>${opportunityPage} / ${pages}</span><button data-opportunity-page="next" ${opportunityPage===pages?'disabled':''}>Next</button>` : '';
}
function evidenceMarkup(item) {
  return `<div class="evidence-card"><span class="badge ${escapeHtml(item.stance)}">${escapeHtml(item.stance)}</span> <span class="small-text">Evidence #${Number(item.id)} · checked ${escapeHtml(dateText(item.retrieved_at))}</span><p>${escapeHtml(item.claim)}</p>${sourceAnchor(item.source_url)}</div>`;
}
function knowledgeMarkup(retrieval) {
  if(!retrieval)return '<p>No passage retrieval recorded.</p>';
  return `<p class="small-text">${escapeHtml(retrieval.mode)} retrieval · ${Math.round(retrieval.coverage*100)}% indexing coverage. Similarity does not prove a claim is true or fresh.</p>`+
    (retrieval.hits.length?retrieval.hits.map(hit=>`<article class="evidence-card"><strong>${escapeHtml(hit.title)}</strong><p>${escapeHtml(hit.passage)}</p><span class="small-text">Company passage #${hit.chunk_id?Number(hit.chunk_id):'removed'}${hit.removed?' · source removed':''}</span>${hit.source_url?sourceAnchor(hit.source_url):''}</article>`).join(''):'<p>No relevant passages retrieved. Novelty is uncertain; check indexing coverage and the supplied library.</p>');
}
function enrichmentMarkup(item) {
  const enrichment=item.enrichment;
  let output='';
  if(enrichment?.source_removed)output='<p class="notice">A company source was removed. Refine again to rebuild this explanation.</p>';
  else if(enrichment){const result=enrichment.result;
    output=`${enrichment.stale?'<p class="notice">Company context or the knowledge index changed. Refine again before using this suggestion.</p>':''}<h3>Refined angle</h3><p>${escapeHtml(result.angle)}</p><p>${escapeHtml(result.why_us)}</p>`+
      (result.comparisons||[]).map(row=>`<article class="evidence-card"><span class="badge">${escapeHtml(row.verdict)}</span><p>Prior claim: ${escapeHtml(row.prior_claim)}</p><p>Difference: ${escapeHtml(row.difference)}</p><span class="small-text">Company passage #${Number(row.chunk_id)}</span></article>`).join('')+`<p class="small-text">${escapeHtml(result.uncertainty)} · Editorial suggestion; human review required.</p>`;
  }
  return knowledgeMarkup(item.knowledge)+output+(intelligenceStatus.provider_available&&intelligenceStatus.has_brief?`<button class="button" data-refine-angle="${Number(item.id)}">Refine angle</button>`:'<p class="small-text">A company brief and Gemini access are needed to refine the angle.</p>');
}
function draftMarkup(draft) {
  const text=draftEdits.get(draft.id)??draft.text, max=draft.channel==='x'?280:3000;
  return `<div class="draft-card"><strong>${channelName(draft.channel)} ${escapeHtml(draft.format)} · version #${Number(draft.id)}</strong>`+
    `<span class="draft-meta">${escapeHtml(dateText(draft.created_at))} · research #${Number(draft.research_run_id)}${draft.revises_id?' · revises #'+Number(draft.revises_id):''}${draft.model_version==='operator-edit'?' · operator edit':''} · unpublished draft</span>`+
    `<label class="small-text" for="draft-text-${Number(draft.id)}">Edit draft</label><textarea id="draft-text-${Number(draft.id)}" data-draft-text="${Number(draft.id)}" maxlength="${max}" rows="6">${escapeHtml(text)}</textarea>`+
    `<span class="draft-meta" id="draft-length-${Number(draft.id)}">${Array.from(text).length}/${max} characters</span>`+
    `<div class="signal-actions"><button class="button small" data-save-draft="${Number(draft.id)}">Save revision</button><button class="button small" data-copy-draft="${Number(draft.id)}">Copy text</button></div>`+
    `<p class="small-text" id="draft-status-${Number(draft.id)}" role="status" aria-live="polite"></p>`+
    `<details><summary class="small-text">Cited evidence (${draft.evidence_ids.length})</summary><p class="small-text">Factual sources</p>${(draft.evidence||[]).map(evidenceMarkup).join('')}</details><details><summary class="small-text">Company context used</summary>${knowledgeMarkup(draft.company_context)}</details></div>`;
}
function renderOpportunityDetail(item) {
  const names={relevance:'Relevance',velocity:'Velocity',novelty:'Novelty',pov_fit:'POV fit'};
  const research=item.research;
  const ready=!!(research?.status==='complete' && research.evidence.length && intelligenceStatus.has_brief && intelligenceStatus.provider_available);
  $('#opportunity-detail').innerHTML=`<p class="eyebrow">Opportunity detail</p><h2 id="opportunity-detail-title" tabindex="-1">${escapeHtml(item.label)}</h2>`+
    `<span class="small-text">${item.signal_ids.length} signals · ${Math.round(item.confidence*100)}% score coverage · analyzed ${escapeHtml(dateText(item.analyzed_at))}</span>`+
    `<div class="score-grid">${Object.entries(names).map(([key,label])=>`<div class="score-cell">${label}<strong>${item.components[key]===null?'Unknown':Number(item.components[key])}</strong></div>`).join('')}</div>`+
    `<p class="small-text">Unknown components are excluded from the weighted total. Score coverage describes available inputs, not factual certainty. Novelty uses lexical comparison and is provisional; no match does not prove a fresh claim.</p>`+
    `<button class="button small" data-chat-opportunity="${Number(item.id)}">Discuss with agent →</button><h3>Why now?</h3><p>${escapeHtml(item.why_now)}</p><h3>Why us?</h3><p>${escapeHtml(item.why_us)}</p><h3>Our angle</h3><p>${escapeHtml(item.angle)}</p>`+
    `<h3>Previous content comparison</h3>${item.prior_content_matches.length?item.prior_content_matches.map(match=>`<p>${escapeHtml(match.title)} · ${Math.round(match.similarity*100)}% text similarity</p>`).join(''):`<p>${item.components.novelty===null?'Novelty is unknown. Add previous company content to compare.':'No close match in the supplied content library.'}</p>`}`+
    `<section class="intelligence-detail-section"><h3>Retrieved company passages</h3>${enrichmentMarkup(item)}</section>`+
    `<details><summary class="small-text">Conversation sources (${item.source_items.length})</summary><p>${escapeHtml(item.reason)}</p><p class="small-text">Signal IDs: ${item.signal_ids.map(Number).join(', ')}</p>${item.source_items.map(source=>`<div class="evidence-card">${sourceAnchor(source.source_url,source.title)}<p>${escapeHtml(source.snippet)}</p><span class="small-text">Source item #${Number(source.id)}</span></div>`).join('')}</details>`+
    `<section class="intelligence-detail-section"><h3>Research and evidence</h3>${research?`<span class="badge ${research.status==='partial'?'unknown':''}">${escapeHtml(research.status)}</span><p class="research-summary">${escapeHtml(research.summary)}</p>${research.error_summary?`<p class="error-text">${escapeHtml(research.error_summary)}</p>`:''}<p class="small-text">${research.evidence.filter(row=>row.stance==='conflict').length} conflicting · ${research.evidence.filter(row=>row.stance==='unknown').length} uncertain evidence records</p><details><summary class="small-text">Source evidence (${research.evidence.length})</summary>${research.evidence.map(evidenceMarkup).join('')}</details>`:'<p>Research this opportunity to check claims against original sources and find conflicting evidence.</p>'}`+
    `${intelligenceStatus.provider_available?`<button class="button primary" data-research-opportunity="${Number(item.id)}">${research?'Research again':'Research topic'}</button>`:'<p class="notice">Research needs a configured Gemini provider.</p>'}</section>`+
    `<section class="intelligence-detail-section"><h3>Drafts</h3>${ready?`<div class="draft-controls">${['linkedin','x'].flatMap(channel=>['post','reply'].map(format=>`<button class="button small" data-generate-draft="${channel}:${format}" data-draft-opportunity="${Number(item.id)}">${channelName(channel)} ${format}</button>`)).join('')}</div>`:
      `<p class="notice">${!intelligenceStatus.has_brief?'Save a company brief. ':''}${!research||research.status!=='complete'?'Complete research with source evidence to unlock drafts. ':''}${!intelligenceStatus.provider_available?'Configure Gemini for drafting.':''}</p>`}`+
    `<p class="small-text">Review every claim before use. Saved edits are editorial revisions and do not verify new claims.</p>${item.drafts.length?item.drafts.map(draftMarkup).join(''):'<p>No drafts yet.</p>'}</section>`;
  renderIntelligenceJobs();
}
async function selectOpportunity(id, focus=true) {
  const request=++detailRequest;
  selectedOpportunityId=id;
  window.history.replaceState(null,'','#opportunities/'+id);
  renderOpportunities();
  $('#opportunity-detail').innerHTML='<div class="empty" role="status">Loading opportunity…</div>';
  try {
    const item=await intelApi('/opportunities/'+id);
    if(request!==detailRequest)return;
    selectedOpportunity=item; renderOpportunityDetail(item);
    if(focus)$('#opportunity-detail-title').focus();
  } catch(error) { if(request===detailRequest){$('#opportunity-detail').innerHTML=`<div class="empty"><strong>Opportunity unavailable</strong><p>${escapeHtml(error.message)}</p></div>`;} }
}
async function loadIntelligence(refreshDetail=false) {
  try {
    const [status,data,jobs]=await Promise.all([intelApi('/status'),intelApi('/opportunities'),intelApi('/jobs')]);
    intelligenceStatus=status; opportunityData=data; intelligenceJobs=jobs;
    renderIntelligenceGuidance(); renderOpportunities(); renderIntelligenceJobs();
    if(selectedOpportunityId && (!selectedOpportunity || refreshDetail)) await selectOpportunity(selectedOpportunityId,false);
    if(activeIntelJob()) scheduleIntelPoll();
  } catch(error) { intelError(error); }
}
function scheduleIntelPoll() {
  clearTimeout(intelligencePoll);
  intelligencePoll=setTimeout(async()=>{
    try {
      const previous=activeIntelJob(); intelligenceJobs=await intelApi('/jobs'); renderIntelligenceJobs();
      if(previous&&!activeIntelJob()) {
        const done=intelligenceJobs.find(job=>job.id===previous.id);
        if(done?.action==='analyze'&&done.status==='complete') { selectedOpportunity=null; selectedOpportunityId=null; opportunityPage=1;
          if(currentView==='opportunities') window.history.replaceState(null,'','#opportunities');
          $('#opportunity-detail').innerHTML='<div class="empty"><strong>Select an opportunity</strong><p>Inspect the angle, research, and drafts.</p></div>'; }
        if(done?.action==='search'&&done.status==='complete'){
          const retrieval=await intelApi('/knowledge/search/'+done.id);
          $('#knowledge-search-results').innerHTML=knowledgeMarkup(retrieval);
        }
        await loadKnowledge();
        await loadIntelligence(true);
      }
      if(activeIntelJob())scheduleIntelPoll();
    } catch(error) { intelError(error); scheduleIntelPoll(); }
  },2000);
}
async function queueIntelligence(path,payload) {
  $('#intelligence-error').textContent='';$('#knowledge-error').textContent='';
  document.querySelectorAll('#analyze-button,[data-research-opportunity],[data-generate-draft],[data-refine-angle],#knowledge-reindex,#knowledge-search-button').forEach(el=>el.disabled=true);
  try {
    const job=await intelApi(path,{method:'POST',...(payload?{body:JSON.stringify(payload)}:{})});
    intelligenceJobs=[job,...intelligenceJobs.filter(row=>row.id!==job.id)]; renderIntelligenceJobs(); scheduleIntelPoll();
  } catch(error) { intelError(error); renderIntelligenceJobs(); }
}
async function loadKnowledge() {
  clearTimeout(knowledgePoll);
  try {
    knowledgeStatus=await intelApi('/knowledge/status');
    $('#knowledge-status').textContent=`${knowledgeStatus.ready} of ${knowledgeStatus.eligible} documents ready · ${knowledgeStatus.semantic_ready} semantically indexed · ${knowledgeStatus.pending} pending · ${knowledgeStatus.failed} failed`;
    $('#knowledge-processing').textContent=knowledgeStatus.embedding_available?'Semantic indexing sends pasted company content to Gemini. Passages and vectors are stored in application Postgres.':'Semantic indexing is unavailable. Exact-word passage retrieval still works.';
    renderCompanyContent();
    if(knowledgeStatus.pending)knowledgePoll=setTimeout(loadKnowledge,3000);
  }catch(error){$('#knowledge-status').textContent=error.message;}
}
function renderCompanyContent() {
  $('#company-content-list').innerHTML=companyContent.length?companyContent.map(item=>`<article class="content-item"><strong>${escapeHtml(item.title)}</strong><span class="small-text">${escapeHtml(item.channel)} · ${escapeHtml(knowledgeStatus?.documents.find(d=>d.content_id===item.id)?.status||'pending')}</span>${knowledgeStatus?.documents.find(d=>d.content_id===item.id)?.error_message?`<p class="error-text">${escapeHtml(knowledgeStatus.documents.find(d=>d.content_id===item.id).error_message)}</p>`:''}${item.url?sourceAnchor(item.url,'Original content'):''}<p>${escapeHtml(item.text.slice(0,300))}${item.text.length>300?'…':''}</p><div class="signal-actions"><button class="button small" data-edit-content="${Number(item.id)}">Edit</button><button class="button small danger" data-delete-content="${Number(item.id)}">Delete</button></div></article>`).join(''):'<p class="small-text">No previous content yet. Novelty stays unknown until you add it.</p>';
}
async function loadCompany() {
  if(companyLoaded)return;
  $('#brief-save-status').textContent='Loading company context…';
  try {
    const [brief,content]=await Promise.all([intelApi('/brief'),intelApi('/content')]);
    const form=$('#company-brief-form');
    if(!companyDirty) for(const key of ['description','audience','expertise','point_of_view','voice','avoid_claims']) form.elements[key].value=brief?.brief[key]||'';
    companyContent=content; renderCompanyContent(); companyLoaded=true; await loadKnowledge();
    intelligenceStatus.has_brief=!!brief; intelligenceStatus.content_count=content.length;
    $('#brief-save-status').textContent=brief?'Saved brief · version '+brief.version:'Add all five required fields to enable company fit and drafting.';
    $('#clear-brief').disabled=!brief;
  } catch(error) { $('#brief-save-status').textContent=error.message; }
}
async function saveBrief(event) {
  event.preventDefault(); const form=event.target,button=form.querySelector('[type="submit"]'); button.disabled=true;
  $('#brief-save-status').textContent='Saving…';
  try {
    const brief=await intelApi('/brief',{method:'PUT',body:JSON.stringify(Object.fromEntries(new FormData(form)))});
    companyDirty=false; intelligenceStatus.has_brief=true; $('#clear-brief').disabled=false;
    $('#brief-save-status').textContent='Saved · version '+brief.version+'. Run analysis again to use this brief.'; renderIntelligenceGuidance();
  } catch(error) { $('#brief-save-status').textContent=error.message; }
  finally {button.disabled=false;}
}
function cancelContentEdit() {
  $('#company-content-form').reset(); $('#company-content-form').elements.id.value='';
  $('#content-save-button').textContent='Add content'; $('#cancel-content-edit').hidden=true;
}
async function saveContent(event) {
  event.preventDefault();const form=event.target,values=Object.fromEntries(new FormData(form)),id=values.id;delete values.id;
  values.url=values.url||null; $('#content-save-button').disabled=true; $('#content-save-status').textContent='Saving…';
  try {
    await intelApi('/content'+(id?'/'+Number(id):''),{method:id?'PUT':'POST',body:JSON.stringify(values)});
    companyContent=await intelApi('/content'); intelligenceStatus.content_count=companyContent.length;
    renderCompanyContent(); cancelContentEdit(); renderIntelligenceGuidance(); $('#content-save-status').textContent='Saved. Knowledge indexing will update the passage comparison.';await loadKnowledge();
  } catch(error) { $('#content-save-status').textContent=error.message; }
  finally {$('#content-save-button').disabled=false;}
}
async function saveDraft(id,button) {
  const text=$('#draft-text-'+id).value; button.disabled=true;
  try {
    const revision=await intelApi('/drafts/'+id,{method:'PUT',body:JSON.stringify({text})});draftEdits.delete(id);
    await selectOpportunity(selectedOpportunityId,false); $('#draft-text-'+revision.id)?.focus(); toast('Draft revision saved');
  } catch(error) { $('#draft-status-'+id).textContent=error.message; }
  finally {if(button.isConnected)button.disabled=false;}
}
async function copyDraft(id) {
  try { await navigator.clipboard.writeText($('#draft-text-'+id).value); $('#draft-status-'+id).textContent='Copied.'; }
  catch { $('#draft-status-'+id).textContent='Copy unavailable. Select the draft text and copy it manually.'; }
}
document.addEventListener('click',async event=>{
  const opportunity=event.target.closest('[data-opportunity]'); if(opportunity){selectOpportunity(Number(opportunity.dataset.opportunity));return;}
  const page=event.target.closest('[data-opportunity-page]'); if(page){opportunityPage+=page.dataset.opportunityPage==='next'?1:-1;renderOpportunities();return;}
  const refine=event.target.closest('[data-refine-angle]');if(refine){queueIntelligence('/opportunities/'+Number(refine.dataset.refineAngle)+'/refine-angle');return;}
  const research=event.target.closest('[data-research-opportunity]');if(research){queueIntelligence('/opportunities/'+Number(research.dataset.researchOpportunity)+'/research');return;}
  const draft=event.target.closest('[data-generate-draft]');if(draft){const[channel,format]=draft.dataset.generateDraft.split(':');queueIntelligence('/opportunities/'+Number(draft.dataset.draftOpportunity)+'/draft',{channel,format});return;}
  const save=event.target.closest('[data-save-draft]');if(save){saveDraft(Number(save.dataset.saveDraft),save);return;}
  const copy=event.target.closest('[data-copy-draft]');if(copy){copyDraft(Number(copy.dataset.copyDraft));return;}
  const edit=event.target.closest('[data-edit-content]');if(edit){const item=companyContent.find(row=>row.id===Number(edit.dataset.editContent)),form=$('#company-content-form');for(const key of ['id','title','channel','url','text'])form.elements[key].value=item[key]||'';$('#content-save-button').textContent='Save content revision';$('#cancel-content-edit').hidden=false;form.elements.title.focus();return;}
  const remove=event.target.closest('[data-delete-content]');if(remove&&window.confirm('Delete this previous content and its stored revisions?')){remove.disabled=true;try{await intelApi('/content/'+Number(remove.dataset.deleteContent),{method:'DELETE'});companyContent=await intelApi('/content');intelligenceStatus.content_count=companyContent.length;renderCompanyContent();cancelContentEdit();renderIntelligenceGuidance();$('#content-save-status').textContent='Deleted. Stored retrieval excerpts have been removed.';await loadKnowledge();if(selectedOpportunityId)selectedOpportunity=null;}catch(error){$('#content-save-status').textContent=error.message;remove.disabled=false;}}
});
document.addEventListener('input',event=>{
  if(event.target.closest('#company-brief-form'))companyDirty=true;
  if(event.target.matches('[data-draft-text]')){const id=Number(event.target.dataset.draftText);draftEdits.set(id,event.target.value);const draft=selectedOpportunity.drafts.find(item=>item.id===id);$('#draft-length-'+id).textContent=Array.from(event.target.value).length+'/'+(draft.channel==='x'?280:3000)+' characters · unsaved';}
});
$('#knowledge-reindex').addEventListener('click',()=>queueIntelligence('/knowledge/reindex'));
$('#knowledge-search-form').addEventListener('submit',event=>{event.preventDefault();queueIntelligence('/knowledge/search',{query:$('#knowledge-query').value});});
$('#analysis-form').addEventListener('submit',event=>{event.preventDefault();queueIntelligence('/analyze',{days:Number($('#analysis-days').value),limit:500});});
$('#company-brief-form').addEventListener('submit',saveBrief);
$('#company-content-form').addEventListener('submit',saveContent);
$('#cancel-content-edit').addEventListener('click',cancelContentEdit);
$('#clear-brief').addEventListener('click',async()=>{
  if(!window.confirm('Delete the stored company brief?'))return;
  try{await intelApi('/brief',{method:'DELETE'});$('#company-brief-form').reset();intelligenceStatus.has_brief=false;companyDirty=false;$('#clear-brief').disabled=true;$('#brief-save-status').textContent='Company brief deleted.';renderIntelligenceGuidance();}
  catch(error){$('#brief-save-status').textContent=error.message;}
});
function initializeIntelligence() {
  const [view,id]=window.location.hash.slice(1).split('/');
  if(view==='opportunities'){selectedOpportunityId=/^[1-9][0-9]*$/.test((id||'').split('?')[0])?Number((id||'').split('?')[0]):null;switchView('opportunities');}
  else if(view==='agent'){agentSessionId=/^[1-9][0-9]*$/.test(id||'')?Number(id):null;switchView('agent');}
  else if(['feed','monitoring','collection','company'].includes(view))switchView(view);
  window.addEventListener('hashchange',()=>{const [next,id]=window.location.hash.slice(1).split('/');if(['feed','monitoring','collection','company','opportunities','agent'].includes(next)){if(next==='opportunities'){selectedOpportunityId=/^[1-9][0-9]*$/.test((id||'').split('?')[0])?Number((id||'').split('?')[0]):null;selectedOpportunity=null;}if(next==='agent')agentSessionId=/^[1-9][0-9]*$/.test(id||'')?Number(id):null;switchView(next);}});
}
initializeIntelligence();
