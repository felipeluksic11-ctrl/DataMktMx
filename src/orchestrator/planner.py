"""Planner — converts a ScoutReport into a WorkPlan stored in DB."""

import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.scout import ScoutReport
from shared.db.models import Portal, WorkPlan
from shared.logging import get_logger

logger = get_logger("orchestrator.planner")


async def create_work_plan(
    session: AsyncSession,
    scout_report: ScoutReport,
    visit_detail: bool = True,
    num_workers_override: int | None = None,
) -> WorkPlan:
    """Create a WorkPlan from a ScoutReport. Status: draft (needs approval)."""

    # Find portal
    stmt = select(Portal).where(Portal.slug == scout_report.portal_slug)
    result = await session.execute(stmt)
    portal = result.scalar_one()

    workers = num_workers_override or scout_report.recommended_workers
    hours = scout_report.estimated_hours_with_detail if visit_detail else scout_report.estimated_hours_cards_only

    plan = WorkPlan(
        portal_id=portal.id,
        operation=scout_report.operation,
        total_listings=scout_report.total_listings,
        total_pages=scout_report.total_pages,
        states_count=scout_report.states_accessible,
        anti_bot_level=scout_report.anti_bot_level,
        selectors_healthy=scout_report.selectors_healthy,
        scout_report=scout_report.to_dict(),
        num_workers=workers,
        visit_detail=visit_detail,
        worker_assignments=scout_report.worker_assignments,
        estimated_hours=hours,
        estimated_cost_usd=scout_report.estimated_cost_usd,
    )

    session.add(plan)
    await session.commit()
    await session.refresh(plan)

    logger.info(
        "planner.plan_created",
        plan_id=plan.id,
        portal=scout_report.portal_slug,
        operation=scout_report.operation,
        listings=scout_report.total_listings,
        workers=workers,
        hours=round(hours, 1),
        cost=round(scout_report.estimated_cost_usd, 2),
    )

    return plan


async def approve_plan(session: AsyncSession, plan_id: str) -> WorkPlan:
    """Approve a work plan for execution."""
    stmt = select(WorkPlan).where(WorkPlan.id == plan_id)
    result = await session.execute(stmt)
    plan = result.scalar_one()

    if plan.status != "draft":
        raise ValueError(f"Plan {plan_id} is {plan.status}, can only approve drafts")

    plan.status = "approved"
    plan.approved_at = datetime.datetime.now(datetime.UTC)
    await session.commit()

    logger.info("planner.plan_approved", plan_id=plan_id)
    return plan


async def cancel_plan(session: AsyncSession, plan_id: str) -> WorkPlan:
    """Cancel a work plan."""
    stmt = select(WorkPlan).where(WorkPlan.id == plan_id)
    result = await session.execute(stmt)
    plan = result.scalar_one()

    if plan.status in ("completed", "cancelled"):
        raise ValueError(f"Plan {plan_id} is already {plan.status}")

    plan.status = "cancelled"
    plan.finished_at = datetime.datetime.now(datetime.UTC)
    await session.commit()

    logger.info("planner.plan_cancelled", plan_id=plan_id)
    return plan
