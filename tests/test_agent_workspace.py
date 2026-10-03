import os,subprocess,sys
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from signalscout.config import Settings
from signalscout.web import create_app

URL=os.environ.get('TEST_DATABASE_URL')
pytestmark=pytest.mark.skipif(not URL,reason='needs disposable PostgreSQL')
@pytest.fixture
def client(monkeypatch):
    subprocess.run([sys.executable,'-m','alembic','upgrade','head'],env={**os.environ,'DATABASE_URL':URL},check=True,capture_output=True)
    monkeypatch.setenv('INTELLIGENCE_PROVIDER_AVAILABLE','true')
    app=create_app(Settings(URL))
    with app.state.engine.begin() as c:c.execute(text('TRUNCATE intelligence_job,agent_chat_session,company_brief,company_content,content_draft,research_evidence,research_run,opportunity,conversation_signal,conversation,intelligence_run,source_item,signal_topic,signal_state,signal RESTART IDENTITY CASCADE'))
    with TestClient(app,base_url='http://localhost',headers={'Origin':'http://localhost'}) as client:yield client
    app.state.engine.dispose()

def session(client):
    r=client.post('/api/intelligence/chat/sessions',json={})
    assert r.status_code==201,r.text
    return r.json()['id']
def send(client,id,message='list opportunities',**extra):
    return client.post(f'/api/intelligence/chat/sessions/{id}/messages',json={'message':message,'request_id':str(uuid4()),**extra})

def test_chat_queue_idempotence_conflicts_retention_and_origin(client):
    id=session(client);token=str(uuid4());body={'message':'list opportunities','request_id':token}
    r=client.post(f'/api/intelligence/chat/sessions/{id}/messages',json=body)
    assert r.status_code==202,r.text
    assert client.post(f'/api/intelligence/chat/sessions/{id}/messages',json=body).json()['id']==r.json()['id']
    assert send(client,id,'analyze').status_code==409
    assert client.post(f'/api/intelligence/chat/sessions/{id}/messages',json={**body,'message':'different'}).status_code==409
    state=client.get(f'/api/intelligence/chat/sessions/{id}').json()
    assert len(state['turns'])==1 and state['turns'][0]['role']=='user'
    assert 'message' not in state['jobs'][0]['payload']
    assert client.delete(f'/api/intelligence/chat/sessions/{id}').status_code==409
    assert send(client,id,'x'*4001).status_code==422
    assert client.post('/api/intelligence/chat/sessions',json={},headers={'Origin':'https://evil.example'}).status_code==403
    from signalscout.intelligence_jobs import recover_running
    with client.app.state.engine.begin() as c:c.execute(text("UPDATE intelligence_job SET status='running'"))
    recover_running(client.app.state.engine,force=True)
    assert client.delete(f'/api/intelligence/chat/sessions/{id}').status_code==200
    assert client.get(f'/api/intelligence/chat/sessions/{id}').status_code==404
    with client.app.state.engine.connect() as c:assert c.execute(text('SELECT count(*) FROM intelligence_job')).scalar_one()==0

def test_worker_offline_chat_persists_actual_activity_and_reload(client,monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    id=session(client);job=send(client,id).json()
    from signalscout.intelligence import make_service
    from signalscout.intelligence_jobs import process_one
    process_one(client.app.state.engine,make_service(client.app.state.engine))
    state=client.get(f'/api/intelligence/chat/sessions/{id}').json()
    assert [t['role'] for t in state['turns']]==['user','assistant']
    assert state['jobs'][0]['status']=='complete'
    assert state['jobs'][0]['result']['mode']=='offline'
    assert [e['status'] for e in state['events']]==['running','complete']
    assert state['events'][0]['tool']=='list_opportunities'
    assert client.get('/api/intelligence/chat/sessions').json()[0]['id']==id
    with client.app.state.engine.begin() as c:c.execute(text("UPDATE agent_chat_session SET expires_at=now()-interval '1 second' WHERE id=:id"),{'id':id})
    make_service(client.app.state.engine).cleanup_expired()
    with client.app.state.engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM intelligence_job_event')).scalar_one()==0
        assert c.execute(text('SELECT count(*) FROM intelligence_job')).scalar_one()==0

def test_model_calls_shared_tools_and_does_not_replay_on_failure(client,monkeypatch):
    from signalscout.intelligence import make_service
    from signalscout.intelligence_jobs import process_one
    make_service(client.app.state.engine)
    import intelligence_workspace as workspace
    class Model:
        def __init__(self,*_):self.calls=0
        def respond(self,contents,tools,system):
            self.calls+=1
            if self.calls==1:return [{'functionCall':{'name':'list_opportunities','args':{}}}]
            raise RuntimeError('secret-key-must-not-leak')
    monkeypatch.setattr(workspace,'WorkspaceModel',Model)
    monkeypatch.setenv('GEMINI_API_KEY','fixture-only')
    id=session(client);send(client,id)
    process_one(client.app.state.engine,make_service(client.app.state.engine))
    state=client.get(f'/api/intelligence/chat/sessions/{id}').json()
    assert state['jobs'][0]['status']=='partial'
    assert len(state['events'])==2
    assert 'not repeated' in state['turns'][-1]['content']
    assert 'secret-key' not in str(state)

def test_research_selection_gate_and_invalid_tool_arguments(client,monkeypatch):
    from signalscout.intelligence import make_service
    make_service(client.app.state.engine)
    from intelligence_workspace import execute_turn
    events=[]
    class Model:
        calls=0
        def respond(self,*_):
            self.calls+=1
            if self.calls==1:return [{'functionCall':{'name':'research_opportunity','args':{'opportunity_id':999}}}]
            return [{'text':'Select an opportunity first.'}]
    result=execute_turn(make_service(client.app.state.engine),'Research opportunity 999',[],model=Model(),emit=lambda **e:events.append(e))
    assert result['status']=='partial'
    assert [e['status'] for e in events]==['running','failed']
    assert 'Select' in events[-1]['summary']
    assert send(client,session(client),selected_opportunity_id=999999).status_code==404

def test_selected_chat_research_and_draft_save_real_artifacts(client):
    from test_intelligence_ui import analyze_fixture,BRIEF,Provider
    from intelligence_workspace import execute_turn
    agent,opportunity=analyze_fixture(client)
    client.put('/api/intelligence/brief',json=BRIEF)
    agent.add_content({'title':'Acme agent security toolkit','text':'Acme agent security toolkit requires verification.','channel':'blog'})
    agent.knowledge.index_pending()
    class RefiningProvider(Provider):
        def refine(self,opportunity,brief,retrieval):
            hit=retrieval['hits'][0]
            return {'comparisons':[{'chunk_id':hit['chunk_id'],'verdict':'uncertain','prior_claim':hit['passage'],'difference':'Freshness requires editorial review.'}],'why_us':'Agent security expertise','angle':'Check the toolkit verification workflow','uncertainty':'Human review required'}
    agent.provider=RefiningProvider()
    class Model:
        calls=0
        def respond(self,*_):
            self.calls+=1
            if self.calls==1:return [{'functionCall':{'name':'research_opportunity','args':{'opportunity_id':opportunity}}}]
            if self.calls==2:return [{'functionCall':{'name':'refine_angle','args':{'opportunity_id':opportunity}}}]
            if self.calls==3:return [{'functionCall':{'name':'draft_content','args':{'opportunity_id':opportunity,'channel':'linkedin','format':'post'}}}]
            return [{'text':'Research and draft saved. Review the sources before use.'}]
    events=[]
    result=execute_turn(agent,'Research and draft this topic',[],selected_id=opportunity,model=Model(),emit=lambda **e:events.append(e))
    assert result['status']=='complete'
    detail=agent.opportunity_detail(opportunity)
    assert detail['research']['status']=='complete' and len(detail['drafts'])==1
    assert any(a['kind']=='source' for e in events for a in e['artifacts'])
    assert any(a['kind']=='draft' and a['id']==detail['drafts'][0]['id'] for e in events for a in e['artifacts'])

def test_bad_model_requests_count_toward_tool_budget(client):
    from signalscout.intelligence import make_service
    make_service(client.app.state.engine)
    from intelligence_workspace import execute_turn
    class Model:
        def respond(self,*_):return [{'functionCall':{'name':'research_opportunity','args':{'opportunity_id':999}}}]
    events=[]
    result=execute_turn(make_service(client.app.state.engine),'Research',[],model=Model(),emit=lambda **e:events.append(e))
    assert len([e for e in events if e['status']=='running'])<=8
    assert result['status']=='partial'

def test_activity_is_visible_while_provider_runs_and_interruptions_close_steps(client,monkeypatch):
    from test_intelligence_ui import analyze_fixture,Provider
    from signalscout.intelligence_jobs import process_one,recover_running
    import intelligence_workspace as workspace
    agent,opportunity=analyze_fixture(client)
    id=session(client);job=send(client,id,'Research this topic',selected_opportunity_id=opportunity).json()
    class ObservedProvider(Provider):
        def research(self,*args):
            state=client.get(f'/api/intelligence/chat/sessions/{id}').json()
            assert state['jobs'][0]['status']=='running'
            assert state['events'][-1]['status']=='running'
            assert state['events'][-1]['tool']=='research_opportunity'
            return super().research(*args)
    agent.provider=ObservedProvider()
    class Model:
        calls=0
        def __init__(self,*_):pass
        def respond(self,*_):
            self.calls+=1
            return [{'functionCall':{'name':'research_opportunity','args':{'opportunity_id':opportunity}}}] if self.calls==1 else [{'text':'Research saved.'}]
    monkeypatch.setenv('GEMINI_API_KEY','fixture-only');monkeypatch.setattr(workspace,'WorkspaceModel',Model)
    process_one(client.app.state.engine,agent)
    assert client.get(f'/api/intelligence/chat/sessions/{id}').json()['jobs'][0]['status']=='complete'
    with client.app.state.engine.begin() as c:
        c.execute(text("UPDATE intelligence_job SET status='running' WHERE id=:id"),{'id':job['id']})
        c.execute(text("INSERT INTO intelligence_job_event(job_id,tool,executor,status,summary,inputs,artifacts) VALUES (:id,'draft_content','draft_writer','running','Started','{}','[]')"),{'id':job['id']})
    recover_running(client.app.state.engine,force=True)
    state=client.get(f'/api/intelligence/chat/sessions/{id}').json()
    assert state['events'][-1]['status']=='failed'
    assert 'not replayed' in state['events'][-1]['summary']
