"""Main application intelligence boundaries, using only disposable PostgreSQL."""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url

from signalscout.config import Settings
from signalscout.web import create_app

URL = os.environ.get('TEST_DATABASE_URL')
pytestmark = pytest.mark.skipif(not URL, reason='needs disposable PostgreSQL')
BRIEF = dict(description='Agent security company', audience='Security leaders',
             expertise='Agent security', point_of_view='Verify actions', voice='Practical',
             avoid_claims='Guaranteed safety')
CONTENT = dict(title='Earlier article', text='Agent security requires verification', channel='blog',
               url='https://company.example/prior')


@pytest.fixture
def client(monkeypatch):
    assert make_url(URL).database == 'signalscout_ui_test'
    monkeypatch.setenv('INTELLIGENCE_PROVIDER_AVAILABLE','true')
    app = create_app(Settings(URL))
    with app.state.engine.begin() as conn:
        conn.execute(text('TRUNCATE intelligence_job, content_draft, research_evidence, research_run, '
                          'opportunity, conversation_signal, conversation, intelligence_run, '
                          'company_content, company_brief, source_item, signal_topic, signal_state, '
                          'signal RESTART IDENTITY CASCADE'))
    with TestClient(app, base_url='http://localhost', headers={'Origin':'http://localhost'}) as client:
        yield client
    app.state.engine.dispose()


def test_main_ui_context_round_trip_and_validation(client):
    assert client.get('/api/intelligence/brief').json() is None
    response=client.put('/api/intelligence/brief',json=BRIEF)
    assert response.status_code == 200, response.text
    assert client.get('/api/intelligence/brief').json()['brief'] == BRIEF
    assert client.put('/api/intelligence/brief',json={**BRIEF,'voice':''}).status_code == 422
    content=client.post('/api/intelligence/content',json=CONTENT).json()
    changed=client.put(f"/api/intelligence/content/{content['id']}",json={**CONTENT,'title':'New title'})
    assert changed.status_code == 200
    items=client.get('/api/intelligence/content').json()
    assert len(items)==1 and items[0]['title']=='New title'
    assert client.delete(f"/api/intelligence/content/{items[0]['id']}").status_code==200
    assert client.get('/api/intelligence/content').json()==[]
    assert client.post('/api/intelligence/content',json={**CONTENT,'url':'javascript:alert(1)'}).status_code==400
    assert client.delete('/api/intelligence/brief').status_code==200
    assert client.get('/api/intelligence/brief').json() is None


def seed_signals(client):
    with client.app.state.engine.begin() as conn:
        for id, title in [(1,'Acme agent security toolkit released'),(2,'Acme launches agent security toolkit')]:
            conn.execute(text("INSERT INTO signal (id,title,snippet,canonical_url_key,published_at) "
                              "VALUES (:id,:title,:title,:url,now())"),
                         dict(id=id,title=title,url=f'https://example.com/{id}'))
            conn.execute(text("INSERT INTO source_item (signal_id,source_key,external_id,source_url,"
                              "content_url,canonical_url_key,target_host,title,normalized_title,snippet,published_at) "
                              "VALUES (:id,'web',:external,:url,:url,:url,'example.com',:title,:title,:title,now())"),
                         dict(id=id,external=str(id),title=title,url=f'https://example.com/{id}'))
        conn.execute(text('INSERT INTO signal_state (signal_id,saved,interesting) VALUES (1,true,true)'))


def test_analysis_queues_reuses_job_and_worker_exposes_opportunities(client):
    seed_signals(client)
    assert client.get('/api/intelligence/status').json()['signal_count']==2
    response=client.post('/api/intelligence/analyze',json={'days':30})
    assert response.status_code == 202, response.text
    job=response.json()
    assert job['status']=='queued'
    repeated=client.post('/api/intelligence/analyze',json={'days':30}).json()
    assert repeated['id']==job['id']
    assert client.post('/api/intelligence/analyze',json={'days':7}).status_code==409
    assert client.get('/api/intelligence/opportunities').json()['opportunities']==[]
    from signalscout.intelligence_jobs import process_one
    from signalscout.intelligence import make_service
    assert process_one(client.app.state.engine,make_service(client.app.state.engine))==job['id']
    done=client.get(f"/api/intelligence/jobs/{job['id']}").json()
    assert done['status']=='complete' and done['result']['run_id']
    items=client.get('/api/intelligence/opportunities').json()
    assert len(items['opportunities'])==1
    item=items['opportunities'][0]
    detail=client.get(f"/api/intelligence/opportunities/{item['id']}").json()
    assert detail['signal_ids']==[1,2]
    assert len(detail['source_items'])==2
    assert detail['components']['pov_fit'] is None
    assert detail['research'] is None and detail['drafts']==[]
    assert detail['analyzed_at']
    assert client.get('/api/signals/1').json()['saved'] is True
    assert client.get('/api/intelligence/opportunities/99999').status_code==404
    assert client.get('/api/intelligence/jobs/99999').status_code==404


class Provider:
    model='test-provider'

    def research(self, opportunity, sources):
        return dict(status='complete',summary='Evidence includes a disagreement.',evidence=[
            dict(source_url=sources[0]['source_url'],claim='Agent security requires verification',stance='support'),
            dict(source_url='https://example.org/conflict',claim='Some researchers disagree',stance='conflict',retrieved=True)])

    def draft(self, opportunity, research, brief, channel, format):
        return dict(text='Agent security requires verification.',evidence_ids=[research['evidence'][0]['id']])


def analyze_fixture(client):
    from signalscout.intelligence import make_service
    seed_signals(client)
    agent=make_service(client.app.state.engine)
    opportunity=agent.analyze()['opportunities'][0]['id']
    agent.provider=Provider()
    return agent,opportunity


@pytest.mark.parametrize(('channel','format'), [('linkedin','post'),('linkedin','reply'),('x','post'),('x','reply')])
def test_research_and_each_draft_queue_share_agent_contract(client,channel,format):
    from signalscout.intelligence_jobs import process_one
    agent,opportunity=analyze_fixture(client)
    client.put('/api/intelligence/brief',json=BRIEF)
    blocked=client.post(f'/api/intelligence/opportunities/{opportunity}/draft',json=dict(channel=channel,format=format))
    assert blocked.status_code==400
    response=client.post(f'/api/intelligence/opportunities/{opportunity}/research')
    assert response.status_code==202, response.text
    process_one(client.app.state.engine,agent)
    detail=client.get(f'/api/intelligence/opportunities/{opportunity}').json()
    assert detail['research']['status']=='complete'
    assert detail['research']['evidence'][1]['stance']=='conflict'
    queued=client.post(f'/api/intelligence/opportunities/{opportunity}/draft',json=dict(channel=channel,format=format))
    assert queued.status_code==202, queued.text
    process_one(client.app.state.engine,agent)
    done=client.get(f"/api/intelligence/jobs/{queued.json()['id']}").json()
    assert done['status']=='complete' and set(done['result'])=={'draft_id','opportunity_id'}
    draft=client.get(f'/api/intelligence/opportunities/{opportunity}').json()['drafts'][0]
    assert draft['channel']==channel and draft['format']==format
    assert draft['evidence'][0]['source_url']=='https://example.com/1'


def test_provider_prerequisites_and_errors_are_visible_and_safe(client,monkeypatch):
    from signalscout.intelligence_jobs import process_one
    agent,opportunity=analyze_fixture(client)
    monkeypatch.setenv('INTELLIGENCE_PROVIDER_AVAILABLE','false')
    denied=client.post(f'/api/intelligence/opportunities/{opportunity}/research')
    assert denied.status_code==503 and 'provider' in denied.json()['detail'].lower()
    monkeypatch.setenv('INTELLIGENCE_PROVIDER_AVAILABLE','true')
    class Broken(Provider):
        def research(self,*args):
            raise RuntimeError('secret-key-private-payload')
    agent.provider=Broken()
    queued=client.post(f'/api/intelligence/opportunities/{opportunity}/research').json()
    process_one(client.app.state.engine,agent)
    done=client.get(f"/api/intelligence/jobs/{queued['id']}").json()
    assert done['status']=='failed'
    assert 'secret-key-private-payload' not in str(done)
    assert client.get(f'/api/intelligence/opportunities/{opportunity}').json()['research']['status']=='partial'
    assert client.post(f'/api/intelligence/opportunities/{opportunity}/draft',json=dict(channel='email',format='post')).status_code==422
    assert client.post('/api/intelligence/analyze',json={'days':100}).status_code==422
    assert client.post('/api/intelligence/analyze',json={'days':30},headers={'Origin':'https://evil.example'}).status_code==403


def test_editorial_revision_retains_original_and_snapshot(client):
    agent,opportunity=analyze_fixture(client)
    agent.set_brief(BRIEF)
    agent.research(opportunity)
    original=agent.draft(opportunity,'x','post')
    # New research must not change citations attached to an existing draft.
    agent.research(opportunity)
    response=client.put(f"/api/intelligence/drafts/{original['id']}",json={'text':'Our edited angle.'})
    assert response.status_code==200, response.text
    revision=response.json()
    assert revision['id']!=original['id'] and revision['revises_id']==original['id']
    drafts=client.get(f'/api/intelligence/opportunities/{opportunity}').json()['drafts']
    assert drafts[0]['text']=='Our edited angle.' and drafts[1]['text']==original['text']
    assert drafts[0]['research_run_id']==original['research_run_id']
    assert drafts[0]['evidence_ids']==original['evidence_ids']
    assert drafts[0]['evidence']==drafts[1]['evidence']
    assert client.put(f"/api/intelligence/drafts/{original['id']}",json={'text':'a'*281}).status_code==400
    assert client.put('/api/intelligence/drafts/99999',json={'text':'Edited'}).status_code==404


def test_abandoned_jobs_fail_visibly_without_replay(client):
    from signalscout.intelligence_jobs import recover_running
    queued=client.post('/api/intelligence/analyze',json={'days':30}).json()
    with client.app.state.engine.begin() as conn:
        conn.execute(text("UPDATE intelligence_job SET status='running',started_at=now()-interval '6 minutes' WHERE id=:id"),queued)
    assert recover_running(client.app.state.engine)==1
    job=client.get(f"/api/intelligence/jobs/{queued['id']}").json()
    assert job['status']=='failed' and job['finished_at']
    assert 'interrupted' in job['error_message'].lower()
    fresh=client.post('/api/intelligence/analyze',json={'days':7}).json()
    assert recover_running(client.app.state.engine,force=True)==0
    assert client.get(f"/api/intelligence/jobs/{fresh['id']}").json()['status']=='queued'


def test_partial_research_preserves_evidence_and_blocks_drafting(client):
    from signalscout.intelligence_jobs import process_one
    agent,opportunity=analyze_fixture(client)
    class Partial(Provider):
        def research(self,*args):
            return {**super().research(*args),'status':'partial'}
    agent.provider=Partial()
    queued=client.post(f'/api/intelligence/opportunities/{opportunity}/research').json()
    process_one(client.app.state.engine,agent)
    assert client.get(f"/api/intelligence/jobs/{queued['id']}").json()['status']=='partial'
    detail=client.get(f'/api/intelligence/opportunities/{opportunity}').json()
    assert detail['research']['evidence'] and detail['research']['status']=='partial'
    assert client.post(f'/api/intelligence/opportunities/{opportunity}/draft',json=dict(channel='x',format='post')).status_code==400


def test_concurrent_submissions_create_only_one_active_job(client):
    from concurrent.futures import ThreadPoolExecutor
    from signalscout.intelligence_jobs import queue_job
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(queue_job,client.app.state.engine,'analyze',{'days':30,'limit':500}) for _ in range(2)]
        jobs=[future.result() for future in futures]
    assert jobs[0]['id']==jobs[1]['id']
    assert len(client.get('/api/intelligence/jobs').json())==1


def test_draft_validation_failure_explains_the_citation_blocker(client):
    from signalscout.intelligence_jobs import process_one
    agent,opportunity=analyze_fixture(client)
    agent.set_brief(BRIEF)
    agent.research(opportunity)
    class Unsupported(Provider):
        def draft(self,opportunity,research,*args):
            return dict(text='We found 999 flaws.',evidence_ids=[research['evidence'][0]['id']])
    agent.provider=Unsupported()
    queued=client.post(f'/api/intelligence/opportunities/{opportunity}/draft',json=dict(channel='x',format='post')).json()
    process_one(client.app.state.engine,agent)
    done=client.get(f"/api/intelligence/jobs/{queued['id']}").json()
    assert done['status']=='failed'
    assert 'numeric claim' in done['error_message'].lower()
    assert client.get(f'/api/intelligence/opportunities/{opportunity}').json()['drafts']==[]


def test_knowledge_queue_and_refine_angle_use_cited_passages(client):
    from signalscout.intelligence_jobs import process_one
    from intelligence_retrieval import KnowledgeService
    agent,opportunity=analyze_fixture(client)
    agent.set_brief(BRIEF)
    content=client.post('/api/intelligence/content',json=CONTENT).json()
    response=client.get('/api/intelligence/knowledge/status')
    assert response.status_code==200, response.text
    assert response.json()['pending']==1
    job=client.post('/api/intelligence/knowledge/reindex').json()
    assert process_one(client.app.state.engine,agent)==job['id']
    assert client.get(f"/api/intelligence/jobs/{job['id']}").json()['status']=='complete'
    search=client.post('/api/intelligence/knowledge/search',json={'query':'Agent security verification'})
    assert search.status_code==202
    process_one(client.app.state.engine,agent)
    result=client.get(f"/api/intelligence/knowledge/search/{search.json()['id']}").json()
    assert result['hits'][0]['source_id']==content['id']
    class Angles(Provider):
        def refine(self,opportunity,brief,retrieval):
            return dict(comparisons=[dict(chunk_id=retrieval['hits'][0]['chunk_id'],verdict='uncertain',prior_claim=CONTENT['text'],difference='Consider enforcement failures')],
                        why_us='Security expertise',angle='Explore enforcement failures',uncertainty='Requires editorial review')
    agent.provider=Angles()
    queued=client.post(f'/api/intelligence/opportunities/{opportunity}/refine-angle')
    assert queued.status_code==202,queued.text
    process_one(client.app.state.engine,agent)
    detail=client.get(f'/api/intelligence/opportunities/{opportunity}').json()
    assert detail['enrichment']['result']['angle']=='Explore enforcement failures'
    assert detail['knowledge']['hits'][0]['passage']==CONTENT['text']
    client.delete(f"/api/intelligence/content/{content['id']}")
    detail=client.get(f'/api/intelligence/opportunities/{opportunity}').json()
    assert detail['enrichment']['source_removed']
    assert detail['enrichment']['result']=={}
    with client.app.state.engine.connect() as conn:
        assert conn.execute(text('SELECT result FROM opportunity_enrichment ORDER BY id DESC LIMIT 1')).scalar_one()=={}


def test_refinement_rejects_forged_company_citations(client):
    agent,opportunity=analyze_fixture(client)
    agent.set_brief(BRIEF);agent.add_content(CONTENT)
    agent.knowledge.index_pending()
    class Forged(Provider):
        def refine(self,*args):
            return dict(comparisons=[dict(chunk_id=999999,verdict='repeated',prior_claim='Invented',difference='Invented')],why_us='Invented',angle='Invented',uncertainty='')
    agent.provider=Forged()
    with pytest.raises(RuntimeError,match='unsupported'):
        agent.refine_angle(opportunity)


def test_draft_records_company_context_separately_from_factual_sources(client):
    agent,opportunity=analyze_fixture(client)
    agent.set_brief(BRIEF);agent.add_content(CONTENT)
    research=agent.research(opportunity)
    agent.knowledge.index_pending(limit=4)
    class Grounded(Provider):
        def draft(self,opportunity,research,*args):
            assert opportunity['company_context']['hits'][0]['role']=='company'
            assert opportunity['factual_context']['hits'][0]['role']=='factual'
            assert all(h['source_id'] in {e['id'] for e in research['evidence']} for h in opportunity['factual_context']['hits'])
            return dict(text='Agent security requires verification.',evidence_ids=[research['evidence'][0]['id']],
                        company_chunk_ids=[opportunity['company_context']['hits'][0]['chunk_id']])
    agent.provider=Grounded()
    draft=agent.draft(opportunity,'x','post')
    detail=client.get(f'/api/intelligence/opportunities/{opportunity}').json()
    assert detail['drafts'][0]['company_context']['hits'][0]['role']=='company'
    assert detail['drafts'][0]['factual_context']['research_id']==research['id']
    revision=client.put(f"/api/intelligence/drafts/{draft['id']}",json={'text':'Editorial revision'}).json()
    revised=client.get(f'/api/intelligence/opportunities/{opportunity}').json()['drafts'][0]
    assert revised['id']==revision['id']
    assert revised['company_context']['id']==detail['drafts'][0]['company_context']['id']


def test_opportunity_inspection_shows_indexed_passages_without_model_calls(client):
    agent,opportunity=analyze_fixture(client)
    agent.add_content(CONTENT);agent.knowledge.index_pending()
    detail=client.get(f'/api/intelligence/opportunities/{opportunity}').json()
    assert detail['knowledge']['mode']=='lexical'
    assert detail['knowledge']['hits'][0]['passage']==CONTENT['text']


def test_idle_worker_indexes_content_saved_during_an_active_job(client):
    from signalscout.intelligence_worker import tick
    from signalscout.intelligence import make_service
    job=client.post('/api/intelligence/analyze',json={'days':30}).json()
    client.post('/api/intelligence/content',json=CONTENT)
    assert client.get('/api/intelligence/knowledge/status').json()['pending']==1
    agent=make_service(client.app.state.engine)
    tick(client.app.state.engine,agent)
    assert client.get(f"/api/intelligence/jobs/{job['id']}").json()['status']=='complete'
    tick(client.app.state.engine,agent)
    assert client.get('/api/intelligence/knowledge/status').json()['ready']==1


def test_standalone_api_exposes_shared_knowledge_service(client):
    from api.main import create_app as agent_app
    agent,opportunity=analyze_fixture(client)
    agent.add_content(CONTENT)
    independent=TestClient(agent_app(agent),base_url='http://localhost',headers={'Origin':'http://localhost'})
    response=independent.post('/knowledge/index')
    assert response.status_code==200,response.text
    result=independent.post('/knowledge/search',json={'query':'Agent verification'})
    assert result.status_code==200 and result.json()['hits']


def test_refinement_cannot_invent_a_prior_claim_with_a_valid_citation(client):
    agent,opportunity=analyze_fixture(client)
    agent.set_brief(BRIEF);agent.add_content(CONTENT);agent.knowledge.index_pending()
    class Invented(Provider):
        def refine(self,opportunity,brief,retrieval):
            return dict(comparisons=[dict(chunk_id=retrieval['hits'][0]['chunk_id'],verdict='different',prior_claim='We guarantee absolute security',difference='New')],why_us='Expertise',angle='New',uncertainty='Review')
    agent.provider=Invented()
    with pytest.raises(RuntimeError,match='prior claim'):
        agent.refine_angle(opportunity)


def test_edit_during_angle_generation_does_not_save_obsolete_claims(client):
    agent,opportunity=analyze_fixture(client)
    agent.set_brief(BRIEF);content=agent.add_content(CONTENT);agent.knowledge.index_pending()
    class Editing(Provider):
        def refine(self,opportunity,brief,retrieval):
            agent.replace_content(content['id'],{**CONTENT,'text':'A revised company argument'})
            return dict(comparisons=[dict(chunk_id=retrieval['hits'][0]['chunk_id'],verdict='uncertain',prior_claim=CONTENT['text'],difference='Review')],why_us='Expertise',angle='Review',uncertainty='Review')
    agent.provider=Editing()
    with pytest.raises(RuntimeError,match='changed'):
        agent.refine_angle(opportunity)


def test_expired_research_cannot_feed_a_new_draft(client):
    agent,opportunity=analyze_fixture(client)
    agent.set_brief(BRIEF);research=agent.research(opportunity)
    with client.app.state.engine.begin() as conn:
        conn.execute(text("UPDATE research_evidence SET claim='[expired]' WHERE research_run_id=:id"),research)
    with pytest.raises(ValueError,match='unexpired'):
        agent.draft(opportunity,'x','post')


def test_evidence_expiry_during_generation_cannot_save_a_draft(client):
    agent,opportunity=analyze_fixture(client);agent.set_brief(BRIEF);research=agent.research(opportunity)
    class Expiring(Provider):
        def draft(self,opportunity,research,*args):
            with client.app.state.engine.begin() as conn:
                conn.execute(text("UPDATE research_evidence SET claim='[expired]' WHERE research_run_id=:id"),research)
            return dict(text='Agent security requires verification.',evidence_ids=[research['evidence'][0]['id']])
    agent.provider=Expiring()
    with pytest.raises(RuntimeError,match='evidence changed'):
        agent.draft(opportunity,'x','post')


def test_expiry_deadline_blocks_retrieval_and_drafts_before_cleanup(client):
    agent,opportunity=analyze_fixture(client);agent.set_brief(BRIEF);research=agent.research(opportunity)
    agent.knowledge.index_pending(limit=4)
    with client.app.state.engine.begin() as conn:
        conn.execute(text("UPDATE research_evidence SET excerpt_expires_at=now()-interval '1 minute' WHERE research_run_id=:id"),research)
    assert agent.knowledge.search('Agent verification',research_id=research['id'])['hits']==[]
    with pytest.raises(ValueError,match='unexpired'):
        agent.draft(opportunity,'x','post')


def test_standalone_ui_inspects_the_same_knowledge_passages(client):
    from ui.app import create_app as agent_ui
    agent,opportunity=analyze_fixture(client);agent.add_content(CONTENT)
    browser=agent_ui(agent).test_client()
    response=browser.post('/knowledge/index',headers={'Origin':'http://localhost'})
    assert response.status_code==302
    page=browser.get(f'/?opportunity={opportunity}')
    assert b'Retrieved company passages' in page.data and CONTENT['text'].encode() in page.data
    search=browser.post('/knowledge/search',data={'query':'Agent verification'},headers={'Origin':'http://localhost'})
    assert search.status_code==200 and CONTENT['text'].encode() in search.data


def test_agent_api_detail_includes_draft_retrieval_provenance(client):
    from api.main import create_app as agent_app
    agent,opportunity=analyze_fixture(client);agent.set_brief(BRIEF);agent.add_content(CONTENT)
    agent.research(opportunity);agent.knowledge.index_pending(limit=4);agent.draft(opportunity,'x','post')
    independent=TestClient(agent_app(agent),base_url='http://localhost')
    detail=independent.get(f'/opportunities/{opportunity}').json()
    assert detail['drafts'][0]['company_context']['hits'][0]['passage']==CONTENT['text']
    assert detail['drafts'][0]['factual_context']['research_id']==detail['research']['id']
