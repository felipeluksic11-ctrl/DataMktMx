"""S3 Exporter — exports clean listings as anonymized CSV to S3.

Rules from CLAUDE.md:
- NEVER export raw URLs, portal IDs, or scraping metadata
- NEVER store personal data (agent names, phones, emails)
- Only aggregates + anonymized listings
"""

import csv
import io
import datetime

import boto3
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config.settings import settings
from shared.logging import get_logger

logger = get_logger("etl.exporter.s3")

# Fields to export (anonymized — no URLs, no portal IDs, no scraping metadata)
EXPORT_FIELDS = [
    "property_type", "listing_type", "price_mxn", "price_usd",
    "state_code", "state_name", "city_norm", "colony_norm", "zip_code",
    "bedrooms", "bathrooms", "parking_spaces",
    "construction_m2", "land_m2", "price_per_m2",
    "quality_score", "completeness", "source_count",
]

EXPORT_HEADERS = [
    "tipo_inmueble", "operacion", "precio_mxn", "precio_usd",
    "estado_code", "estado_nombre", "ciudad", "colonia", "codigo_postal",
    "recamaras", "banos", "estacionamientos",
    "construccion_m2", "terreno_m2", "precio_m2",
    "calidad", "completitud", "fuentes",
]


async def export_to_s3(session: AsyncSession) -> dict:
    """Export clean listings to S3 as CSV. Returns stats."""
    if not settings.s3_bucket:
        logger.warning("exporter.no_s3_bucket")
        return {"error": "S3_BUCKET not configured"}

    # Fetch clean listings
    result = await session.execute(text(f"""
        SELECT {', '.join(EXPORT_FIELDS)}
        FROM clean.clean_listings
        ORDER BY state_code, price_mxn DESC
    """))
    rows = result.fetchall()

    if not rows:
        logger.info("exporter.no_data")
        return {"exported": 0}

    # Build CSV in memory
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(EXPORT_HEADERS)
    for row in rows:
        writer.writerow(list(row))

    csv_content = buffer.getvalue().encode("utf-8")

    # Upload to S3
    timestamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%d_%H%M%S")
    s3_key = f"exports/listings_{timestamp}.csv"

    s3 = boto3.client(
        "s3",
        region_name=settings.s3_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )

    s3.put_object(
        Bucket=settings.s3_bucket,
        Key=s3_key,
        Body=csv_content,
        ContentType="text/csv",
    )

    stats = {
        "exported": len(rows),
        "s3_key": s3_key,
        "size_bytes": len(csv_content),
    }

    logger.info("exporter.uploaded", **stats)
    return stats


async def export_to_file(session: AsyncSession, path: str) -> dict:
    """Export clean listings to a local CSV file. For development."""
    result = await session.execute(text(f"""
        SELECT {', '.join(EXPORT_FIELDS)}
        FROM clean.clean_listings
        ORDER BY state_code, price_mxn DESC
    """))
    rows = result.fetchall()

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(EXPORT_HEADERS)
        for row in rows:
            writer.writerow(list(row))

    stats = {"exported": len(rows), "path": path}
    logger.info("exporter.file_written", **stats)
    return stats
