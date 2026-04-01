import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Base


class ExportBatch(Base):
    """Tracks each export to S3."""

    __tablename__ = "export_batches"
    __table_args__ = {"schema": "export"}

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default_factory=lambda: str(uuid4()), init=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending | running | completed | failed
    total_listings: Mapped[int] = mapped_column(Integer, default=0)
    s3_key: Mapped[str | None] = mapped_column(Text, default=None)
    error_detail: Mapped[str | None] = mapped_column(Text, default=None)
    stats: Mapped[dict | None] = mapped_column(JSONB, default=None)
    started_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    finished_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
