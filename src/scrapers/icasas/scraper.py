"""iCasas.mx scraper — Playwright Chromium with infinite scroll.

iCasas is an aggregator that loads listings via infinite scroll.
Uses Chromium headless with JS evaluate for extraction.
"""

import asyncio
import re
import hashlib

from scrapers.base import BaseScraper, ScrapedItem
from scrapers.icasas import config
from shared.proxy.manager import ProxyManager
from shared.logging import get_logger

logger = get_logger("scraper.icasas")


class ICasasScraper(BaseScraper):
    portal_slug = "icasas"
    portal_name = "iCasas"

    _use_chromium = True

    def __init__(
        self,
        proxy_manager: ProxyManager | None = None,
        mode: str = "full",
        known_cache=None,
        **kwargs,
    ):
        super().__init__(proxy_manager)
        self._portal_proxy_policy = config.PROXY_POLICY
        self.mode = mode
        self.known_cache = known_cache
        self._seen_ids: set[str] = set()

    async def _init_browser_for_state(self):
        from shared.stealth.browser import create_stealth_browser
        browser, context = await create_stealth_browser(
            proxy_manager=self.proxy_manager,
            portal_slug=self.portal_slug,
            engine="chromium",
            via_proxy=self._uses_proxy,
        )
        self._current_browser = browser
        self._current_context = context

    async def scrape(self) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []

        await self._init_browser_for_state()
        try:
            for search in config.SEARCHES:
                try:
                    search_items = await self._scrape_search(search)
                    # Dedup across searches
                    new_items = []
                    for item in search_items:
                        if item.external_id not in self._seen_ids:
                            self._seen_ids.add(item.external_id)
                            new_items.append(item)
                    items.extend(new_items)

                    logger.info(
                        "scraper.search_done",
                        city=search["city"],
                        type=search["type"],
                        operation=search["operation"],
                        count=len(new_items),
                        total=len(items),
                    )
                except Exception:
                    self.stats["errors"] += 1
                    logger.exception("scraper.search_error", city=search["city"])
        finally:
            await self._close_browser()

        return items

    async def _scrape_search(self, search: dict) -> list[ScrapedItem]:
        """Scrape a single search URL with infinite scroll."""
        city = search["city"]
        state = search["state"]
        prop_type = search["type"]
        operation = search["operation"]
        url = search["url"]

        page = await self._current_context.new_page()
        items: list[ScrapedItem] = []

        try:
            await page.goto(url, timeout=config.PAGE_LOAD_TIMEOUT_MS, wait_until="domcontentloaded")
            await asyncio.sleep(4)

            # Accept cookies if present
            try:
                await page.click('button:has-text("Aceptar")', timeout=3000)
            except Exception:
                pass

            prev_count = 0
            stale_rounds = 0

            for scroll in range(config.MAX_SCROLLS):
                # Scroll down
                await page.evaluate("window.scrollBy(0, window.innerHeight * 2)")
                await asyncio.sleep(config.SCROLL_DELAY_S)

                # Extract listings via JS
                raw = await page.evaluate("""() => {
                    const links = document.querySelectorAll('a[href*="/propiedad/"]');
                    const results = [];
                    const seen = new Set();
                    links.forEach(a => {
                        const href = a.href.split('?')[0];
                        if (seen.has(href)) return;
                        seen.add(href);
                        let parent = a;
                        for (let i = 0; i < 5; i++) {
                            if (parent.parentElement &&
                                parent.parentElement.querySelectorAll('a[href*="/propiedad/"]').length <= 2) {
                                parent = parent.parentElement;
                            } else break;
                        }
                        const text = parent.textContent.replace(/\\s+/g, ' ').trim();
                        if (text.length > 20 && text.length < 600) {
                            results.push({url: href, text: text.substring(0, 400)});
                        }
                    });
                    return results;
                }""")

                # Parse new listings
                for r in raw:
                    sid_m = re.search(r"/propiedad/([a-f0-9-]+)", r["url"])
                    sid = sid_m.group(1) if sid_m else hashlib.md5(r["url"].encode()).hexdigest()[:16]
                    if sid in self._seen_ids:
                        continue

                    item = _parse_listing_text(r["text"], r["url"], sid, city, state, prop_type, operation)
                    if item:
                        items.append(item)

                # Check for stale scroll
                if len(raw) == prev_count:
                    stale_rounds += 1
                    if stale_rounds >= 3:
                        break
                else:
                    stale_rounds = 0
                    prev_count = len(raw)

                # Callback every 10 scrolls
                if (scroll + 1) % 10 == 0 and self.on_page_scraped and items:
                    await self.on_page_scraped(items[-20:])  # Last batch
                    logger.info("scraper.scroll_progress", scroll=scroll + 1, count=len(items), city=city)

        except Exception:
            logger.exception("scraper.scroll_error", city=city, url=url)
        finally:
            await page.close()

        # Final callback
        if self.on_page_scraped and items:
            await self.on_page_scraped(items)

        return items

    @staticmethod
    def _partial_to_item(p: dict) -> ScrapedItem:
        return ScrapedItem(
            external_id=p["external_id"],
            url_listing=p.get("url_listing"),
            title=p.get("title"),
            operation=p.get("operation"),
            property_type=p.get("property_type"),
            price=p.get("price"),
            currency=p.get("currency"),
            neighborhood=p.get("neighborhood"),
            city=p.get("city"),
            state=p.get("state"),
            country="Mexico",
            bedrooms=p.get("bedrooms"),
            bathrooms=p.get("bathrooms"),
            construction_m2=p.get("construction_m2"),
        )


def _parse_listing_text(
    text: str, url: str, source_id: str,
    city: str, state: str, prop_type: str, operation: str,
) -> ScrapedItem | None:
    """Parse a listing from its card text."""
    # Price
    price = None
    m = re.search(r"([\d,.]+)\s*(?:MX\$|pesos|mxn|\$)", text, re.I)
    if not m:
        m = re.search(r"MX?\$\s*([\d,.]+)", text)
    if m:
        price = float(m.group(1).replace(".", "").replace(",", ""))
    if not price or price < 1000:
        return None

    # Bedrooms
    bedrooms = None
    m = re.search(r"(\d+)\s*(?:recámara|recamara|habitaci[oó]n|rec[.\s]|dorm)", text, re.I)
    if m:
        bedrooms = int(m.group(1))

    # Bathrooms
    bathrooms = None
    m = re.search(r"(\d+)\s*(?:baño|bano|bath)", text, re.I)
    if m:
        bathrooms = int(m.group(1))

    # Area
    area = None
    m = re.search(r"(\d+[\d,.]*)\s*(?:m²|m2|metros?\s*cuadrados)", text, re.I)
    if m:
        area = float(m.group(1).replace(",", "."))

    # Zone
    zone = None
    m = re.search(r"(?:en|,)\s+([A-Z][a-záéíóúñ\s]+?)(?:,|\s+Cancún|\s+Quintana|\s+Yucatán|$)", text)
    if m:
        zone = m.group(1).strip()[:50]

    return ScrapedItem(
        external_id=source_id,
        url_listing=url,
        operation=operation,
        property_type=prop_type,
        price=price,
        currency="MXN",
        neighborhood=zone,
        city=city,
        state=state,
        country="Mexico",
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        construction_m2=area,
    )
