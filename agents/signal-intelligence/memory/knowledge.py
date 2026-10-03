"""Application-owned Postgres passage index and redaction-aware retrieval records."""
from __future__ import annotations
import json
import re
from sqlalchemy import text


class KnowledgeStore:
    def __init__(self, engine, chunker='paragraph-1600-160-v1'):
        self.engine = engine
        self.chunker = chunker

    def status(self, config='lexical-v1'):
        with self.engine.connect() as conn:
            rows = conn.execute(text('''SELECT d.id,d.content_id,d.evidence_id,r.research_run_id,d.status,d.error_message,d.indexed_at,
              EXISTS(SELECT 1 FROM knowledge_chunk c WHERE c.document_id=d.id AND c.chunker_version=:chunker) AS chunks_ready,
              EXISTS(SELECT 1 FROM knowledge_chunk c JOIN knowledge_embedding e ON e.chunk_id=c.id
                WHERE c.document_id=d.id AND e.config=:config) AS semantic_ready
              FROM knowledge_document d LEFT JOIN research_evidence r ON r.id=d.evidence_id WHERE eligible AND (d.evidence_id IS NULL OR r.excerpt_expires_at>now()) ORDER BY d.id'''),dict(config=config,chunker=self.chunker)).mappings().all()
            revision=conn.execute(text('SELECT revision FROM knowledge_state WHERE id=1')).scalar_one()
        docs=[dict(r) for r in rows]
        return dict(documents=docs, eligible=len(docs), ready=sum(d['chunks_ready'] for d in docs),
                    semantic_ready=sum(d['semantic_ready'] for d in docs),
                    pending=sum(d['status']=='pending' or (not config.startswith('lexical-v1') and d['status']=='ready' and not d['semantic_ready']) for d in docs),failed=sum(d['status']=='failed' for d in docs),
                    revision=revision,config=config)

    def pending(self, config, semantic, limit):
        with self.engine.connect() as conn:
            return [dict(r) for r in conn.execute(text('''SELECT d.*,coalesce(c.content_text,e.claim) AS body
              FROM knowledge_document d LEFT JOIN company_content c ON c.id=d.content_id
              LEFT JOIN research_evidence e ON e.id=d.evidence_id
              WHERE d.eligible AND (d.evidence_id IS NULL OR e.excerpt_expires_at>now()) AND d.status<>'failed' AND (d.status='pending' OR NOT EXISTS (SELECT 1 FROM knowledge_chunk k WHERE k.document_id=d.id AND k.chunker_version=:chunker) OR (:semantic AND NOT EXISTS
              (SELECT 1 FROM knowledge_chunk k JOIN knowledge_embedding v ON v.chunk_id=k.id
               WHERE k.document_id=d.id AND v.config=:config))) ORDER BY d.id LIMIT :limit'''),
              dict(config=config,semantic=semantic,limit=limit,chunker=self.chunker)).mappings()]

    def commit_index(self, document, chunks, vectors, config):
        with self.engine.begin() as conn:
            row=conn.execute(text('SELECT eligible,source_hash FROM knowledge_document WHERE id=:id FOR UPDATE'),document).mappings().first()
            if not row or not row['eligible'] or row['source_hash']!=document['source_hash']:
                return False
            for ordinal,chunk in enumerate(chunks):
                chunk_id=conn.execute(text('''INSERT INTO knowledge_chunk
                 (document_id,source_hash,chunker_version,ordinal,passage,heading,start_offset,end_offset)
                 VALUES (:document,:hash,:chunker,:ordinal,:passage,:heading,:start,:end)
                 ON CONFLICT(document_id,source_hash,chunker_version,ordinal) DO UPDATE SET passage=EXCLUDED.passage RETURNING id'''),
                 dict(document=document['id'],hash=document['source_hash'],chunker=self.chunker,ordinal=ordinal,passage=chunk['text'],
                      heading=chunk['heading'],start=chunk['start'],end=chunk['end'])).scalar_one()
                if vectors is not None:
                    conn.execute(text('''INSERT INTO knowledge_embedding(chunk_id,config,embedding)
                      VALUES (:id,:config,CAST(:vector AS vector)) ON CONFLICT(chunk_id,config)
                      DO UPDATE SET embedding=EXCLUDED.embedding'''),
                      dict(id=chunk_id,config=config,vector=json.dumps(vectors[ordinal])))
            conn.execute(text("UPDATE knowledge_document SET status='ready',error_message=NULL,indexed_at=now() WHERE id=:id"),document)
            conn.execute(text('UPDATE knowledge_state SET revision=revision+1 WHERE id=1'))
        return True

    def fail(self, doc):
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE knowledge_document SET status='failed',error_message='Indexing failed. Check embedding access and retry.' "
                              "WHERE id=:id AND eligible AND source_hash=:source_hash"),doc)

    def retry(self):
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE knowledge_document SET status='pending',error_message=NULL WHERE eligible AND status='failed'"))

    def candidates(self, query, config, vector=None, research_id=None):
        # Both channels apply the same eligibility/version/corpus filters before LIMIT.
        base='''FROM knowledge_chunk c JOIN knowledge_document d ON d.id=c.document_id
          LEFT JOIN research_evidence r ON r.id=d.evidence_id
          WHERE d.eligible AND c.source_hash=d.source_hash AND c.chunker_version=:chunker
          AND ((CAST(:research AS integer) IS NULL AND d.content_id IS NOT NULL) OR
               (CAST(:research AS integer) IS NOT NULL AND r.research_run_id=:research AND r.claim NOT IN ('[expired]','') AND r.excerpt_expires_at>now()) )'''
        fields='''c.id AS chunk_id,d.id AS document_id,c.passage,c.heading,d.title,d.source_url,d.source_hash,
          coalesce(d.content_id,d.evidence_id) AS source_id,
          CASE WHEN d.content_id IS NOT NULL THEN 'company' ELSE 'factual' END AS role,r.stance'''
        params=dict(query=' OR '.join(re.findall(r'[\w-]{3,}', query)[:40]),config=config,research=research_id,chunker=self.chunker)
        with self.engine.connect() as conn:
            lexical=[dict(r) for r in conn.execute(text('SELECT '+fields+", ts_rank(c.search_text,websearch_to_tsquery('simple',:query)) AS score "+base+
              " AND c.search_text @@ websearch_to_tsquery('simple',:query) ORDER BY score DESC,c.id LIMIT 20"),params).mappings()]
            semantic=[]
            if vector is not None:
                params['vector']=json.dumps(vector)
                semantic=[dict(r) for r in conn.execute(text('SELECT '+fields+', 1-(v.embedding <=> CAST(:vector AS vector)) AS score '+
                  base.replace('WHERE d.eligible','JOIN knowledge_embedding v ON v.chunk_id=c.id AND v.config=:config WHERE d.eligible')+
                  ' AND 1-(v.embedding <=> CAST(:vector AS vector))>=0.55 ORDER BY score DESC,c.id LIMIT 20'),params).mappings()]
        return lexical,semantic

    def save_retrieval(self, query, hits, *, purpose, mode, coverage, revision, config, opportunity_id=None,research_id=None):
        with self.engine.begin() as conn:
            id=conn.execute(text('''INSERT INTO retrieval_run(opportunity_id,research_id,purpose,query,mode,coverage,corpus_revision,config)
              VALUES (:opportunity,:research,:purpose,:query,:mode,:coverage,:revision,:config) RETURNING id'''),
              dict(opportunity=opportunity_id,research=research_id,purpose=purpose,query=query,mode=mode,coverage=coverage,revision=revision,config=config)).scalar_one()
            for i,hit in enumerate(hits):
                # Source deletion racing retrieval must not reintroduce private text.
                valid=conn.execute(text('SELECT eligible,source_hash FROM knowledge_document WHERE id=:id FOR SHARE'),
                                   dict(id=hit['document_id'])).mappings().first()
                if not valid or not valid['eligible'] or valid['source_hash']!=hit['source_hash']:
                    continue
                conn.execute(text('''INSERT INTO retrieval_hit(run_id,ordinal,document_id,chunk_id,source_hash,role,
                  source_id,title,source_url,passage,score) VALUES (:run,:ordinal,:document_id,:chunk_id,:source_hash,
                  :role,:source_id,:title,:source_url,:passage,:score)'''),dict(hit,run=id,ordinal=i))
        return self.get_retrieval(id)

    def get_retrieval(self, id):
        with self.engine.connect() as conn:
            run=conn.execute(text('SELECT * FROM retrieval_run WHERE id=:id'),dict(id=id)).mappings().first()
            if not run:
                raise LookupError('Retrieval not found')
            hits=[dict(r) for r in conn.execute(text('SELECT * FROM retrieval_hit WHERE run_id=:id ORDER BY ordinal'),dict(id=id)).mappings()]
        return dict(run,hits=hits)

    def latest(self, opportunity_id,purpose='comparison'):
        with self.engine.connect() as conn:
            id=conn.execute(text('SELECT id FROM retrieval_run WHERE opportunity_id=:id AND purpose=:purpose ORDER BY id DESC LIMIT 1'),
                            dict(id=opportunity_id,purpose=purpose)).scalar_one_or_none()
        return self.get_retrieval(id) if id else None

    def validate_snapshot(self, conn, retrieval):
        rows=conn.execute(text('''SELECT d.eligible,d.source_hash,h.source_hash AS snapshot_hash,h.removed
          FROM retrieval_hit h JOIN knowledge_document d ON d.id=h.document_id
          WHERE h.run_id=:id ORDER BY d.id FOR SHARE OF d'''),dict(id=retrieval)).mappings().all()
        if any(r['removed'] or not r['eligible'] or r['source_hash']!=r['snapshot_hash'] for r in rows):
            raise RuntimeError('Knowledge source changed during generation; retry')

    def save_enrichment(self, opportunity, retrieval, brief, result, model):
        with self.engine.begin() as conn:
            self.validate_snapshot(conn,retrieval)
            active=conn.execute(text('SELECT id FROM company_brief WHERE active ORDER BY version DESC LIMIT 1')).scalar_one_or_none()
            if active!=brief:
                raise RuntimeError('Company brief changed during generation; retry')
            id=conn.execute(text('''INSERT INTO opportunity_enrichment(opportunity_id,retrieval_id,brief_id,result,model_version,prompt_version)
              VALUES (:opportunity,:retrieval,:brief,CAST(:result AS jsonb),:model,'angle-v1') RETURNING id'''),
              dict(opportunity=opportunity,retrieval=retrieval,brief=brief,result=json.dumps(result),model=model)).scalar_one()
        return dict(id=id,**result)

    def enrichment(self, opportunity):
        with self.engine.connect() as conn:
            row=conn.execute(text('SELECT * FROM opportunity_enrichment WHERE opportunity_id=:id ORDER BY id DESC LIMIT 1'),dict(id=opportunity)).mappings().first()
        if not row:
            return None
        retrieval=self.get_retrieval(row['retrieval_id'])
        current=self.status()['revision']
        with self.engine.connect() as conn:
            brief=conn.execute(text('SELECT id FROM company_brief WHERE active ORDER BY id DESC LIMIT 1')).scalar_one_or_none()
        # Delete cannot leave generated private excerpts accessible through a summary.
        removed=any(h['removed'] for h in retrieval['hits'])
        return dict(row,result={} if removed else row['result'],source_removed=removed,
                    stale=current!=retrieval['corpus_revision'] or brief!=row['brief_id'],retrieval=retrieval)
