"""Propiedades.com HTTP scraper — hybrid: browser cookies + httpx speed.

Propiedades.com uses itemprop microdata (Schema.org) in server-side
rendered HTML. Pure httpx times out from VPS IP (TLS fingerprint filtered).

Solution: CookieBridge solves with browser once, then httpx with cookies.
~10x faster than full browser scraping.
"""

from scrapers.base import ScrapedItem
from scrapers.base.http_scraper import HttpScraper
from scrapers.propiedades import config
from scrapers.propiedades.http_parser import parse_search_html
from shared.logging import get_logger
from shared.stealth.cookie_bridge import CookieBridge

logger = get_logger("scraper.propiedades.http")


class PropiedadesHttpScraper(HttpScraper):
    portal_slug = "propiedades"
    portal_name = "Propiedades.com (HTTP Hybrid)"

    # Moderate delays — cookies should prevent blocks
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
        self._bridge: CookieBridge | None = None

        if mode == "incremental":
            from scrapers.base.modes import INCREMENTAL_MAX_PAGES
            self.max_pages = min(max_pages, INCREMENTAL_MAX_PAGES)

    async def _get_bridge_for_state(self, state_url: str) -> CookieBridge:
        """Get a fresh CookieBridge solved for a specific state URL.

        Propiedades.com ties session cookies to the first URL visited.
        We must solve the WAF per state to get state-specific results.
        """
        if self._bridge:
            await self._bridge.close()
        self._bridge = CookieBridge(
            base_url=state_url,
            card_selector=config.SELECTORS["listing_card"],
            timeout_s=60.0,
        )
        return self._bridge

    async def fetch_page(self, url: str) -> str | None:
        """Override: use CookieBridge instead of raw httpx."""
        if not self._bridge:
            return None
        return await self._bridge.get(url)

    def _build_search_url(
        self, state: str, operation: str, page: int,
    ) -> str:
        url = config.SEARCH_URL_TEMPLATE.format(
            operation=config.OPERATIONS.get(operation, operation),
            state=state,
            page=page,
        )
        if self.mode == "incremental":
            url += f"&{config.SORT_RECENT_PARAM}"
        return url

    async def scrape(self) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []

        try:
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
        finally:
            if self._bridge:
                await self._bridge.close()

        return items

    async def _scrape_search(
        self, state: str, operation: str,
    ) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []
        state_name = state.replace("-", " ").title()
        consecutive_empty = 0

        # Fresh bridge per state+operation — cookies are tied to the first URL
        first_url = self._build_search_url(state, operation, 1)
        await self._get_bridge_for_state(first_url)
        self.logger.info("http.bridge_reset", state=state, operation=operation)

        for page_num in range(1, self.max_pages + 1):
            url = self._build_search_url(state, operation, page_num)
            html = await self.fetch_page(url)

            if not html:
                self.logger.info(
                    "http.no_response", page=page_num, state=state,
                )
                break

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

            # Enrich with operation; use region from HTML as state (fallback to URL slug)
            for p in partials:
                # Use badge_operation if available, else from search
                p["operation"] = p.pop(
                    "badge_operation", None,
                ) or operation
                # Prefer addressRegion from HTML over search URL slug
                p["state"] = p.get("region") or state_name
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
        lower = html[:2000].lower()
        return any(
            marker in lower
            for marker in [
                "captcha",
                "cf-browser-verification",
                "access denied",
                "challenge-platform",
            ]
        )

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
            street_and_number=p.get("street_and_number"),
            neighborhood=p.get("neighborhood"),
            municipality=p.get("municipality"),
            state=p.get("state"),
            country="Mexico",
            zip_code=p.get("zip_code"),
            latitude=p.get("latitude"),
            longitude=p.get("longitude"),
            bedrooms=p.get("bedrooms"),
            bathrooms=p.get("bathrooms"),
            half_bathrooms=p.get("half_bathrooms"),
            parking_spaces=p.get("parking_spaces"),
            construction_m2=p.get("construction_m2"),
            land_m2=p.get("land_m2"),
        )
