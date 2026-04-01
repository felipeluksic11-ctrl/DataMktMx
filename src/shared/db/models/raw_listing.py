import datetime
from uuid import uuid4

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Base


class RawListing(Base):
    """Raw listing as scraped from a portal. Never leaves the VPS."""

    __tablename__ = "raw_listings"
    __table_args__ = (
        Index("ix_raw_portal_extid", "portal_id", "external_id", unique=True),
        Index("ix_raw_location", "state", "city", "municipality", "neighborhood"),
        Index("ix_raw_operation_type", "operation", "property_type"),
        {"schema": "raw"},
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default_factory=lambda: str(uuid4()), init=False
    )
    portal_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("portals.id", ondelete="CASCADE")
    )
    external_id: Mapped[str] = mapped_column(String(255))
    scrape_job_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("scrape_jobs.id", ondelete="SET NULL"), default=None
    )

    # === Identifiers ===
    url_listing: Mapped[str | None] = mapped_column(Text, default=None)
    internal_code: Mapped[str | None] = mapped_column(String(100), default=None)
    title: Mapped[str | None] = mapped_column(Text, default=None)
    description: Mapped[str | None] = mapped_column(Text, default=None)

    # === Classification ===
    operation: Mapped[str | None] = mapped_column(String(20), default=None)  # venta | renta | vacacional
    property_type: Mapped[str | None] = mapped_column(String(50), default=None)

    # === Price ===
    price: Mapped[float | None] = mapped_column(Float, default=None)
    currency: Mapped[str | None] = mapped_column(String(3), default=None)  # MXN | USD
    maintenance_fee: Mapped[float | None] = mapped_column(Float, default=None)

    # === Location ===
    street_and_number: Mapped[str | None] = mapped_column(Text, default=None)
    neighborhood: Mapped[str | None] = mapped_column(String(200), default=None)  # vecindario o barrio
    city: Mapped[str | None] = mapped_column(String(100), default=None)
    municipality: Mapped[str | None] = mapped_column(String(100), default=None)
    state: Mapped[str | None] = mapped_column(String(100), default=None)
    country: Mapped[str | None] = mapped_column(String(50), default=None)
    zip_code: Mapped[str | None] = mapped_column(String(10), default=None)
    geom: Mapped[None] = mapped_column(
        Geometry("POINT", srid=4326), nullable=True, default=None, init=False
    )

    # === Media (URLs only, no files) ===
    video_url: Mapped[str | None] = mapped_column(Text, default=None)
    tour_360_url: Mapped[str | None] = mapped_column(Text, default=None)
    images_count: Mapped[int] = mapped_column(Integer, default=0)

    # === Dimensions ===
    land_m2: Mapped[float | None] = mapped_column(Float, default=None)
    construction_m2: Mapped[float | None] = mapped_column(Float, default=None)

    # === Age / Status ===
    antiquity: Mapped[str | None] = mapped_column(String(50), default=None)  # preventa | en_construccion | a_estrenar | <years>
    construction_years: Mapped[int | None] = mapped_column(Integer, default=None)

    # === Rooms & Spaces ===
    bedrooms: Mapped[int | None] = mapped_column(Integer, default=None)
    bathrooms: Mapped[int | None] = mapped_column(Integer, default=None)
    half_bathrooms: Mapped[int | None] = mapped_column(Integer, default=None)
    parking_spaces: Mapped[int | None] = mapped_column(Integer, default=None)

    # === Features (JSONB arrays of strings) ===
    extra_rooms: Mapped[list | None] = mapped_column(JSONB, default=None)       # cocina_integral, cuarto_juegos, cuarto_servicio, cuarto_tv, estudio, oficina, sotano, atico
    services: Mapped[list | None] = mapped_column(JSONB, default=None)          # acceso_discapacidad, aire_acondicionado, caseta_seguridad, internet, seguridad_privada, servicios_basicos, calefaccion
    amenities: Mapped[list | None] = mapped_column(JSONB, default=None)         # alberca, area_eventos, area_juegos, area_lavado, gimnasio, jacuzzi, cancha_squash, cancha_tenis, coworking
    exteriors: Mapped[list | None] = mapped_column(JSONB, default=None)         # asador, jardin_privado, patio, terraza
    extras: Mapped[list | None] = mapped_column(JSONB, default=None)            # amueblado, closet, escuela_cercana, frente_parque, linea_blanca, permite_mascotas, chimenea, duplex

    # === Condition & Features ===
    conservation_status: Mapped[str | None] = mapped_column(String(30), default=None)  # excelente | bueno | regular | malo | remodelado | para_remodelar
    has_balcony: Mapped[bool | None] = mapped_column(Boolean, default=None)
    has_elevator: Mapped[bool | None] = mapped_column(Boolean, default=None)
    has_storage: Mapped[bool | None] = mapped_column(Boolean, default=None)  # bodega
    built_levels: Mapped[int | None] = mapped_column(Integer, default=None)
    minimum_stay: Mapped[int | None] = mapped_column(Integer, default=None)  # for rentals/vacacional
    availability: Mapped[str | None] = mapped_column(String(100), default=None)

    # === Raw data ===
    raw_json: Mapped[dict | None] = mapped_column(JSONB, default=None)

    # === Timestamps ===
    first_seen_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
    last_seen_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
