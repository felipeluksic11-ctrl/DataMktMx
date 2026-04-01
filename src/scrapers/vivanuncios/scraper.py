"""Vivanuncios scraper — reuses Inmuebles24 parser since same frontend."""

import asyncio
import random

from playwright.async_api import Page, BrowserContext

from scrapers.base import BaseScraper, ScrapedItem
from scrapers.inmuebles24.parser import parse_search_results, parse_detail_page
from scrapers.vivanuncios import config
from shared.proxy.manager import ProxyManager
from shared.stealth.browser import BrowserConfig, create_stealth_browser


class VivanunciosScraper(BaseScraper):
    portal_slug = "vivanuncios"
    portal_name = "Vivanuncios"

    def __init__(
        self,
        proxy_manager: ProxyManager | None = None,
        states: list[str] | None = None,
        operations: list[str] | None = None,
        max_pages: int = config.MAX_PAGES_PER_SEARCH,
        visit_detail: bool = True,
    ):
        super().__init__(proxy_manager)
        self.states = states or config.STATES
        self.operations = operations or ["venta", "renta"]
        self.max_pages = max_pages
        self.visit_detail = visit_detail

    def _build_url(self, state: str, operation: str, page: int) -> str:
        op_slug = config.OPERATIONS.get(operation, operation)
        loc_code = config.STATE_CODES.get(state, "")
        return f"{config.BASE_URL}/s-{op_slug}-inmuebles/{state}/v1{config.CATEGORY_CODE}{loc_code}p{page}"

    async def scrape(self) -> list[ScrapedItem]:
        browser, context = await create_stealth_browser(
            config=BrowserConfig(headless=True),
            proxy_manager=self.proxy_manager,
        )

        try:
            items: list[ScrapedItem] = []
            for state in self.states:
                for operation in self.operations:
                    search_items = await self._scrape_search(context, state, operation)
                    items.extend(search_items)
                    self.logger.info(
                        "scraper.search_done",
                        state=state, operation=operation, count=len(search_items),
                    )
            return items
        finally:
            await context.close()
            await browser.close()

    async def _scrape_search(self, context: BrowserContext, state: str, operation: str) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []

        for page_num in range(1, self.max_pages + 1):
            url = self._build_url(state, operation, page_num)
            page = await context.new_page()
            try:
                response = await page.goto(url, wait_until="domcontentloaded", timeout=config.PAGE_LOAD_TIMEOUT_MS)
                if not response or response.status >= 400:
                    break

                try:
                    await page.wait_for_selector(config.SELECTORS["listing_card"], timeout=10000)
                except Exception:
                    break

                # Reuse I24 parser — same HTML structure
                partials = await parse_search_results(page)
                if not partials:
                    break

                state_name = state.replace("-", " ").title()
                for p in partials:
                    p["operation"] = operation
                    p["state"] = state_name
                    p["country"] = "México"
                    # Fix URLs to use Vivanuncios domain
                    if p.get("url_listing") and p["url_listing"].startswith("/"):
                        p["url_listing"] = config.BASE_URL + p["url_listing"]
                    if p.get("detail_url") and p["detail_url"].startswith("/"):
                        p["detail_url"] = config.BASE_URL + p["detail_url"]

                if self.visit_detail:
                    for partial in partials:
                        detail_url = partial.get("detail_url")
                        if not detail_url:
                            continue
                        detail_page = await context.new_page()
                        try:
                            await detail_page.goto(detail_url, wait_until="domcontentloaded", timeout=config.PAGE_LOAD_TIMEOUT_MS)
                            item = await parse_detail_page(detail_page, partial)
                            items.append(item)
                            await asyncio.sleep(random.uniform(
                                config.REQUEST_DELAY_MIN_MS / 1000,
                                config.REQUEST_DELAY_MAX_MS / 1000,
                            ))
                        except Exception:
                            self.stats["errors"] += 1
                            items.append(self._partial_to_item(partial))
                        finally:
                            await detail_page.close()
                else:
                    items.extend([self._partial_to_item(p) for p in partials])

                if self.on_page_scraped:
                    page_items_viv = items[-len(partials):]  # items just added
                    await self.on_page_scraped(page_items_viv)

                self.logger.info("scraper.page_done", page=page_num, count=len(partials), total=len(items))
                await asyncio.sleep(random.uniform(
                    config.REQUEST_DELAY_MIN_MS / 1000,
                    config.REQUEST_DELAY_MAX_MS / 1000,
                ))
            except Exception:
                self.stats["errors"] += 1
                self.logger.exception("scraper.page_error", page=page_num, url=url)
            finally:
                await page.close()

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
            country="México",
            bedrooms=p.get("bedrooms"),
            bathrooms=p.get("bathrooms"),
            half_bathrooms=p.get("half_bathrooms"),
            parking_spaces=p.get("parking_spaces"),
            construction_m2=p.get("construction_m2"),
            land_m2=p.get("land_m2"),
        )
