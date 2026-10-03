const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const nodes = new Map();
const node = selector => {
  if (!nodes.has(selector)) nodes.set(selector, {
    textContent: '', innerHTML: '', className: '',
    classList: { add() {}, remove() {} }, addEventListener() {},
  });
  return nodes.get(selector);
};
const listeners = new Map();
const document = { querySelector: node, addEventListener(event, handler) { listeners.set(event, handler); }, activeElement: null };
const context = vm.createContext({ document, setTimeout, clearTimeout });
const script = fs.readFileSync('src/signalscout/static/app.js', 'utf8');
vm.runInContext(script.replace(/\binitialize\(\);\s*$/, ''), context);

vm.runInContext('renderFeed({items:[], total:1, page_size:20})', context);
assert.equal(node('#feed-count').textContent, '1 signal');

vm.runInContext(`renderFeed({items:[{
  id:7, source_key:'hn', topics:['AI agents'], published_at:null,
  title:'AI agents', snippet:'Source text', metric_name:'points', metric_value:1,
  source_count:1, saved:false, interesting:false, dismissed:false
}], total:1, page_size:20})`, context);
assert.match(node('#signal-list').innerHTML, /1 point</);

vm.runInContext(`runs=[{
  queued_at:'2026-09-29T10:00:00Z', trigger:'manual', status:'complete',
  finished_at:'2026-09-29T10:00:01Z', sources:[
    {source_key:'hn', status:'complete', accepted_count:1, hit_count:1}
  ]
}]; renderRuns()`, context);
assert.match(node('#collection-table tbody').innerHTML, /1 accepted · 1 hit/);

const first = {focus() { document.activeElement = first; }};
const last = {focus() { document.activeElement = last; }};
const overlay = node('#detail-overlay');
overlay.classList.contains = () => true;
overlay.querySelectorAll = () => [first, last];
document.activeElement = last;
let prevented = false;
listeners.get('keydown')({key:'Tab', shiftKey:false, preventDefault() { prevented = true; }});
assert.equal(prevented, true);
assert.equal(document.activeElement, first);

const replacement = node('#signal-list [data-detail="7"]');
replacement.focus = () => { document.activeElement = replacement; };
context.oldFocus = {isConnected:false, focus() {}};
vm.runInContext('currentDetail={id:7}; detailFocus=oldFocus; closeDetail()', context);
assert.equal(document.activeElement, replacement);

async function checkFeedSummaryRefresh() {
  context.URLSearchParams = URLSearchParams;
  context.window = {scrollTo() {},history:{replaceState(){}}};
  document.querySelectorAll = () => [];
  for (const selector of ['#source-filter','#topic-filter','#date-filter']) node(selector).value='all';
  node('#engagement-filter').value='0';
  node('#found-count').textContent='2';
  node('#new-count').textContent='5';
  context.fetch = async path => ({ok:true, json:async () => path.startsWith('/api/summary')
    ? {found:23,new_since_last_visit:21,grouped_duplicate_hits:2}
    : {items:[],total:23,page_size:20}});
  vm.runInContext("switchView('feed')", context);
  await new Promise(setImmediate);
  assert.equal(node('#found-count').textContent, 23);
  assert.equal(node('#duplicate-count').textContent, 2);
  assert.equal(node('#new-count').textContent, '5');
}
checkFeedSummaryRefresh().catch(error => { console.error(error); process.exitCode=1; });
