"""Supabase Exporter — syncs raw listings to archive.mined_listings.

Permanent backup of all mined data. Uses PostgREST upsert via httpx.
Never loses data: ON CONFLICT updates, soft-delete only on Supabase side.
"""

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config.settings import settings
from shared.logging import get_logger

logger = get_logger("etl.exporter.supabase")

BATCH_SIZE = 500

# Query raw_listings joined with portal slug.
# Excludes url_listing, raw_json, and scraping metadata per CLAUDE.md rules.
SYNC_QUERY = """
    SELECT
        p.slug              AS portal_slug,
        r.external_id,
        r.operation,
        r.property_type,
        r.price,
        r.currency,
        r.maintenance_fee,
        r.state             AS state_name,
        r.municipality,
        r.city,
        r.neighborhood      AS colony,
        r.zip_code,
        r.bedrooms,
        r.bathrooms,
        r.half_bathrooms,
        r.parking_spaces,
        r.construction_m2,
        r.land_m2,
        r.built_levels,
        r.antiquity,
        r.construction_years,
        r.conservation_status,
        r.has_balcony,
        r.has_elevator,
        r.has_storage,
        r.extra_rooms,
        r.services,
        r.amenities,
        r.exteriors,
        r.extras,
        r.description,
        r.first_seen_at,
        r.last_seen_at
    FROM raw.raw_listings r
    JOIN portals p ON p.id = r.portal_id
    WHERE r.operation IS NOT NULL
      AND r.property_type IS NOT NULL
    ORDER BY r.created_at
"""


def _build_headers() -> dict[str, str]:
    return {
        "apikey": settings.supabase_service_key,
        "Authorization": f"Bearer {settings.supabase_service_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
        "Accept-Profile": "archive",
        "Content-Profile": "archive",
    }


def _row_to_dict(row) -> dict:
    """Convert a DB row to a dict matching archive.mined_listings columns."""
    d = dict(row._mapping)
    # Convert datetimes to ISO strings for JSON
    for ts_field in ("first_seen_at", "last_seen_at"):
        if d.get(ts_field):
            d[ts_field] = d[ts_field].isoformat()
    return d


async def sync_to_supabase(session: AsyncSession) -> dict:
    """Sync all raw_listings to Supabase archive. Returns stats.

    Uses PostgREST upsert (ON CONFLICT on portal_slug + external_id).
    Existing rows get updated with latest data; nothing is ever deleted.
    """
    if not settings.supabase_url or not settings.supabase_service_key:
        logger.warning("supabase.not_configured")
        return {"error": "SUPABASE_URL or SUPABASE_SERVICE_KEY not configured"}

    result = await session.execute(text(SYNC_QUERY))
    rows = result.fetchall()

    if not rows:
        logger.info("supabase.no_data")
        return {"synced": 0}

    url = f"{settings.supabase_url}/rest/v1/mined_listings?on_conflict=portal_slug,external_id"
    headers = _build_headers()

    total_synced = 0
    total_errors = 0

    async with httpx.AsyncClient(timeout=60.0) as client:
        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i : i + BATCH_SIZE]
            payload = [_row_to_dict(r) for r in batch]

            try:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code in (200, 201):
                    total_synced += len(batch)
                    logger.info(
                        "supabase.batch_synced",
                        batch=i // BATCH_SIZE + 1,
                        count=len(batch),
                    )
                else:
                    total_errors += len(batch)
                    logger.error(
                        "supabase.batch_error",
                        batch=i // BATCH_SIZE + 1,
                        status=resp.status_code,
                        body=resp.text[:500],
                    )
            except httpx.HTTPError as e:
                total_errors += len(batch)
                logger.error(
                    "supabase.batch_exception",
                    batch=i // BATCH_SIZE + 1,
                    error=str(e),
                )

    stats = {
        "total_rows": len(rows),
        "synced": total_synced,
        "errors": total_errors,
    }
    logger.info("supabase.sync_complete", **stats)
    return stats
