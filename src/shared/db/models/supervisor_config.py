import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Base


class SupervisorConfig(Base):
    """Per-portal supervisor configuration (thresholds, auto-apply rules)."""

    __tablename__ = "supervisor_configs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default_factory=lambda: str(uuid4()), init=False
    )
    portal_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("portals.id", ondelete="CASCADE"), unique=True
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    run_after_scrape: Mapped[bool] = mapped_column(Boolean, default=True)

    # Confidence thresholds
    auto_apply_threshold: Mapped[float] = mapped_column(Float, default=0.9)
    queue_review_threshold: Mapped[float] = mapped_column(Float, default=0.5)

    # Cost controls
    max_daily_cost_usd: Mapped[float] = mapped_column(Float, default=1.0)

    # Optional scheduled diagnostics
    cron_expression: Mapped[str | None] = mapped_column(String(100), default=None)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), init=False
    )
