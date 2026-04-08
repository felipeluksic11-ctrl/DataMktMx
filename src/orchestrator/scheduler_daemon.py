"""Scheduler Daemon — long-running process that replaces cron.

Reads schedule_configs from DB, computes next_run_at, and executes
scrapers at the right times. Supports manual triggers via Redis pub/sub.

Usage:
    python -m orchestrator.scheduler_daemon

Docker Compose:
    command: python -m orchestrator.scheduler_daemon
"""

import asyncio
import datetime
import json
import os
import signal
import sys

from croniter import croniter
from sqlalchemy import select, update

from orchestrator.schedule_queue import (
    QueueEntry,
    compute_retry_delay,
    is_rate_limited,
    sort_by_priority,
)
from scrapers.runner import run_enrichment, run_scraper
from shared.audit import log_audit
from shared.config import settings
from shared.db.models import Portal, ScrapeJob
from shared.db.models.schedule_config import ScheduleConfig
from shared.db.models.schedule_run import ScheduleRun
from shared.db.session import get_engine, get_session_factory
from shared.logging import get_logger, setup_logging
from shared.proxy.bandwidth import create_tracker

logger = get_logger("scheduler.daemon")

# Configurable via env
POLL_INTERVAL_S = int(os.environ.get("SCHEDULER_POLL_INTERVAL", "30"))
MAX_CONCURRENT = int(os.environ.get("SCHEDULER_MAX_CONCURRENT", "3"))
REDIS_CHANNEL = "scheduler:trigger"
SUPERVISOR_CHANNEL = "supervisor:scrape_completed"


class SchedulerDaemon:
    """Main scheduler daemon that replaces cron."""

    def __init__(self):
        self._session_factory = get_session_factory()
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        self._running_tasks: dict[str, asyncio.Task] = {}  # schedule_id -> task
        self._shutdown = False
        self._redis = None

    async def start(self):
        """Main entry point — runs until SIGTERM."""
        setup_logging()
        logger.info(
            "scheduler.starting",
            max_concurrent=MAX_CONCURRENT,
            poll_interval=POLL_INTERVAL_S,
        )

        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._handle_shutdown)

        # Acquire Redis lock (single instance enforcement)
        await self._acquire_lock()

        # Initialize next_run_at for all schedules
        await self._init_schedules()

        # Start Redis listener for manual triggers
        listener_task = asyncio.create_task(self._redis_listener())

        # Start supervisor daemon listener
        from supervisors.supervisor_daemon import start_supervisor_listener
        self._shutdown_event = asyncio.Event()
        supervisor_listener = asyncio.create_task(start_supervisor_listener(self._shutdown_event))

        # Main loop
        try:
            while not self._shutdown:
                await self._tick()
                await asyncio.sleep(POLL_INTERVAL_S)
        except asyncio.CancelledError:
            pass
        finally:
            logger.info("scheduler.shutting_down", running=len(self._running_tasks))
            # Wait for in-progress scrapes
            if self._running_tasks:
                logger.info("scheduler.waiting_for_tasks", count=len(self._running_tasks))
                await asyncio.gather(*self._running_tasks.values(), return_exceptions=True)
            listener_task.cancel()
            supervisor_listener.cancel()
            await self._release_lock()
            engine = get_engine()
            await engine.dispose()
            logger.info("scheduler.stopped")

    def _handle_shutdown(self):
        """Signal handler for graceful shutdown."""
        logger.info("scheduler.signal_received")
        self._shutdown = True
        if hasattr(self, '_shutdown_event'):
            self._shutdown_event.set()

    async def _acquire_lock(self):
        """Acquire Redis distributed lock to ensure single instance."""
        import redis.asyncio as aioredis

        self._redis = aioredis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password or None,
            decode_responses=True,
        )
        # Try to acquire lock with 5-minute TTL (refreshed each tick)
        acquired = await self._redis.set("scheduler:lock", "1", nx=True, ex=300)
        if not acquired:
            logger.error("scheduler.lock_held", msg="Another scheduler instance is running")
            sys.exit(1)
        logger.info("scheduler.lock_acquired")

    async def _release_lock(self):
        """Release Redis lock."""
        if self._redis:
            await self._redis.delete("scheduler:lock")
            await self._redis.aclose()

    async def _refresh_lock(self):
        """Refresh lock TTL to keep ownership."""
        if self._redis:
            await self._redis.expire("scheduler:lock", 300)

    async def _init_schedules(self):
        """Compute next_run_at for all enabled schedules on startup."""
        async with self._session_factory() as session:
            stmt = select(ScheduleConfig).where(ScheduleConfig.is_enabled.is_(True))
            result = await session.execute(stmt)
            schedules = result.scalars().all()

            now = datetime.datetime.now(datetime.UTC)
            for sched in schedules:
                if sched.next_run_at is None:
                    cron = croniter(sched.cron_expression, now)
                    sched.next_run_at = cron.get_next(datetime.datetime).replace(
                        tzinfo=datetime.UTC
                    )
            await session.commit()

        logger.info("scheduler.init_complete", schedules=len(schedules))

    async def _tick(self):
        """One iteration of the main loop."""
        await self._refresh_lock()
        now = datetime.datetime.now(datetime.UTC)

        # Load due schedules
        async with self._session_factory() as session:
            stmt = (
                select(ScheduleConfig, Portal)
                .join(Portal, ScheduleConfig.portal_id == Portal.id)
                .where(
                    ScheduleConfig.is_enabled.is_(True),
                    ScheduleConfig.next_run_at <= now,
                    Portal.is_active.is_(True),
                )
            )
            result = await session.execute(stmt)
            rows = result.all()

        if not rows:
            return

        # Build queue entries
        candidates = []
        for sched, portal in rows:
            # Skip if rate limited
            if is_rate_limited(sched.last_run_at, sched.rate_limit_s, now):
                continue
            # Skip if already running
            if sched.id in self._running_tasks:
                continue

            candidates.append(
                QueueEntry(
                    schedule_id=sched.id,
                    portal_slug=portal.slug,
                    portal_id=portal.id,
                    mode=sched.mode,
                    budget_mb=sched.budget_mb,
                    states=sched.states,
                    visit_detail=sched.visit_detail,
                    priority=sched.priority,
                    cron_expression=sched.cron_expression,
                    max_retries=sched.max_retries,
                    retry_backoff_s=sched.retry_backoff_s,
                )
            )

        if not candidates:
            return

        # Sort by priority and launch
        queue = sort_by_priority(candidates)
        for entry in queue:
            if self._shutdown:
                break
            task = asyncio.create_task(self._execute(entry))
            self._running_tasks[entry.schedule_id] = task

    async def _execute(self, entry: QueueEntry):
        """Execute a single schedule entry with semaphore control."""
        async with self._semaphore:
            await self._run_schedule(entry)

    async def _run_schedule(self, entry: QueueEntry):
        """Run a schedule: create run record, execute scraper, update state."""
        schedule_run = None
        try:
            # Create schedule_run record
            async with self._session_factory() as session:
                schedule_run = ScheduleRun(
                    schedule_id=entry.schedule_id,
                    trigger=entry.trigger,
                    status="running",
                    retry_count=entry.retry_count,
                )
                schedule_run.started_at = datetime.datetime.now(datetime.UTC)
                session.add(schedule_run)
                await session.commit()
                await session.refresh(schedule_run)

            logger.info(
                "scheduler.run_starting",
                schedule_id=entry.schedule_id,
                portal=entry.portal_slug,
                mode=entry.mode,
                budget_mb=entry.budget_mb,
                trigger=entry.trigger,
            )

            # Create independent bandwidth tracker
            tracker = create_tracker(budget_mb=entry.budget_mb)

            # Execute the scrape
            kwargs = {
                "visit_detail": entry.visit_detail,
                "_dispose_engine": False,  # scheduler manages engine lifecycle
            }
            if entry.states:
                kwargs["states"] = entry.states

            if entry.mode == "enrich":
                job = await run_enrichment(
                    entry.portal_slug,
                    tracker=tracker,
                    **kwargs,
                )
            else:
                job = await run_scraper(
                    entry.portal_slug,
                    mode=entry.mode,
                    tracker=tracker,
                    **kwargs,
                )

            # Update schedule_run with results
            async with self._session_factory() as session:
                stmt = select(ScheduleRun).where(ScheduleRun.id == schedule_run.id)
                result = await session.execute(stmt)
                run = result.scalar_one()
                run.status = "completed"
                run.finished_at = datetime.datetime.now(datetime.UTC)
                if job:
                    run.scrape_job_id = job.id

                # Update schedule_config
                stmt2 = select(ScheduleConfig).where(ScheduleConfig.id == entry.schedule_id)
                result2 = await session.execute(stmt2)
                sched = result2.scalar_one()
                sched.last_run_at = datetime.datetime.now(datetime.UTC)
                sched.last_run_status = job.status if job else "completed"
                sched.run_count = (sched.run_count or 0) + 1
                # Compute next run
                cron = croniter(sched.cron_expression, datetime.datetime.now(datetime.UTC))
                sched.next_run_at = cron.get_next(datetime.datetime).replace(
                    tzinfo=datetime.UTC
                )

                # Audit log
                bw_stats = tracker.get_stats()
                await log_audit(
                    session,
                    entity_type="schedule",
                    entity_id=entry.schedule_id,
                    action="completed",
                    summary=f"{entry.portal_slug} {entry.mode} completed: "
                    f"{job.total_new if job else 0} new, "
                    f"{job.total_scraped if job else 0} total, "
                    f"{bw_stats['total_mb']:.1f} MB used",
                    actor="scheduler",
                    is_automatic=True,
                    metadata={
                        "job_id": job.id if job else None,
                        "bandwidth": bw_stats,
                        "trigger": entry.trigger,
                    },
                )
                await session.commit()

            logger.info(
                "scheduler.run_completed",
                schedule_id=entry.schedule_id,
                portal=entry.portal_slug,
                mode=entry.mode,
                job_status=job.status if job else "no_job",
            )

            # Notify supervisor daemon
            await self._notify_supervisor(entry.portal_slug, entry.portal_id, job)

        except Exception as exc:
            error_msg = str(exc)[:2000]
            logger.exception(
                "scheduler.run_failed",
                schedule_id=entry.schedule_id,
                portal=entry.portal_slug,
            )

            # Update run as failed
            if schedule_run:
                async with self._session_factory() as session:
                    stmt = select(ScheduleRun).where(ScheduleRun.id == schedule_run.id)
                    result = await session.execute(stmt)
                    run = result.scalar_one()
                    run.status = "failed"
                    run.error_detail = error_msg
                    run.finished_at = datetime.datetime.now(datetime.UTC)

                    # Update schedule_config
                    stmt2 = select(ScheduleConfig).where(
                        ScheduleConfig.id == entry.schedule_id
                    )
                    result2 = await session.execute(stmt2)
                    sched = result2.scalar_one()
                    sched.last_run_at = datetime.datetime.now(datetime.UTC)
                    sched.last_run_status = "failed"
                    # Still compute next run
                    cron = croniter(
                        sched.cron_expression, datetime.datetime.now(datetime.UTC)
                    )
                    sched.next_run_at = cron.get_next(datetime.datetime).replace(
                        tzinfo=datetime.UTC
                    )

                    # Audit log
                    await log_audit(
                        session,
                        entity_type="schedule",
                        entity_id=entry.schedule_id,
                        action="failed",
                        summary=f"{entry.portal_slug} {entry.mode} failed: {error_msg[:200]}",
                        actor="scheduler",
                        is_automatic=True,
                        is_success=False,
                        metadata={"trigger": entry.trigger, "error": error_msg},
                    )
                    await session.commit()

            # Schedule retry if within limits
            if entry.retry_count < entry.max_retries:
                delay = compute_retry_delay(entry.retry_backoff_s, entry.retry_count)
                logger.info(
                    "scheduler.retry_queued",
                    schedule_id=entry.schedule_id,
                    retry_count=entry.retry_count + 1,
                    delay_s=delay,
                )
                await asyncio.sleep(delay)
                retry_entry = QueueEntry(
                    schedule_id=entry.schedule_id,
                    portal_slug=entry.portal_slug,
                    portal_id=entry.portal_id,
                    mode=entry.mode,
                    budget_mb=entry.budget_mb,
                    states=entry.states,
                    visit_detail=entry.visit_detail,
                    priority=entry.priority,
                    cron_expression=entry.cron_expression,
                    max_retries=entry.max_retries,
                    retry_backoff_s=entry.retry_backoff_s,
                    trigger="retry",
                    retry_count=entry.retry_count + 1,
                )
                task = asyncio.create_task(self._execute(retry_entry))
                self._running_tasks[f"{entry.schedule_id}_retry_{entry.retry_count + 1}"] = task

        finally:
            # Remove from running tasks
            self._running_tasks.pop(entry.schedule_id, None)

    async def _notify_supervisor(self, portal_slug: str, portal_id: str, job: ScrapeJob | None):
        """Publish notification for supervisor daemon."""
        if self._redis and job:
            try:
                await self._redis.publish(
                    SUPERVISOR_CHANNEL,
                    json.dumps({
                        "portal_slug": portal_slug,
                        "portal_id": portal_id,
                        "job_id": job.id,
                        "job_status": job.status,
                    }),
                )
            except Exception:
                logger.warning("scheduler.supervisor_notify_failed", portal=portal_slug)

    async def _redis_listener(self):
        """Listen for manual trigger requests from the API."""
        import redis.asyncio as aioredis

        try:
            sub = aioredis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                password=settings.redis_password or None,
                decode_responses=True,
            )
            pubsub = sub.pubsub()
            await pubsub.subscribe(REDIS_CHANNEL)

            async for message in pubsub.listen():
                if self._shutdown:
                    break
                if message["type"] != "message":
                    continue

                try:
                    data = json.loads(message["data"])
                    schedule_id = data.get("schedule_id")
                    if not schedule_id:
                        continue

                    logger.info("scheduler.manual_trigger", schedule_id=schedule_id)

                    # Load the schedule
                    async with self._session_factory() as session:
                        stmt = (
                            select(ScheduleConfig, Portal)
                            .join(Portal, ScheduleConfig.portal_id == Portal.id)
                            .where(ScheduleConfig.id == schedule_id)
                        )
                        result = await session.execute(stmt)
                        row = result.one_or_none()

                    if not row:
                        logger.warning("scheduler.manual_not_found", schedule_id=schedule_id)
                        continue

                    sched, portal = row
                    entry = QueueEntry(
                        schedule_id=sched.id,
                        portal_slug=portal.slug,
                        portal_id=portal.id,
                        mode=sched.mode,
                        budget_mb=sched.budget_mb,
                        states=sched.states,
                        visit_detail=sched.visit_detail,
                        priority=100,  # manual triggers get highest priority
                        cron_expression=sched.cron_expression,
                        max_retries=sched.max_retries,
                        retry_backoff_s=sched.retry_backoff_s,
                        trigger="manual",
                    )
                    task = asyncio.create_task(self._execute(entry))
                    self._running_tasks[sched.id] = task

                except Exception:
                    logger.exception("scheduler.manual_trigger_error")

            await pubsub.unsubscribe(REDIS_CHANNEL)
            await sub.aclose()
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("scheduler.redis_listener_error")

async def main():
    daemon = SchedulerDaemon()
    await daemon.start()


if __name__ == "__main__":
    asyncio.run(main())
