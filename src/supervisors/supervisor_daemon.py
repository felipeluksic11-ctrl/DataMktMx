"""Supervisor Daemon — autonomous quality monitoring and repair.

Runs as a coroutine inside the scheduler daemon process.
Listens for scrape completion events and runs diagnostics automatically.

Triggers:
- Redis "supervisor:scrape_completed" (auto after each scrape)
- Redis "supervisor:manual_trigger" (dashboard button)
- Internal cron (if supervisor_config has cron_expression)
"""

import asyncio
import datetime
import json
import time

from sqlalchemy import select, func

from scrapers.quality_check import check_quality
from shared.audit import log_audit
from shared.config import settings
from shared.db.models import Portal
from shared.db.models.repair_log import RepairLog
from shared.db.models.supervisor_config import SupervisorConfig
from shared.db.models.supervisor_run import SupervisorRun
from shared.db.session import get_session_factory
from shared.logging import get_logger
from supervisors.repair_applier import apply_selector_override
from supervisors.scrape_supervisor import ScrapeSupervisor

logger = get_logger("supervisor.daemon")

SCRAPE_COMPLETED_CHANNEL = "supervisor:scrape_completed"
MANUAL_TRIGGER_CHANNEL = "supervisor:manual_trigger"


class SupervisorDaemonRunner:
    """Handles supervisor logic. Called from scheduler daemon or standalone."""

    def __init__(self):
        self._session_factory = get_session_factory()
        self._supervisor = ScrapeSupervisor()

    async def run_diagnostic(
        self,
        portal_slug: str,
        portal_id: str,
        scrape_job_id: str | None = None,
        trigger: str = "auto_post_scrape",
    ) -> SupervisorRun | None:
        """Run a full diagnostic cycle for a portal.

        Returns:
            SupervisorRun record, or None if skipped
        """
        async with self._session_factory() as session:
            # Load supervisor config
            stmt = select(SupervisorConfig).where(SupervisorConfig.portal_id == portal_id)
            result = await session.execute(stmt)
            config = result.scalar_one_or_none()

            if not config or not config.is_enabled:
                logger.info("supervisor.disabled", portal=portal_slug)
                return None

            # Check daily AI budget
            if not await self._check_daily_budget(session, portal_id, config.max_daily_cost_usd):
                logger.warning("supervisor.daily_budget_exceeded", portal=portal_slug)
                return None

        # Get quality snapshot
        async with self._session_factory() as session:
            quality_before = await check_quality(session, portal_id, portal_slug)

        start_time = time.time()

        # Create supervisor_run record
        async with self._session_factory() as session:
            run = SupervisorRun(
                portal_id=portal_id,
                scrape_job_id=scrape_job_id,
                trigger=trigger,
                status="running",
                quality_before=quality_before,
            )
            session.add(run)
            await session.commit()
            await session.refresh(run)

        try:
            # Run the actual diagnosis
            repair_result = await self._supervisor.check_and_repair(
                portal_slug, portal_id, quality_before
            )

            duration = time.time() - start_time

            # Process repairs
            repairs_suggested = 0
            repairs_applied = 0
            repairs_queued = 0

            if repair_result and repair_result.get("repairs"):
                async with self._session_factory() as session:
                    # Reload config for thresholds
                    stmt = select(SupervisorConfig).where(
                        SupervisorConfig.portal_id == portal_id
                    )
                    result = await session.execute(stmt)
                    config = result.scalar_one()

                    for repair in repair_result["repairs"]:
                        confidence = repair.get("confidence", 0)
                        field = repair.get("field", "unknown")
                        new_selector = repair.get("new_selector")
                        old_selector = repair.get("old_selector")
                        repairs_suggested += 1

                        # Determine status based on confidence thresholds
                        if confidence >= config.auto_apply_threshold and new_selector:
                            status = "auto_applied"
                            repairs_applied += 1
                            # Apply the override
                            await apply_selector_override(
                                session, portal_id, field, new_selector, actor="auto"
                            )
                        elif confidence >= config.queue_review_threshold:
                            status = "queued"
                            repairs_queued += 1
                        else:
                            status = "rejected"

                        # Create repair_log
                        repair_log = RepairLog(
                            supervisor_run_id=run.id,
                            portal_id=portal_id,
                            field=field,
                            old_selector=old_selector,
                            new_selector=new_selector,
                            confidence=confidence,
                            data_present=repair.get("data_present"),
                            extraction_method=repair.get("extraction_method"),
                            reason=repair.get("reason"),
                            status=status,
                            quality_before=quality_before.get(field),
                        )
                        if status == "auto_applied":
                            repair_log.applied_at = datetime.datetime.now(datetime.UTC)
                            repair_log.applied_by = "auto"

                        session.add(repair_log)

                    await session.commit()

            # Update supervisor_run
            async with self._session_factory() as session:
                stmt = select(SupervisorRun).where(SupervisorRun.id == run.id)
                result = await session.execute(stmt)
                run_record = result.scalar_one()
                run_record.status = "completed"
                run_record.repairs_suggested = repairs_suggested
                run_record.repairs_applied = repairs_applied
                run_record.repairs_queued = repairs_queued
                run_record.duration_s = duration
                run_record.diagnosis = repair_result

                # AI cost tracking (estimate)
                if repair_result:
                    run_record.ai_model = "claude-sonnet-4-6"
                    run_record.ai_cost_usd = 0.025  # approximate per analysis
                    run_record.ai_tokens_in = repair_result.get("tokens_in", 0)
                    run_record.ai_tokens_out = repair_result.get("tokens_out", 0)

                # Audit log
                await log_audit(
                    session,
                    entity_type="supervisor",
                    entity_id=run.id,
                    action="completed",
                    summary=f"{portal_slug} diagnostic: {repairs_suggested} suggested, "
                    f"{repairs_applied} auto-applied, {repairs_queued} queued",
                    actor="supervisor",
                    is_automatic=trigger != "manual",
                    metadata={
                        "repairs_suggested": repairs_suggested,
                        "repairs_applied": repairs_applied,
                        "repairs_queued": repairs_queued,
                        "duration_s": round(duration, 1),
                    },
                )
                await session.commit()

            logger.info(
                "supervisor.diagnostic_complete",
                portal=portal_slug,
                suggested=repairs_suggested,
                applied=repairs_applied,
                queued=repairs_queued,
                duration_s=round(duration, 1),
            )
            return run_record

        except Exception as exc:
            logger.exception("supervisor.diagnostic_failed", portal=portal_slug)
            async with self._session_factory() as session:
                stmt = select(SupervisorRun).where(SupervisorRun.id == run.id)
                result = await session.execute(stmt)
                run_record = result.scalar_one()
                run_record.status = "failed"
                run_record.error_detail = str(exc)[:2000]
                run_record.duration_s = time.time() - start_time
                await session.commit()
            return None

    async def _check_daily_budget(
        self,
        session,
        portal_id: str,
        max_daily_cost: float,
    ) -> bool:
        """Check if today's AI spend is within budget."""
        today_start = datetime.datetime.now(datetime.UTC).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        stmt = (
            select(func.sum(SupervisorRun.ai_cost_usd))
            .where(
                SupervisorRun.portal_id == portal_id,
                SupervisorRun.created_at >= today_start,
            )
        )
        result = await session.execute(stmt)
        total_today = result.scalar() or 0
        return total_today < max_daily_cost


async def start_supervisor_listener(shutdown_event: asyncio.Event | None = None):
    """Start Redis listeners for supervisor triggers.

    This is designed to be called from the scheduler daemon.
    """
    import redis.asyncio as aioredis

    runner = SupervisorDaemonRunner()

    redis_client = aioredis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password or None,
        decode_responses=True,
    )

    pubsub = redis_client.pubsub()
    await pubsub.subscribe(SCRAPE_COMPLETED_CHANNEL, MANUAL_TRIGGER_CHANNEL)

    logger.info("supervisor.listener_started")

    try:
        async for message in pubsub.listen():
            if shutdown_event and shutdown_event.is_set():
                break
            if message["type"] != "message":
                continue

            try:
                data = json.loads(message["data"])
                channel = message["channel"]

                if channel == SCRAPE_COMPLETED_CHANNEL:
                    # Auto diagnostic after scrape
                    portal_slug = data.get("portal_slug")
                    portal_id = data.get("portal_id")
                    job_id = data.get("job_id")
                    if portal_slug and portal_id:
                        asyncio.create_task(
                            runner.run_diagnostic(
                                portal_slug, portal_id, job_id, trigger="auto_post_scrape"
                            )
                        )

                elif channel == MANUAL_TRIGGER_CHANNEL:
                    # Manual diagnostic from UI
                    portal_slug = data.get("portal_slug")
                    portal_id = data.get("portal_id")
                    if portal_slug and portal_id:
                        asyncio.create_task(
                            runner.run_diagnostic(
                                portal_slug, portal_id, trigger="manual"
                            )
                        )

            except Exception:
                logger.exception("supervisor.listener_message_error")

    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe()
        await redis_client.aclose()
        logger.info("supervisor.listener_stopped")
