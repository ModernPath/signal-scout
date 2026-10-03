"""PostgreSQL lifecycle and chat memory for the independent agent.

Revision ID: 0006_agent_memory
Revises: 0005_intelligence
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_agent_memory"
down_revision = "0005_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("company_content", sa.Column("active", sa.Boolean(), nullable=False,
                                                server_default=sa.true()))
    op.add_column("company_content", sa.Column("replaces_id", sa.Integer(),
                                                sa.ForeignKey("company_content.id", ondelete="SET NULL")))
    op.add_column("company_brief", sa.Column("active", sa.Boolean(), nullable=False,
                                              server_default=sa.true()))
    op.add_column("intelligence_run", sa.Column("algorithm_version", sa.String(80),
                                                 nullable=False, server_default="cluster-score-v1"))
    op.add_column("research_run", sa.Column("model_version", sa.String(80), nullable=False,
                                             server_default="unknown"))
    op.add_column("research_run", sa.Column("error_summary", sa.Text()))
    op.add_column("content_draft", sa.Column("model_version", sa.String(80), nullable=False,
                                              server_default="unknown"))
    op.add_column("content_draft", sa.Column("prompt_version", sa.String(80), nullable=False,
                                              server_default="draft-v1"))
    op.add_column("content_draft", sa.Column("status", sa.String(20), nullable=False,
                                              server_default="draft"))
    op.add_column("research_evidence", sa.Column("excerpt_expires_at", sa.DateTime(timezone=True)))
    op.create_table(
        "agent_chat_session",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_chat_session_expires", "agent_chat_session", ["expires_at"])
    op.create_table(
        "agent_chat_turn",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("agent_chat_session.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("role", sa.String(12), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="agent_chat_turn_role"),
    )
    op.create_index("ix_agent_chat_turn_session", "agent_chat_turn", ["session_id", "id"])


def downgrade() -> None:
    op.drop_index("ix_agent_chat_turn_session", table_name="agent_chat_turn")
    op.drop_table("agent_chat_turn")
    op.drop_index("ix_agent_chat_session_expires", table_name="agent_chat_session")
    op.drop_table("agent_chat_session")
    op.drop_column("research_evidence", "excerpt_expires_at")
    op.drop_column("content_draft", "status")
    op.drop_column("content_draft", "prompt_version")
    op.drop_column("content_draft", "model_version")
    op.drop_column("research_run", "error_summary")
    op.drop_column("research_run", "model_version")
    op.drop_column("intelligence_run", "algorithm_version")
    op.drop_column("company_brief", "active")
    op.drop_column("company_content", "replaces_id")
    op.drop_column("company_content", "active")
