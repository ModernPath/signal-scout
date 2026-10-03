"""Keep independently rebuildable chunk versions and embedding configurations."""
from alembic import op
revision='0011_chunker_versions'
down_revision='0010_knowledge_redaction'
branch_labels=depends_on=None

def upgrade():
    op.execute('''ALTER TABLE knowledge_chunk ADD COLUMN chunker_version text NOT NULL DEFAULT 'paragraph-1600-160-v1';
      ALTER TABLE knowledge_chunk DROP CONSTRAINT knowledge_chunk_document_id_source_hash_ordinal_key;
      ALTER TABLE knowledge_chunk ADD CONSTRAINT knowledge_chunk_version_unique UNIQUE(document_id,source_hash,chunker_version,ordinal);
      UPDATE knowledge_embedding SET config=config||chr(58)||'paragraph-1600-160-v1';''')

def downgrade():
    # Reverting config/chunk versions could destroy historical provenance; disable retrieval instead.
    raise RuntimeError('Disable semantic retrieval for rollback; chunk version history is retained')
