"""Scheduler — runs the full scraping + ETL cycle on a schedule.

Flow:
1. Scout all active portals
2. Generate WorkPlans
3. Auto-approve if selectors healthy + anti-bot ≤ medium
4. Execute approved plans (launch workers)
5. Wait for workers to complete
6. Run ETL pipeline (raw → clean)
7. Export to S3
8. Send alert with summary

This runs as a single async function called by cron or Dramatiq periodic task.
"""

import asyncio
import datetime

from sqlalchemy import select

from etl.pipeline import run_pipeline
from etl.exporters.s3 import export_to_s3, export_to_file
from etl.exporters.supabase import sync_to_supabase
from orchestrator.planner import create_work_plan, approve_plan
from orchestrator.scouts import SCOUT_REGISTRY
from orchestrator.orchestrator import execute_plan
from shared.db.models import Portal, WorkPlan
from shared.db.session import get_engine, get_session_factory
from shared.logging import get_logger, setup_logging

logger = get_logger("scheduler")


async def run_full_cycle(
    operations: list[str] | None = None,
    auto_approve: bool = True,
    run_etl: bool = True,
    export: bool = True,
    mode: str = "incremental",
) -> dict:
    """Run the complete scout → scrape → ETL → export cycle.

    Modes:
    - "incremental" (daily): sort by recent, stop on known listings (~0.86GB/day)
    - "full" (monthly): scrape all pages to detect removed listings (~13GB)

    Returns summary dict with stats from each phase.
    """
    setup_logging()
    operations = operations or ["venta", "renta"]
    summary: dict = {
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        "scouts": [],
        "plans": [],
        "etl": None,
        "export": None,
        "supabase_sync": None,
        "errors": [],
    }

    session_factory = get_session_factory()

    async with session_factory() as session:
        # Get active portals
        stmt = select(Portal).where(Portal.is_active.is_(True))
        result = await session.execute(stmt)
        portals = result.scalars().all()

        if not portals:
            logger.warning("scheduler.no_active_portals")
            return summary

        # Phase 1: Scout all active portals
        logger.info("scheduler.phase_scout", portals=[p.slug for p in portals])

        for portal in portals:
            for operation in operations:
                scout_cls = SCOUT_REGISTRY.get(portal.slug)
                if not scout_cls:
                    logger.warning("scheduler.no_scout", portal=portal.slug)
                    continue

                try:
                    scout = scout_cls()
                    report = await scout.run(operation=operation)
                    summary["scouts"].append(report.to_dict())

                    # Phase 2: Create WorkPlan
                    plan = await create_work_plan(session, report)
                    summary["plans"].append({
                        "plan_id": plan.id,
                        "portal": portal.slug,
                        "operation": operation,
                        "status": plan.status,
                        "listings": plan.total_listings,
                        "workers": plan.num_workers,
                    })

                    # Phase 3: Auto-approve if safe
                    if auto_approve and report.selectors_healthy and report.anti_bot_level in ("none", "low", "medium"):
                        await approve_plan(session, plan.id)
                        summary["plans"][-1]["status"] = "approved"

                        # Phase 4: Execute
                        await execute_plan(session, plan.id)
                        summary["plans"][-1]["status"] = "running"

                except Exception as e:
                    error = f"Scout/plan error for {portal.slug}/{operation}: {str(e)[:200]}"
                    summary["errors"].append(error)
                    logger.exception("scheduler.scout_error", portal=portal.slug, operation=operation)

        # Phase 5: Run ETL
        if run_etl:
            logger.info("scheduler.phase_etl")
            try:
                etl_stats = await run_pipeline(session, full_rebuild=False)
                summary["etl"] = etl_stats
            except Exception as e:
                summary["errors"].append(f"ETL error: {str(e)[:200]}")
                logger.exception("scheduler.etl_error")

        # Phase 6: Export
        if export:
            logger.info("scheduler.phase_export")
            try:
                export_stats = await export_to_s3(session)
                summary["export"] = export_stats
            except Exception as e:
                # Fall back to local file export
                try:
                    export_stats = await export_to_file(
                        session,
                        f"/opt/propyte/exports/listings_{datetime.datetime.now().strftime('%Y%m%d')}.csv"
                    )
                    summary["export"] = export_stats
                except Exception as e2:
                    summary["errors"].append(f"Export error: {str(e2)[:200]}")
                    logger.exception("scheduler.export_error")

        # Phase 7: Sync to Supabase (permanent backup)
        logger.info("scheduler.phase_supabase_sync")
        try:
            sync_stats = await sync_to_supabase(session)
            summary["supabase_sync"] = sync_stats
        except Exception as e:
            summary["errors"].append(f"Supabase sync error: {str(e)[:200]}")
            logger.exception("scheduler.supabase_sync_error")

    engine = get_engine()
    await engine.dispose()

    logger.info(
        "scheduler.cycle_complete",
        scouts=len(summary["scouts"]),
        plans=len(summary["plans"]),
        errors=len(summary["errors"]),
    )

    return summary


async def run_etl_only() -> dict:
    """Run just the ETL pipeline (no scraping)."""
    setup_logging()
    session_factory = get_session_factory()
    async with session_factory() as session:
        stats = await run_pipeline(session, full_rebuild=False)
    engine = get_engine()
    await engine.dispose()
    return stats


def main():
    """CLI entry point for the scheduler.

    Usage:
        python -m orchestrator.scheduler              # daily incremental (default)
        python -m orchestrator.scheduler incremental   # same
        python -m orchestrator.scheduler full          # monthly full scrape
        python -m orchestrator.scheduler etl           # ETL only (no scraping)
    """
    import sys
    setup_logging()

    arg = sys.argv[1] if len(sys.argv) > 1 else "incremental"

    if arg == "etl":
        logger.info("scheduler.running_etl_only")
        asyncio.run(run_etl_only())
    elif arg == "full":
        logger.info("scheduler.running_full_cycle", mode="full")
        asyncio.run(run_full_cycle(mode="full"))
    else:
        logger.info("scheduler.running_incremental")
        asyncio.run(run_full_cycle(mode="incremental"))


if __name__ == "__main__":
    main()
