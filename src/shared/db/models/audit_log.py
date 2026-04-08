import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Base


class AuditLog(Base):
    """Unified append-only changelog for all operational changes."""

    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default_factory=lambda: str(uuid4()), init=False
    )
    entity_type: Mapped[str] = mapped_column(
        String(50)
    )  # schedule | portal | supervisor | repair | config | scrape_job
    entity_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), default=None)
    action: Mapped[str] = mapped_column(
        String(50)
    )  # created | updated | deleted | enabled | disabled | triggered | applied | rejected
    actor: Mapped[str] = mapped_column(String(50), default="system")  # system | admin | scheduler | supervisor
    is_automatic: Mapped[bool] = mapped_column(Boolean, default=False)
    is_success: Mapped[bool] = mapped_column(Boolean, default=True)
    summary: Mapped[str] = mapped_column(Text)
    diff: Mapped[dict | None] = mapped_column(JSONB, default=None)  # {field: {old, new}}
    tags: Mapped[list | None] = mapped_column(ARRAY(String), default=None)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, default=None)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
