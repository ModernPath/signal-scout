"""Standalone Phase 2 intelligence records.

Revision ID: 0005_intelligence
Revises: 0004_source_runs
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005_intelligence"
down_revision = "0004_source_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_brief",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, unique=True),
        sa.Column("brief", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "company_content",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("url", sa.Text()),
        sa.Column("channel", sa.String(40), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "intelligence_run",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fingerprint", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('complete', 'failed')", name="intelligence_run_status"),
    )
    op.create_table(
        "conversation",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("intelligence_run.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
    )
    op.create_table(
        "conversation_signal",
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False),
        sa.Column("signal_id", sa.Integer(), sa.ForeignKey("signal.id", ondelete="RESTRICT"), nullable=False),
        sa.PrimaryKeyConstraint("conversation_id", "signal_id"),
    )
    op.create_table(
        "opportunity",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("conversation.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("components", JSONB(), nullable=False),
        sa.Column("why_now", sa.Text(), nullable=False),
        sa.Column("why_us", sa.Text(), nullable=False),
        sa.Column("angle", sa.Text(), nullable=False),
        sa.Column("evidence_source_item_ids", JSONB(), nullable=False),
        sa.Column("prior_content_matches", JSONB(), nullable=False),
    )
    op.create_index("ix_opportunity_rank", "opportunity", ["rank"])
    op.create_table(
        "research_run",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("opportunity_id", sa.Integer(), sa.ForeignKey("opportunity.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('complete', 'partial')", name="research_run_status"),
    )
    op.create_table(
        "research_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("research_run_id", sa.Integer(), sa.ForeignKey("research_run.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("claim", sa.Text(), nullable=False),
        sa.Column("stance", sa.String(20), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("stance IN ('support', 'conflict', 'unknown')", name="research_evidence_stance"),
    )
    op.create_table(
        "content_draft",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("opportunity_id", sa.Integer(), sa.ForeignKey("opportunity.id", ondelete="CASCADE"), nullable=False),
        sa.Column("research_run_id", sa.Integer(), sa.ForeignKey("research_run.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("channel", sa.String(12), nullable=False),
        sa.Column("format", sa.String(12), nullable=False),
        sa.Column("draft_text", sa.Text(), nullable=False),
        sa.Column("evidence_ids", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("channel IN ('linkedin', 'x')", name="draft_channel"),
        sa.CheckConstraint("format IN ('post', 'reply')", name="draft_format"),
    )


def downgrade() -> None:
    op.drop_table("content_draft")
    op.drop_table("research_evidence")
    op.drop_table("research_run")
    op.drop_index("ix_opportunity_rank", table_name="opportunity")
    op.drop_table("opportunity")
    op.drop_table("conversation_signal")
    op.drop_table("conversation")
    op.drop_table("intelligence_run")
    op.drop_table("company_content")
    op.drop_table("company_brief")
