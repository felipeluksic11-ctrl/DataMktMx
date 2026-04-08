"""Cookie Bridge — solve WAF challenges with browser, reuse cookies with httpx.

Strategy:
1. Launch a stealth browser (Camoufox)
2. Navigate to ONE page to trigger and solve JS challenge
3. Extract all cookies from the browser context
4. Close the browser
5. Use cookies with httpx/curl_cffi for fast bulk requests
6. When cookies expire (403/503), re-solve with browser

This gives browser-level stealth for the challenge + httpx speed for data.

Usage:
    bridge = CookieBridge("https://www.properstar.com.mx")
    html = await bridge.get("https://www.properstar.com.mx/mexico/quintana-roo/comprar")
    # First call: browser solves WAF, then httpx with cookies
    # Subsequent calls: httpx only (fast)
"""

import asyncio
import time

import httpx

from shared.logging import get_logger
from shared.proxy.manager import ProxyManager
from shared.stealth.browser import create_stealth_browser

logger = get_logger("stealth.cookie_bridge")

# Headers that mimic a real Chrome browser
CHROME_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "es-MX,es;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Sec-Ch-Ua": '"Chromium";v="131", "Not_A Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

# Cookie validity — re-solve if older than this (seconds)
COOKIE_MAX_AGE_S = 25 * 60  # 25 min (Azure WAF default is 30 min)


class CookieBridge:
    """Solve WAF with browser once, then use cookies for fast httpx requests."""

    def __init__(
        self,
        base_url: str,
        proxy_manager: ProxyManager | None = None,
        card_selector: str = "article",
        timeout_s: float = 60.0,
    ):
        self.base_url = base_url
        self.proxy_manager = proxy_manager or ProxyManager()
        self.card_selector = card_selector
        self.timeout_s = timeout_s
        self._cookies: dict[str, str] = {}
        self._cookie_time: float = 0
        self._solve_count: int = 0
        self._request_count: int = 0
        self._client: httpx.AsyncClient | None = None

    @property
    def cookies_valid(self) -> bool:
        if not self._cookies:
            return False
        age = time.time() - self._cookie_time
        return age < COOKIE_MAX_AGE_S

    async def _solve_challenge(self, url: str | None = None) -> None:
        """Launch browser, navigate to a page, solve WAF, capture cookies."""
        solve_url = url or self.base_url

        browser, context = await create_stealth_browser(
            proxy_manager=self.proxy_manager,
        )

        try:
            page = await context.new_page()

            # Navigate and wait for content to load (WAF challenge auto-solves)
            await page.goto(solve_url, wait_until="domcontentloaded", timeout=45000)

            # Wait for actual content (cards) to confirm WAF passed
            try:
                await page.wait_for_selector(self.card_selector, timeout=20000)
            except Exception:
                # WAF might still be challenging — wait more
                await asyncio.sleep(5)
                try:
                    await page.wait_for_selector(self.card_selector, timeout=15000)
                except Exception:
                    logger.warning("cookie_bridge.cards_not_found", url=solve_url)

            # Extract cookies from browser context
            browser_cookies = await context.cookies()
            self._cookies = {}
            for c in browser_cookies:
                self._cookies[c["name"]] = c["value"]

            self._cookie_time = time.time()
            self._solve_count += 1

            # Also capture the User-Agent the browser used
            ua = await page.evaluate("navigator.userAgent")
            if ua:
                CHROME_HEADERS["User-Agent"] = ua

            logger.info(
                "cookie_bridge.solved",
                url=solve_url,
                cookies=len(self._cookies),
                solve_count=self._solve_count,
                cookie_names=list(self._cookies.keys()),
            )

        finally:
            await context.close()
            await browser.close()

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Get or create httpx client with current cookies."""
        if self._client is None or not self.cookies_valid:
            if self._client:
                await self._client.aclose()
            self._client = httpx.AsyncClient(
                timeout=self.timeout_s,
                follow_redirects=True,
                headers=CHROME_HEADERS,
                cookies=self._cookies,
            )
        return self._client

    async def get(self, url: str) -> str | None:
        """GET a URL using cookies. Solves WAF challenge if needed.

        Returns HTML string or None on failure.
        """
        # Solve WAF if cookies expired or not yet obtained
        if not self.cookies_valid:
            await self._solve_challenge(url)

        client = await self._ensure_client()

        try:
            resp = await client.get(url)
            self._request_count += 1

            # Check if WAF blocked us (cookie expired)
            if resp.status_code in (403, 503):
                logger.warning(
                    "cookie_bridge.waf_block",
                    status=resp.status_code,
                    url=url,
                    cookie_age_s=int(time.time() - self._cookie_time),
                )
                # Re-solve and retry
                await self._solve_challenge(url)
                client = await self._ensure_client()
                resp = await client.get(url)

                if resp.status_code in (403, 503):
                    logger.error("cookie_bridge.waf_block_persistent", url=url)
                    return None

            if resp.status_code >= 400:
                logger.warning("cookie_bridge.http_error", status=resp.status_code, url=url)
                return None

            return resp.text

        except httpx.TimeoutException:
            logger.warning("cookie_bridge.timeout", url=url)
            return None
        except Exception:
            logger.exception("cookie_bridge.request_error", url=url)
            return None

    async def close(self) -> None:
        """Close the httpx client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def get_stats(self) -> dict:
        return {
            "solve_count": self._solve_count,
            "request_count": self._request_count,
            "cookies_valid": self.cookies_valid,
            "cookie_age_s": int(time.time() - self._cookie_time) if self._cookie_time else 0,
            "cookie_count": len(self._cookies),
        }
