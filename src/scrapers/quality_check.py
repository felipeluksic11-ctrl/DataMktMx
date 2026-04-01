"""Data quality supervisor — checks extraction quality periodically.

Runs every N pages and logs fill rates per field. Flags portals where
key fields fall below expected thresholds.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.logging import get_logger

logger = get_logger("scraper.quality")

# Minimum expected fill rates per field (0-100%)
THRESHOLDS = {
    "title": 90,
    "price": 85,
    "operation": 95,
    "property_type": 70,
    "neighborhood": 50,
    "municipality": 80,
    "state": 95,
    "bedrooms": 40,
    "bathrooms": 40,
    "construction_m2": 20,
    "land_m2": 20,
}


async def check_quality(
    session: AsyncSession,
    portal_id: str,
    portal_slug: str,
    scrape_job_id: str | None = None,
) -> dict:
    """Check data quality for a portal's recent listings.

    Returns dict with fill rates and any warnings.
    """
    # Build WHERE clause
    where = "portal_id = :portal_id"
    params: dict = {"portal_id": portal_id}
    if scrape_job_id:
        where += " AND scrape_job_id = :job_id"
        params["job_id"] = scrape_job_id

    query = text(f"""
        SELECT
            COUNT(*) as total,
            ROUND(100.0 * COUNT(title) / NULLIF(COUNT(*), 0), 1) as title,
            ROUND(100.0 * COUNT(price) / NULLIF(COUNT(*), 0), 1) as price,
            ROUND(100.0 * COUNT(operation) / NULLIF(COUNT(*), 0), 1) as operation,
            ROUND(100.0 * COUNT(property_type) / NULLIF(COUNT(*), 0), 1) as property_type,
            ROUND(100.0 * COUNT(neighborhood) / NULLIF(COUNT(*), 0), 1) as neighborhood,
            ROUND(100.0 * COUNT(municipality) / NULLIF(COUNT(*), 0), 1) as municipality,
            ROUND(100.0 * COUNT(state) / NULLIF(COUNT(*), 0), 1) as state,
            ROUND(100.0 * COUNT(bedrooms) / NULLIF(COUNT(*), 0), 1) as bedrooms,
            ROUND(100.0 * COUNT(bathrooms) / NULLIF(COUNT(*), 0), 1) as bathrooms,
            ROUND(100.0 * COUNT(construction_m2) / NULLIF(COUNT(*), 0), 1) as construction_m2,
            ROUND(100.0 * COUNT(land_m2) / NULLIF(COUNT(*), 0), 1) as land_m2,
            ROUND(100.0 * COUNT(parking_spaces) / NULLIF(COUNT(*), 0), 1) as parking_spaces
        FROM raw.raw_listings
        WHERE {where}
    """)

    result = await session.execute(query, params)
    row = result.mappings().first()

    if not row or row["total"] == 0:
        return {"total": 0, "warnings": []}

    fill_rates = {
        "total": int(row["total"]),
        "title": float(row["title"] or 0),
        "price": float(row["price"] or 0),
        "operation": float(row["operation"] or 0),
        "property_type": float(row["property_type"] or 0),
        "neighborhood": float(row["neighborhood"] or 0),
        "municipality": float(row["municipality"] or 0),
        "state": float(row["state"] or 0),
        "bedrooms": float(row["bedrooms"] or 0),
        "bathrooms": float(row["bathrooms"] or 0),
        "construction_m2": float(row["construction_m2"] or 0),
        "land_m2": float(row["land_m2"] or 0),
        "parking_spaces": float(row["parking_spaces"] or 0),
    }

    # Check against thresholds
    warnings = []
    for field, threshold in THRESHOLDS.items():
        rate = fill_rates.get(field, 0)
        if rate < threshold:
            warnings.append(f"{field}: {rate}% (expected >{threshold}%)")

    # Log
    if warnings:
        logger.warning(
            "quality.below_threshold",
            portal=portal_slug,
            total=fill_rates["total"],
            warnings=warnings,
        )
    else:
        logger.info(
            "quality.ok",
            portal=portal_slug,
            total=fill_rates["total"],
            bedrooms=fill_rates["bedrooms"],
            bathrooms=fill_rates["bathrooms"],
            construction_m2=fill_rates["construction_m2"],
            land_m2=fill_rates["land_m2"],
        )

    fill_rates["warnings"] = warnings
    return fill_rates
