"""Application adapter for the independently runnable intelligence agent."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path as FilePath
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy import text
from .intelligence_jobs import queue_job, list_jobs, get_job, JobConflict


def make_service(engine, *, use_subagents=False):
    directory = FilePath(os.environ.get('SIGNAL_INTELLIGENCE_DIR',
                         FilePath(__file__).resolve().parents[2] / 'agents' / 'signal-intelligence'))
    if not (directory / 'intelligence_service.py').is_file():
        raise RuntimeError('Intelligence agent is not installed')
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))
    from intelligence_service import IntelligenceService
    from memory.memory import IntelligenceStore
    from intelligence_subagents import SubagentRunner
    runner = SubagentRunner(database_url=engine.url.render_as_string(hide_password=False)) if use_subagents and os.environ.get('GEMINI_API_KEY') else None
    embedder = None
    if use_subagents and os.environ.get('GEMINI_API_KEY') and os.environ.get('KNOWLEDGE_SEMANTIC_ENABLED','true').lower()=='true':
        from intelligence_embeddings import GeminiEmbedder
        embedder=GeminiEmbedder(os.environ['GEMINI_API_KEY'],os.environ.get('KNOWLEDGE_EMBEDDING_MODEL','gemini-embedding-2'))
    return IntelligenceService(IntelligenceStore(engine), subagent_runner=runner,embedder=embedder)


class BriefIn(BaseModel):
    description: str = Field(min_length=1, max_length=4000)
    audience: str = Field(min_length=1, max_length=4000)
    expertise: str = Field(min_length=1, max_length=4000)
    point_of_view: str = Field(min_length=1, max_length=4000)
    voice: str = Field(min_length=1, max_length=4000)
    avoid_claims: str = Field(default='', max_length=4000)


class ContentIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=1, max_length=20000)
    channel: str = Field(min_length=1, max_length=40)
    url: str | None = Field(default=None, max_length=2048)


class SearchIn(BaseModel):
    query: str = Field(min_length=1,max_length=1200)


class AnalyzeIn(BaseModel):
    days: int = Field(default=30, ge=1, le=90)
    limit: int = Field(default=500, ge=1, le=1000)


class DraftIn(BaseModel):
    channel: Literal['linkedin', 'x']
    format: Literal['post', 'reply']


class EditDraftIn(BaseModel):
    text: str = Field(min_length=1, max_length=3000)


Id = Annotated[int, Path(ge=1)]


def call(action, *args, **kwargs):
    try:
        return action(*args, **kwargs)
    except ValueError as error:
        raise HTTPException(400, str(error)) from None
    except LookupError:
        raise HTTPException(404, 'Intelligence record not found') from None
    except RuntimeError:
        raise HTTPException(503, 'Intelligence operation unavailable') from None


def make_router(engine):
    router = APIRouter(prefix='/intelligence')
    agent = make_service(engine)

    @router.get('/knowledge/status')
    def knowledge_status():
        enabled=provider_available() and os.environ.get('KNOWLEDGE_SEMANTIC_ENABLED','true').lower()=='true'
        config=os.environ.get('KNOWLEDGE_EMBEDDING_MODEL','gemini-embedding-2')+':768:retrieval-prefix-v1:paragraph-1600-160-v1' if enabled else 'lexical-v1:paragraph-1600-160-v1'
        return dict(call(agent.knowledge.store.status,config),embedding_available=enabled)

    @router.get('/content/{content_id}/index')
    def content_index(content_id: Id):
        documents=knowledge_status()['documents']
        item=next((d for d in documents if d['content_id']==content_id),None)
        if item is None:
            raise HTTPException(404,'Content indexing record not found')
        return item

    @router.post('/knowledge/reindex',status_code=202)
    def reindex():
        return enqueue('index',{})

    @router.post('/knowledge/search',status_code=202)
    def search_knowledge(payload: SearchIn):
        return enqueue('search',payload.model_dump())

    @router.get('/knowledge/search/{job_id}')
    def search_result(job_id: Id):
        job=call(get_job,engine,job_id)
        if job['action']!='search' or job['status']!='complete':
            raise HTTPException(409,'Knowledge search is not complete')
        return call(agent.knowledge.get_retrieval,job['result']['retrieval_id'])

    @router.post('/opportunities/{opportunity_id}/refine-angle',status_code=202)
    def refine_angle(opportunity_id: Id):
        call(agent.opportunity,opportunity_id)
        require_provider()
        if not agent.get_brief():
            raise HTTPException(400,'Save a company brief before refining an angle.')
        return enqueue('refine_angle',{},opportunity_id)

    @router.get('/brief')
    def brief():
        return call(agent.get_brief)

    @router.put('/brief')
    def set_brief(payload: BriefIn):
        return call(agent.set_brief, payload.model_dump())

    @router.delete('/brief')
    def clear_brief():
        return call(agent.clear_brief)

    @router.get('/content')
    def content():
        return call(agent.list_content)

    @router.post('/content')
    def add_content(payload: ContentIn):
        return call(agent.add_content, payload.model_dump())

    @router.put('/content/{content_id}')
    def replace_content(content_id: Id, payload: ContentIn):
        return call(agent.replace_content, content_id, payload.model_dump())

    @router.delete('/content/{content_id}')
    def delete_content(content_id: Id):
        return call(agent.delete_content, content_id)

    @router.get('/opportunities')
    def opportunities():
        data = call(agent.opportunities)
        with engine.connect() as conn:
            data['analyzed_at'] = conn.execute(text('SELECT created_at FROM intelligence_run WHERE id=:id'),
                                               {'id':data['run_id']}).scalar_one_or_none()
        return data

    @router.get('/opportunities/{opportunity_id}')
    def opportunity(opportunity_id: Id):
        data = call(agent.opportunity_detail, opportunity_id)
        with engine.connect() as conn:
            data['analyzed_at'] = conn.execute(text('SELECT r.created_at FROM intelligence_run r '
                'JOIN conversation c ON c.run_id=r.id JOIN opportunity o ON o.conversation_id=c.id '
                'WHERE o.id=:id'), {'id':opportunity_id}).scalar_one()
            for draft in data['drafts']:
                metadata = conn.execute(text('SELECT revises_id,model_version,retrieval_id,factual_retrieval_id FROM content_draft WHERE id=:id'),
                                        {'id':draft['id']}).mappings().one()
                draft.update(metadata)
                draft['evidence'] = [dict(row) for row in conn.execute(text(
                    'SELECT id,source_url,claim,stance,retrieved_at FROM research_evidence '
                    'WHERE research_run_id=:research AND id=ANY(:ids) ORDER BY id'),
                    {'research':draft['research_run_id'],'ids':draft['evidence_ids']}).mappings()]
        return data

    def enqueue(action, payload, opportunity_id=None):
        try:
            return queue_job(engine, action, payload, opportunity_id)
        except JobConflict as error:
            raise HTTPException(409, str(error)) from None

    @router.post('/analyze', status_code=202)
    def analyze(payload: AnalyzeIn):
        return enqueue('analyze', payload.model_dump())

    @router.get('/jobs')
    def jobs():
        return list_jobs(engine)

    @router.get('/jobs/{job_id}')
    def job(job_id: Id):
        return call(get_job, engine, job_id)

    def provider_available():
        return os.environ.get('INTELLIGENCE_PROVIDER_AVAILABLE', '').lower() == 'true'

    @router.get('/status')
    def status():
        with engine.connect() as conn:
            count=conn.execute(text('SELECT count(*) FROM signal s LEFT JOIN signal_state st ON st.signal_id=s.id '
                                   'WHERE COALESCE(st.dismissed,false)=false')).scalar_one()
        return {'signal_count':count, 'provider_available':provider_available(), 'has_brief':agent.get_brief() is not None,
                'content_count':len(agent.list_content())}

    def require_provider():
        if not provider_available():
            raise HTTPException(503, 'Gemini provider is unavailable. Configure GEMINI_API_KEY and restart the services.')

    @router.post('/opportunities/{opportunity_id}/research', status_code=202)
    def research(opportunity_id: Id):
        call(agent.opportunity, opportunity_id)
        require_provider()
        return enqueue('research', {}, opportunity_id)

    @router.post('/opportunities/{opportunity_id}/draft', status_code=202)
    def draft(opportunity_id: Id, payload: DraftIn):
        call(agent.opportunity, opportunity_id)
        research = agent.store.latest_research(opportunity_id)
        if not research or research['status'] != 'complete' or not research['evidence']:
            raise HTTPException(400, 'Complete research with evidence is required before drafting.')
        if not agent.get_brief():
            raise HTTPException(400, 'Save a complete company brief before drafting.')
        require_provider()
        return enqueue('draft', payload.model_dump(), opportunity_id)

    @router.put('/drafts/{draft_id}')
    def edit_draft(draft_id: Id, payload: EditDraftIn):
        with engine.begin() as conn:
            original = conn.execute(text('SELECT * FROM content_draft WHERE id=:id'),
                                    {'id':draft_id}).mappings().first()
            if not original:
                raise HTTPException(404, 'Draft not found')
            value = payload.text.strip()
            limit = 280 if original['channel'] == 'x' else 3000
            if not value or len(value) > limit:
                raise HTTPException(400, f'Draft must contain 1–{limit} characters.')
            row = conn.execute(text('INSERT INTO content_draft (opportunity_id,research_run_id,channel,format,'
                'draft_text,evidence_ids,model_version,prompt_version,revises_id,retrieval_id,factual_retrieval_id) '
                "VALUES (:opportunity,:research,:channel,:format,:value,CAST(:evidence AS jsonb),"
                "'operator-edit','editorial-v1',:original,:retrieval,:factual) RETURNING id,revises_id"),
                {'opportunity':original['opportunity_id'],'research':original['research_run_id'],
                 'channel':original['channel'],'format':original['format'],'value':value,
                 'evidence':json.dumps(original['evidence_ids']),'original':draft_id,'retrieval':original['retrieval_id'],'factual':original['factual_retrieval_id']}).mappings().one()
        return dict(row)

    from .agent_workspace import make_router as make_workspace_router
    router.include_router(make_workspace_router(engine, agent))
    return router
