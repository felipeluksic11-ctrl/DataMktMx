"""Inmuebles24 scraper — crawls search results and detail pages.

Anti-bot strategy:
- Fresh browser + proxy session per state
- Rotate proxy session every 3-5 pages within a state
- On 403/block: immediate session rotation with backoff
- Gaussian delays 3-8s between pages (configurable)
"""

import asyncio
import random

from playwright.async_api import Page

from scrapers.base import BaseScraper, ScrapedItem
from scrapers.inmuebles24 import config
from shared.config import settings
from scrapers.inmuebles24.parser import parse_search_results, parse_detail_page
from shared.proxy.manager import ProxyManager


class Inmuebles24Scraper(BaseScraper):
    portal_slug = "inmuebles24"
    portal_name = "Inmuebles24"

    # I24 is aggressive with anti-bot — rotate more frequently
    rotate_min_pages = config.SESSION_ROTATE_MIN_PAGES
    rotate_max_pages = config.SESSION_ROTATE_MAX_PAGES
    rotate_delay_min_s = config.SESSION_ROTATE_DELAY_MIN_S
    rotate_delay_max_s = config.SESSION_ROTATE_DELAY_MAX_S

    def __init__(
        self,
        proxy_manager: ProxyManager | None = None,
        states: list[str] | None = None,
        operations: list[str] | None = None,
        property_types: list[str] | None = None,
        max_pages: int = config.MAX_PAGES_PER_SEARCH,
        visit_detail: bool = True,
        mode: str = "full",  # "full" or "incremental"
        known_cache=None,  # KnownListingsCache for incremental mode
    ):
        super().__init__(proxy_manager)
        self.states = states or config.STATES
        self.operations = operations or ["venta", "renta", "vacacional"]
        self.property_types = property_types or ["all"]
        self.max_pages = max_pages
        self.visit_detail = visit_detail
        self.mode = mode
        self.known_cache = known_cache

        # In incremental mode, limit pages and use sort-by-recent URL
        if mode == "incremental":
            from scrapers.base.modes import INCREMENTAL_MAX_PAGES
            self.max_pages = min(max_pages, INCREMENTAL_MAX_PAGES)

    async def scrape(self) -> list[ScrapedItem]:
        items: list[ScrapedItem] = []

        for state in self.states:
            await self._init_browser_for_state()
            try:
                for operation in self.operations:
                    # Reset block counter per operation — a blocked IP for venta
                    # doesn't mean all operations are blocked
                    self._consecutive_blocks = 0
                    for prop_type in self.property_types:
                        search_items = await self._scrape_search(
                            state, operation, prop_type
                        )
                        items.extend(search_items)
                        self.logger.info(
                            "scraper.search_done",
                            state=state,
                            operation=operation,
                            property_type=prop_type,
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
        property_type: str,
    ) -> list[ScrapedItem]:
        """Scrape all pages of a search query (state + operation + type).

        Rotates proxy session every N pages to avoid detection.
        """
        items: list[ScrapedItem] = []
        op_slug = config.OPERATIONS.get(operation, operation)
        type_slug = config.PROPERTY_TYPES.get(property_type, property_type)

        for page_num in range(1, self.max_pages + 1):
            # Check if we need to rotate proxy session
            await self._maybe_rotate()

            # Use sort-by-recent URL in incremental mode
            template = config.SEARCH_URL_RECENT_TEMPLATE if self.mode == "incremental" else config.SEARCH_URL_TEMPLATE
            url = template.format(
                property_type=type_slug,
                operation=op_slug,
                location=state,
                page=page_num,
            )

            page = await self._current_context.new_page()
            try:
                page_items, was_blocked = await self._scrape_search_page(
                    page, url, operation, property_type, state=state
                )

                # Handle block/403 — rotate IP and retry up to 3 times
                if was_blocked:
                    await page.close()
                    max_retries = 3
                    for retry in range(max_retries):
                        self._consecutive_blocks += 1
                        self.logger.warning(
                            "scraper.blocked",
                            page=page_num,
                            state=state,
                            retry=retry + 1,
                            consecutive_blocks=self._consecutive_blocks,
                        )

                        if self._consecutive_blocks >= 6:
                            self.logger.warning(
                                "scraper.operation_blocked",
                                state=state,
                                operation=operation,
                                consecutive_blocks=self._consecutive_blocks,
                            )
                            break

                        # Rotate to new IP and retry
                        await self._rotate_session(reason="403_blocked")
                        page = await self._current_context.new_page()
                        page_items, was_blocked = await self._scrape_search_page(
                            page, url, operation, property_type, state=state
                        )

                        if not was_blocked:
                            self._consecutive_blocks = 0
                            break
                        await page.close()
                    else:
                        # All retries exhausted
                        continue

                    if was_blocked and self._consecutive_blocks >= 6:
                        break
                else:
                    self._consecutive_blocks = 0

                if not page_items:
                    self.logger.info("scraper.no_more_results", page=page_num, state=state)
                    break

                # In incremental mode: check if we've hit known listings
                if self.mode == "incremental" and self.known_cache:
                    ext_ids = [item.external_id for item in page_items]
                    if self.known_cache.should_stop(ext_ids):
                        new_items = [item for item in page_items if not self.known_cache.is_known(item.external_id)]
                        items.extend(new_items)
                        self.logger.info(
                            "scraper.incremental_stop",
                            page=page_num, state=state,
                            new_in_page=len(new_items), known_in_page=len(ext_ids) - len(new_items),
                        )
                        break

                # Persist immediately if callback is set
                if self.on_page_scraped:
                    await self.on_page_scraped(page_items)

                items.extend(page_items)
                self.total_items_scraped += len(page_items)
                self._pages_since_rotation += 1

                # Spot check: verify extraction against screenshot every N items
                if (self.total_items_scraped % self.spot_check_interval < len(page_items)
                        and page_items and settings.anthropic_api_key):
                    try:
                        from supervisors.spot_checker import SpotChecker
                        screenshot = await page.screenshot(full_page=False)
                        sample = page_items[0]
                        checker = SpotChecker()
                        await checker.verify_extraction(
                            screenshot_bytes=screenshot,
                            extracted_data={
                                "title": sample.title,
                                "price": sample.price,
                                "currency": sample.currency,
                                "bedrooms": sample.bedrooms,
                                "bathrooms": sample.bathrooms,
                                "parking_spaces": sample.parking_spaces,
                                "construction_m2": sample.construction_m2,
                                "land_m2": sample.land_m2,
                                "neighborhood": sample.neighborhood,
                                "municipality": sample.municipality,
                                "state": sample.state,
                                "property_type": sample.property_type,
                            },
                            portal_name=self.portal_name,
                        )
                    except Exception:
                        self.logger.exception("scraper.spot_check_error")

                self.logger.info(
                    "scraper.page_done",
                    page=page_num,
                    count=len(page_items),
                    total=len(items),
                    state=state,
                    pages_until_rotate=self._rotate_after - self._pages_since_rotation,
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
        property_type: str,
        state: str = "",
    ) -> tuple[list[ScrapedItem], bool]:
        """Scrape a single search results page.

        Returns (items, was_blocked) — was_blocked=True on 403/captcha.
        """
        response = await page.goto(url, wait_until="domcontentloaded", timeout=config.PAGE_LOAD_TIMEOUT_MS)

        if not response:
            self.logger.warning("scraper.no_response", url=url)
            return [], False

        # If Cloudflare challenge, wait for it to resolve
        if response.status == 403 or response.status == 503:
            # Give CF challenge time to execute JS and redirect
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
                # Re-check URL — CF may have redirected after challenge
                final_url = page.url
                if final_url != url:
                    self.logger.info("scraper.cf_redirect", from_url=url, to_url=final_url)
            except Exception:
                pass

            # Check final page content after potential CF challenge
            content = await page.content()
            has_cards = await page.query_selector(config.SELECTORS["listing_card"])
            if has_cards:
                # CF challenge passed — continue with normal parsing
                self.logger.info("scraper.cf_challenge_passed", url=url)
            else:
                self.logger.warning(
                    "scraper.blocked_detail",
                    url=url,
                    status=response.status,
                    has_cf="challenge" in content.lower() or "cf-" in content.lower(),
                    content_len=len(content),
                )
                return [], True

        if response.status >= 400:
            self.logger.warning("scraper.bad_response", url=url, status=response.status)
            return [], False

        # Check for captcha/challenge page in content
        content = await page.content()
        if self._is_blocked_response(response, content):
            return [], True

        # Wait for listing cards to render
        try:
            await page.wait_for_selector(
                config.SELECTORS["listing_card"],
                timeout=10000,
            )
        except Exception:
            self.logger.warning("scraper.no_cards_selector", url=url)
            return [], False

        partials = await parse_search_results(page)
        if not partials:
            return [], False

        # Enrich with operation, property type, and state from search URL
        state_name = state.replace("-", " ").title()
        for p in partials:
            p["operation"] = operation
            if property_type != "all" and not p.get("property_type"):
                p["property_type"] = property_type
            p["state"] = state_name
            p["country"] = "México"

        if not self.visit_detail:
            return [self._partial_to_item(p) for p in partials], False

        # Visit detail pages for richer data (m², antiquity, amenities, etc.)
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
                    timeout=15000,
                )
                item = await parse_detail_page(detail_page, partial)
                items.append(item)

                await asyncio.sleep(random.uniform(0.5, 1.5))
            except Exception:
                self.stats["errors"] += 1
                self.logger.exception("scraper.detail_error", url=detail_url)
                items.append(self._partial_to_item(partial))
            finally:
                await detail_page.close()

        return items, False

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
            country="México",
            bedrooms=p.get("bedrooms"),
            bathrooms=p.get("bathrooms"),
            half_bathrooms=p.get("half_bathrooms"),
            parking_spaces=p.get("parking_spaces"),
            construction_m2=p.get("construction_m2"),
            land_m2=p.get("land_m2"),
            antiquity=p.get("antiquity"),
            built_levels=p.get("built_levels"),
        )
