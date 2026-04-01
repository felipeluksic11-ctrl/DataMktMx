"""ETL Pipeline: raw_listings → clean_listings.

Steps:
1. Fetch all raw listings (or incremental since last run)
2. Normalize: state, municipality, neighborhood, property type, price
3. Calculate: price_mxn, price_usd, price_per_m2
4. Score: completeness + quality
5. Deduplicate across portals
6. Upsert into clean.clean_listings

This is deterministic — no LLM, no ML. Pure regex and rules.
"""

import datetime
import time
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from etl.catalogs import STATES
from etl.dedup.engine import DedupCluster, ListingForDedup, find_duplicates
from etl.normalizers.location import (
    normalize_municipality,
    normalize_neighborhood,
    normalize_state,
)
from etl.normalizers.price import calculate_price_per_m2, normalize_price
from etl.normalizers.property import normalize_operation, normalize_property_type
from etl.validators.quality import calculate_completeness, calculate_quality
from shared.db.models import CleanListing, RawListing
from shared.logging import get_logger

logger = get_logger("etl.pipeline")


async def run_pipeline(session: AsyncSession, full_rebuild: bool = False) -> dict:
    """Run the complete ETL pipeline.

    Args:
        session: async DB session
        full_rebuild: if True, process all raw listings. If False, only new/updated.

    Returns:
        dict with stats: processed, cleaned, duplicates, errors
    """
    start = time.time()
    stats = {"processed": 0, "cleaned": 0, "duplicates": 0, "errors": 0, "skipped": 0}

    logger.info("pipeline.starting", full_rebuild=full_rebuild)

    # Step 1: Fetch raw listings
    if full_rebuild:
        # Delete all clean listings first
        await session.execute(text("DELETE FROM clean.clean_listings"))
        stmt = select(RawListing)
    else:
        # Only listings not yet in clean
        stmt = select(RawListing).where(
            ~RawListing.id.in_(
                select(CleanListing.raw_listing_id)
            )
        )

    result = await session.execute(stmt)
    raw_listings = result.scalars().all()

    if not raw_listings:
        logger.info("pipeline.no_new_listings")
        return stats

    logger.info("pipeline.fetched_raw", count=len(raw_listings))

    # Step 2-4: Normalize, calculate, score each listing
    clean_data: list[dict] = []
    dedup_input: list[ListingForDedup] = []

    # Get portal slugs for dedup
    portal_slugs: dict[str, str] = {}
    portal_result = await session.execute(text("SELECT id, slug FROM portals"))
    for row in portal_result:
        portal_slugs[str(row[0])] = row[1]

    for raw in raw_listings:
        stats["processed"] += 1
        try:
            cleaned = _normalize_listing(raw)
            if cleaned is None:
                stats["skipped"] += 1
                continue

            clean_data.append(cleaned)

            # Prepare dedup input
            dedup_input.append(ListingForDedup(
                id=raw.id,
                portal_slug=portal_slugs.get(raw.portal_id, "unknown"),
                state_code=cleaned["state_code"],
                municipality=cleaned["municipality"],
                neighborhood=cleaned["neighborhood"],
                price_mxn=cleaned["price_mxn"],
                property_type=cleaned["property_type"],
                construction_m2=cleaned.get("construction_m2"),
                land_m2=cleaned.get("land_m2"),
                bedrooms=cleaned.get("bedrooms"),
                street=raw.street_and_number,
                completeness=cleaned["completeness"],
            ))

        except Exception:
            stats["errors"] += 1
            logger.exception("pipeline.normalize_error", raw_id=raw.id)

    logger.info("pipeline.normalized", clean=len(clean_data), errors=stats["errors"], skipped=stats["skipped"])

    # Step 5: Deduplication
    clusters = find_duplicates(dedup_input)
    stats["duplicates"] = sum(len(c.listings) - 1 for c in clusters)

    # Build cluster lookup: raw_listing_id → cluster_id
    cluster_map: dict[str, str] = {}
    source_count_map: dict[str, int] = {}
    for cluster in clusters:
        for listing in cluster.listings:
            cluster_map[listing.id] = cluster.cluster_id
            source_count_map[listing.id] = cluster.source_count

    # Step 6: Upsert into clean_listings
    for cleaned in clean_data:
        raw_id = cleaned["raw_listing_id"]
        try:
            clean_listing = CleanListing(
                raw_listing_id=raw_id,
                property_type=cleaned["property_type"] or "unknown",
                listing_type=cleaned["operation"] or "unknown",
                dedup_cluster_id=cluster_map.get(raw_id),
                price_mxn=cleaned.get("price_mxn"),
                price_usd=cleaned.get("price_usd"),
                state_code=cleaned.get("state_code"),
                state_name=cleaned.get("state_name"),
                city_norm=cleaned.get("city"),
                colony_norm=cleaned.get("neighborhood"),
                zip_code=cleaned.get("zip_code"),
                bedrooms=cleaned.get("bedrooms"),
                bathrooms=cleaned.get("bathrooms"),
                parking_spaces=cleaned.get("parking_spaces"),
                construction_m2=cleaned.get("construction_m2"),
                land_m2=cleaned.get("land_m2"),
                price_per_m2=cleaned.get("price_per_m2"),
                quality_score=cleaned.get("quality_score"),
                completeness=cleaned.get("completeness"),
                source_count=source_count_map.get(raw_id, 1),
                amenities=cleaned.get("amenities"),
            )
            session.add(clean_listing)
            stats["cleaned"] += 1
        except Exception:
            stats["errors"] += 1
            logger.exception("pipeline.insert_error", raw_id=raw_id)

    await session.commit()

    duration = time.time() - start
    stats["duration_seconds"] = round(duration, 1)

    logger.info(
        "pipeline.completed",
        duration_s=round(duration, 1),
        **{k: v for k, v in stats.items() if k != "duration_seconds"},
    )

    return stats


def _normalize_listing(raw: RawListing) -> dict | None:
    """Normalize a single raw listing into clean data. Returns None to skip."""

    # State
    state_code, state_name = normalize_state(raw.state)

    # Municipality
    municipality, zip_from_muni = normalize_municipality(raw.municipality, state_code)

    # Neighborhood
    neighborhood = normalize_neighborhood(raw.neighborhood)

    # Zip code (from raw, or extracted from municipality address)
    zip_code = raw.zip_code or zip_from_muni

    # Property type
    property_type = normalize_property_type(raw.property_type)

    # Operation
    operation = normalize_operation(raw.operation)

    # Price
    price_mxn, price_usd = normalize_price(raw.price, raw.currency, operation)

    # Skip listings without price or state — too incomplete
    if price_mxn is None and price_usd is None:
        return None

    # Price per m2
    price_per_m2 = calculate_price_per_m2(price_mxn, raw.construction_m2, raw.land_m2)

    # Build clean data dict
    data = {
        "raw_listing_id": raw.id,
        "property_type": property_type,
        "operation": operation,
        "price_mxn": price_mxn,
        "price_usd": price_usd,
        "state_code": state_code,
        "state_name": state_name,
        "city": state_name,  # For now, city = state (will improve with more granular data)
        "municipality": municipality,
        "neighborhood": neighborhood,
        "zip_code": zip_code,
        "bedrooms": raw.bedrooms,
        "bathrooms": raw.bathrooms,
        "parking_spaces": raw.parking_spaces,
        "construction_m2": raw.construction_m2,
        "land_m2": raw.land_m2,
        "price_per_m2": price_per_m2,
        "description": raw.description,
        "title": raw.title,
        "images_count": raw.images_count,
        "latitude": None,  # from geom
        "amenities": None,
    }

    # Completeness & quality
    data["completeness"] = calculate_completeness(data)
    data["quality_score"] = calculate_quality(data)

    return data
