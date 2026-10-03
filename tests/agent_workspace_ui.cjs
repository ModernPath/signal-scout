const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const nodes=new Map();const node=s=>{if(!nodes.has(s))nodes.set(s,{innerHTML:'',textContent:'',value:'',disabled:false,addEventListener(){}});return nodes.get(s)};
const ctx=vm.createContext({document:{addEventListener(){},querySelector:node},$:node,escapeHtml:s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])),safeExternalUrl:u=>/^https?:\/\//.test(u)?u:null,dateText:s=>s||'',setInterval(){},clearInterval(){},window:{location:{hash:'#agent'},history:{replaceState(){}}},crypto:{randomUUID:()=> 'id'}});
vm.runInContext(fs.readFileSync('src/signalscout/static/agent_workspace.js','utf8'),ctx);
ctx.state={turns:[{id:5,role:'assistant',content:'**Result** <script>bad</script>'}],jobs:[{id:1,status:'complete',result:{mode:'gemini',assistant_turn_id:5}}],events:[{id:1,job_id:1,tool:'research_opportunity',executor:'evidence_researcher',status:'running',summary:'Started',inputs:{opportunity_id:49},artifacts:[]},{id:2,job_id:1,tool:'research_opportunity',executor:'evidence_researcher',status:'complete',summary:'Checked sources',inputs:{opportunity_id:49},artifacts:[{kind:'source',url:'javascript:bad',title:'<img>'},{kind:'opportunity',id:49,title:'Topic'},{kind:'draft',id:7,opportunity_id:49,title:'Draft'}]}]};
vm.runInContext('renderAgentWorkspace(state)',ctx);
assert.doesNotMatch(node('#agent-messages').innerHTML,/<script>/);
assert.match(node('#agent-messages').innerHTML,/&lt;script/);
assert.match(node('#agent-activity').innerHTML,/evidence_researcher/);
assert.match(node('#agent-activity').innerHTML,/complete/);
assert.doesNotMatch(node('#agent-activity').innerHTML,/href="javascript:/);
assert.match(node('#agent-activity').innerHTML,/#opportunities\/49/);
assert.match(node('#agent-activity').innerHTML,/draft=7/);
assert.equal((node('#agent-activity').innerHTML.match(/<details/g)||[]).length,1);
console.log('Agent workspace rendering, trace and artifact safety passed');

assert.match(node('#agent-messages').innerHTML,/<strong>Result<\/strong>/);
assert.match(node('#agent-messages').innerHTML,/#opportunities\/49/);
// Loading a completed selected turn must not override the operator's explicit choice to unpin it.
vm.runInContext('agentPinnedId=null',ctx);
ctx.restoreState={jobs:[{opportunity_id:49}]};
assert.equal(vm.runInContext('restoreAgentContext(restoreState)',ctx),'');
