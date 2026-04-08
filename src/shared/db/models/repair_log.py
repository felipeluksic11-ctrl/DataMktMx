import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Base


class RepairLog(Base):
    """Individual selector repair action, linked to a supervisor_run."""

    __tablename__ = "repair_logs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default_factory=lambda: str(uuid4()), init=False
    )
    supervisor_run_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("supervisor_runs.id", ondelete="CASCADE")
    )
    portal_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("portals.id", ondelete="CASCADE")
    )
    field: Mapped[str] = mapped_column(String(50))  # price, bedrooms, etc.
    old_selector: Mapped[str | None] = mapped_column(Text, default=None)
    new_selector: Mapped[str | None] = mapped_column(Text, default=None)
    confidence: Mapped[float | None] = mapped_column(Float, default=None)  # 0.0 to 1.0
    data_present: Mapped[bool | None] = mapped_column(Boolean, default=None)
    extraction_method: Mapped[str | None] = mapped_column(String(50), default=None)  # css | text_pattern | json_ld
    reason: Mapped[str | None] = mapped_column(Text, default=None)  # AI explanation

    status: Mapped[str] = mapped_column(
        String(20), default="suggested"
    )  # suggested | auto_applied | manually_applied | rejected | queued

    applied_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    applied_by: Mapped[str | None] = mapped_column(String(50), default=None)  # auto | admin

    # Quality tracking
    quality_before: Mapped[float | None] = mapped_column(Float, default=None)
    quality_after: Mapped[float | None] = mapped_column(Float, default=None)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
