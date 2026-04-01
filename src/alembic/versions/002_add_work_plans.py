"""Add work_plans table for scout-driven orchestration.

Revision ID: 002
Revises: 001
Create Date: 2026-03-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "work_plans",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("portal_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("portals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("operation", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'draft'")),
        # Scout results
        sa.Column("total_listings", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("total_pages", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("states_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("anti_bot_level", sa.String(10), nullable=False, server_default=sa.text("'none'")),
        sa.Column("selectors_healthy", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("scout_report", postgresql.JSONB, nullable=True),
        # Plan config
        sa.Column("num_workers", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("visit_detail", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("worker_assignments", postgresql.JSONB, nullable=True),
        sa.Column("proxy_provider", sa.String(30), nullable=True),
        # Estimates
        sa.Column("estimated_hours", sa.Float, nullable=False, server_default=sa.text("0")),
        sa.Column("estimated_cost_usd", sa.Float, nullable=False, server_default=sa.text("0")),
        # Execution results
        sa.Column("actual_hours", sa.Float, nullable=True),
        sa.Column("actual_cost_usd", sa.Float, nullable=True),
        sa.Column("total_scraped", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("total_new", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("total_errors", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("error_detail", sa.Text, nullable=True),
        # Timestamps
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("work_plans")
