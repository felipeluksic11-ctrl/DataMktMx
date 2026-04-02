"""Scraper runner — orchestrates scraping jobs end-to-end."""

import asyncio
import datetime

from sqlalchemy import select, or_, and_

from scrapers.base import BaseScraper
from scrapers.inmuebles24 import Inmuebles24Scraper
from scrapers.lamudi import LamudiScraper
from scrapers.propiedades import PropiedadesScraper
from scrapers.vivanuncios import VivanunciosScraper
from scrapers.storage import upsert_raw_listings
from shared.db.models import RawListing
from scrapers.quality_check import check_quality
from shared.config import settings
from shared.db.models import Portal, ScrapeJob
from shared.db.session import get_engine, get_session_factory
from shared.logging import get_logger, setup_logging
from shared.proxy.bandwidth import BandwidthTracker, BudgetExhausted
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

    # Get bandwidth tracker (already initialized in main() with correct budget)
    tracker = BandwidthTracker.get_instance()
    logger.info(
        "runner.budget_set",
        budget_mb=tracker.budget_mb,
        portal=portal_slug,
    )

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

            # Run supervisor check if API key is configured
            if settings.anthropic_api_key:
                try:
                    from supervisors.scrape_supervisor import ScrapeSupervisor
                    async with session_factory() as q_session:
                        quality = await check_quality(q_session, portal.id, portal_slug, job.id)
                    if quality.get("warnings"):
                        supervisor = ScrapeSupervisor()
                        await supervisor.check_and_repair(
                            portal_slug, portal.id, quality
                        )
                except Exception:
                    logger.exception("runner.supervisor_error", portal=portal_slug)

        except BudgetExhausted as e:
            # Budget exceeded — save what we have, don't raise
            job.total_scraped = total_stats["new"] + total_stats["updated"]
            job.total_new = total_stats["new"]
            job.total_updated = total_stats["updated"]
            job.total_errors = total_stats["errors"]
            job.status = "stopped_budget"
            job.error_detail = str(e)
            job.finished_at = datetime.datetime.now(datetime.UTC)
            await session.commit()
            tracker.log_summary()
            logger.warning(
                "runner.budget_stop",
                job_id=job.id,
                portal=portal_slug,
                used_mb=e.used_mb,
                budget_mb=e.budget_mb,
                items_saved=job.total_scraped,
            )

        except Exception as e:
            job.status = "failed"
            job.error_detail = str(e)[:2000]
            job.total_errors = (job.total_errors or 0) + 1
            job.finished_at = datetime.datetime.now(datetime.UTC)
            await session.commit()
            tracker.log_summary()
            logger.exception("runner.job_failed", job_id=job.id, portal=portal_slug)
            raise

    # Log final bandwidth stats
    tracker.log_summary()

    # Dispose engine
    engine = get_engine()
    await engine.dispose()


async def run_enrichment(portal_slug: str, **kwargs) -> None:
    """Enrich incomplete listings by visiting their detail pages.

    Only visits listings that are missing key fields (construction_m2,
    description, amenities). This is Phase 2 of the scraping strategy.

    Much cheaper than full detail scraping: only visits listings that
    actually need enrichment instead of all listings.
    """
    setup_logging()

    # Get bandwidth tracker (already initialized in main() with correct budget)
    tracker = BandwidthTracker.get_instance()
    logger.info("runner.enrich_start", portal=portal_slug, budget_mb=tracker.budget_mb)

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

        # Query listings missing key detail fields
        stmt = (
            select(RawListing.external_id, RawListing.url_listing)
            .where(
                RawListing.portal_id == portal.id,
                RawListing.url_listing.is_not(None),
                or_(
                    RawListing.construction_m2.is_(None),
                    RawListing.description.is_(None),
                    and_(
                        RawListing.amenities.is_(None),
                        RawListing.services.is_(None),
                    ),
                ),
            )
            .order_by(RawListing.last_seen_at.desc())
        )
        result = await session.execute(stmt)
        incomplete = result.all()

        if not incomplete:
            logger.info("runner.enrich_nothing", portal=portal_slug)
            return

        logger.info(
            "runner.enrich_found",
            portal=portal_slug,
            incomplete_count=len(incomplete),
        )

        # Create enrichment job
        job = ScrapeJob(portal_id=portal.id, status="running")
        job.started_at = datetime.datetime.now(datetime.UTC)
        job.metadata_ = {"mode": "enrich", "target_count": len(incomplete)}
        session.add(job)
        await session.commit()
        await session.refresh(job)

    # Build list of (external_id, url) tuples
    enrich_targets = [(row.external_id, row.url_listing) for row in incomplete]

    # Import the portal's detail parser
    if portal_slug == "inmuebles24":
        from scrapers.inmuebles24.parser import parse_detail_page
        from scrapers.inmuebles24 import config as portal_config
    elif portal_slug == "propiedades":
        from scrapers.propiedades.parser import parse_detail_page
        from scrapers.propiedades import config as portal_config
    elif portal_slug == "lamudi":
        from scrapers.lamudi.parser import parse_detail_page
        from scrapers.lamudi import config as portal_config
    elif portal_slug == "vivanuncios":
        from scrapers.inmuebles24.parser import parse_detail_page
        from scrapers.vivanuncios import config as portal_config
    else:
        logger.error("runner.enrich_no_parser", portal=portal_slug)
        return

    # Create a scraper instance for browser management
    scraper = scraper_cls(proxy_manager=proxy_manager, visit_detail=False)
    total_stats = {"enriched": 0, "errors": 0, "skipped": 0}

    try:
        import random

        await scraper._init_browser_for_state()

        for i, (ext_id, detail_url) in enumerate(enrich_targets):
            # Budget check
            tracker.check_budget()

            # Rotate session periodically
            await scraper._maybe_rotate()

            page = await scraper._current_context.new_page()
            try:
                response = await page.goto(
                    detail_url,
                    wait_until="domcontentloaded",
                    timeout=15000,
                )

                if not response or response.status >= 400:
                    total_stats["skipped"] += 1
                    continue

                # Parse detail page
                partial = {"external_id": ext_id, "url_listing": detail_url}
                item = await parse_detail_page(page, partial)

                # Persist enriched data
                async with session_factory() as persist_session:
                    await upsert_raw_listings(
                        session=persist_session,
                        items=[item],
                        portal_id=portal.id,
                        scrape_job_id=job.id,
                    )
                total_stats["enriched"] += 1
                scraper._pages_since_rotation += 1

                # Log progress every 50 items
                if (i + 1) % 50 == 0:
                    bw = tracker.get_stats()
                    logger.info(
                        "runner.enrich_progress",
                        portal=portal_slug,
                        done=i + 1,
                        total=len(enrich_targets),
                        enriched=total_stats["enriched"],
                        bandwidth_mb=bw["total_mb"],
                        remaining_mb=bw["budget_remaining_mb"],
                    )

                # Delay between detail visits
                await asyncio.sleep(random.uniform(1.0, 3.0))

            except BudgetExhausted:
                raise
            except Exception:
                total_stats["errors"] += 1
                scraper.logger.exception("runner.enrich_error", url=detail_url)
            finally:
                await page.close()

    except BudgetExhausted as e:
        tracker.log_summary()
        logger.warning(
            "runner.enrich_budget_stop",
            portal=portal_slug,
            enriched=total_stats["enriched"],
            used_mb=e.used_mb,
        )
    except Exception:
        logger.exception("runner.enrich_failed", portal=portal_slug)
    finally:
        await scraper._close_browser()

    # Update job
    async with session_factory() as session:
        stmt = select(ScrapeJob).where(ScrapeJob.id == job.id)
        result = await session.execute(stmt)
        job = result.scalar_one()
        job.total_scraped = total_stats["enriched"]
        job.total_errors = total_stats["errors"]
        job.status = "completed"
        job.finished_at = datetime.datetime.now(datetime.UTC)
        job.metadata_ = {
            "mode": "enrich",
            "target_count": len(enrich_targets),
            **total_stats,
        }
        await session.commit()

    tracker.log_summary()
    logger.info(
        "runner.enrich_done",
        portal=portal_slug,
        **total_stats,
        target_count=len(enrich_targets),
    )

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

    enrich = False
    if "--enrich" in args:
        enrich = True
        args.remove("--enrich")

    if "--no-detail" in args:
        visit_detail = False
        args.remove("--no-detail")

    states = None
    if "--states" in args:
        idx = args.index("--states")
        if idx + 1 < len(args):
            states = [s.strip() for s in args[idx + 1].split(",")]
            args = args[:idx] + args[idx + 2:]
        else:
            args = args[:idx]

    budget_mb = None
    if "--budget" in args:
        idx = args.index("--budget")
        if idx + 1 < len(args):
            budget_mb = float(args[idx + 1])
            args = args[:idx] + args[idx + 2:]
        else:
            args = args[:idx]

    # Initialize bandwidth tracker with CLI budget or settings default
    BandwidthTracker.get_instance(budget_mb=budget_mb or settings.proxy_budget_mb)

    portal_slug = args[0] if args else None
    kwargs = {"visit_detail": visit_detail}
    if states:
        kwargs["states"] = states

    if enrich:
        if not portal_slug:
            logger.error("runner.enrich_requires_portal")
            return
        logger.info("runner.starting_enrich", portal=portal_slug, budget_mb=budget_mb)
        asyncio.run(run_enrichment(portal_slug))
    elif portal_slug:
        logger.info("runner.starting_single", portal=portal_slug, mode=mode, visit_detail=visit_detail, states=states, budget_mb=budget_mb)
        asyncio.run(run_scraper(portal_slug, mode=mode, **kwargs))
    else:
        logger.info("runner.starting_all", mode=mode, visit_detail=visit_detail, budget_mb=budget_mb)
        asyncio.run(run_all_active(mode=mode, **kwargs))


if __name__ == "__main__":
    main()
