"""Lightweight HTTP-only scraper base class.

Uses httpx instead of Playwright for portals that serve listing data
in server-side rendered HTML. ~20-40x less bandwidth and ~5-15x faster
than browser-based scraping.

Use for: Lamudi (Next.js SSR), Propiedades.com (microdata in HTML).
NOT for: Inmuebles24 (Cloudflare JS challenge requires browser).
"""

import asyncio
import random
from collections.abc import Callable, Awaitable

import httpx

from scrapers.base import ScrapedItem
from shared.logging import get_logger
from shared.proxy.bandwidth import BandwidthTracker, BudgetExhausted

logger = get_logger(__name__)

# Callback type: receives a list of ScrapedItems, returns stats dict
OnPageCallback = Callable[["list[ScrapedItem]"], Awaitable[dict[str, int]]]

# Realistic browser headers
DEFAULT_HEADERS = {
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "es-MX,es;q=0.9,en-US;q=0.5,en;q=0.3",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

USER_AGENTS = [
    (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
]


class HttpScraper:
    """Lightweight HTTP-only scraper for SSR portals.

    Subclasses must implement:
    - portal_slug: str
    - portal_name: str
    - _parse_search_html(html, url) -> list[dict]
    - scrape() -> list[ScrapedItem]
    """

    portal_slug: str = ""
    portal_name: str = ""

    # Bandwidth: direct VPS IP, doesn't count against proxy budget
    via_proxy: bool = False

    # Delays between requests (ms)
    delay_min_ms: int = 1000
    delay_max_ms: int = 3000

    # Max retries per request
    max_retries: int = 3

    def __init__(self, proxy_url: str | None = None):
        self.proxy_url = proxy_url
        self.via_proxy = proxy_url is not None
        self.logger = get_logger(f"http_scraper.{self.portal_slug}")
        self.on_page_scraped: OnPageCallback | None = None
        self.total_items_scraped: int = 0
        self.stats: dict[str, int] = {
            "scraped": 0,
            "errors": 0,
            "pages": 0,
        }
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the httpx client (lazy init)."""
        if self._client is None:
            headers = {**DEFAULT_HEADERS}
            headers["User-Agent"] = random.choice(USER_AGENTS)
            self._client = httpx.AsyncClient(
                follow_redirects=True,
                timeout=30.0,
                headers=headers,
                proxy=self.proxy_url,
            )
        return self._client

    async def close(self):
        """Close the httpx client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def fetch_page(self, url: str) -> str | None:
        """Fetch a URL and return HTML content. Tracks bandwidth.

        Returns None on failure (after retries).
        """
        tracker = BandwidthTracker.get_instance()

        # Budget check (only matters if via_proxy)
        if self.via_proxy:
            tracker.check_budget()

        client = await self._get_client()

        for attempt in range(1, self.max_retries + 1):
            try:
                response = await client.get(url)
                byte_count = len(response.content)
                tracker.add_bytes(
                    byte_count,
                    portal=self.portal_slug,
                    via_proxy=self.via_proxy,
                )

                if response.status_code == 200:
                    self.stats["pages"] += 1
                    self.logger.info(
                        "http.page_fetched",
                        url=url,
                        size_kb=round(byte_count / 1024, 1),
                        status=response.status_code,
                    )
                    return response.text

                if response.status_code == 403:
                    self.logger.warning(
                        "http.blocked",
                        url=url,
                        status=response.status_code,
                        attempt=attempt,
                    )
                    # Rotate user-agent on block
                    client.headers["User-Agent"] = random.choice(
                        USER_AGENTS,
                    )
                    await asyncio.sleep(random.uniform(3, 8))
                    continue

                if response.status_code >= 500:
                    self.logger.warning(
                        "http.server_error",
                        url=url,
                        status=response.status_code,
                        attempt=attempt,
                    )
                    await asyncio.sleep(random.uniform(2, 5))
                    continue

                # Other non-200 status
                self.logger.warning(
                    "http.bad_status",
                    url=url,
                    status=response.status_code,
                )
                return None

            except httpx.TimeoutException:
                self.logger.warning(
                    "http.timeout", url=url, attempt=attempt,
                )
                await asyncio.sleep(random.uniform(2, 5))
            except httpx.HTTPError as e:
                self.logger.warning(
                    "http.error", url=url, error=str(e), attempt=attempt,
                )
                await asyncio.sleep(random.uniform(2, 5))

        self.stats["errors"] += 1
        self.logger.error("http.all_retries_failed", url=url)
        return None

    async def _delay(self):
        """Random delay between requests."""
        await asyncio.sleep(
            random.uniform(
                self.delay_min_ms / 1000,
                self.delay_max_ms / 1000,
            )
        )

    async def run(self, job=None) -> list[ScrapedItem]:
        """Execute scraping with logging."""
        import datetime

        self.logger.info("http_scraper.started", portal=self.portal_slug)
        start = datetime.datetime.now(datetime.UTC)
        tracker = BandwidthTracker.get_instance()

        try:
            items = await self.scrape()
            self.stats["scraped"] = len(items)

            bw_stats = tracker.get_stats()
            portal_mb = bw_stats["by_portal"].get(self.portal_slug, 0)
            self.logger.info(
                "http_scraper.completed",
                portal=self.portal_slug,
                total=len(items),
                pages=self.stats["pages"],
                duration_s=(
                    datetime.datetime.now(datetime.UTC) - start
                ).total_seconds(),
                bandwidth_portal_mb=portal_mb,
                bandwidth_total_mb_all=bw_stats["total_mb_all"],
                proxy_mb=bw_stats["total_mb"],
            )
            return items
        except BudgetExhausted as e:
            self.stats["errors"] += 1
            tracker.log_summary()
            self.logger.error(
                "http_scraper.budget_exhausted",
                portal=self.portal_slug,
                used_mb=e.used_mb,
                budget_mb=e.budget_mb,
            )
            raise
        except Exception:
            self.stats["errors"] += 1
            self.logger.exception(
                "http_scraper.failed", portal=self.portal_slug,
            )
            raise
        finally:
            await self.close()

    async def scrape(self) -> list[ScrapedItem]:
        """Override in subclass."""
        raise NotImplementedError
