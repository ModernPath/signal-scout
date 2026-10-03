"""Signals, source provenance, topics, and triage state.

Revision ID: 0003_feed
Revises: 0002_monitoring
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "0003_feed"
down_revision = "0002_monitoring"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signal",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=False),
        sa.Column("canonical_url_key", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_signal_published", "signal", [sa.text("published_at DESC"), sa.text("id DESC")])
    op.create_table(
        "source_item",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("signal_id", sa.Integer(), sa.ForeignKey("signal.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_key", sa.String(20), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("content_url", sa.Text(), nullable=False),
        sa.Column("canonical_url_key", sa.Text(), nullable=False),
        sa.Column("target_host", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("normalized_title", sa.Text(), nullable=False),
        sa.Column("snippet", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("metric_name", sa.String(40)),
        sa.Column("metric_value", sa.Integer()),
        sa.Column("matched_terms", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("source_key", "external_id"),
        sa.CheckConstraint("metric_value IS NULL OR metric_value >= 0", name="source_item_metric_nonnegative"),
    )
    op.create_index("ix_source_item_signal_source", "source_item", ["signal_id", "source_key"])
    op.create_index("ix_source_item_canonical", "source_item", ["canonical_url_key"])
    op.create_table(
        "signal_topic",
        sa.Column("signal_id", sa.Integer(), sa.ForeignKey("signal.id", ondelete="CASCADE"), nullable=False),
        sa.Column("topic", sa.String(100), nullable=False),
        sa.PrimaryKeyConstraint("signal_id", "topic"),
    )
    op.create_index("ix_signal_topic_topic_signal", "signal_topic", ["topic", "signal_id"])
    op.create_table(
        "signal_state",
        sa.Column("signal_id", sa.Integer(), sa.ForeignKey("signal.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("saved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("dismissed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("interesting", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("saved_at", sa.DateTime(timezone=True)),
        sa.Column("dismissed_at", sa.DateTime(timezone=True)),
        sa.Column("interesting_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("signal_state")
    op.drop_index("ix_signal_topic_topic_signal", table_name="signal_topic")
    op.drop_table("signal_topic")
    op.drop_index("ix_source_item_canonical", table_name="source_item")
    op.drop_index("ix_source_item_signal_source", table_name="source_item")
    op.drop_table("source_item")
    op.drop_index("ix_signal_published", table_name="signal")
    op.drop_table("signal")
