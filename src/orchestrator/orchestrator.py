"""Orchestrator — takes an approved WorkPlan and launches distributed workers.

Flow:
1. Receive approved WorkPlan
2. Enqueue N Dramatiq tasks (one per worker assignment)
3. Monitor progress
4. Update WorkPlan with results when all workers complete
"""

import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.worker_task import run_worker_task
from shared.db.models import WorkPlan
from shared.logging import get_logger

logger = get_logger("orchestrator")


async def execute_plan(session: AsyncSession, plan_id: str) -> WorkPlan:
    """Launch all workers for an approved WorkPlan."""
    stmt = select(WorkPlan).where(WorkPlan.id == plan_id)
    result = await session.execute(stmt)
    plan = result.scalar_one()

    if plan.status != "approved":
        raise ValueError(f"Plan {plan_id} is {plan.status}, must be 'approved' to execute")

    if not plan.worker_assignments:
        raise ValueError(f"Plan {plan_id} has no worker assignments")

    # Get portal slug
    from shared.db.models import Portal
    portal_stmt = select(Portal).where(Portal.id == plan.portal_id)
    portal = (await session.execute(portal_stmt)).scalar_one()

    plan.status = "running"
    plan.started_at = datetime.datetime.now(datetime.UTC)
    await session.commit()

    # Enqueue one Dramatiq task per worker assignment
    for assignment in plan.worker_assignments:
        worker_id = assignment["worker_id"]
        states = assignment["states"]

        logger.info(
            "orchestrator.launching_worker",
            plan=plan_id,
            worker=worker_id,
            states=states,
            listings=assignment.get("total_listings", 0),
        )

        run_worker_task.send(
            plan_id=plan_id,
            worker_id=worker_id,
            portal_slug=portal.slug,
            operation=plan.operation,
            states=states,
            visit_detail=plan.visit_detail,
        )

    logger.info(
        "orchestrator.all_workers_launched",
        plan=plan_id,
        num_workers=len(plan.worker_assignments),
    )

    return plan


async def complete_plan(
    session: AsyncSession,
    plan_id: str,
    total_scraped: int,
    total_new: int,
    total_errors: int,
) -> WorkPlan:
    """Mark a plan as completed with final stats. Called after all workers finish."""
    stmt = select(WorkPlan).where(WorkPlan.id == plan_id)
    result = await session.execute(stmt)
    plan = result.scalar_one()

    plan.status = "completed"
    plan.finished_at = datetime.datetime.now(datetime.UTC)
    plan.total_scraped = total_scraped
    plan.total_new = total_new
    plan.total_errors = total_errors

    if plan.started_at:
        delta = plan.finished_at - plan.started_at
        plan.actual_hours = delta.total_seconds() / 3600

    await session.commit()
    logger.info(
        "orchestrator.plan_completed",
        plan=plan_id,
        scraped=total_scraped,
        new=total_new,
        errors=total_errors,
        hours=round(plan.actual_hours or 0, 1),
    )
    return plan
