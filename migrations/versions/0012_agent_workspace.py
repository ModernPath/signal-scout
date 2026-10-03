"""Queued chat and observable tool activity in the existing agent memory."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
revision='0012_agent_workspace'
down_revision='0011_chunker_versions'
branch_labels=depends_on=None

def upgrade():
    op.drop_constraint('intelligence_job_action','intelligence_job',type_='check')
    op.create_check_constraint('intelligence_job_action','intelligence_job',"action IN ('analyze','research','draft','index','search','refine_angle','chat')")
    op.add_column('intelligence_job',sa.Column('chat_session_id',sa.Integer(),sa.ForeignKey('agent_chat_session.id',ondelete='CASCADE')))
    op.add_column('intelligence_job',sa.Column('chat_turn_id',sa.Integer(),sa.ForeignKey('agent_chat_turn.id',ondelete='CASCADE')))
    op.add_column('intelligence_job',sa.Column('request_key',UUID(),unique=True))
    op.create_table('intelligence_job_event',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('job_id',sa.Integer(),sa.ForeignKey('intelligence_job.id',ondelete='CASCADE'),nullable=False),
        sa.Column('tool',sa.String(60),nullable=False),sa.Column('executor',sa.String(80),nullable=False),
        sa.Column('status',sa.String(12),nullable=False),sa.Column('summary',sa.String(500),nullable=False),
        sa.Column('inputs',JSONB(),nullable=False),sa.Column('artifacts',JSONB(),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
        sa.CheckConstraint("status IN ('running','complete','partial','failed')",name='intelligence_job_event_status'))
    op.create_index('ix_intelligence_event_job','intelligence_job_event',['job_id','id'])

def downgrade():
    op.drop_table('intelligence_job_event')
    for name in ('request_key','chat_turn_id','chat_session_id'):op.drop_column('intelligence_job',name)
    op.drop_constraint('intelligence_job_action','intelligence_job',type_='check')
    op.create_check_constraint('intelligence_job_action','intelligence_job',"action IN ('analyze','research','draft','index','search','refine_angle')")
