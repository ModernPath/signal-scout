// Queued conversations and actual saved tool activity; provider keys stay in the worker.
let agentSessionId=null,agentState=null,agentPoll=null,agentBusy=false,agentRequestToken=null;
let agentPinnedId,agentContextSessionId=null,agentLoadRequest=0;
function restoreAgentContext(state){if(agentPinnedId===undefined)agentPinnedId=state.jobs[0]?.opportunity_id||null;return agentPinnedId?String(agentPinnedId):'';}
function agentArtifact(a){
  const title=escapeHtml(a.title||'Saved result');
  if(a.kind==='opportunity'&&Number(a.id)>0)return `<a class="agent-artifact" href="#opportunities/${Number(a.id)}">${title} →</a>`;
  if(a.kind==='draft'&&Number(a.opportunity_id)>0)return `<a class="agent-artifact" href="#opportunities/${Number(a.opportunity_id)}?draft=${Number(a.id)}">${title} →</a>`;
  if(a.kind==='passage')return `<button class="agent-artifact link-button" data-view="company">${title} · passage #${Number(a.id)} →</button>`;
  const url=safeExternalUrl(a.url);return url?`<a class="agent-artifact" href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${title} ↗</a>`:`<span class="small-text">${title}</span>`;
}
function agentReplyText(text){return escapeHtml(text).replace(/\*\*([^*\n]+)\*\*/g,'<strong>$1</strong>');}
function agentMessageResults(turn,state){
 if(turn.role!=='assistant')return '';
 const job=state.jobs.find(j=>j.result?.assistant_turn_id===turn.id);
 const refs=job?state.events.filter(e=>e.job_id===job.id).flatMap(e=>e.artifacts||[]).slice(0,10):[];
 return refs.length?'<div class="agent-result-cards">'+refs.map(agentArtifact).join('')+'</div>':'';
}
function agentExecutorLabel(name){return ({'Shared intelligence service':'SignalScout coordinator',evidence_researcher:'Research agent',draft_writer:'Draft writer',topic_analyst:'Topic analyst'})[name]||name;}
function renderAgentWorkspace(state){
 agentState=state;
 $('#agent-messages').innerHTML=state.turns.length?state.turns.map(t=>`<article class="agent-message ${t.role==='user'?'user':'assistant'}"><strong>${t.role==='user'?'You':'SignalScout'}</strong><p>${agentReplyText(t.content)}</p>${agentMessageResults(t,state)}</article>`).join(''):'<div class="empty"><strong>What should we explore?</strong><p>Ask about ranked opportunities, company knowledge, or a selected topic.</p></div>';
 const steps=[];
 for(const e of state.events){if(e.status==='running')steps.push({...e});else{const step=[...steps].reverse().find(s=>s.job_id===e.job_id&&s.tool===e.tool&&s.status==='running');if(step)Object.assign(step,e);else steps.push(e);}}
 $('#agent-activity').innerHTML=steps.length?steps.map(e=>`<details class="agent-step ${escapeHtml(e.status)}" ${e.status==='running'?'open':''}><summary><span class="agent-step-icon">${e.status==='running'?'●':e.status==='complete'?'✓':'!'}</span><span>${escapeHtml(e.summary)}<small>${escapeHtml(agentExecutorLabel(e.executor))} · ${escapeHtml(e.status)}</small></span></summary><div class="agent-step-detail"><p class="small-text">${escapeHtml(e.executor)} · ${escapeHtml(e.tool)} · ${escapeHtml(dateText(e.created_at))}</p>${Object.entries(e.inputs||{}).map(([k,v])=>`<p class="small-text">${escapeHtml(k)}: ${escapeHtml(v)}</p>`).join('')}${(e.artifacts||[]).map(agentArtifact).join('')}</div></details>`).join(''):'<p class="small-text">Actual actions will appear here as the agent works.</p>';
 const job=state.jobs[0],active=state.jobs.some(j=>['queued','running'].includes(j.status));
 $('#agent-turn-status').textContent=job?`${job.status} ${job.result?.mode?'· '+job.result.mode:''}${job.error_message?' · '+job.error_message:''}`:'';
 $('#agent-send').disabled=active;$('#agent-delete').disabled=active||!agentSessionId;
 $('#agent-opportunity').disabled=active;
 agentBusy=active;
}
async function loadAgentWorkspace(){
 const request=++agentLoadRequest;
 try{
  const hash=window.location.hash.slice(1).split('/');if(hash[0]==='agent'&&/^[1-9][0-9]*$/.test(hash[1]||''))agentSessionId=Number(hash[1]);
  const [sessions,opps,globalJobs]=await Promise.all([api('/intelligence/chat/sessions'),api('/intelligence/opportunities'),api('/intelligence/jobs')]);
  if(request!==agentLoadRequest)return;
  if(agentContextSessionId!==agentSessionId){agentPinnedId=undefined;agentContextSessionId=agentSessionId;}
  $('#agent-session').innerHTML='<option value="">New conversation</option>'+sessions.map(s=>`<option value="${Number(s.id)}" ${s.id===agentSessionId?'selected':''}>${escapeHtml(s.title||'Conversation #'+s.id)}</option>`).join('');
  $('#agent-opportunity').innerHTML='<option value="">No opportunity selected</option>'+opps.opportunities.map(o=>`<option value="${Number(o.id)}">${escapeHtml(o.label)}</option>`).join('');
  const state=agentSessionId?await api('/intelligence/chat/sessions/'+agentSessionId):{turns:[],jobs:[],events:[]};
  if(request!==agentLoadRequest)return;
  $('#agent-opportunity').value=restoreAgentContext(state);
  renderAgentWorkspace(state);
  const busy=globalJobs.some(j=>['queued','running'].includes(j.status));
  $('#agent-send').disabled=busy;$('#agent-global-status').textContent=busy&&!agentBusy?'Another intelligence action is active. You can continue when it finishes.':'';
  clearInterval(agentPoll);agentPoll=null;
  if(busy)agentPoll=setInterval(()=>{if(currentView==='agent')loadAgentWorkspace();},2000);
 }catch(e){$('#agent-error').textContent=e.message;}
}
async function sendAgentMessage(message){
 if(!message.trim()||agentBusy)return;
 $('#agent-error').textContent='';$('#agent-send').disabled=true;
 try{
  if(!agentSessionId){const session=await api('/intelligence/chat/sessions',{method:'POST',body:'{}'});agentSessionId=session.id;window.history.replaceState(null,'','#agent/'+agentSessionId);}
  agentRequestToken=agentRequestToken||crypto.randomUUID();
  const opportunity=Number($('#agent-opportunity').value)||null;
  await api('/intelligence/chat/sessions/'+agentSessionId+'/messages',{method:'POST',body:JSON.stringify({message,request_id:agentRequestToken,selected_opportunity_id:opportunity})});
  agentRequestToken=null;$('#agent-input').value='';await loadAgentWorkspace();
 }catch(e){$('#agent-error').textContent=e.message;$('#agent-send').disabled=false;}
}
document.addEventListener('click',e=>{
 const prompt=e.target.closest('[data-agent-prompt]');if(prompt){agentRequestToken=null;$('#agent-input').value=prompt.dataset.agentPrompt;$('#agent-input').focus();}
 const context=e.target.closest('[data-chat-opportunity]');if(context){agentPinnedId=Number(context.dataset.chatOpportunity);agentContextSessionId=agentSessionId;switchView('agent');$('#agent-input').focus();}
});
$('#agent-form').addEventListener('submit',e=>{e.preventDefault();sendAgentMessage($('#agent-input').value);});
$('#agent-input').addEventListener('input',()=>{agentRequestToken=null;});
$('#agent-opportunity').addEventListener('change',()=>{agentRequestToken=null;agentPinnedId=Number($('#agent-opportunity').value)||null;});
$('#agent-session').addEventListener('change',()=>{agentPinnedId=undefined;agentSessionId=Number($('#agent-session').value)||null;window.history.replaceState(null,'',agentSessionId?'#agent/'+agentSessionId:'#agent');$('#agent-opportunity').value='';loadAgentWorkspace();});
$('#agent-new').addEventListener('click',()=>{agentPinnedId=null;agentSessionId=null;agentContextSessionId=null;window.history.replaceState(null,'','#agent');$('#agent-opportunity').value='';loadAgentWorkspace();});
$('#agent-delete').addEventListener('click',async()=>{if(!agentSessionId||!window.confirm('Delete this conversation and its activity? Saved opportunities and drafts remain available.'))return;try{await api('/intelligence/chat/sessions/'+agentSessionId,{method:'DELETE'});agentPinnedId=null;agentSessionId=null;agentContextSessionId=null;window.history.replaceState(null,'','#agent');loadAgentWorkspace();}catch(e){$('#agent-error').textContent=e.message;}});
