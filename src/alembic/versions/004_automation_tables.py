"""Automation tables — schedules, supervisor history, repairs, audit log.

Adds DB-based scheduling (replaces cron), supervisor run history with
repair tracking, and a unified audit log for all operational changes.

Revision ID: 004
Revises: 003
Create Date: 2026-04-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Add selector_overrides to portals ---
    op.add_column(
        "portals",
        sa.Column("selector_overrides", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'")),
    )

    # --- schedule_groups ---
    op.create_table(
        "schedule_groups",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("execution_mode", sa.String(20), nullable=False, server_default=sa.text("'sequential'")),
        sa.Column("stagger_seconds", sa.Integer, nullable=False, server_default=sa.text("1800")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- schedule_configs ---
    op.create_table(
        "schedule_configs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("portal_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("portals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("group_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("schedule_groups.id", ondelete="SET NULL"), nullable=True),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("cron_expression", sa.String(100), nullable=False),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("budget_mb", sa.Float, nullable=False),
        sa.Column("states", postgresql.JSONB, nullable=True),
        sa.Column("visit_detail", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("priority", sa.Integer, nullable=False, server_default=sa.text("50")),
        sa.Column("rate_limit_s", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("max_retries", sa.Integer, nullable=False, server_default=sa.text("3")),
        sa.Column("retry_backoff_s", sa.Integer, nullable=False, server_default=sa.text("300")),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_status", sa.String(20), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("run_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_schedule_configs_portal", "schedule_configs", ["portal_id"])
    op.create_index("ix_schedule_configs_next_run", "schedule_configs", ["next_run_at"])

    # --- schedule_runs ---
    op.create_table(
        "schedule_runs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("schedule_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("schedule_configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scrape_job_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("scrape_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("trigger", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("error_detail", sa.Text, nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_schedule_runs_schedule", "schedule_runs", ["schedule_id"])
    op.create_index("ix_schedule_runs_status", "schedule_runs", ["status"])

    # --- supervisor_runs ---
    op.create_table(
        "supervisor_runs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("portal_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("portals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scrape_job_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("scrape_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("trigger", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'running'")),
        sa.Column("quality_before", postgresql.JSONB, nullable=True),
        sa.Column("quality_after", postgresql.JSONB, nullable=True),
        sa.Column("diagnosis", postgresql.JSONB, nullable=True),
        sa.Column("repairs_suggested", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("repairs_applied", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("repairs_queued", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("ai_cost_usd", sa.Float, nullable=False, server_default=sa.text("0")),
        sa.Column("ai_model", sa.String(50), nullable=True),
        sa.Column("ai_tokens_in", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("ai_tokens_out", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("duration_s", sa.Float, nullable=True),
        sa.Column("error_detail", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_supervisor_runs_portal", "supervisor_runs", ["portal_id"])

    # --- repair_logs ---
    op.create_table(
        "repair_logs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("supervisor_run_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("supervisor_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("portal_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("portals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field", sa.String(50), nullable=False),
        sa.Column("old_selector", sa.Text, nullable=True),
        sa.Column("new_selector", sa.Text, nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("data_present", sa.Boolean, nullable=True),
        sa.Column("extraction_method", sa.String(50), nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'suggested'")),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_by", sa.String(50), nullable=True),
        sa.Column("quality_before", sa.Float, nullable=True),
        sa.Column("quality_after", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_repair_logs_portal", "repair_logs", ["portal_id"])
    op.create_index("ix_repair_logs_status", "repair_logs", ["status"])

    # --- supervisor_configs ---
    op.create_table(
        "supervisor_configs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("portal_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("portals.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("run_after_scrape", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("auto_apply_threshold", sa.Float, nullable=False, server_default=sa.text("0.9")),
        sa.Column("queue_review_threshold", sa.Float, nullable=False, server_default=sa.text("0.5")),
        sa.Column("max_daily_cost_usd", sa.Float, nullable=False, server_default=sa.text("1.0")),
        sa.Column("cron_expression", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- audit_log ---
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("actor", sa.String(50), nullable=False, server_default=sa.text("'system'")),
        sa.Column("is_automatic", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("is_success", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("diff", postgresql.JSONB, nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String), nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_log_entity", "audit_log", ["entity_type", "entity_id"])
    op.create_index("ix_audit_log_created", "audit_log", ["created_at"])
    op.execute("CREATE INDEX ix_audit_log_tags ON audit_log USING GIN (tags)")


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("supervisor_configs")
    op.drop_table("repair_logs")
    op.drop_table("supervisor_runs")
    op.drop_table("schedule_runs")
    op.drop_table("schedule_configs")
    op.drop_table("schedule_groups")
    op.drop_column("portals", "selector_overrides")
