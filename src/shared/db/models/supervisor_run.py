import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Base


class SupervisorRun(Base):
    """History of every supervisor diagnostic invocation."""

    __tablename__ = "supervisor_runs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default_factory=lambda: str(uuid4()), init=False
    )
    portal_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("portals.id", ondelete="CASCADE")
    )
    scrape_job_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("scrape_jobs.id", ondelete="SET NULL"), default=None
    )
    trigger: Mapped[str] = mapped_column(String(20))  # auto_post_scrape | manual | scheduled
    status: Mapped[str] = mapped_column(
        String(20), default="running"
    )  # running | completed | failed

    # Quality snapshots
    quality_before: Mapped[dict | None] = mapped_column(JSONB, default=None)
    quality_after: Mapped[dict | None] = mapped_column(JSONB, default=None)
    diagnosis: Mapped[dict | None] = mapped_column(JSONB, default=None)

    # Repair counts
    repairs_suggested: Mapped[int] = mapped_column(Integer, default=0)
    repairs_applied: Mapped[int] = mapped_column(Integer, default=0)
    repairs_queued: Mapped[int] = mapped_column(Integer, default=0)

    # AI usage
    ai_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    ai_model: Mapped[str | None] = mapped_column(String(50), default=None)
    ai_tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    ai_tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    duration_s: Mapped[float | None] = mapped_column(Float, default=None)

    error_detail: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
