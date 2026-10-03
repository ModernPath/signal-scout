"""Persistent single-operator queue; provider work never runs in a web request."""
import json
from sqlalchemy import text


class JobConflict(ValueError):
    pass


def queue_job(engine, action, payload, opportunity_id=None):
    with engine.begin() as conn:
        conn.execute(text('SELECT pg_advisory_xact_lock(20261001)'))
        active=conn.execute(text("SELECT * FROM intelligence_job WHERE status IN ('queued','running') "
                                 "ORDER BY id LIMIT 1")).mappings().first()
        if active:
            if active['action']==action and active['opportunity_id']==opportunity_id and active['payload']==payload:
                return dict(active)
            raise JobConflict('Another intelligence job is active. Wait for it to finish.')
        row=conn.execute(text('INSERT INTO intelligence_job (action,payload,opportunity_id) '
                              'VALUES (:action,CAST(:payload AS jsonb),:opportunity) RETURNING *'),
                         dict(action=action,payload=json.dumps(payload),opportunity=opportunity_id)).mappings().one()
        return dict(row)


def list_jobs(engine):
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(text('SELECT * FROM intelligence_job ORDER BY id DESC LIMIT 20')).mappings()]


def get_job(engine, id):
    with engine.connect() as conn:
        row=conn.execute(text('SELECT * FROM intelligence_job WHERE id=:id'),{'id':id}).mappings().first()
    if not row:
        raise LookupError('Job not found')
    return dict(row)


def process_one(engine, agent):
    with engine.begin() as conn:
        row=conn.execute(text("SELECT * FROM intelligence_job WHERE status='queued' ORDER BY id "
                              "FOR UPDATE SKIP LOCKED LIMIT 1")).mappings().first()
        if not row:
            return None
        job=dict(row)
        conn.execute(text("UPDATE intelligence_job SET status='running',started_at=now() WHERE id=:id"),job)
    result=None
    error=None
    status='complete'
    try:
        if job['action']=='chat':
            from .agent_workspace import run_turn
            result=run_turn(engine,agent,job)
            status=result.pop('status')
        elif job['action']=='analyze':
            # Bounded deterministic analysis; model research remains a selected action.
            from .intelligence import make_service
            data=make_service(engine).analyze(**job['payload'])
            result={'run_id':data['run_id'],'opportunity_count':len(data['opportunities'])}
        elif job['action']=='research':
            data=agent.research(job['opportunity_id'])
            status=data['status']
            result={'research_id':data['id'],'opportunity_id':job['opportunity_id']}
        elif job['action']=='index':
            agent.knowledge.store.retry()
            data=agent.knowledge.index_pending(limit=2)
            status='partial' if data['batch_failed'] else 'complete'
            result={'indexed':data['indexed']}
        elif job['action']=='search':
            data=agent.search_knowledge(**job['payload'])
            result={'retrieval_id':data['id']}
        elif job['action']=='refine_angle':
            data=agent.refine_angle(job['opportunity_id'])
            result={'enrichment_id':data['id'],'opportunity_id':job['opportunity_id']}
        elif job['action']=='draft':
            data=agent.draft(job['opportunity_id'],**job['payload'])
            result={'draft_id':data['id'],'opportunity_id':job['opportunity_id']}
        else:
            raise ValueError('Unsupported intelligence action')
    except Exception as exception:
        status='failed'
        error={'analyze':'Analysis failed. Retry after checking the database and company context.',
               'research':'Research failed or returned unusable evidence. Check the provider and retry.',
               'draft':'Draft generation failed validation or the provider was unavailable. Review research and retry.',
               'index':'Indexing failed. Check embedding access and retry.',
               'search':'Knowledge search failed. Retry after indexing content.',
               'refine_angle':'Angle refinement failed. Check company context, indexing and provider access.',
               'chat':'Chat was interrupted. Review completed activity before submitting another message.'}.get(job['action'],'Unknown intelligence action')
        safe_validation_errors={
            'Draft contains unsupported numeric claims':'Draft included a numeric claim without cited evidence. Regenerate the draft or review the research.',
            'Draft exceeds channel length limit':'Draft exceeded the channel length limit. Regenerate a shorter draft.',
            'Draft contains a prohibited claim':'Draft contained a claim prohibited by your company brief. Review the brief and regenerate.',
            'Draft provider cited unsupported evidence':'Draft cited evidence outside this research snapshot. Regenerate the draft.'}
        if job['action']=='draft' and isinstance(exception,RuntimeError):
            error=safe_validation_errors.get(str(exception),error)
    with engine.begin() as conn:
        if status=='failed':
            conn.execute(text("INSERT INTO intelligence_job_event(job_id,tool,executor,status,summary,inputs,artifacts) SELECT :id,tool,executor,'failed','Work interrupted; review any saved results before retrying.',inputs,'[]' FROM intelligence_job_event e WHERE job_id=:id AND status='running' AND NOT EXISTS (SELECT 1 FROM intelligence_job_event done WHERE done.job_id=e.job_id AND done.tool=e.tool AND done.id>e.id)"),{'id':job['id']})
        conn.execute(text('UPDATE intelligence_job SET status=:status,result=CAST(:result AS jsonb),'
                          'error_message=:error,finished_at=now() WHERE id=:id'),
                     dict(id=job['id'],status=status,result=json.dumps(result),error=error))
    return job['id']


def recover_running(engine, *, force=False):
    """Mark abandoned work failed; never automatically repeat provider requests."""
    with engine.begin() as conn:
        rows=conn.execute(text("UPDATE intelligence_job SET status='failed',finished_at=now(),"
            "error_message='Intelligence work was interrupted. Retry the action.' "
            "WHERE status='running' AND (:force OR started_at<now()-interval '5 minutes') RETURNING id"),
            {'force':force}).all()
        for row in rows:
            conn.execute(text("INSERT INTO intelligence_job_event(job_id,tool,executor,status,summary,inputs,artifacts) SELECT :id,tool,executor,'failed','Worker interrupted; action was not replayed.',inputs,'[]' FROM intelligence_job_event e WHERE job_id=:id AND status='running' AND NOT EXISTS (SELECT 1 FROM intelligence_job_event done WHERE done.job_id=e.job_id AND done.tool=e.tool AND done.id>e.id)"),{'id':row[0]})
    return len(rows)
