"""MercadoLibre scraper — pure HTTP with LD+JSON extraction.

MercadoLibre serves RealEstateListing structured data in LD+JSON
(Schema.org) in the HTML. No browser needed — fast httpx requests.
"""

import asyncio
import json
import random
import re
import hashlib

import httpx
from selectolax.parser import HTMLParser

from scrapers.base import ScrapedItem
from scrapers.base.http_scraper import HttpScraper
from scrapers.mercadolibre import config
from shared.logging import get_logger

logger = get_logger("scraper.mercadolibre")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-MX,es;q=0.9,en-US;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
}


class MercadoLibreScraper(HttpScraper):
    portal_slug = "mercadolibre"
    portal_name = "MercadoLibre Inmuebles"

    delay_min_ms = config.REQUEST_DELAY_MIN_MS
    delay_max_ms = config.REQUEST_DELAY_MAX_MS

    def __init__(
        self,
        states: list[str] | None = None,
        operations: list[str] | None = None,
        property_types: list[str] | None = None,
        mode: str = "full",
        known_cache=None,
        **kwargs,
    ):
        super().__init__()
        self.mode = mode
        self.known_cache = known_cache
        self.states = states or config.PHASE1_STATES
        self.operations = operations or ["renta", "venta"]
        self.property_types = property_types or config.PROPERTY_TYPES
        self._session: httpx.AsyncClient | None = None
        self._seen_ids: set[str] = set()

    async def _get_session(self) -> httpx.AsyncClient:
        if self._session is None:
            self._session = httpx.AsyncClient(
                headers=HEADERS,
                follow_redirects=True,
                timeout=20.0,
            )
        return self._session

    async def run(self, job=None) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []

        try:
            for state in self.states:
                state_name = state.replace("-", " ").title()
                for operation in self.operations:
                    for prop_type in self.property_types:
                        try:
                            search_items = await self._scrape_search(
                                state, state_name, operation, prop_type
                            )
                            items.extend(search_items)
                        except Exception:
                            self.stats["errors"] += 1
                            logger.exception(
                                "scraper.search_error",
                                state=state, operation=operation, type=prop_type,
                            )
        finally:
            if self._session:
                await self._session.aclose()

        return items

    async def _scrape_search(
        self, state: str, state_name: str, operation: str, prop_type: str,
    ) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []
        op_slug = config.OPERATIONS.get(operation, operation)
        base_url = config.SEARCH_URL_TEMPLATE.format(
            property_type=prop_type, operation=op_slug, state=state,
        )
        url = base_url

        for page_num in range(1, config.MAX_PAGES_PER_SEARCH + 1):
            session = await self._get_session()
            try:
                resp = await session.get(url)
                if resp.status_code != 200:
                    logger.warning("scraper.http_error", status=resp.status_code, url=url)
                    break

                html = resp.text
                ld_listings = _extract_ld_json(html)

                if not ld_listings:
                    break

                new_count = 0
                page_items = []
                for ld_item in ld_listings:
                    item = _parse_ld_listing(ld_item, operation, state_name, prop_type)
                    if not item or item.external_id in self._seen_ids:
                        continue
                    self._seen_ids.add(item.external_id)
                    page_items.append(item)
                    new_count += 1

                if self.on_page_scraped and page_items:
                    await self.on_page_scraped(page_items)

                items.extend(page_items)

                logger.info(
                    "scraper.page_done",
                    page=page_num, count=new_count, total=len(items),
                    state=state, operation=operation, type=prop_type,
                )

                if new_count == 0:
                    break

                # Next page URL
                url = _get_next_page_url(html, url, page_num)
                if not url:
                    break

            except httpx.TimeoutException:
                logger.warning("scraper.timeout", url=url)
                break

            await asyncio.sleep(random.uniform(
                self.delay_min_ms / 1000, self.delay_max_ms / 1000
            ))

        logger.info(
            "scraper.search_done",
            state=state, operation=operation, type=prop_type, count=len(items),
        )
        return items


def _extract_ld_json(html: str) -> list[dict]:
    """Extract RealEstateListing items from LD+JSON."""
    tree = HTMLParser(html)
    listings = []
    for script in tree.css("script[type='application/ld+json']"):
        try:
            data = json.loads(script.text())
            graph = data.get("@graph", [])
            for item in graph:
                if item.get("@type") == "RealEstateListing":
                    listings.append(item)
        except (json.JSONDecodeError, TypeError):
            continue
    return listings


def _parse_ld_listing(
    item: dict, operation: str, state: str, prop_type: str,
) -> ScrapedItem | None:
    """Parse a LD+JSON RealEstateListing into ScrapedItem."""
    offers = item.get("offers", {})
    price = offers.get("price")
    currency = offers.get("priceCurrency", "MXN")

    if not price or price < 1000:
        return None

    if currency == "USD":
        price = price * 20

    name = item.get("name", "")

    # Bedrooms
    bedrooms = item.get("numberOfRooms")
    if bedrooms:
        try:
            bedrooms = int(bedrooms)
        except (ValueError, TypeError):
            bedrooms = None
    if not bedrooms:
        m = re.search(r"(\d+)\s*(?:rec[áa]mara|habitaci[oó]n|rec|hab)", name, re.I)
        if m:
            bedrooms = int(m.group(1))

    # Area
    area = None
    floor_size = item.get("floorSize", {})
    if isinstance(floor_size, dict):
        val = floor_size.get("value")
        if val:
            try:
                area = float(val)
            except (ValueError, TypeError):
                pass

    # Bathrooms
    bathrooms = None
    m = re.search(r"(\d+)\s*(?:ba[ñn]o|bath)", name, re.I)
    if m:
        bathrooms = int(m.group(1))

    # Zone
    zone = None
    address = item.get("address", {})
    if isinstance(address, dict):
        zone = address.get("addressLocality") or address.get("streetAddress")
        if zone:
            zone = zone.strip()[:50]

    # URL and ID
    url = offers.get("url", "")
    id_match = re.search(r"MLM-?(\d+)", url)
    external_id = f"MLM{id_match.group(1)}" if id_match else hashlib.md5(url.encode()).hexdigest()[:16]

    normalized_type = "departamento" if "departamento" in prop_type else "casa"

    return ScrapedItem(
        external_id=external_id,
        url_listing=url,
        title=name,
        operation=operation,
        property_type=normalized_type,
        listing_type=operation,
        price=float(price),
        currency=currency,
        neighborhood=zone,
        state=state,
        country="Mexico",
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        construction_m2=area,
    )


def _get_next_page_url(html: str, current_url: str, page_num: int) -> str | None:
    """Build next page URL using MercadoLibre's _Desde_ pattern."""
    tree = HTMLParser(html)
    next_link = tree.css_first('a.andes-pagination__link[title="Siguiente"]')
    if next_link:
        href = next_link.attributes.get("href")
        if href:
            return href

    base = current_url.split("_Desde_")[0].rstrip("/")
    offset = page_num * 48 + 1
    return f"{base}_Desde_{offset}_NoIndex_True"
