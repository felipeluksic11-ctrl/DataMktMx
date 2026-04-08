"""Properstar.com.mx scraper — uses Chromium + JS evaluate.

Properstar is behind Azure WAF. Chromium (not Camoufox) passes the
JS challenge more reliably. Data extraction uses page.evaluate() to
run JavaScript directly in the DOM — faster and more robust than
CSS selectors with Playwright's query API.
"""

import asyncio
import random
import re

from playwright.async_api import Page

from scrapers.base import BaseScraper, ScrapedItem
from scrapers.properstar import config
from shared.proxy.manager import ProxyManager


class PropertystarScraper(BaseScraper):
    portal_slug = "properstar"
    portal_name = "Properstar"

    # Longer rotation intervals — Azure WAF penalizes new sessions
    rotate_min_pages = 6
    rotate_max_pages = 12
    rotate_delay_min_s = 5.0
    rotate_delay_max_s = 10.0

    # Force Chromium engine (not Camoufox) — WAF passes better with Chromium
    _use_chromium = True

    def __init__(
        self,
        proxy_manager: ProxyManager | None = None,
        states: list[str] | None = None,
        operations: list[str] | None = None,
        max_pages: int = config.MAX_PAGES_PER_SEARCH,
        visit_detail: bool = True,
        mode: str = "full",
        known_cache=None,
        **kwargs,
    ):
        super().__init__(proxy_manager)
        self._portal_proxy_policy = getattr(config, "PROXY_POLICY", "direct")
        self.mode = mode
        self.known_cache = known_cache
        self.states = states or config.PHASE1_STATES
        self.operations = operations or ["venta", "alquiler"]
        self.max_pages = max_pages
        self.visit_detail = visit_detail

    def _build_search_url(self, state: str, operation: str, page: int) -> str:
        op_slug = config.OPERATIONS.get(operation, operation)
        url = config.SEARCH_URL_TEMPLATE.format(state=state, operation=op_slug)
        if page > 1:
            url += f"?p={page}"
        return url

    async def _init_browser_for_state(self):
        """Override: use Chromium instead of Camoufox."""
        from shared.stealth.browser import create_stealth_browser
        browser, context = await create_stealth_browser(
            proxy_manager=self.proxy_manager,
            portal_slug=self.portal_slug,
            engine="chromium",
            via_proxy=self._uses_proxy,
        )
        self._current_browser = browser
        self._current_context = context
        self._pages_since_rotation = 0
        self._rotate_after = self._next_rotation_threshold()

    async def scrape(self) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []

        for state in self.states:
            await self._init_browser_for_state()
            try:
                for operation in self.operations:
                    search_items = await self._scrape_search(state, operation)
                    items.extend(search_items)
                    self.logger.info(
                        "scraper.search_done",
                        state=state,
                        operation=operation,
                        count=len(search_items),
                    )
            except Exception:
                self.stats["errors"] += 1
                self.logger.exception("scraper.state_error", state=state)
            finally:
                await self._close_browser()

        return items

    async def _scrape_search(self, state: str, operation: str) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []
        consecutive_empty = 0

        for page_num in range(1, self.max_pages + 1):
            url = self._build_search_url(state, operation, page_num)
            page = await self._current_context.new_page()
            try:
                page_items = await self._scrape_page_js(page, url, operation, state, page_num)

                if not page_items:
                    consecutive_empty += 1
                    if consecutive_empty >= 2:
                        self.logger.info("scraper.no_more_results", page=page_num, state=state)
                        break
                    page_num += 0  # Don't increment, retry
                    continue

                consecutive_empty = 0

                if self.on_page_scraped:
                    await self.on_page_scraped(page_items)

                items.extend(page_items)
                self._pages_since_rotation += 1

                self.logger.info(
                    "scraper.page_done",
                    page=page_num,
                    count=len(page_items),
                    total=len(items),
                    state=state,
                )

                # Delay between pages
                await asyncio.sleep(random.uniform(2.0, 4.0))

            except Exception:
                self.stats["errors"] += 1
                self.logger.exception("scraper.page_error", page=page_num, url=url)
                consecutive_empty += 1
                if consecutive_empty >= 3:
                    break
            finally:
                await page.close()

        return items

    async def _scrape_page_js(
        self, page: Page, url: str, operation: str, state: str, page_num: int,
    ) -> list[ScrapedItem]:
        """Scrape a page using JavaScript DOM evaluation — the approach that works."""
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)

        if not response or response.status in (403, 503):
            self.logger.warning("scraper.waf_block", url=url, status=response.status if response else None)
            await asyncio.sleep(random.uniform(5, 10))
            return []

        # Wait for cards to render
        await asyncio.sleep(3)

        # Extract listings using JavaScript (from the working scraper)
        raw_listings = await page.evaluate("""() => {
            const items = document.querySelectorAll('.item-adaptive');
            const results = [];
            for (const item of items) {
                const link = item.querySelector('a[href*="/vivienda/"]') || item.querySelector('a[href*="/listing/"]');
                if (!link) continue;
                const url = link.href.split('?')[0];
                const priceEl = item.querySelector('.listing-price-main');
                const titleEl = item.querySelector('.listing-title');
                const locEl = item.querySelector('.item-location');
                const hlEl = item.querySelector('.item-highlights');
                const dataEl = item.querySelector('.item-data');
                results.push({
                    url: url,
                    priceText: priceEl ? priceEl.textContent.trim() : '',
                    title: titleEl ? titleEl.textContent.trim() : '',
                    location: locEl ? locEl.textContent.trim() : '',
                    highlights: hlEl ? hlEl.textContent.replace(/\\s+/g, ' ').trim() : '',
                    dataText: dataEl ? dataEl.textContent.replace(/\\s+/g, ' ').trim() : '',
                });
            }
            return results;
        }""")

        if not raw_listings:
            return []

        # Log total on first page
        if page_num == 1:
            total_text = await page.evaluate("""() => {
                const h1 = document.querySelector('h1');
                return h1 ? h1.textContent.trim() : '';
            }""")
            total_match = re.search(r"([\d.,]+)\s*resultado", total_text or "")
            if total_match:
                total = int(total_match.group(1).replace(".", "").replace(",", ""))
                self.logger.info(
                    "scraper.total_results",
                    state=state,
                    operation=operation,
                    total=total,
                )

        state_name = _state_slug_to_name(state)
        items = []
        for raw in raw_listings:
            item = _parse_raw_listing(raw, operation, state_name)
            if item:
                items.append(item)

        return items

    @staticmethod
    def _partial_to_item(p: dict) -> ScrapedItem:
        return ScrapedItem(
            external_id=p["external_id"],
            url_listing=p.get("url_listing"),
            title=p.get("title"),
            description=p.get("description"),
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
            half_bathrooms=p.get("half_bathrooms"),
            parking_spaces=p.get("parking_spaces"),
            construction_m2=p.get("construction_m2"),
            land_m2=p.get("land_m2"),
            images_count=p.get("images_count", 0),
            antiquity=p.get("antiquity"),
            built_levels=p.get("built_levels"),
        )


def _parse_raw_listing(raw: dict, operation: str, state: str) -> ScrapedItem | None:
    """Parse a raw JS-extracted listing into a ScrapedItem."""
    url = raw.get("url", "")
    if not url:
        return None

    # External ID from URL
    match = re.search(r"/vivienda/(\d+)", url) or re.search(r"/listing/(\d+)", url)
    if not match:
        match = re.search(r"-(\d{5,})(?:\?|$|/)", url)
    if not match:
        return None
    external_id = match.group(1)

    # Price
    price_text = raw.get("priceText", "")
    price, currency = None, None
    if price_text:
        currency = "USD" if "USD" in price_text.upper() else "MXN"
        digits = re.sub(r"[^\d.]", "", price_text.replace(",", "").replace(".", ""))
        if digits:
            try:
                price = float(digits)
            except ValueError:
                pass

    # Features from highlights
    highlights = raw.get("highlights", "")
    bedrooms = _extract_int(r"(\d+)\s*habitaci[oó]n", highlights)
    bathrooms = _extract_int(r"(\d+)\s*ba[ñn]o", highlights)
    area = _extract_float(r"([\d,.]+)\s*m[²2]", highlights)

    # Property type from dataText
    data_text = raw.get("dataText", "")
    property_type = _detect_property_type(data_text)

    # Location
    location = raw.get("location", "")
    city, neighborhood = _parse_location(location)

    return ScrapedItem(
        external_id=external_id,
        url_listing=url,
        title=raw.get("title"),
        operation=operation,
        property_type=property_type,
        listing_type=operation,
        price=price,
        currency=currency,
        neighborhood=neighborhood,
        city=city,
        state=state,
        country="Mexico",
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        construction_m2=area,
    )


def _extract_int(pattern: str, text: str) -> int | None:
    m = re.search(pattern, text, re.I)
    return int(m.group(1)) if m else None


def _extract_float(pattern: str, text: str) -> float | None:
    m = re.search(pattern, text, re.I)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


def _detect_property_type(text: str) -> str | None:
    text_lower = text.lower()
    for keyword, ptype in [
        ("casa independiente", "casa"), ("casa con terraza", "casa"), ("casa", "casa"),
        ("villa", "casa"), ("townhouse", "casa"),
        ("piso con terraza", "departamento"), ("piso", "departamento"),
        ("penthouse", "departamento"), ("departamento", "departamento"),
        ("apartamento", "departamento"), ("estudio", "departamento"), ("loft", "departamento"),
        ("terreno", "terreno"), ("local", "local_comercial"),
    ]:
        if keyword in text_lower:
            return ptype
    return None


def _parse_location(location: str) -> tuple[str | None, str | None]:
    if not location:
        return None, None
    parts = [p.strip() for p in location.split(",")]
    if len(parts) >= 2:
        return parts[-1], parts[0]
    return parts[0] if parts else None, None


def _state_slug_to_name(slug: str) -> str:
    clean = slug.removesuffix("-l1")
    return clean.replace("-", " ").title()
