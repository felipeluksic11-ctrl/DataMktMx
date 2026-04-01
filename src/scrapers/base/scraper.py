import abc
import datetime
from dataclasses import dataclass, field

from shared.db.models import ScrapeJob
from shared.logging import get_logger
from shared.proxy.manager import ProxyManager

logger = get_logger(__name__)


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
    """Abstract base class for all portal scrapers."""

    portal_slug: str = ""
    portal_name: str = ""

    def __init__(self, proxy_manager: ProxyManager | None = None):
        self.proxy_manager = proxy_manager or ProxyManager()
        self.logger = get_logger(f"scraper.{self.portal_slug}")
        self.stats: dict[str, int] = {
            "scraped": 0,
            "errors": 0,
        }

    @abc.abstractmethod
    async def scrape(self) -> list[ScrapedItem]:
        """Run the full scraping cycle. Returns list of scraped items."""
        ...

    async def run(self, job: ScrapeJob) -> list[ScrapedItem]:
        """Execute scraping with logging and error tracking."""
        self.logger.info("scraper.started", portal=self.portal_slug)
        start = datetime.datetime.now(datetime.UTC)

        try:
            items = await self.scrape()
            self.stats["scraped"] = len(items)
            self.logger.info(
                "scraper.completed",
                portal=self.portal_slug,
                total=len(items),
                duration_s=(datetime.datetime.now(datetime.UTC) - start).total_seconds(),
            )
            return items
        except Exception:
            self.stats["errors"] += 1
            self.logger.exception("scraper.failed", portal=self.portal_slug)
            raise
