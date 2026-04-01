"""Propiedades.com scraper — crawls search results and detail pages."""

import asyncio
import random

from playwright.async_api import Page, BrowserContext

from scrapers.base import BaseScraper, ScrapedItem
from scrapers.propiedades import config
from scrapers.propiedades.parser import parse_search_results, parse_detail_page
from shared.proxy.manager import ProxyManager
from shared.stealth.browser import BrowserConfig, create_stealth_browser


class PropiedadesScraper(BaseScraper):
    portal_slug = "propiedades"
    portal_name = "Propiedades.com"

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
        self.mode = mode
        self.known_cache = known_cache
        self.states = states or config.STATES
        self.operations = operations or ["venta", "renta"]
        self.max_pages = max_pages
        self.visit_detail = visit_detail

    async def scrape(self) -> list[ScrapedItem]:
        browser, context = await create_stealth_browser(
            config=BrowserConfig(headless=True),
            proxy_manager=self.proxy_manager,
        )

        try:
            items: list[ScrapedItem] = []

            for state in self.states:
                for operation in self.operations:
                    search_items = await self._scrape_search(
                        context, state, operation
                    )
                    items.extend(search_items)
                    self.logger.info(
                        "scraper.search_done",
                        state=state,
                        operation=operation,
                        count=len(search_items),
                    )

            return items
        finally:
            await context.close()
            await browser.close()

    async def _scrape_search(
        self,
        context: BrowserContext,
        state: str,
        operation: str,
    ) -> list[ScrapedItem]:
        """Scrape all pages of a search query (state + operation)."""
        items: list[ScrapedItem] = []
        op_slug = config.OPERATIONS.get(operation, operation)

        for page_num in range(1, self.max_pages + 1):
            url = config.SEARCH_URL_TEMPLATE.format(
                operation=op_slug,
                state=state,
                page=page_num,
            )

            page = await context.new_page()
            try:
                page_items = await self._scrape_search_page(
                    page, url, operation, state=state
                )

                if not page_items:
                    self.logger.info("scraper.no_more_results", page=page_num, state=state)
                    break

                if self.on_page_scraped:
                    await self.on_page_scraped(page_items)

                items.extend(page_items)
                self.logger.info(
                    "scraper.page_done",
                    page=page_num,
                    count=len(page_items),
                    total=len(items),
                    state=state,
                )

                # Random delay between pages
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
    ) -> list[ScrapedItem]:
        """Scrape a single search results page."""
        response = await page.goto(url, wait_until="domcontentloaded", timeout=config.PAGE_LOAD_TIMEOUT_MS)

        if not response or response.status >= 400:
            self.logger.warning("scraper.bad_response", url=url, status=response.status if response else None)
            return []

        # Wait for listing cards to render
        try:
            await page.wait_for_selector(
                config.SELECTORS["listing_card"],
                timeout=10000,
            )
        except Exception:
            self.logger.warning("scraper.no_cards_selector", url=url)
            return []

        partials = await parse_search_results(page)
        if not partials:
            return []

        # Enrich with operation and state from search URL
        state_name = state.replace("-", " ").title()
        for p in partials:
            p["operation"] = p.get("badge_operation") or operation
            p["state"] = state_name
            p["country"] = p.get("country") or "México"

        if not self.visit_detail:
            return [self._partial_to_item(p) for p in partials]

        # Visit detail pages for richer data
        items: list[ScrapedItem] = []
        for partial in partials:
            detail_url = partial.get("detail_url")
            if not detail_url:
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
                # Fall back to card data
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
            street_and_number=p.get("street_and_number"),
            neighborhood=p.get("neighborhood"),
            city=p.get("city"),
            municipality=p.get("municipality"),
            state=p.get("state"),
            country=p.get("country") or "México",
            zip_code=p.get("zip_code"),
            latitude=p.get("latitude"),
            longitude=p.get("longitude"),
            bedrooms=p.get("bedrooms"),
            bathrooms=p.get("bathrooms"),
            half_bathrooms=p.get("half_bathrooms"),
            parking_spaces=p.get("parking_spaces"),
            construction_m2=p.get("construction_m2"),
            land_m2=p.get("land_m2"),
            antiquity=p.get("antiquity"),
            built_levels=p.get("built_levels"),
        )
