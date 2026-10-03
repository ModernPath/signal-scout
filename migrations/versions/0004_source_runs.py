"""Per-source collection outcomes.

Revision ID: 0004_source_runs
Revises: 0003_feed
"""

from alembic import op
import sqlalchemy as sa


revision = "0004_source_runs"
down_revision = "0003_feed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_run",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("collection_run.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_key", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accepted_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(50)),
        sa.Column("error_message", sa.String(200)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("run_id", "source_key"),
        sa.CheckConstraint("status IN ('complete', 'failed', 'unavailable', 'skipped')", name="source_run_status"),
    )


def downgrade() -> None:
    op.drop_table("source_run")
