"""Properstar.com.mx scraper — crawls search results and detail pages.

Properstar is behind Azure WAF with a JS challenge. Requires Playwright/Camoufox.
Content is SSR — cards are in initial HTML after WAF challenge completes.

Rate limiting is aggressive: 3-4 rapid loads trigger 503 "Service unavailable".
Uses longer delays (3.5-7s) and retries on WAF blocks.
"""

import asyncio
import random

from playwright.async_api import Page

from scrapers.base import BaseScraper, ScrapedItem
from scrapers.properstar import config
from scrapers.properstar.parser import parse_search_results, parse_detail_page, get_total_results
from shared.proxy.manager import ProxyManager


class PropertystarScraper(BaseScraper):
    portal_slug = "properstar"
    portal_name = "Properstar"

    # Longer rotation intervals — Azure WAF penalizes new sessions
    rotate_min_pages = 6
    rotate_max_pages = 12
    rotate_delay_min_s = 5.0
    rotate_delay_max_s = 10.0

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
        self._portal_proxy_policy = getattr(config, "PROXY_POLICY", "proxy_required")
        self.mode = mode
        self.known_cache = known_cache
        self.states = states or config.STATES
        self.operations = operations or ["venta"]
        self.max_pages = max_pages
        self.visit_detail = visit_detail

    def _build_search_url(self, state: str, operation: str, page: int) -> str:
        """Build search URL for a given state, operation, and page number.

        Example: https://www.properstar.com.mx/mexico/jalisco/comprar?p=2
        """
        op_slug = config.OPERATIONS.get(operation, operation)
        url = config.SEARCH_URL_TEMPLATE.format(
            state=state,
            operation=op_slug,
        )
        if page > 1:
            url += f"?p={page}"
        return url

    async def scrape(self) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []

        for state in self.states:
            await self._init_browser_for_state()
            try:
                for operation in self.operations:
                    search_items = await self._scrape_search(
                        state, operation
                    )
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

    async def _scrape_search(
        self,
        state: str,
        operation: str,
    ) -> list[ScrapedItem]:
        """Scrape all pages of a search query (state + operation)."""
        items: list[ScrapedItem] = []
        max_page = self.max_pages

        for page_num in range(1, max_page + 1):
            await self._maybe_rotate()

            url = self._build_search_url(state, operation, page_num)
            page = await self._current_context.new_page()
            try:
                page_items = await self._scrape_search_page(
                    page, url, operation, state=state, page_num=page_num,
                )

                if not page_items:
                    self.logger.info("scraper.no_more_results", page=page_num, state=state)
                    break

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

                # Longer delays — Azure WAF is aggressive
                await asyncio.sleep(
                    random.uniform(
                        config.REQUEST_DELAY_MIN_MS / 1000,
                        config.REQUEST_DELAY_MAX_MS / 1000,
                    )
                )
            except Exception:
                self.stats["errors"] += 1
                self.logger.exception(
                    "scraper.page_error", page=page_num, url=url
                )
            finally:
                await page.close()

        return items

    async def _scrape_search_page(
        self,
        page: Page,
        url: str,
        operation: str,
        state: str = "",
        page_num: int = 1,
    ) -> list[ScrapedItem]:
        """Scrape a single search results page.

        Handles Azure WAF by waiting for card selector with generous timeout.
        Retries once on 403/503 (WAF block).
        """
        response = await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=config.PAGE_LOAD_TIMEOUT_MS,
        )

        if not response:
            self.logger.warning("scraper.no_response", url=url)
            return []

        # Azure WAF block — retry once after delay
        if response.status in (403, 503):
            self.logger.warning(
                "scraper.waf_block",
                url=url,
                status=response.status,
                attempt=1,
            )
            await asyncio.sleep(random.uniform(8, 15))
            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=config.PAGE_LOAD_TIMEOUT_MS,
            )
            if not response or response.status >= 400:
                self.logger.warning(
                    "scraper.waf_block_retry_failed",
                    url=url,
                    status=response.status if response else None,
                )
                return []

        # Wait for listing cards to render after WAF challenge
        try:
            await page.wait_for_selector(
                config.SELECTORS["listing_card"],
                timeout=config.CARD_WAIT_TIMEOUT_MS,
            )
        except Exception:
            # Cards didn't appear — might be WAF challenge page or no results
            self.logger.warning("scraper.no_cards_selector", url=url)
            return []

        # Log total results on first page
        if page_num == 1:
            total = await get_total_results(page)
            if total is not None:
                self.logger.info(
                    "scraper.total_results",
                    state=state,
                    operation=operation,
                    total=total,
                    estimated_pages=(total + config.LISTINGS_PER_PAGE - 1) // config.LISTINGS_PER_PAGE,
                )

        partials = await parse_search_results(page)
        if not partials:
            return []

        # Enrich with operation and state from search context
        state_name = _state_slug_to_name(state)
        for p in partials:
            p["operation"] = operation
            p["state"] = state_name
            p["country"] = "Mexico"

        if not self.visit_detail:
            return [self._partial_to_item(p) for p in partials]

        # Visit detail pages for richer data
        items: list[ScrapedItem] = []
        for partial in partials:
            detail_url = partial.get("detail_url")
            if not detail_url:
                items.append(self._partial_to_item(partial))
                continue

            detail_page = await page.context.new_page()
            try:
                await detail_page.goto(
                    detail_url,
                    wait_until="domcontentloaded",
                    timeout=config.PAGE_LOAD_TIMEOUT_MS,
                )
                item = await parse_detail_page(detail_page, partial)
                items.append(item)

                await asyncio.sleep(
                    random.uniform(
                        config.REQUEST_DELAY_MIN_MS / 1000,
                        config.REQUEST_DELAY_MAX_MS / 1000,
                    )
                )
            except Exception:
                self.stats["errors"] += 1
                self.logger.exception("scraper.detail_error", url=detail_url)
                items.append(self._partial_to_item(partial))
            finally:
                await detail_page.close()

        return items

    @staticmethod
    def _partial_to_item(p: dict) -> ScrapedItem:
        """Convert a partial dict (from search card) to a ScrapedItem."""
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


def _state_slug_to_name(slug: str) -> str:
    """Convert URL slug to human-readable state name.

    Handles special cases like 'puebla-l1' → 'Puebla',
    'coahuila-de-zaragoza' → 'Coahuila De Zaragoza'.
    """
    # Remove -l1 suffix (disambiguation suffix on Properstar)
    clean = slug.removesuffix("-l1")
    return clean.replace("-", " ").title()
