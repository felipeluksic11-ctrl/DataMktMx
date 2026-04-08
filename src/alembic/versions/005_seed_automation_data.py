"""Seed schedule_configs and supervisor_configs from current cron entries.

Converts the 9 active cron entries + 1 ETL to DB-based schedules,
and creates default supervisor_configs for each active portal.

Revision ID: 005
Revises: 004
Create Date: 2026-04-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # Get portal IDs by slug
    portals = conn.execute(
        sa.text("SELECT id, slug FROM portals WHERE slug IN ('lamudi', 'propiedades', 'properstar')")
    ).fetchall()

    portal_map = {row[1]: row[0] for row in portals}

    if not portal_map:
        # No portals seeded yet — skip (user must seed portals first)
        return

    # ── Create schedule groups ──────────────────────────────────
    conn.execute(sa.text("""
        INSERT INTO schedule_groups (id, name, description, execution_mode, stagger_seconds)
        VALUES
            (gen_random_uuid(), 'Daily Incremental', 'Cards-only daily scrape for all active portals', 'sequential', 1800),
            (gen_random_uuid(), 'Monthly Full', 'Complete full scrape on 1st of each month', 'sequential', 1800),
            (gen_random_uuid(), 'Weekly Enrichment', 'Detail enrichment for listings with missing fields', 'sequential', 1800)
        ON CONFLICT (name) DO NOTHING
    """))

    # Get group IDs
    groups = conn.execute(sa.text("SELECT id, name FROM schedule_groups")).fetchall()
    group_map = {row[1]: row[0] for row in groups}

    # ── Seed schedule_configs (from cron entries) ───────────────

    schedules = [
        # Daily Incremental
        ("Lamudi Daily Incremental", "lamudi", "Daily Incremental", "incremental", "0 8 * * *", 200, False, 70),
        ("Propiedades Daily Incremental", "propiedades", "Daily Incremental", "incremental", "30 8 * * *", 200, False, 70),
        ("Properstar Daily Incremental", "properstar", "Daily Incremental", "incremental", "0 9 * * *", 300, False, 60),
        # Monthly Full
        ("Lamudi Monthly Full", "lamudi", "Monthly Full", "full", "0 6 1 * *", 1500, False, 50),
        ("Propiedades Monthly Full", "propiedades", "Monthly Full", "full", "30 6 1 * *", 3000, False, 50),
        ("Properstar Monthly Full", "properstar", "Monthly Full", "full", "0 7 1 * *", 2000, False, 50),
        # Weekly Enrichment
        ("Propiedades Weekly Enrich", "propiedades", "Weekly Enrichment", "enrich", "0 9 * * 3", 300, True, 40),
        ("Lamudi Weekly Enrich", "lamudi", "Weekly Enrichment", "enrich", "0 9 * * 4", 300, True, 40),
        ("Properstar Weekly Enrich", "properstar", "Weekly Enrichment", "enrich", "0 9 * * 5", 300, True, 40),
    ]

    for name, slug, group_name, mode, cron, budget, visit_detail, priority in schedules:
        portal_id = portal_map.get(slug)
        group_id = group_map.get(group_name)
        if not portal_id:
            continue

        conn.execute(sa.text("""
            INSERT INTO schedule_configs (name, portal_id, group_id, mode, cron_expression, budget_mb, visit_detail, priority, rate_limit_s)
            VALUES (:name, :portal_id, :group_id, :mode, :cron, :budget, :visit_detail, :priority, :rate_limit)
        """), {
            "name": name,
            "portal_id": portal_id,
            "group_id": group_id,
            "mode": mode,
            "cron": cron,
            "budget": budget,
            "visit_detail": visit_detail,
            "priority": priority,
            "rate_limit": 3600,  # 1 hour between runs for same portal
        })

    # ── Seed supervisor_configs ─────────────────────────────────
    for slug, portal_id in portal_map.items():
        conn.execute(sa.text("""
            INSERT INTO supervisor_configs (portal_id, is_enabled, run_after_scrape, auto_apply_threshold, queue_review_threshold, max_daily_cost_usd)
            VALUES (:portal_id, true, true, 0.9, 0.5, 1.0)
            ON CONFLICT (portal_id) DO NOTHING
        """), {"portal_id": portal_id})


def downgrade() -> None:
    op.execute("DELETE FROM schedule_configs")
    op.execute("DELETE FROM schedule_groups")
    op.execute("DELETE FROM supervisor_configs")
