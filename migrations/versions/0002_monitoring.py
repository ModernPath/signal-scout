"""Monitoring profile and queued collection runs.

Revision ID: 0002_monitoring
Revises: 0001_application_core
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "0002_monitoring"
down_revision = "0001_application_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "monitor_profile",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("id = 1", name="monitor_profile_singleton"),
    )
    op.create_table(
        "monitor_rule",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("monitor_profile.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("value", sa.String(100), nullable=False),
        sa.Column("normalized_value", sa.String(100), nullable=False),
        sa.CheckConstraint("kind IN ('topic', 'include', 'exclude', 'competitor', 'person')", name="monitor_rule_kind"),
        sa.UniqueConstraint("profile_id", "kind", "normalized_value"),
    )
    op.create_table(
        "source_config",
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("monitor_profile.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_key", sa.String(20), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("profile_id", "source_key"),
        sa.CheckConstraint("source_key IN ('x', 'web', 'hn', 'reddit', 'github', 'rss')", name="source_config_key"),
    )
    op.create_table(
        "collection_run",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("trigger", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("scheduled_slot", sa.DateTime(timezone=True), unique=True),
        sa.Column("profile_snapshot", JSONB(), nullable=False),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("trigger IN ('initial', 'scheduled', 'manual')", name="collection_run_trigger"),
        sa.CheckConstraint("status IN ('queued', 'running', 'complete', 'partial', 'failed')", name="collection_run_status"),
    )
    op.create_index("ix_collection_run_queued", "collection_run", [sa.text("queued_at DESC")])


def downgrade() -> None:
    op.drop_index("ix_collection_run_queued", table_name="collection_run")
    op.drop_table("collection_run")
    op.drop_table("source_config")
    op.drop_table("monitor_rule")
    op.drop_table("monitor_profile")
