"""Dramatiq worker task — the unit of distributed scraping.

Each worker task:
1. Gets a unique identity (fingerprint, viewport, delays)
2. Gets a unique proxy session (different IP)
3. Scrapes its assigned states/pages
4. Writes results to the shared PostgreSQL
5. Reports health metrics back

Launched by the Orchestrator, one task per worker assignment.
"""

import asyncio
import datetime
import time

import dramatiq

import shared.dramatiq_broker  # noqa: F401 — configure broker before @dramatiq.actor
from shared.logging import get_logger, setup_logging

logger = get_logger("orchestrator.worker")


@dramatiq.actor(max_retries=1, time_limit=6 * 3600 * 1000)  # 6 hour max
def run_worker_task(
    plan_id: str,
    worker_id: str,
    portal_slug: str,
    operation: str,
    states: list[str],
    visit_detail: bool = True,
    max_pages: int = 50,
) -> dict:
    """Dramatiq actor — runs a scraping worker asynchronously."""
    setup_logging()
    return asyncio.run(
        _run_worker(plan_id, worker_id, portal_slug, operation, states, visit_detail, max_pages)
    )


async def _run_worker(
    plan_id: str,
    worker_id: str,
    portal_slug: str,
    operation: str,
    states: list[str],
    visit_detail: bool,
    max_pages: int,
) -> dict:
    """The actual async worker logic."""
    import random

    from scrapers.runner import SCRAPER_REGISTRY
    from scrapers.storage import upsert_raw_listings
    from shared.db.models import Portal, ScrapeJob, WorkPlan
    from shared.db.session import get_engine, get_session_factory
    from shared.proxy.manager import ProxyManager
    from shared.stealth.identity import create_identity
    from sqlalchemy import select

    start = time.time()
    logger.info("worker.starting", worker=worker_id, plan=plan_id, states=states, portal=portal_slug)

    # Create unique identity for this worker
    identity = create_identity(worker_id)

    # Create proxy session
    proxy_manager = ProxyManager.from_settings()
    proxy_session = None
    if proxy_manager.has_proxies:
        proxy_session = proxy_manager.create_session(worker_id)

    # Randomize state order (anti-correlation)
    shuffled_states = list(states)
    random.shuffle(shuffled_states)

    session_factory = get_session_factory()
    stats = {"scraped": 0, "new": 0, "updated": 0, "errors": 0}

    async with session_factory() as session:
        # Get portal
        stmt = select(Portal).where(Portal.slug == portal_slug)
        portal = (await session.execute(stmt)).scalar_one()

        # Create scrape job for this worker
        job = ScrapeJob(portal_id=portal.id, status="running")
        job.started_at = datetime.datetime.now(datetime.UTC)
        job.metadata_ = {"worker_id": worker_id, "plan_id": plan_id, "states": states}
        session.add(job)
        await session.commit()
        await session.refresh(job)

        try:
            # Create scraper from registry
            scraper_cls = SCRAPER_REGISTRY.get(portal_slug)
            if not scraper_cls:
                raise ValueError(f"No scraper registered for portal: {portal_slug}")

            scraper = scraper_cls(
                proxy_manager=proxy_manager,
                states=shuffled_states,
                operations=[operation],
                property_types=["all"],
                max_pages=max_pages,
                visit_detail=visit_detail,
            )

            items = await scraper.scrape()

            # Persist
            batch_stats = await upsert_raw_listings(
                session=session,
                items=items,
                portal_id=portal.id,
                scrape_job_id=job.id,
            )

            stats["scraped"] = len(items)
            stats["new"] = batch_stats["new"]
            stats["updated"] = batch_stats["updated"]
            stats["errors"] = batch_stats["errors"]

            job.status = "completed"
            job.total_scraped = stats["scraped"]
            job.total_new = stats["new"]
            job.total_updated = stats["updated"]
            job.total_errors = stats["errors"]

        except Exception as e:
            job.status = "failed"
            job.error_detail = str(e)[:2000]
            stats["errors"] += 1
            logger.exception("worker.failed", worker=worker_id)

        job.finished_at = datetime.datetime.now(datetime.UTC)
        await session.commit()

    duration = time.time() - start
    stats["duration_seconds"] = round(duration, 1)

    if proxy_manager.has_proxies:
        stats["proxy_stats"] = proxy_manager.get_stats()

    logger.info(
        "worker.completed",
        worker=worker_id,
        duration_s=round(duration, 1),
        **{k: v for k, v in stats.items() if k != "proxy_stats"},
    )

    engine = get_engine()
    await engine.dispose()
    return stats
