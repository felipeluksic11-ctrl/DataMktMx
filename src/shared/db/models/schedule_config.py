import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Base


class ScheduleConfig(Base):
    """DB-based schedule configuration — replaces cron file entries."""

    __tablename__ = "schedule_configs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default_factory=lambda: str(uuid4()), init=False
    )

    # Required fields (no default) — must come first for dataclass ordering
    name: Mapped[str] = mapped_column(String(100))
    portal_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("portals.id", ondelete="CASCADE")
    )
    mode: Mapped[str] = mapped_column(String(20))  # incremental | full | enrich
    cron_expression: Mapped[str] = mapped_column(String(100))
    budget_mb: Mapped[float] = mapped_column(Float)

    # Optional fields (with defaults)
    group_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("schedule_groups.id", ondelete="SET NULL"), default=None
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    states: Mapped[list | None] = mapped_column(JSONB, default=None)  # null = use PHASE1_STATES
    visit_detail: Mapped[bool] = mapped_column(Boolean, default=False)

    # Scheduling behavior
    priority: Mapped[int] = mapped_column(Integer, default=50)  # 1-100, higher = run first
    rate_limit_s: Mapped[int] = mapped_column(Integer, default=0)  # min seconds between runs
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    retry_backoff_s: Mapped[int] = mapped_column(Integer, default=300)

    # State tracking
    last_run_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    last_run_status: Mapped[str | None] = mapped_column(String(20), default=None)
    next_run_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    run_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), init=False
    )
