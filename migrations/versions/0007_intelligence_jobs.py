"""Queued application intelligence work and editorial draft revisions."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision='0007_intelligence_jobs'
down_revision='0006_agent_memory'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('intelligence_job',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('action',sa.String(12),nullable=False),
        sa.Column('opportunity_id',sa.Integer(),sa.ForeignKey('opportunity.id',ondelete='CASCADE')),
        sa.Column('payload',JSONB(),nullable=False),
        sa.Column('status',sa.String(12),nullable=False,server_default='queued'),
        sa.Column('queued_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column('started_at',sa.DateTime(timezone=True)),
        sa.Column('finished_at',sa.DateTime(timezone=True)),
        sa.Column('result',JSONB()),sa.Column('error_message',sa.Text()),
        sa.CheckConstraint("action IN ('analyze','research','draft')",name='intelligence_job_action'),
        sa.CheckConstraint("status IN ('queued','running','complete','partial','failed')",name='intelligence_job_status'))
    op.create_index('ix_intelligence_job_active','intelligence_job',[sa.text('(1)')],unique=True,
                    postgresql_where=sa.text("status IN ('queued','running')"))
    op.add_column('content_draft',sa.Column('revises_id',sa.Integer(),
                      sa.ForeignKey('content_draft.id',ondelete='SET NULL')))


def downgrade():
    op.drop_column('content_draft','revises_id')
    op.drop_table('intelligence_job')
