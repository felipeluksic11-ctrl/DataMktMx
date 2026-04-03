"""Lamudi.com.mx HTTP scraper — uses httpx instead of Playwright.

~20-40x less bandwidth than browser-based scraping because it only
downloads the HTML document (~150KB) instead of the full SPA bundle
(~4MB with JS, XHR, etc.).

Lamudi serves fully server-side rendered HTML with all card data
including lat/lng, price, bedrooms, bathrooms, and area in the
`data-serp-map-hover-listing` JSON attribute.

Falls back to browser-based LamudiScraper if HTTP scraping fails
(e.g., anti-bot blocks, captcha).
"""

from scrapers.base import ScrapedItem
from scrapers.base.http_scraper import HttpScraper
from scrapers.lamudi import config
from scrapers.lamudi.http_parser import parse_search_html
from shared.logging import get_logger

logger = get_logger("scraper.lamudi.http")


class LamudiHttpScraper(HttpScraper):
    portal_slug = "lamudi"
    portal_name = "Lamudi (HTTP)"

    # Lighter delays — no browser overhead, but still courteous
    delay_min_ms = 1000
    delay_max_ms = 2500

    def __init__(
        self,
        states: list[str] | None = None,
        operations: list[str] | None = None,
        max_pages: int = config.MAX_PAGES_PER_SEARCH,
        mode: str = "full",
        known_cache=None,
        proxy_url: str | None = None,
        **kwargs,
    ):
        super().__init__(proxy_url=proxy_url)
        self.mode = mode
        self.known_cache = known_cache
        self.states = states or config.STATES
        self.operations = operations or ["venta", "renta"]
        self.max_pages = max_pages

        if mode == "incremental":
            from scrapers.base.modes import INCREMENTAL_MAX_PAGES
            self.max_pages = min(max_pages, INCREMENTAL_MAX_PAGES)

    def _build_search_url(
        self, state: str, operation: str, page: int,
    ) -> str:
        op_slug = config.OPERATIONS.get(operation, operation)
        url = config.SEARCH_URL_TEMPLATE.format(
            location=state, operation=op_slug,
        )
        params = []
        if self.mode == "incremental":
            params.append(config.SORT_RECENT_PARAM)
        if page > 1:
            params.append(f"page={page}")
        if params:
            url += "?" + "&".join(params)
        return url

    async def scrape(self) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []

        for state in self.states:
            for operation in self.operations:
                try:
                    search_items = await self._scrape_search(
                        state, operation,
                    )
                    items.extend(search_items)
                    self.logger.info(
                        "http.search_done",
                        state=state,
                        operation=operation,
                        count=len(search_items),
                    )
                except Exception:
                    self.stats["errors"] += 1
                    self.logger.exception(
                        "http.state_error", state=state,
                    )

        return items

    async def _scrape_search(
        self, state: str, operation: str,
    ) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []
        state_name = state.replace("-", " ").title()
        consecutive_empty = 0

        for page_num in range(1, self.max_pages + 1):
            url = self._build_search_url(state, operation, page_num)
            html = await self.fetch_page(url)

            if not html:
                self.logger.info(
                    "http.no_response", page=page_num, state=state,
                )
                break

            # Check for anti-bot / captcha in response
            if self._is_blocked(html):
                self.logger.warning(
                    "http.blocked_response",
                    page=page_num,
                    state=state,
                )
                break

            partials = parse_search_html(html)

            if not partials:
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    self.logger.info(
                        "http.no_more_results",
                        page=page_num,
                        state=state,
                    )
                    break
                await self._delay()
                continue

            consecutive_empty = 0

            # Enrich with operation and state
            for p in partials:
                p["operation"] = operation
                p["state"] = state_name
                p["country"] = "Mexico"

            page_items = [self._partial_to_item(p) for p in partials]

            # Incremental mode: check known listings
            if self.mode == "incremental" and self.known_cache:
                ext_ids = [item.external_id for item in page_items]
                if self.known_cache.should_stop(ext_ids):
                    self.logger.info(
                        "http.incremental_stop",
                        page=page_num,
                        state=state,
                        reason="mostly_known",
                    )
                    items.extend(page_items)
                    break

            if self.on_page_scraped:
                await self.on_page_scraped(page_items)

            items.extend(page_items)
            self.total_items_scraped += len(page_items)

            self.logger.info(
                "http.page_done",
                page=page_num,
                count=len(page_items),
                total=len(items),
                state=state,
            )

            await self._delay()

        return items

    def _is_blocked(self, html: str) -> bool:
        """Check if response HTML indicates anti-bot blocking."""
        lower = html[:2000].lower()
        return any(
            marker in lower
            for marker in [
                "captcha",
                "cf-browser-verification",
                "challenge-platform",
                "access denied",
            ]
        )

    @staticmethod
    def _partial_to_item(p: dict) -> ScrapedItem:
        """Convert a partial dict to a ScrapedItem."""
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
