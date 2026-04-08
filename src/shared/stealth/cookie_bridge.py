"""Cookie Bridge — solve WAF challenges with browser, reuse cookies with curl_cffi.

Strategy:
1. Launch a stealth browser (Camoufox)
2. Navigate to ONE page to trigger and solve JS challenge / Akamai / WAF
3. Extract all cookies from the browser context
4. Close the browser
5. Use cookies with curl_cffi (Chrome TLS fingerprint) for fast bulk requests
6. When cookies expire (403/503), re-solve with browser

curl_cffi impersonates Chrome's TLS fingerprint (JA3/JA4), which is required
for Akamai Bot Manager and similar systems that verify TLS + cookies together.

Usage:
    bridge = CookieBridge("https://propiedades.com")
    html = await bridge.get("https://propiedades.com/inmuebles-en-venta-en-ciudad-de-mexico")
"""

import asyncio
import time

from shared.logging import get_logger
from shared.proxy.manager import ProxyManager
from shared.stealth.browser import create_stealth_browser

logger = get_logger("stealth.cookie_bridge")

# Cookie validity — re-solve if older than this (seconds)
COOKIE_MAX_AGE_S = 25 * 60  # 25 min


class CookieBridge:
    """Solve WAF with browser once, then use cookies with curl_cffi for speed."""

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
        self._user_agent: str = ""
        self._session = None

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
            await page.goto(solve_url, wait_until="domcontentloaded", timeout=45000)

            # Wait for actual content to confirm WAF passed
            try:
                await page.wait_for_selector(self.card_selector, timeout=20000)
            except Exception:
                await asyncio.sleep(5)
                try:
                    await page.wait_for_selector(self.card_selector, timeout=15000)
                except Exception:
                    logger.warning("cookie_bridge.cards_not_found", url=solve_url)

            # Extract cookies
            browser_cookies = await context.cookies()
            self._cookies = {c["name"]: c["value"] for c in browser_cookies}
            self._cookie_time = time.time()
            self._solve_count += 1

            # Capture User-Agent
            self._user_agent = await page.evaluate("navigator.userAgent") or ""

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

        # Reset curl_cffi session with new cookies
        self._session = None

    def _get_session(self):
        """Get or create curl_cffi session with Chrome TLS impersonation."""
        if self._session is None:
            from curl_cffi.requests import Session
            self._session = Session(
                impersonate="chrome131",
                timeout=self.timeout_s,
            )
            # Set cookies
            for name, value in self._cookies.items():
                self._session.cookies.set(name, value)
            # Set User-Agent from browser
            if self._user_agent:
                self._session.headers["User-Agent"] = self._user_agent

        return self._session

    async def get(self, url: str) -> str | None:
        """GET a URL using cookies + Chrome TLS fingerprint.

        Returns HTML string or None on failure.
        """
        if not self.cookies_valid:
            await self._solve_challenge(url)

        # curl_cffi is synchronous — run in thread pool
        loop = asyncio.get_event_loop()
        try:
            resp = await loop.run_in_executor(None, self._sync_get, url)
            return resp
        except Exception:
            logger.exception("cookie_bridge.request_error", url=url)
            return None

    def _sync_get(self, url: str) -> str | None:
        """Synchronous GET with curl_cffi (Chrome TLS impersonation)."""
        session = self._get_session()

        try:
            resp = session.get(url, allow_redirects=True)
            self._request_count += 1

            if resp.status_code in (403, 503):
                logger.warning(
                    "cookie_bridge.waf_block",
                    status=resp.status_code,
                    url=url,
                    cookie_age_s=int(time.time() - self._cookie_time),
                )
                return None  # Caller should trigger re-solve

            if resp.status_code >= 400:
                logger.warning("cookie_bridge.http_error", status=resp.status_code, url=url)
                return None

            return resp.text

        except Exception as e:
            logger.warning("cookie_bridge.curl_error", url=url, error=str(e)[:200])
            return None

    async def close(self) -> None:
        """Close the session."""
        if self._session:
            self._session.close()
            self._session = None

    def get_stats(self) -> dict:
        return {
            "solve_count": self._solve_count,
            "request_count": self._request_count,
            "cookies_valid": self.cookies_valid,
            "cookie_age_s": int(time.time() - self._cookie_time) if self._cookie_time else 0,
        }
