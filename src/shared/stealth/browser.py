"""Stealth browser factory — creates anti-detection browser contexts.

Uses Camoufox (Firefox-based) with unique fingerprints per worker.
Each worker gets its own browser instance with:
- Unique proxy session (from ProxyManager)
- Unique viewport, timezone, locale (from WorkerIdentity)
- Camoufox's built-in fingerprint randomization
- Resource blocking (images, fonts, media) to save proxy bandwidth
- Real-time bandwidth tracking with budget enforcement
"""

from shared.logging import get_logger
from shared.proxy.bandwidth import BandwidthTracker
from shared.proxy.manager import ProxyManager, ProxySession
from shared.stealth.identity import WorkerIdentity, create_identity

logger = get_logger("stealth.browser")

# Resources to block — saves ~80% bandwidth
# NOTE: keep "stylesheet" and "script" allowed — Cloudflare challenges need them
BLOCKED_RESOURCE_TYPES = {"image", "font", "media", "imageset"}
BLOCKED_URL_PATTERNS = [
    "google-analytics", "googletagmanager", "facebook.net",
    "doubleclick", "adservice", "hotjar", "clarity.ms",
    "sentry.io", "newrelic", "segment.com",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico",
    ".mp4", ".webm", ".mp3", ".ogg",
    ".pdf", ".zip",
]


async def create_worker_browser(
    identity: WorkerIdentity,
    proxy_session: ProxySession | None = None,
    portal_slug: str = "unknown",
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

    # Bandwidth tracker
    tracker = BandwidthTracker.get_instance()

    # Block heavy resources to save proxy bandwidth
    async def _block_resources(route):
        request = route.request
        if request.resource_type in BLOCKED_RESOURCE_TYPES:
            tracker.add_blocked()
            await route.abort()
            return
        url = request.url.lower()
        if any(pattern in url for pattern in BLOCKED_URL_PATTERNS):
            tracker.add_blocked()
            await route.abort()
            return
        await route.continue_()

    await context.route("**/*", _block_resources)

    # Track response sizes for bandwidth monitoring
    async def _track_response(response):
        try:
            body = await response.body()
            byte_count = len(body)
            tracker.add_bytes(byte_count, portal=portal_slug)
        except Exception:
            # Some responses (redirects, aborted) don't have a body
            pass

    context.on("response", _track_response)

    logger.info(
        "browser.created",
        worker=identity.worker_id,
        viewport=f"{identity.viewport_width}x{identity.viewport_height}",
        timezone=identity.timezone,
        locale=identity.locale,
        resource_blocking="enabled",
    )

    return browser, context


async def create_stealth_browser(config=None, proxy_manager=None, portal_slug="unknown"):
    """Create a browser with a random unique identity.

    Each call gets a unique worker_id seed, producing different
    viewport, timezone, locale, and delay profiles.
    """
    import random as _rng
    # Unique seed per browser instance — different fingerprint each time
    worker_id = f"w-{_rng.randint(100000, 999999)}"
    identity = create_identity(worker_id)
    if config:
        identity.headless = config.headless
        # DON'T override viewport — use the randomized one from identity
        identity.page_timeout_ms = config.timeout_ms
        identity.navigation_timeout_ms = config.navigation_timeout_ms

    proxy_session = None
    if proxy_manager and proxy_manager.has_proxies:
        proxy_session = proxy_manager.create_session("default")

    return await create_worker_browser(identity, proxy_session, portal_slug=portal_slug)


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
