"""Persist scraped items to raw_listings table."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from scrapers.base import ScrapedItem
from shared.db.models import RawListing
from shared.logging import get_logger

logger = get_logger("scraper.storage")

# All ScrapedItem fields that map directly to RawListing columns
_DIRECT_FIELDS = [
    "url_listing", "internal_code", "title", "description",
    "operation", "property_type",
    "price", "currency", "maintenance_fee",
    "street_and_number", "neighborhood", "city", "municipality",
    "state", "country", "zip_code",
    "video_url", "tour_360_url", "images_count",
    "land_m2", "construction_m2",
    "antiquity", "construction_years",
    "bedrooms", "bathrooms", "half_bathrooms", "parking_spaces",
    "extra_rooms", "services", "amenities", "exteriors", "extras",
    "conservation_status",
    "has_balcony", "has_elevator", "has_storage",
    "built_levels", "minimum_stay", "availability",
    "raw_json",
]


async def upsert_raw_listings(
    session: AsyncSession,
    items: list[ScrapedItem],
    portal_id: str,
    scrape_job_id: str | None = None,
) -> dict[str, int]:
    """Insert or update raw listings. Returns counts of new/updated/errors."""
    stats = {"new": 0, "updated": 0, "errors": 0}

    for item in items:
        try:
            stmt = select(RawListing).where(
                RawListing.portal_id == portal_id,
                RawListing.external_id == item.external_id,
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                # Update: overwrite only non-None fields from the new scrape
                for field in _DIRECT_FIELDS:
                    new_val = getattr(item, field, None)
                    if new_val is not None:
                        setattr(existing, field, new_val)
                existing.scrape_job_id = scrape_job_id or existing.scrape_job_id
                stats["updated"] += 1
            else:
                kwargs = {
                    "portal_id": portal_id,
                    "scrape_job_id": scrape_job_id,
                    "external_id": item.external_id,
                }
                for field in _DIRECT_FIELDS:
                    kwargs[field] = getattr(item, field, None)

                listing = RawListing(**kwargs)
                session.add(listing)
                stats["new"] += 1

        except Exception:
            stats["errors"] += 1
            await session.rollback()
            logger.exception("storage.upsert_error", external_id=item.external_id)

    await session.commit()
    logger.info("storage.batch_done", **stats)
    return stats
