"""Seed the portals table with all 7 target portals."""

import asyncio

from sqlalchemy import select

from shared.config import settings  # noqa: F401 — load env
from shared.db.models import Portal
from shared.db.session import get_engine, get_session_factory
from shared.logging import setup_logging, get_logger

logger = get_logger("seed")

PORTALS = [
    {
        "name": "Inmuebles24",
        "slug": "inmuebles24",
        "base_url": "https://www.inmuebles24.com",
        "scraper_module": "scrapers.inmuebles24",
        "is_active": True,
        "avg_listings": 200000,
        "notes": "Portal más grande de MX. Propiedad de Navent/OLX.",
    },
    {
        "name": "Propiedades.com",
        "slug": "propiedades",
        "base_url": "https://propiedades.com",
        "scraper_module": "scrapers.propiedades",
        "is_active": False,
        "avg_listings": 80000,
        "notes": "Segundo portal. También de Navent.",
    },
    {
        "name": "EasyBroker",
        "slug": "easybroker",
        "base_url": "https://www.easybroker.com",
        "scraper_module": "scrapers.easybroker",
        "is_active": False,
        "avg_listings": 60000,
        "notes": "CRM de brokers con portal público. Tiene API pero solo handshake.",
    },
    {
        "name": "Segundamano",
        "slug": "segundamano",
        "base_url": "https://www.segundamano.mx",
        "scraper_module": "scrapers.segundamano",
        "is_active": False,
        "avg_listings": 40000,
        "notes": "Clasificados generales con sección inmobiliaria.",
    },
    {
        "name": "Lamudi",
        "slug": "lamudi",
        "base_url": "https://www.lamudi.com.mx",
        "scraper_module": "scrapers.lamudi",
        "is_active": False,
        "avg_listings": 50000,
        "notes": "Portal de EMPG (Emerging Markets Property Group).",
    },
    {
        "name": "Vivanuncios",
        "slug": "vivanuncios",
        "base_url": "https://www.vivanuncios.com.mx",
        "scraper_module": "scrapers.vivanuncios",
        "is_active": False,
        "avg_listings": 30000,
        "notes": "eBay Classifieds / Adevinta.",
    },
    {
        "name": "Facebook Marketplace",
        "slug": "facebook",
        "base_url": "https://www.facebook.com/marketplace",
        "scraper_module": "scrapers.facebook",
        "is_active": False,
        "avg_listings": None,
        "notes": "Via Apify actors inicialmente. Volumen desconocido.",
    },
]


async def seed() -> None:
    setup_logging()
    session_factory = get_session_factory()

    async with session_factory() as session:
        for portal_data in PORTALS:
            stmt = select(Portal).where(Portal.slug == portal_data["slug"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                logger.info("seed.portal_exists", slug=portal_data["slug"])
                continue

            portal = Portal(**portal_data)
            session.add(portal)
            logger.info("seed.portal_created", slug=portal_data["slug"])

        await session.commit()

    engine = get_engine()
    await engine.dispose()
    logger.info("seed.done")


if __name__ == "__main__":
    asyncio.run(seed())
