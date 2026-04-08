import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Base


class ScheduleRun(Base):
    """Each execution attempt of a schedule, linking to the ScrapeJob it created."""

    __tablename__ = "schedule_runs"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, default_factory=lambda: str(uuid4()), init=False
    )
    schedule_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("schedule_configs.id", ondelete="CASCADE")
    )
    scrape_job_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("scrape_jobs.id", ondelete="SET NULL"), default=None
    )
    trigger: Mapped[str] = mapped_column(String(20))  # cron | manual | retry
    status: Mapped[str] = mapped_column(
        String(20), default="queued"
    )  # queued | running | completed | failed | skipped
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_detail: Mapped[str | None] = mapped_column(Text, default=None)

    queued_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), init=False
    )
    started_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    finished_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
