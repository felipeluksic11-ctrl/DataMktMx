"""Stealth browser factory — creates anti-detection browser contexts.

Uses Camoufox (Firefox-based) with unique fingerprints per worker.
Each worker gets its own browser instance with:
- Unique proxy session (from ProxyManager)
- Unique viewport, timezone, locale (from WorkerIdentity)
- Camoufox's built-in fingerprint randomization
- uBlock Origin to block trackers
"""

from shared.logging import get_logger
from shared.proxy.manager import ProxyManager, ProxySession
from shared.stealth.identity import WorkerIdentity, create_identity

logger = get_logger("stealth.browser")


async def create_worker_browser(
    identity: WorkerIdentity,
    proxy_session: ProxySession | None = None,
):
    """Create a stealth browser + context for a specific worker.

    Returns (browser, context). Caller is responsible for closing both.
    """
    from camoufox import AsyncCamoufox

    launch_kwargs: dict = {
        "headless": identity.headless,
    }

    # Proxy — Playwright needs server/username/password as separate fields
    if proxy_session and proxy_session.proxy_url:
        from urllib.parse import urlparse
        parsed = urlparse(proxy_session.proxy_url)
        launch_kwargs["proxy"] = {
            "server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}",
            "username": parsed.username or "",
            "password": parsed.password or "",
        }
        logger.info(
            "browser.proxy_set",
            worker=identity.worker_id,
            provider=str(proxy_session.provider),
            server=f"{parsed.hostname}:{parsed.port}",
        )

    # Launch Camoufox — proxy must be passed both to launch AND context
    # Some versions of Camoufox/Playwright only respect proxy in context
    proxy_dict = launch_kwargs.pop("proxy", None)

    camoufox = AsyncCamoufox(**launch_kwargs)
    browser = await camoufox.__aenter__()

    # Create context with proxy + worker-specific viewport and locale
    context_kwargs = {
        "viewport": {"width": identity.viewport_width, "height": identity.viewport_height},
        "locale": identity.locale,
        "timezone_id": identity.timezone,
    }
    if proxy_dict:
        context_kwargs["proxy"] = proxy_dict

    context = await browser.new_context(**context_kwargs)
    context.set_default_timeout(identity.page_timeout_ms)
    context.set_default_navigation_timeout(identity.navigation_timeout_ms)

    logger.info(
        "browser.created",
        worker=identity.worker_id,
        viewport=f"{identity.viewport_width}x{identity.viewport_height}",
        timezone=identity.timezone,
        locale=identity.locale,
    )

    return browser, context


async def create_stealth_browser(config=None, proxy_manager=None):
    """Legacy wrapper — creates a browser with default identity.

    Use create_worker_browser() for distributed scraping.
    """
    identity = create_identity("default")
    if config:
        identity.headless = config.headless
        identity.viewport_width = config.viewport_width
        identity.viewport_height = config.viewport_height
        identity.page_timeout_ms = config.timeout_ms
        identity.navigation_timeout_ms = config.navigation_timeout_ms

    proxy_session = None
    if proxy_manager and proxy_manager.has_proxies:
        proxy_session = proxy_manager.create_session("default")

    return await create_worker_browser(identity, proxy_session)


# Keep BrowserConfig for backward compat
from dataclasses import dataclass

@dataclass
class BrowserConfig:
    headless: bool = True
    proxy_provider: str | None = None
    viewport_width: int = 1920
    viewport_height: int = 1080
    timeout_ms: int = 30_000
    navigation_timeout_ms: int = 60_000
