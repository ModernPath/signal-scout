"""RAG lifecycle and retrieval contracts, with network-free embedding fixtures."""
import os
import sys
from pathlib import Path
import pytest
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'agents/signal-intelligence'))


def test_chunking_preserves_original_passages_and_long_paragraphs():
    from intelligence_retrieval import chunk_text
    source = '# Expertise\n\n' + 'Verification before execution. ' * 150
    chunks = chunk_text(source, size=900)
    assert len(chunks) > 1
    assert all(source[c['start']:c['end']] == c['text'] for c in chunks)
    assert all(len(c['text']) <= 900 for c in chunks)
    assert all(any(c['start'] <= i < c['end'] for c in chunks) for i in range(len(source)))


def test_embedding_provider_rejects_malformed_vectors_without_exposing_payload():
    from intelligence_embeddings import validate_vectors
    for invalid in ([[1.0]], [[float('nan')] * 768], [[0.0] * 768]):
        with pytest.raises(RuntimeError, match='Invalid embedding'):
            validate_vectors(invalid, 1)
    value = validate_vectors([[1.0] + [0.0] * 767], 1)
    assert len(value[0]) == 768 and value[0][0] == 1.0

URL = os.environ.get('TEST_DATABASE_URL')

@pytest.fixture
def store():
    if not URL:
        pytest.skip('requires disposable PostgreSQL')
    assert URL.endswith('/signalscout_ui_test')
    from memory.memory import IntelligenceStore
    engine = create_engine(URL)
    with engine.begin() as conn:
        conn.execute(text('TRUNCATE company_content,company_brief,signal RESTART IDENTITY CASCADE'))
    yield IntelligenceStore(engine)
    engine.dispose()


def test_content_changes_create_durable_index_work_and_delete_invalidates(store):
    content = store.add_content(dict(title='Prior', text='Verify before execution', channel='blog'))
    with store.engine.connect() as conn:
        exists = conn.execute(text("SELECT to_regclass('knowledge_document') IS NOT NULL")).scalar_one()
        assert exists, 'Content mutations must create durable indexing work'
        row = conn.execute(text('SELECT * FROM knowledge_document WHERE content_id=:id'), content).mappings().one()
        assert row['status'] == 'pending' and row['eligible']
    changed = store.replace_content(content['id'], dict(title='Revised',text='Check actions before running',channel='blog'))
    with store.engine.connect() as conn:
        old = conn.execute(text('SELECT eligible FROM knowledge_document WHERE content_id=:id'),content).scalar_one()
        assert old is False
    store.delete_content(changed['id'])
    with store.engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM knowledge_document WHERE eligible')).scalar_one() == 0

class Embedder:
    config='fixture:768:v1'
    def __init__(self):
        self.calls=[]
    def embed(self,texts,*,query=False):
        self.calls.append((texts,query))
        result=[]
        for text_value in texts:
            lower=text_value.lower()
            match=any(w in lower for w in ('verify','check','execution','running','safety','unsafe'))
            result.append([1.0,0.0] + [0.0]*766 if match else [0.0,1.0]+[0.0]*766)
        return result


def test_semantic_retrieval_idempotence_and_snapshot_redaction(store):
    from intelligence_retrieval import KnowledgeService
    embedder=Embedder()
    knowledge=KnowledgeService(store.engine,embedder=embedder)
    item=store.add_content(dict(title='Action policy',text='Verify before execution.',channel='blog'))
    store.add_content(dict(title='Travel',text='Hotel reservations and expense forms.',channel='blog'))
    result=knowledge.index_pending()
    assert result['indexed']==2
    count=len(embedder.calls)
    assert knowledge.index_pending()['indexed']==0 and len(embedder.calls)==count
    retrieved=knowledge.search('Check unsafe actions before running')
    assert retrieved['mode']=='hybrid'
    assert retrieved['hits'][0]['source_id']==item['id']
    assert retrieved['hits'][0]['passage']=='Verify before execution.'
    store.delete_content(item['id'])
    assert all(h['source_id']!=item['id'] for h in knowledge.search('Check actions')['hits'])
    historic=knowledge.get_retrieval(retrieved['id'])
    assert historic['hits'][0]['removed'] and historic['hits'][0]['passage']=='[source removed]'
    with store.engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM knowledge_chunk c JOIN knowledge_document d ON d.id=c.document_id WHERE d.content_id=:id'),item).scalar_one()==0


def test_lexical_fallback_and_stale_embedding_commit(store):
    from intelligence_retrieval import KnowledgeService
    item=store.add_content(dict(title='Exact product',text='AcmeGuard verifies tools.',channel='blog'))
    knowledge=KnowledgeService(store.engine)
    assert knowledge.index_pending()['indexed']==1
    hits=knowledge.search('AcmeGuard')['hits']
    assert hits[0]['source_id']==item['id']
    assert knowledge.search('unrelated bananas')['hits']==[]
    class Deleting(Embedder):
        def embed(self,texts,**kwargs):
            if not self.calls:
                store.delete_content(item['id'])
            return super().embed(texts,**kwargs)
    stale=KnowledgeService(store.engine,embedder=Deleting())
    stale.index_pending()
    assert stale.search('AcmeGuard')['hits']==[]


def test_provider_refinement_uses_numbered_original_passages_and_safe_rules():
    from intelligence_provider import GeminiProvider
    class Local(GeminiProvider):
        def _generate(self,prompt,**kwargs):
            assert 'Untrusted company passages' in prompt
            assert 'Verify before execution' in prompt
            assert 'chunk_id' in prompt
            return {'candidates':[{'content':{'parts':[{'text':'{"comparisons": [], "why_us":"Expertise", "angle":"Angle", "uncertainty":"Review"}'}]}}]}
    result=Local('fixture-only').refine({'label':'Security','angle':'Safe actions'},{'expertise':'Verification'},
      {'coverage':1,'mode':'hybrid','hits':[dict(chunk_id=17,passage='Verify before execution',title='Prior',role='company')]})
    assert result['model_version']=='gemini-2.5-flash'


def test_topic_subagent_loads_refinement_inputs_by_snapshot_ids():
    import importlib.util
    path=Path(__file__).resolve().parents[1]/'agents/signal-intelligence/subagents/topic_analyst.py'
    spec=importlib.util.spec_from_file_location('topic_rag_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    class Store:
        def get_opportunity(self,id): return dict(id=id,label='Security',angle='Verify')
        def get_brief(self): return dict(id=4,brief={'expertise':'Verification'})
    class Provider:
        def refine(self,opportunity,brief,retrieval): return dict(angle='Refined')
    class Knowledge:
        def get_retrieval(self,id): return dict(id=id,opportunity_id=2,hits=[dict(chunk_id=9,removed=False)])
    assert module.run(dict(opportunity_id=2,retrieval_id=3,brief_id=4),Store(),provider=Provider(),knowledge=Knowledge())['angle']=='Refined'


def test_model_rebuild_preserves_old_vectors_and_provider_failure_is_visible(store):
    from intelligence_retrieval import KnowledgeService
    store.add_content(dict(title='Policy',text='Verify before execution',channel='blog'))
    original=KnowledgeService(store.engine,embedder=Embedder());original.index_pending()
    class Broken(Embedder):
        config='other-model:768:v2'
        def embed(self,*args,**kwargs): raise RuntimeError('private-provider-payload')
    replacement=KnowledgeService(store.engine,embedder=Broken())
    result=replacement.index_pending()
    assert result['failed']==1
    assert 'private-provider-payload' not in str(result)
    assert original.search('Check actions')['hits']
    assert replacement.search('Verify')['mode']=='lexical-provider-unavailable'
    with store.engine.connect() as conn:
        assert conn.execute(text('SELECT count(*) FROM knowledge_embedding')).scalar_one()>0


def test_research_retention_removes_derived_passages_and_historical_excerpts(store):
    from intelligence_service import IntelligenceService
    from intelligence_retrieval import KnowledgeService
    from datetime import datetime,timezone,timedelta
    with store.engine.begin() as conn:
        conn.execute(text("INSERT INTO signal(title,snippet,canonical_url_key,published_at) VALUES ('Verify tools','Verify tools','https://example.com/retention',now())"))
    opportunity=IntelligenceService(store).analyze()['opportunities'][0]['id']
    research=store.save_research(opportunity,dict(status='complete',summary='Checked',model_version='fake',evidence=[dict(source_url='https://example.com/retention',claim='Verify tools',stance='support',retrieved_at=datetime.now(timezone.utc),excerpt_expires_at=datetime.now(timezone.utc)+timedelta(days=1))]))
    knowledge=KnowledgeService(store.engine);knowledge.index_pending()
    snapshot=knowledge.search('Verify tools',opportunity_id=opportunity,research_id=research['id'])
    assert snapshot['hits']
    store.cleanup_expired(datetime.now(timezone.utc)+timedelta(days=2))
    assert knowledge.get_retrieval(snapshot['id'])['hits'][0]['removed']
    assert knowledge.search('Verify tools',research_id=research['id'])['hits']==[]


def test_empty_model_difference_is_uncertain_not_a_fresh_claim():
    from intelligence_provider import GeminiProvider
    import json
    class Empty(GeminiProvider):
        def _generate(self,*args,**kwargs):
            value=dict(comparisons=[dict(chunk_id=7,verdict='different',prior_claim='Check actions',difference='')],why_us='Expertise',angle='Review checks',uncertainty='')
            return {'candidates':[{'content':{'parts':[{'text':json.dumps(value)}]}}]}
    result=Empty('fixture').refine(dict(label='Checks',angle='Review'),{},dict(hits=[],coverage=0))
    assert result['comparisons'][0]['verdict']=='uncertain'
    assert result['comparisons'][0]['difference']
    assert result['uncertainty']


def test_research_checks_a_starting_reference_before_broadening():
    from intelligence_provider import GeminiProvider
    class Reference(GeminiProvider):
        def _generate(self,prompt,**kwargs):
            assert 'Check the starting source references first' in prompt
            assert 'at least two distinct source URLs' in prompt
            return {'candidates':[{'groundingMetadata':{'groundingChunks':[{'web':{'uri':'https://github.com/pgvector/pgvector'}}],
               'groundingSupports':[{'segment':{'text':'SUPPORT: Vector search is available.'},'groundingChunkIndices':[0]}]}}]}
    result=Reference('fixture').research(dict(label='Vector search'),[dict(title='pgvector',source_url='https://github.com/pgvector/pgvector')])
    assert result['evidence'][0]['source_url']=='https://github.com/pgvector/pgvector'


def test_draft_provider_requests_a_nonempty_typed_factual_citation_list():
    from intelligence_provider import GeminiProvider
    class Structured(GeminiProvider):
        def _generate(self,prompt,**kwargs):
            schema=kwargs.get('schema')
            assert schema and schema['properties']['evidence_ids']['minItems']==1
            assert schema['properties']['evidence_ids']['items']['type']=='INTEGER'
            return {'candidates':[{'content':{'parts':[{'text':'{"text":"Verify tools.","evidence_ids":[7],"company_chunk_ids":[]}'}]}}]}
    result=Structured('fixture').draft(dict(label='Tools',angle='Verify',why_now='Current'),
        dict(evidence=[dict(id=7,claim='Verify tools.',source_url='https://example.com')]),{},'x','post')
    assert result['evidence_ids']==[7]


def test_chunker_change_reindexes_without_overwriting_existing_snapshot(store):
    from intelligence_retrieval import KnowledgeService
    item=store.add_content(dict(title='Policy',text='Verify every action before execution. '*80,channel='blog'))
    old=KnowledgeService(store.engine,embedder=Embedder())
    old.index_pending();snapshot=old.search('Verify execution')
    changed=KnowledgeService(store.engine,embedder=Embedder(),chunk_size=400,chunk_overlap=40)
    assert changed.index_pending()['indexed']==1
    assert changed.search('Verify')['config']!=snapshot['config']
    assert old.get_retrieval(snapshot['id'])['hits'][0]['passage']==snapshot['hits'][0]['passage']


def test_agent_local_settings_can_disable_semantic_processing(tmp_path,monkeypatch):
    import agent_env
    monkeypatch.setattr(agent_env,'AGENT_DIR',tmp_path)
    monkeypatch.delenv('KNOWLEDGE_SEMANTIC_ENABLED',raising=False)
    (tmp_path/'.env.local').write_text('KNOWLEDGE_SEMANTIC_ENABLED=false\nUNRELATED_SECRET=do-not-load\n')
    agent_env.load_agent_environment()
    assert os.environ['KNOWLEDGE_SEMANTIC_ENABLED']=='false'
    assert 'UNRELATED_SECRET' not in os.environ


def test_refinement_selects_numbered_original_quotes_with_a_compact_schema():
    import json
    from intelligence_provider import GeminiProvider
    long_passage=' '.join(f'Sentence {i} explains a distinct verification practice in detail.' for i in range(60))
    class Quotes(GeminiProvider):
        def _generate(self,prompt,**kwargs):
            schema=kwargs.get('schema')
            assert schema
            item=schema['properties']['comparisons']['items']['properties']
            # Gemini rejects schemas that enumerate passage text; quotes are selected by number.
            assert 'enum' not in item.get('prior_claim',{})
            assert item['quote_id']=={'type':'INTEGER'}
            assert len(json.dumps(schema))<1500
            assert '"quote_id": 1' in prompt and 'Log results afterward.' in prompt
            value=dict(comparisons=[dict(quote_id=1,verdict='different',difference='Covers logging, not permissions.')],
                       why_us='Expertise',angle='Review',uncertainty='Review')
            return {'candidates':[{'content':{'parts':[{'text':json.dumps(value)}]}}]}
    result=Quotes('fixture').refine(dict(label='Checks',angle='Review'),{},dict(coverage=1,hits=[
        dict(chunk_id=7,title='Prior',passage='Check permissions before execution. Log results afterward.'),
        dict(chunk_id=8,title='Long',passage=long_passage)]))
    assert result['comparisons']==[dict(chunk_id=7,verdict='different',prior_claim='Log results afterward.',
                                        difference='Covers logging, not permissions.')]


def test_refinement_rejects_a_quote_number_outside_the_supplied_passages():
    import json
    from intelligence_provider import GeminiProvider
    class Forged(GeminiProvider):
        def _generate(self,prompt,**kwargs):
            value=dict(comparisons=[dict(quote_id=9,verdict='different',difference='Invented.')],
                       why_us='Expertise',angle='Review',uncertainty='Review')
            return {'candidates':[{'content':{'parts':[{'text':json.dumps(value)}]}}]}
    with pytest.raises(RuntimeError,match='unsupported company passages'):
        Forged('fixture').refine(dict(label='Checks',angle='Review'),{},dict(coverage=1,hits=[
            dict(chunk_id=7,title='Prior',passage='Check permissions before execution.')]))


def test_subagents_use_the_service_database_instead_of_an_unrelated_environment(monkeypatch,tmp_path):
    from intelligence_subagents import SubagentRunner
    from types import SimpleNamespace
    (tmp_path/'topic_analyst.py').write_text('# fixture')
    monkeypatch.setenv('DATABASE_URL','postgresql+psycopg://wrong:wrong@localhost/unrelated')
    def run(*args,**kwargs):
        assert kwargs['env']['DATABASE_URL']=='postgresql+psycopg://scout:fixture@localhost/signalscout_ui_test'
        return SimpleNamespace(stdout='{"status":"success","data":{"label":"Valid"}}',returncode=0)
    monkeypatch.setattr('subprocess.run',run)
    runner=SubagentRunner(directory=tmp_path,database_url='postgresql+psycopg://scout:fixture@localhost/signalscout_ui_test')
    assert runner.run('topic_analyst',{'signal_ids':[1]})['label']=='Valid'


def test_draft_prompt_preserves_conflicting_research_stance():
    from intelligence_provider import GeminiProvider
    class Stances(GeminiProvider):
        def _generate(self,prompt,**kwargs):
            assert '"stance": "conflict"' in prompt
            assert 'Qualify conflicting or uncertain claims' in prompt
            return {'candidates':[{'content':{'parts':[{'text':'{"text":"Researchers disagree.","evidence_ids":[7],"company_chunk_ids":[]}'}]}}]}
    Stances('fixture').draft(dict(label='Tools',angle='Verify',why_now='Current'),
      dict(evidence=[dict(id=7,claim='Researchers disagree.',source_url='https://example.com',stance='conflict')]),{},'x','post')
