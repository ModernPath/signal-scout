"""Postgres knowledge index, source lifecycle and retrieval provenance."""
from alembic import op
revision = '0008_company_knowledge'
down_revision = '0007_intelligence_jobs'
branch_labels = depends_on = None


def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    op.execute('''
    CREATE TABLE knowledge_state (id integer PRIMARY KEY CHECK(id=1), revision bigint NOT NULL DEFAULT 0);
    INSERT INTO knowledge_state(id) VALUES (1);
    CREATE TABLE knowledge_document (
      id bigserial PRIMARY KEY,
      content_id integer UNIQUE REFERENCES company_content(id) ON DELETE CASCADE,
      evidence_id integer UNIQUE REFERENCES research_evidence(id) ON DELETE CASCADE,
      source_hash text NOT NULL, title text NOT NULL, source_url text,
      eligible boolean NOT NULL DEFAULT true, status text NOT NULL DEFAULT 'pending',
      error_message text, indexed_at timestamptz,
      CHECK ((content_id IS NOT NULL)::int + (evidence_id IS NOT NULL)::int = 1),
      CHECK(status IN ('pending','ready','failed','retired')));
    CREATE TABLE knowledge_chunk (
      id bigserial PRIMARY KEY, document_id bigint NOT NULL REFERENCES knowledge_document(id) ON DELETE CASCADE,
      source_hash text NOT NULL, ordinal integer NOT NULL, passage text NOT NULL, heading text NOT NULL,
      start_offset integer NOT NULL, end_offset integer NOT NULL,
      search_text tsvector GENERATED ALWAYS AS (to_tsvector('simple', passage)) STORED,
      UNIQUE(document_id,source_hash,ordinal));
    CREATE INDEX knowledge_chunk_search ON knowledge_chunk USING gin(search_text);
    CREATE TABLE knowledge_embedding (
      chunk_id bigint REFERENCES knowledge_chunk(id) ON DELETE CASCADE,
      config text NOT NULL, embedding vector(768) NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(chunk_id,config));
    CREATE TABLE retrieval_run (
      id bigserial PRIMARY KEY, opportunity_id integer REFERENCES opportunity(id) ON DELETE CASCADE,
      research_id integer REFERENCES research_run(id) ON DELETE CASCADE,
      purpose text NOT NULL, query text NOT NULL, mode text NOT NULL, coverage double precision NOT NULL,
      corpus_revision bigint NOT NULL, config text NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
    CREATE TABLE retrieval_hit (
      run_id bigint REFERENCES retrieval_run(id) ON DELETE CASCADE, ordinal integer NOT NULL,
      document_id bigint REFERENCES knowledge_document(id) ON DELETE SET NULL,
      chunk_id bigint REFERENCES knowledge_chunk(id) ON DELETE SET NULL,
      source_hash text NOT NULL, role text NOT NULL, source_id integer NOT NULL,
      title text NOT NULL, source_url text, passage text NOT NULL,
      score double precision NOT NULL, removed boolean NOT NULL DEFAULT false,
      PRIMARY KEY(run_id,ordinal));
    CREATE TABLE opportunity_enrichment (
      id bigserial PRIMARY KEY, opportunity_id integer NOT NULL REFERENCES opportunity(id) ON DELETE CASCADE,
      retrieval_id bigint NOT NULL REFERENCES retrieval_run(id), brief_id integer REFERENCES company_brief(id),
      result jsonb NOT NULL, model_version text NOT NULL, prompt_version text NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now());
    ALTER TABLE content_draft ADD COLUMN retrieval_id bigint REFERENCES retrieval_run(id);
    ALTER TABLE intelligence_job ALTER COLUMN action TYPE varchar(20);
    ALTER TABLE intelligence_job DROP CONSTRAINT intelligence_job_action;
    ALTER TABLE intelligence_job ADD CONSTRAINT intelligence_job_action
      CHECK(action IN ('analyze','research','draft','index','search','refine_angle'));
    ''')
    op.execute('''
    CREATE FUNCTION sync_company_knowledge() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE document bigint;
    BEGIN
      INSERT INTO knowledge_document(content_id,source_hash,title,source_url,eligible,status)
        VALUES(NEW.id,NEW.content_hash,NEW.title,NEW.url,NEW.active,CASE WHEN NEW.active THEN 'pending' ELSE 'retired' END)
        ON CONFLICT(content_id) DO UPDATE SET
          eligible=NEW.active, status=CASE WHEN NOT NEW.active THEN 'retired'
             WHEN knowledge_document.source_hash<>NEW.content_hash THEN 'pending' ELSE knowledge_document.status END,
          source_hash=NEW.content_hash,title=NEW.title,source_url=NEW.url RETURNING id INTO document;
      IF NEW.content_text='' THEN
        UPDATE retrieval_hit SET passage='[source removed]',title='[source removed]',source_url=NULL,removed=true
          WHERE document_id=document;
        DELETE FROM knowledge_chunk WHERE document_id=document;
      END IF;
      UPDATE knowledge_state SET revision=revision+1 WHERE id=1;
      RETURN NEW;
    END $$;
    CREATE TRIGGER company_knowledge AFTER INSERT OR UPDATE ON company_content
      FOR EACH ROW EXECUTE FUNCTION sync_company_knowledge();
    CREATE FUNCTION sync_evidence_knowledge() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE document bigint;
    BEGIN
      INSERT INTO knowledge_document(evidence_id,source_hash,title,source_url,eligible,status)
        VALUES(NEW.id,md5(NEW.claim), 'Research evidence #'||NEW.id,NEW.source_url,
          NEW.claim NOT IN ('[expired]',''),CASE WHEN NEW.claim IN ('[expired]','') THEN 'retired' ELSE 'pending' END)
        ON CONFLICT(evidence_id) DO UPDATE SET eligible=NEW.claim NOT IN ('[expired]',''),
          source_hash=md5(NEW.claim),status=CASE WHEN NEW.claim IN ('[expired]','') THEN 'retired'
          WHEN knowledge_document.source_hash<>md5(NEW.claim) THEN 'pending' ELSE knowledge_document.status END
        RETURNING id INTO document;
      IF NEW.claim IN ('[expired]','') THEN
        UPDATE retrieval_hit SET passage='[source expired]',title='[source expired]',source_url=NULL,removed=true
          WHERE document_id=document;
        DELETE FROM knowledge_chunk WHERE document_id=document;
      END IF;
      UPDATE knowledge_state SET revision=revision+1 WHERE id=1;
      RETURN NEW;
    END $$;
    CREATE TRIGGER evidence_knowledge AFTER INSERT OR UPDATE OF claim ON research_evidence
      FOR EACH ROW EXECUTE FUNCTION sync_evidence_knowledge();
    INSERT INTO knowledge_document(content_id,source_hash,title,source_url,eligible,status)
      SELECT id,content_hash,title,url,active,CASE WHEN active THEN 'pending' ELSE 'retired' END FROM company_content;
    INSERT INTO knowledge_document(evidence_id,source_hash,title,source_url,eligible,status)
      SELECT id,md5(claim),'Research evidence #'||id,source_url,claim NOT IN ('[expired]',''),
      CASE WHEN claim IN ('[expired]','') THEN 'retired' ELSE 'pending' END FROM research_evidence;
    ''')


def downgrade():
    op.execute('DROP TRIGGER evidence_knowledge ON research_evidence; DROP FUNCTION sync_evidence_knowledge(); '
               'DROP TRIGGER company_knowledge ON company_content; DROP FUNCTION sync_company_knowledge();')
    op.execute('ALTER TABLE content_draft DROP COLUMN retrieval_id; '
               'ALTER TABLE intelligence_job DROP CONSTRAINT intelligence_job_action; '
               "DELETE FROM intelligence_job WHERE action IN ('index','search','refine_angle'); "
               "ALTER TABLE intelligence_job ADD CONSTRAINT intelligence_job_action CHECK(action IN ('analyze','research','draft')); "
               'DROP TABLE opportunity_enrichment,retrieval_hit,retrieval_run,knowledge_embedding,knowledge_chunk,knowledge_document,knowledge_state;')
