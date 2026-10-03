"""Key-free session APIs and worker activity persistence."""
import json
from uuid import UUID
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field,ConfigDict
from sqlalchemy import text
from .intelligence_jobs import JobConflict

class MessageIn(BaseModel):
    model_config=ConfigDict(extra='forbid')
    message:str=Field(min_length=1,max_length=4000)
    request_id:UUID
    selected_opportunity_id:int|None=Field(default=None,ge=1)

def queue_message(engine,session_id,payload):
    message=payload.message.strip()
    if not message:raise ValueError('Enter a message.')
    with engine.begin() as c:
        c.execute(text('SELECT pg_advisory_xact_lock(20261001)'))
        if not c.execute(text('SELECT id FROM agent_chat_session WHERE id=:id AND expires_at>now() FOR UPDATE'),{'id':session_id}).first():raise LookupError('Session not found')
        existing=c.execute(text('SELECT j.*,t.content FROM intelligence_job j JOIN agent_chat_turn t ON t.id=j.chat_turn_id WHERE request_key=:key'),{'key':payload.request_id}).mappings().first()
        if existing:
            if existing['chat_session_id']!=session_id or existing['content']!=message or existing['opportunity_id']!=payload.selected_opportunity_id:raise JobConflict('Submission token was already used for another message.')
            return {k:v for k,v in existing.items() if k!='content'}
        if c.execute(text("SELECT id FROM intelligence_job WHERE status IN ('queued','running')")).first():raise JobConflict('Another intelligence job is active. Wait for it to finish.')
        if payload.selected_opportunity_id and not c.execute(text('SELECT id FROM opportunity WHERE id=:id'),{'id':payload.selected_opportunity_id}).first():raise LookupError('Opportunity not found')
        turn=c.execute(text("INSERT INTO agent_chat_turn(session_id,role,content) VALUES (:id,'user',:message) RETURNING id"),{'id':session_id,'message':message}).scalar_one()
        c.execute(text("UPDATE agent_chat_session SET updated_at=now(),expires_at=now()+interval '90 days' WHERE id=:id"),{'id':session_id})
        return dict(c.execute(text("INSERT INTO intelligence_job(action,payload,opportunity_id,chat_session_id,chat_turn_id,request_key) VALUES ('chat','{}',:opportunity,:session,:turn,:key) RETURNING *"),{'opportunity':payload.selected_opportunity_id,'session':session_id,'turn':turn,'key':payload.request_id}).mappings().one())

def event(engine,job_id,**fields):
    with engine.begin() as c:
        c.execute(text('INSERT INTO intelligence_job_event(job_id,tool,executor,status,summary,inputs,artifacts) VALUES (:job,:tool,:executor,:status,:summary,CAST(:inputs AS jsonb),CAST(:artifacts AS jsonb))'),dict(job=job_id,**{k:v for k,v in fields.items() if k not in ('inputs','artifacts')},inputs=json.dumps(fields.get('inputs',{})),artifacts=json.dumps(fields.get('artifacts',[]))))

def run_turn(engine,agent,job):
    from intelligence_workspace import execute_turn
    history=agent.chat_history(job['chat_session_id'])
    with engine.connect() as c:message=c.execute(text('SELECT content FROM agent_chat_turn WHERE id=:id'),{'id':job['chat_turn_id']}).scalar_one()
    prior=[t for t in history if t['id']<job['chat_turn_id']][-12:]
    result=execute_turn(agent,message,prior,selected_id=job['opportunity_id'],emit=lambda **e:event(engine,job['id'],**e))
    turn=agent.append_chat_turn(job['chat_session_id'],'assistant',result['reply'][:4000])
    return {'assistant_turn_id':turn['id'],'session_id':job['chat_session_id'],'mode':result['mode'],'status':result['status']}

def make_router(engine,agent):
    router=APIRouter(prefix='/chat')
    def invoke(fn,*args):
        try:return fn(*args)
        except JobConflict as e:raise HTTPException(409,str(e)) from None
        except LookupError:raise HTTPException(404,'Chat session or opportunity not found') from None
        except ValueError as e:raise HTTPException(400,str(e)) from None
    @router.post('/sessions',status_code=201)
    def create():return agent.create_chat_session()
    @router.get('/sessions')
    def sessions():
        with engine.connect() as c:return [dict(r) for r in c.execute(text("SELECT s.id,s.created_at,s.updated_at,(SELECT left(content,80) FROM agent_chat_turn WHERE session_id=s.id AND role='user' ORDER BY id LIMIT 1) AS title FROM agent_chat_session s WHERE expires_at>now() ORDER BY updated_at DESC LIMIT 30")).mappings()]
    @router.get('/sessions/{id}')
    def session(id:int):
        turns=invoke(agent.chat_history,id)
        with engine.connect() as c:
            jobs=[dict(r) for r in c.execute(text('SELECT * FROM intelligence_job WHERE chat_session_id=:id ORDER BY id DESC LIMIT 20'),{'id':id}).mappings()]
            events=[dict(r) for r in c.execute(text('SELECT e.* FROM intelligence_job_event e JOIN intelligence_job j ON j.id=e.job_id WHERE j.chat_session_id=:id ORDER BY e.id DESC LIMIT 160'),{'id':id}).mappings()][::-1]
        return {'id':id,'turns':turns,'jobs':jobs,'events':events}
    @router.post('/sessions/{id}/messages',status_code=202)
    def message(id:int,payload:MessageIn):return invoke(queue_message,engine,id,payload)
    @router.delete('/sessions/{id}')
    def delete(id:int):
        with engine.begin() as c:
            c.execute(text('SELECT pg_advisory_xact_lock(20261001)'))
            if c.execute(text("SELECT id FROM intelligence_job WHERE chat_session_id=:id AND status IN ('queued','running')"),{'id':id}).first():raise HTTPException(409,'Wait for this conversation to finish before deleting it.')
            if not c.execute(text('DELETE FROM agent_chat_session WHERE id=:id RETURNING id'),{'id':id}).first():raise HTTPException(404,'Chat session not found')
        return {'id':id,'deleted':True}
    return router
