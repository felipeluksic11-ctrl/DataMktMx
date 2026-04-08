"""Properstar HTTP scraper — hybrid mode: browser solves WAF, httpx scrapes.

Azure WAF issues a clearance cookie that lasts ~30 minutes.
This scraper uses CookieBridge to solve the WAF challenge once with a browser,
then switches to fast httpx requests with the cookie for bulk pagination.

10-50x faster than full browser scraping per page.
"""

import asyncio
import random

from selectolax.parser import HTMLParser

from scrapers.base import ScrapedItem
from scrapers.base.http_scraper import HttpScraper
from scrapers.properstar import config
from shared.logging import get_logger
from shared.stealth.cookie_bridge import CookieBridge

logger = get_logger("http_scraper.properstar")


class PropertystarHttpScraper(HttpScraper):
    portal_slug = "properstar"
    portal_name = "Properstar (HTTP Hybrid)"

    # Moderate delays — WAF cookie should prevent blocks
    delay_min_ms = 1500
    delay_max_ms = 3000

    def __init__(
        self,
        states: list[str] | None = None,
        operations: list[str] | None = None,
        max_pages: int = config.MAX_PAGES_PER_SEARCH,
        mode: str = "full",
        known_cache=None,
        **kwargs,
    ):
        super().__init__()
        self.mode = mode
        self.known_cache = known_cache
        self.states = states or config.PHASE1_STATES
        self.operations = operations or ["venta", "alquiler"]
        self.max_pages = max_pages
        self._bridge: CookieBridge | None = None

    async def _get_bridge(self) -> CookieBridge:
        if self._bridge is None:
            self._bridge = CookieBridge(
                base_url=config.BASE_URL,
                card_selector=config.SELECTORS["listing_card"],
                timeout_s=45.0,
            )
        return self._bridge

    async def run(self, job=None) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []

        for state in self.states:
            for operation in self.operations:
                try:
                    search_items = await self._scrape_search(state, operation)
                    items.extend(search_items)
                    logger.info(
                        "http.search_done",
                        state=state,
                        operation=operation,
                        count=len(search_items),
                    )
                except Exception:
                    logger.exception("http.state_error", state=state, operation=operation)

        # Cleanup
        if self._bridge:
            await self._bridge.close()

        return items

    async def _scrape_search(self, state: str, operation: str) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []
        bridge = await self._get_bridge()
        state_name = state.replace("-", " ").title()

        for page_num in range(1, self.max_pages + 1):
            op_slug = config.OPERATIONS.get(operation, operation)
            url = config.SEARCH_URL_TEMPLATE.format(state=state, operation=op_slug)
            if page_num > 1:
                url += f"?p={page_num}"

            html = await bridge.get(url)
            if not html:
                logger.info("http.no_response", page=page_num, state=state)
                break

            # Parse cards from HTML
            partials = _parse_search_html(html)
            if not partials:
                logger.info("http.no_cards", page=page_num, state=state)
                break

            # Log total on first page
            if page_num == 1:
                total = _get_total_from_html(html)
                if total:
                    logger.info(
                        "http.total_results",
                        state=state,
                        operation=operation,
                        total=total,
                    )

            # Enrich with state/operation
            for p in partials:
                p["operation"] = operation
                p["state"] = state_name
                p["country"] = "Mexico"

            page_items = [self._partial_to_item(p) for p in partials]

            # Incremental mode: check known listings
            if self.mode == "incremental" and self.known_cache:
                ext_ids = [item.external_id for item in page_items]
                if self.known_cache.should_stop(ext_ids):
                    logger.info("http.incremental_stop", page=page_num, state=state)
                    if self.on_page_scraped:
                        await self.on_page_scraped(page_items)
                    items.extend(page_items)
                    break

            if self.on_page_scraped:
                await self.on_page_scraped(page_items)

            items.extend(page_items)

            logger.info(
                "http.page_done",
                page=page_num,
                count=len(page_items),
                total=len(items),
                state=state,
            )

            # Delay between pages
            await asyncio.sleep(
                random.uniform(self.delay_min_ms / 1000, self.delay_max_ms / 1000)
            )

        return items

    @staticmethod
    def _partial_to_item(p: dict) -> ScrapedItem:
        return ScrapedItem(
            external_id=p["external_id"],
            url_listing=p.get("url_listing"),
            title=p.get("title"),
            operation=p.get("operation"),
            property_type=p.get("property_type"),
            listing_type=p.get("operation"),
            price=p.get("price"),
            currency=p.get("currency"),
            neighborhood=p.get("neighborhood"),
            city=p.get("city"),
            municipality=p.get("municipality"),
            state=p.get("state"),
            country="Mexico",
            latitude=p.get("latitude"),
            longitude=p.get("longitude"),
            bedrooms=p.get("bedrooms"),
            bathrooms=p.get("bathrooms"),
            construction_m2=p.get("construction_m2"),
            land_m2=p.get("land_m2"),
            images_count=p.get("images_count", 0),
        )


# ──────────────────── HTML Parsing (selectolax) ────────────────────


def _parse_search_html(html: str) -> list[dict]:
    """Parse Properstar search results from raw HTML using selectolax."""
    tree = HTMLParser(html)
    cards = tree.css(config.SELECTORS["listing_card"])
    if not cards:
        return []

    results = []
    for card in cards:
        # External ID + URL from link
        link = card.css_first("a[href*='/listing/']") or card.css_first("a[href]")
        if not link:
            continue
        href = link.attributes.get("href", "")
        if not href:
            continue
        detail_url = href if href.startswith("http") else config.BASE_URL + href

        # Extract ID from URL
        import re
        match = re.search(r"/listing/(\d+)", detail_url)
        if not match:
            match = re.search(r"-(\d{5,})(?:\?|$|/)", detail_url)
        if not match:
            continue
        external_id = match.group(1)

        # Price
        price = None
        currency = None
        price_el = card.css_first(config.SELECTORS.get("card_price", ".price"))
        if price_el:
            price_text = price_el.text(strip=True)
            price, currency = _clean_price(price_text)

        # Location
        location_el = card.css_first(config.SELECTORS.get("card_location", ".location"))
        city = None
        neighborhood = None
        if location_el:
            loc_text = location_el.text(strip=True)
            parts = [p.strip() for p in loc_text.split(",")]
            if len(parts) >= 2:
                neighborhood = parts[0]
                city = parts[-1]
            elif parts:
                city = parts[0]

        # Features (beds, baths, m2)
        bedrooms = None
        bathrooms = None
        construction_m2 = None
        land_m2 = None
        feat_els = card.css(config.SELECTORS.get("card_features", ".feature"))
        for feat in feat_els:
            text = feat.text(strip=True).lower()
            val = _extract_number(text)
            if val is None:
                continue
            if "hab" in text or "rec" in text or "dorm" in text or "bed" in text:
                bedrooms = int(val)
            elif "baño" in text or "bano" in text or "bath" in text:
                bathrooms = int(val)
            elif "m²" in text or "m2" in text:
                if construction_m2 is None:
                    construction_m2 = val
                else:
                    land_m2 = val

        # Property type
        property_type = None
        type_el = card.css_first(config.SELECTORS.get("card_type", ".property-type"))
        if type_el:
            property_type = type_el.text(strip=True).lower()

        # Title
        title_el = card.css_first("h2") or card.css_first("h3") or card.css_first(".title")
        title = title_el.text(strip=True) if title_el else None

        results.append({
            "external_id": external_id,
            "detail_url": detail_url,
            "url_listing": detail_url,
            "title": title,
            "price": price,
            "currency": currency,
            "property_type": property_type,
            "neighborhood": neighborhood,
            "city": city,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "construction_m2": construction_m2,
            "land_m2": land_m2,
        })

    return results


def _get_total_from_html(html: str) -> int | None:
    """Extract total results count from H1 text."""
    tree = HTMLParser(html)
    h1 = tree.css_first("h1")
    if not h1:
        return None
    import re
    text = h1.text(strip=True)
    match = re.search(r"([\d.,]+)\s*resultado", text)
    if match:
        return int(match.group(1).replace(".", "").replace(",", ""))
    return None


def _clean_price(text: str) -> tuple[float | None, str | None]:
    if not text:
        return None, None
    import re
    currency = "USD" if "USD" in text.upper() or "US$" in text else "MXN"
    digits = re.sub(r"[^\d.]", "", text.replace(",", ""))
    try:
        return float(digits), currency
    except ValueError:
        return None, None


def _extract_number(text: str) -> float | None:
    import re
    match = re.search(r"([\d.,]+)", text)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None
