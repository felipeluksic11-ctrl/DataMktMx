"""Scraper runner — orchestrates scraping jobs end-to-end."""

import asyncio
import datetime

from sqlalchemy import select

from scrapers.base import BaseScraper
from scrapers.inmuebles24 import Inmuebles24Scraper
from scrapers.lamudi import LamudiScraper
from scrapers.propiedades import PropiedadesScraper
from scrapers.vivanuncios import VivanunciosScraper
from scrapers.storage import upsert_raw_listings
from scrapers.quality_check import check_quality
from shared.config import settings
from shared.db.models import Portal, ScrapeJob
from shared.db.session import get_engine, get_session_factory
from shared.logging import get_logger, setup_logging
from shared.proxy.manager import ProxyManager

logger = get_logger("scraper.runner")

# Registry of available scrapers
SCRAPER_REGISTRY: dict[str, type[BaseScraper]] = {
    "inmuebles24": Inmuebles24Scraper,
    "lamudi": LamudiScraper,
    "propiedades": PropiedadesScraper,
    "vivanuncios": VivanunciosScraper,
}


async def run_scraper(portal_slug: str, mode: str = "full", **kwargs) -> None:
    """Run a single scraper by portal slug.

    Args:
        portal_slug: which portal to scrape
        mode: "full" (all pages) or "incremental" (recent only, stop on known)
        **kwargs: passed to the scraper constructor (states, operations, etc.)
    """
    setup_logging()

    scraper_cls = SCRAPER_REGISTRY.get(portal_slug)
    if not scraper_cls:
        logger.error("runner.unknown_portal", slug=portal_slug)
        return

    session_factory = get_session_factory()
    proxy_manager = ProxyManager.from_settings()

    async with session_factory() as session:
        # Find portal
        stmt = select(Portal).where(Portal.slug == portal_slug)
        result = await session.execute(stmt)
        portal = result.scalar_one_or_none()

        if not portal:
            logger.error("runner.portal_not_found", slug=portal_slug)
            return

        if not portal.is_active:
            logger.warning("runner.portal_inactive", slug=portal_slug)
            return

        # For incremental mode: load known listings cache
        known_cache = None
        if mode == "incremental":
            from scrapers.base.known_listings import KnownListingsCache
            known_cache = KnownListingsCache()
            await known_cache.load(session, portal.id)
            logger.info("runner.incremental_mode", known=known_cache.total_known, portal=portal_slug)

        # Create scrape job
        job = ScrapeJob(portal_id=portal.id, status="running")
        job.started_at = datetime.datetime.now(datetime.UTC)
        job.metadata_ = {"mode": mode}
        session.add(job)
        await session.commit()
        await session.refresh(job)

        logger.info("runner.job_started", job_id=job.id, portal=portal_slug, mode=mode)

        try:
            # Accumulated stats across all pages
            total_stats = {"new": 0, "updated": 0, "errors": 0, "pages": 0}

            async def persist_page(page_items):
                """Callback: persist items to DB after each page.
                Uses a fresh session to avoid greenlet conflicts with Playwright.
                """
                async with session_factory() as persist_session:
                    page_stats = await upsert_raw_listings(
                        session=persist_session,
                        items=page_items,
                        portal_id=portal.id,
                        scrape_job_id=job.id,
                    )
                    total_stats["new"] += page_stats["new"]
                    total_stats["updated"] += page_stats["updated"]
                    total_stats["errors"] += page_stats["errors"]
                    total_stats["pages"] += 1

                    # Quality check every 10 pages
                    if total_stats["pages"] % 10 == 0:
                        await check_quality(persist_session, portal.id, portal_slug, job.id)

                return page_stats

            # Run scraper with per-page persistence
            scraper = scraper_cls(
                proxy_manager=proxy_manager,
                mode=mode,
                known_cache=known_cache,
                **kwargs,
            )
            scraper.on_page_scraped = persist_page
            items = await scraper.run(job)

            # Final job update
            job.total_scraped = total_stats["new"] + total_stats["updated"]
            job.total_new = total_stats["new"]
            job.total_updated = total_stats["updated"]
            job.total_errors = total_stats["errors"] + scraper.stats["errors"]
            job.status = "completed"
            job.finished_at = datetime.datetime.now(datetime.UTC)
            await session.commit()

            logger.info(
                "runner.job_completed",
                job_id=job.id,
                portal=portal_slug,
                **total_stats,
            )

        except Exception as e:
            job.status = "failed"
            job.error_detail = str(e)[:2000]
            job.total_errors = (job.total_errors or 0) + 1
            job.finished_at = datetime.datetime.now(datetime.UTC)
            await session.commit()
            logger.exception("runner.job_failed", job_id=job.id, portal=portal_slug)
            raise

    # Dispose engine
    engine = get_engine()
    await engine.dispose()


async def run_all_active(mode: str = "full", **kwargs) -> None:
    """Run scrapers for all active portals in parallel.

    Args:
        mode: "full" (all pages) or "incremental" (recent only, stop on known)
        **kwargs: passed to each scraper (e.g. visit_detail=False)
    """
    setup_logging()
    session_factory = get_session_factory()

    async with session_factory() as session:
        stmt = select(Portal).where(Portal.is_active.is_(True))
        result = await session.execute(stmt)
        portals = result.scalars().all()

    slugs = [p.slug for p in portals if p.slug in SCRAPER_REGISTRY]
    logger.info("runner.launching_parallel", portals=slugs, mode=mode)

    async def safe_run(slug: str):
        try:
            await run_scraper(slug, mode=mode, **kwargs)
        except Exception:
            logger.exception("runner.portal_error", slug=slug)

    await asyncio.gather(*[safe_run(slug) for slug in slugs])

    engine = get_engine()
    await engine.dispose()


def main() -> None:
    """CLI entry point.

    Usage:
        python -m scrapers                              # all active portals, full mode
        python -m scrapers --mode incremental            # all active portals, incremental
        python -m scrapers inmuebles24                   # single portal, full mode
        python -m scrapers inmuebles24 --mode incremental # single portal, incremental
    """
    import sys

    setup_logging()

    # Parse flags from argv
    args = sys.argv[1:]
    mode = "full"
    visit_detail = True

    if "--mode" in args:
        idx = args.index("--mode")
        if idx + 1 < len(args):
            mode = args[idx + 1]
            args = args[:idx] + args[idx + 2:]
        else:
            args = args[:idx]

    if "--no-detail" in args:
        visit_detail = False
        args.remove("--no-detail")

    portal_slug = args[0] if args else None
    kwargs = {"visit_detail": visit_detail}

    if portal_slug:
        logger.info("runner.starting_single", portal=portal_slug, mode=mode, visit_detail=visit_detail)
        asyncio.run(run_scraper(portal_slug, mode=mode, **kwargs))
    else:
        logger.info("runner.starting_all", mode=mode, visit_detail=visit_detail)
        asyncio.run(run_all_active(mode=mode, **kwargs))


if __name__ == "__main__":
    main()
