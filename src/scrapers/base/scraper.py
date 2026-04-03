import abc
import asyncio
import datetime
import random
from collections.abc import Callable, Awaitable
from dataclasses import dataclass, field
from typing import Optional

from shared.db.models import ScrapeJob
from shared.logging import get_logger
from shared.proxy.bandwidth import BandwidthTracker, BudgetExhausted
from shared.proxy.manager import ProxyManager
from shared.stealth.browser import BrowserConfig, create_stealth_browser

logger = get_logger(__name__)

# Callback type: receives a list of ScrapedItems, returns stats dict
OnPageCallback = Callable[["list[ScrapedItem]"], Awaitable[dict[str, int]]]

# Default rotation settings (overridable per portal via config)
DEFAULT_ROTATE_MIN_PAGES = 4
DEFAULT_ROTATE_MAX_PAGES = 7
DEFAULT_ROTATE_DELAY_MIN_S = 4.0
DEFAULT_ROTATE_DELAY_MAX_S = 8.0


@dataclass
class ScrapedItem:
    """Standard output from any portal scraper — matches full mining spec."""

    external_id: str

    # Identifiers
    url_listing: str | None = None
    internal_code: str | None = None
    title: str | None = None
    description: str | None = None

    # Classification
    operation: str | None = None  # venta | renta | vacacional
    property_type: str | None = None  # casa, departamento, terreno, etc.
    listing_type: str | None = None  # alias for operation (kept for compat)

    # Price
    price: float | None = None
    currency: str | None = None  # MXN | USD
    maintenance_fee: float | None = None

    # Location
    street_and_number: str | None = None
    neighborhood: str | None = None  # vecindario o barrio
    city: str | None = None
    municipality: str | None = None
    state: str | None = None
    country: str | None = None
    zip_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None

    # Media (URLs only, no files)
    video_url: str | None = None
    tour_360_url: str | None = None
    images_count: int = 0

    # Dimensions
    land_m2: float | None = None
    construction_m2: float | None = None

    # Age / status
    antiquity: str | None = None  # preventa | en_construccion | a_estrenar | <years>
    construction_years: int | None = None

    # Rooms & spaces
    bedrooms: int | None = None
    bathrooms: int | None = None
    half_bathrooms: int | None = None
    parking_spaces: int | None = None

    # Más ambientes (JSONB list of strings)
    extra_rooms: list[str] | None = None  # cocina_integral, cuarto_juegos, cuarto_servicio, cuarto_tv, estudio, oficina, sotano, atico

    # Servicios (JSONB list)
    services: list[str] | None = None  # acceso_discapacidad, aire_acondicionado, caseta_seguridad, internet, seguridad_privada, servicios_basicos, calefaccion

    # Amenidades (JSONB list)
    amenities: list[str] | None = None  # alberca, area_eventos, area_juegos, area_lavado, gimnasio, jacuzzi, cancha_squash, cancha_tenis, coworking

    # Exteriores (JSONB list)
    exteriors: list[str] | None = None  # asador, jardin_privado, patio, terraza

    # Extras (JSONB list)
    extras: list[str] | None = None  # amueblado, closet, escuela_cercana, frente_parque, linea_blanca, permite_mascotas, chimenea, duplex

    # Condition & features
    conservation_status: str | None = None  # excelente | bueno | regular | malo | remodelado | para_remodelar
    has_balcony: bool | None = None
    has_elevator: bool | None = None
    has_storage: bool | None = None  # bodega
    built_levels: int | None = None
    minimum_stay: int | None = None  # for rentals
    availability: str | None = None

    # Raw data
    raw_json: dict | None = None


class BaseScraper(abc.ABC):
    """Abstract base class for all portal scrapers.

    Includes proxy session rotation to avoid anti-bot detection.
    Subclasses can use _current_context for page creation and call
    _maybe_rotate() between pages to rotate proxy sessions.
    """

    portal_slug: str = ""
    portal_name: str = ""

    # Rotation config — override in subclass or portal config
    rotate_min_pages: int = DEFAULT_ROTATE_MIN_PAGES
    rotate_max_pages: int = DEFAULT_ROTATE_MAX_PAGES
    rotate_delay_min_s: float = DEFAULT_ROTATE_DELAY_MIN_S
    rotate_delay_max_s: float = DEFAULT_ROTATE_DELAY_MAX_S

    def __init__(self, proxy_manager: ProxyManager | None = None):
        self.proxy_manager = proxy_manager or ProxyManager()
        self.logger = get_logger(f"scraper.{self.portal_slug}")
        self.on_page_scraped: OnPageCallback | None = None
        self.total_items_scraped: int = 0
        self.spot_check_interval: int = 500  # verify every N items
        self.stats: dict[str, int] = {
            "scraped": 0,
            "errors": 0,
        }

        # Browser/context rotation state
        self._current_browser = None
        self._current_context = None
        self._pages_since_rotation: int = 0
        self._rotate_after: int = self._next_rotation_threshold()
        self._consecutive_blocks: int = 0

    @property
    def _proxy_policy(self) -> str:
        """Get proxy policy from portal config. Override or set PROXY_POLICY in config."""
        return getattr(self, '_portal_proxy_policy', 'proxy_required')

    @property
    def _uses_proxy(self) -> bool:
        """Whether this scraper uses proxy (affects budget tracking and rotation)."""
        return self._proxy_policy != "direct"

    def _next_rotation_threshold(self) -> int:
        """Random number of pages before next proxy rotation."""
        return random.randint(self.rotate_min_pages, self.rotate_max_pages)

    async def _create_fresh_browser(self):
        """Create a new browser + context with a fresh proxy session."""
        # Check budget before creating a new browser (only if using proxy)
        tracker = BandwidthTracker.get_instance()
        if self._uses_proxy:
            tracker.check_budget()

        # Direct policy: skip proxy entirely, use VPS IP
        effective_proxy = self.proxy_manager if self._uses_proxy else None

        browser, context = await create_stealth_browser(
            config=BrowserConfig(headless=True),
            proxy_manager=effective_proxy,
            portal_slug=self.portal_slug,
            via_proxy=self._uses_proxy,
        )
        self.logger.info(
            "scraper.fresh_browser",
            proxy_policy=self._proxy_policy,
            has_proxy=effective_proxy.has_proxies if effective_proxy else False,
            bandwidth_mb=round(tracker.total_mb, 1),
            budget_remaining_mb=round(tracker.budget_remaining_mb, 1),
        )
        return browser, context

    async def _close_browser(self, context=None, browser=None):
        """Safely close browser and context."""
        ctx = context or self._current_context
        brw = browser or self._current_browser
        try:
            if ctx:
                await ctx.close()
        except Exception:
            pass
        try:
            if brw:
                await brw.close()
        except Exception:
            pass

    async def _rotate_session(self, reason: str = "scheduled"):
        """Close current browser and create fresh one with new proxy IP."""
        self.logger.info(
            "scraper.session_rotate",
            reason=reason,
            pages_since_last=self._pages_since_rotation,
        )
        await self._close_browser()
        self._current_browser, self._current_context = await self._create_fresh_browser()
        self._pages_since_rotation = 0
        self._rotate_after = self._next_rotation_threshold()

        # Post-rotation delay — new IP needs to look natural
        delay = random.uniform(self.rotate_delay_min_s, self.rotate_delay_max_s)
        self.logger.info("scraper.rotation_cooldown", delay_s=round(delay, 1))
        await asyncio.sleep(delay)

    async def _maybe_rotate(self) -> None:
        """Rotate proxy session if page threshold reached. Also checks budget."""
        # Budget check before continuing (only for proxy traffic)
        tracker = BandwidthTracker.get_instance()
        if self._uses_proxy:
            tracker.check_budget()

        # Log bandwidth stats every 10 pages
        if self._pages_since_rotation > 0 and self.total_items_scraped % 10 == 0:
            stats = tracker.get_stats()
            self.logger.info(
                "scraper.bandwidth_check",
                total_mb=stats["total_mb"],
                budget_remaining_mb=stats["budget_remaining_mb"],
                avg_kb_per_request=stats["avg_kb_per_request"],
                blocked_requests=stats["blocked_requests"],
                proxy_policy=self._proxy_policy,
            )

        # Skip rotation for direct connections — no proxy IP to rotate
        if not self._uses_proxy:
            return

        if self._pages_since_rotation >= self._rotate_after:
            await self._rotate_session(reason="page_limit")

    async def _init_browser_for_state(self):
        """Create fresh browser for a new state. Call at start of each state loop."""
        self._current_browser, self._current_context = await self._create_fresh_browser()
        self._pages_since_rotation = 0
        self._rotate_after = self._next_rotation_threshold()
        self._consecutive_blocks = 0

    def _is_blocked_response(self, response, content: str | None = None) -> bool:
        """Check if a response indicates we're blocked."""
        if not response:
            return False
        if response.status == 403:
            return True
        if content and any(m in content.lower() for m in [
            "captcha", "challenge", "cf-browser-verification", "blocked",
        ]):
            return True
        return False

    @abc.abstractmethod
    async def scrape(self) -> list[ScrapedItem]:
        """Run the full scraping cycle. Returns list of scraped items."""
        ...

    async def run(self, job: ScrapeJob) -> list[ScrapedItem]:
        """Execute scraping with logging and error tracking."""
        self.logger.info("scraper.started", portal=self.portal_slug)
        start = datetime.datetime.now(datetime.UTC)
        tracker = BandwidthTracker.get_instance()

        try:
            items = await self.scrape()
            self.stats["scraped"] = len(items)

            # Log bandwidth summary for this portal
            bw_stats = tracker.get_stats()
            portal_mb = bw_stats["by_portal"].get(self.portal_slug, 0)
            self.logger.info(
                "scraper.completed",
                portal=self.portal_slug,
                total=len(items),
                duration_s=(datetime.datetime.now(datetime.UTC) - start).total_seconds(),
                bandwidth_portal_mb=portal_mb,
                bandwidth_total_mb=bw_stats["total_mb"],
                bandwidth_remaining_mb=bw_stats["budget_remaining_mb"],
                avg_kb_per_request=bw_stats["avg_kb_per_request"],
                blocked_requests=bw_stats["blocked_requests"],
            )
            return items
        except BudgetExhausted as e:
            self.stats["errors"] += 1
            tracker.log_summary()
            self.logger.error(
                "scraper.budget_exhausted",
                portal=self.portal_slug,
                used_mb=e.used_mb,
                budget_mb=e.budget_mb,
            )
            raise
        except Exception:
            self.stats["errors"] += 1
            self.logger.exception("scraper.failed", portal=self.portal_slug)
            raise
