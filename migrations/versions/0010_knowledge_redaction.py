"""Redact generated explanations and queries when their source is removed."""
from alembic import op
revision='0010_knowledge_redaction'
down_revision='0009_draft_knowledge'
branch_labels=depends_on=None

def upgrade():
    op.execute('''CREATE FUNCTION redact_knowledge_outputs() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE document bigint;
      BEGIN
        IF TG_TABLE_NAME='company_content' THEN
          IF NEW.content_text<>'' THEN RETURN NEW; END IF;
          SELECT id INTO document FROM knowledge_document WHERE content_id=NEW.id;
        ELSE
          IF NEW.claim NOT IN ('[expired]','') THEN RETURN NEW; END IF;
          SELECT id INTO document FROM knowledge_document WHERE evidence_id=NEW.id;
        END IF;
        UPDATE opportunity_enrichment SET result='{}'::jsonb WHERE retrieval_id IN
          (SELECT run_id FROM retrieval_hit WHERE document_id=document);
        UPDATE retrieval_run SET query='[source removed or expired]' WHERE id IN
          (SELECT run_id FROM retrieval_hit WHERE document_id=document);
        RETURN NEW;
      END $$;
      CREATE TRIGGER company_knowledge_redaction AFTER UPDATE ON company_content
        FOR EACH ROW EXECUTE FUNCTION redact_knowledge_outputs();
      CREATE TRIGGER evidence_knowledge_redaction AFTER UPDATE OF claim ON research_evidence
        FOR EACH ROW EXECUTE FUNCTION redact_knowledge_outputs();''')

def downgrade():
    op.execute('DROP TRIGGER company_knowledge_redaction ON company_content; '
               'DROP TRIGGER evidence_knowledge_redaction ON research_evidence; '
               'DROP FUNCTION redact_knowledge_outputs();')
