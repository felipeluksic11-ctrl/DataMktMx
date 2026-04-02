"""Stealth browser factory — creates anti-detection browser contexts.

Supports two engines:
- Camoufox (Firefox-based) — default for most portals
- Chromium (Playwright) — required for portals with Cloudflare (e.g. Inmuebles24)

Each worker gets its own browser instance with:
- Unique proxy session (from ProxyManager)
- Unique viewport, timezone, locale (from WorkerIdentity)
- Resource blocking (images, fonts, media) to save proxy bandwidth
- Real-time bandwidth tracking with budget enforcement
"""

from shared.logging import get_logger
from shared.proxy.bandwidth import BandwidthTracker
from shared.proxy.manager import ProxyManager, ProxySession
from shared.stealth.identity import WorkerIdentity, create_identity

logger = get_logger("stealth.browser")

# Resources to block — saves bandwidth
# NOTE: keep "script" allowed — Cloudflare challenges and SPA rendering need JS
# Stylesheets blocked — not needed for data extraction, saves ~1-2 MB/page
BLOCKED_RESOURCE_TYPES = {"image", "font", "media", "imageset", "stylesheet"}
BLOCKED_URL_PATTERNS = [
    "google-analytics", "googletagmanager", "facebook.net",
    "doubleclick", "adservice", "hotjar", "clarity.ms",
    "sentry.io", "newrelic", "segment.com",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico",
    ".mp4", ".webm", ".mp3", ".ogg",
    ".pdf", ".zip",
]

# Chromium anti-detection init script — removes headless indicators
CHROMIUM_ANTI_DETECT_SCRIPT = """
    Object.defineProperty(navigator, "webdriver", { get: () => undefined });
"""


async def _setup_context_interceptors(context, portal_slug: str = "unknown", allow_stylesheets: bool = False):
    """Set up resource blocking and bandwidth tracking on a context.

    Args:
        allow_stylesheets: If True, don't block CSS. Required for Cloudflare-
            protected portals where CSS is needed for the JS challenge to pass.
    """
    tracker = BandwidthTracker.get_instance()

    blocked_types = BLOCKED_RESOURCE_TYPES
    if allow_stylesheets:
        blocked_types = blocked_types - {"stylesheet"}

    async def _block_resources(route):
        request = route.request
        if request.resource_type in blocked_types:
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

    async def _track_response(response):
        try:
            body = await response.body()
            byte_count = len(body)
            tracker.add_bytes(byte_count, portal=portal_slug)
        except Exception:
            pass

    context.on("response", _track_response)


async def create_worker_browser(
    identity: WorkerIdentity,
    proxy_session: ProxySession | None = None,
    portal_slug: str = "unknown",
):
    """Create a stealth browser + context using Camoufox (Firefox).

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

    await _setup_context_interceptors(context, portal_slug, allow_stylesheets=False)

    logger.info(
        "browser.created",
        engine="camoufox",
        worker=identity.worker_id,
        viewport=f"{identity.viewport_width}x{identity.viewport_height}",
        timezone=identity.timezone,
        locale=identity.locale,
        resource_blocking="enabled",
    )

    return browser, context


async def create_chromium_browser(
    identity: WorkerIdentity,
    proxy_session: ProxySession | None = None,
    portal_slug: str = "unknown",
):
    """Create a stealth browser + context using Playwright Chromium.

    Required for Cloudflare-protected portals (e.g. Inmuebles24).
    Camoufox/Firefox gets hard-blocked by CF; Chromium with anti-detection
    flags passes the JS challenge reliably.

    Returns (browser, context). Caller is responsible for closing both.
    """
    from playwright.async_api import async_playwright

    pw = await async_playwright().start()

    launch_args = [
        "--disable-blink-features=AutomationControlled",
    ]

    browser = await pw.chromium.launch(
        headless=identity.headless,
        args=launch_args,
    )

    # Build context kwargs
    context_kwargs = {
        "viewport": {"width": identity.viewport_width, "height": identity.viewport_height},
        "locale": identity.locale,
        "timezone_id": identity.timezone,
        "user_agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    # Proxy
    if proxy_session and proxy_session.proxy_url:
        from urllib.parse import urlparse
        parsed = urlparse(proxy_session.proxy_url)
        context_kwargs["proxy"] = {
            "server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}",
            "username": parsed.username or "",
            "password": parsed.password or "",
        }
        logger.info(
            "browser.proxy_set",
            engine="chromium",
            worker=identity.worker_id,
            provider=str(proxy_session.provider),
            server=f"{parsed.hostname}:{parsed.port}",
        )

    context = await browser.new_context(**context_kwargs)
    context.set_default_timeout(identity.page_timeout_ms)
    context.set_default_navigation_timeout(identity.navigation_timeout_ms)

    # Anti-detection: remove navigator.webdriver
    await context.add_init_script(CHROMIUM_ANTI_DETECT_SCRIPT)

    # CF-protected portals need stylesheets for the JS challenge
    await _setup_context_interceptors(context, portal_slug, allow_stylesheets=True)

    # Store playwright instance on browser for cleanup
    browser._playwright = pw

    logger.info(
        "browser.created",
        engine="chromium",
        worker=identity.worker_id,
        viewport=f"{identity.viewport_width}x{identity.viewport_height}",
        timezone=identity.timezone,
        locale=identity.locale,
        resource_blocking="enabled",
    )

    return browser, context


async def create_chromium_context(
    browser,
    identity: WorkerIdentity,
    proxy_session: ProxySession | None = None,
    portal_slug: str = "unknown",
):
    """Create a fresh context on an existing Chromium browser.

    Use this for context-level rotation (new cookies/fingerprint, same process).
    Cheaper than creating a new browser — avoids Chromium startup overhead.
    """
    context_kwargs = {
        "viewport": {"width": identity.viewport_width, "height": identity.viewport_height},
        "locale": identity.locale,
        "timezone_id": identity.timezone,
        "user_agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    if proxy_session and proxy_session.proxy_url:
        from urllib.parse import urlparse
        parsed = urlparse(proxy_session.proxy_url)
        context_kwargs["proxy"] = {
            "server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}",
            "username": parsed.username or "",
            "password": parsed.password or "",
        }

    context = await browser.new_context(**context_kwargs)
    context.set_default_timeout(identity.page_timeout_ms)
    context.set_default_navigation_timeout(identity.navigation_timeout_ms)
    await context.add_init_script(CHROMIUM_ANTI_DETECT_SCRIPT)
    await _setup_context_interceptors(context, portal_slug, allow_stylesheets=True)

    return context


async def create_stealth_browser(config=None, proxy_manager=None, portal_slug="unknown", engine="camoufox"):
    """Create a browser with a random unique identity.

    Each call gets a unique worker_id seed, producing different
    viewport, timezone, locale, and delay profiles.

    Args:
        engine: "camoufox" (default) or "chromium" (for CF-protected portals)
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

    if engine == "chromium":
        return await create_chromium_browser(identity, proxy_session, portal_slug=portal_slug)

    return await create_worker_browser(identity, proxy_session, portal_slug=portal_slug)


async def close_browser(browser):
    """Safely close a browser, handling both Camoufox and Chromium."""
    try:
        # If it's a Chromium browser, also stop playwright
        pw = getattr(browser, "_playwright", None)
        await browser.close()
        if pw:
            await pw.stop()
    except Exception:
        pass


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
