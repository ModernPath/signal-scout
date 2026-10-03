"""Separate factual retrieval from company editorial context on drafts."""
from alembic import op
revision='0009_draft_knowledge'
down_revision='0008_company_knowledge'
branch_labels=depends_on=None

def upgrade():
    op.execute('ALTER TABLE content_draft ADD COLUMN factual_retrieval_id bigint REFERENCES retrieval_run(id)')

def downgrade():
    op.execute('ALTER TABLE content_draft DROP COLUMN factual_retrieval_id')
