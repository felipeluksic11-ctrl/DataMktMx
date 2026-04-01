import datetime
from uuid import uuid4

from geoalchemy2 import Geometry
from sqlalchemy import (
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


class CleanListing(Base):
    """Cleaned, deduplicated listing ready for aggregation and export."""

    __tablename__ = "clean_listings"
    __table_args__ = (
        Index("ix_clean_location", "state_code", "city_norm", "colony_norm"),
        Index("ix_clean_type_price", "property_type", "listing_type", "price_mxn"),
        {"schema": "clean"},
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default_factory=lambda: str(uuid4()), init=False
    )
    raw_listing_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("raw.raw_listings.id", ondelete="CASCADE")
    )
    property_type: Mapped[str] = mapped_column(String(50))
    listing_type: Mapped[str] = mapped_column(String(10))  # sale | rent
    dedup_cluster_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), default=None
    )
    price_mxn: Mapped[float | None] = mapped_column(Float, default=None)
    price_usd: Mapped[float | None] = mapped_column(Float, default=None)

    # Normalized location
    state_code: Mapped[str | None] = mapped_column(String(5), default=None)
    state_name: Mapped[str | None] = mapped_column(String(100), default=None)
    city_norm: Mapped[str | None] = mapped_column(String(100), default=None)
    colony_norm: Mapped[str | None] = mapped_column(String(200), default=None)
    zip_code: Mapped[str | None] = mapped_column(String(10), default=None)
    geom: Mapped[None] = mapped_column(
        Geometry("POINT", srid=4326), nullable=True, default=None, init=False
    )

    # Normalized attributes
    bedrooms: Mapped[int | None] = mapped_column(Integer, default=None)
    bathrooms: Mapped[float | None] = mapped_column(Float, default=None)
    parking_spaces: Mapped[int | None] = mapped_column(Integer, default=None)
    construction_m2: Mapped[float | None] = mapped_column(Float, default=None)
    land_m2: Mapped[float | None] = mapped_column(Float, default=None)
    price_per_m2: Mapped[float | None] = mapped_column(Float, default=None)

    # Quality
    quality_score: Mapped[float | None] = mapped_column(Float, default=None)
    completeness: Mapped[float | None] = mapped_column(Float, default=None)
    source_count: Mapped[int] = mapped_column(Integer, default=1)

    # Anonymized summary (no URLs, no agent info)
    summary: Mapped[str | None] = mapped_column(Text, default=None)

    # Extra normalized fields
    amenities: Mapped[dict | None] = mapped_column(JSONB, default=None)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), init=False
    )
