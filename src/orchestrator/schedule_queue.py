"""Priority queue for schedule execution.

Manages which schedules should run next based on priority,
rate limits, and concurrency constraints.
"""

import datetime
from dataclasses import dataclass, field

from shared.logging import get_logger

logger = get_logger("scheduler.queue")


@dataclass
class QueueEntry:
    """A schedule that is ready to run."""

    schedule_id: str
    portal_slug: str
    portal_id: str
    mode: str
    budget_mb: float
    states: list[str] | None
    visit_detail: bool
    priority: int  # higher = run first
    cron_expression: str
    max_retries: int
    retry_backoff_s: int
    trigger: str = "cron"  # cron | manual | retry
    retry_count: int = 0
    schedule_run_id: str | None = None


def sort_by_priority(entries: list[QueueEntry]) -> list[QueueEntry]:
    """Sort queue entries by priority (highest first), then by portal name."""
    return sorted(entries, key=lambda e: (-e.priority, e.portal_slug))


def is_rate_limited(
    last_run_at: datetime.datetime | None,
    rate_limit_s: int,
    now: datetime.datetime | None = None,
) -> bool:
    """Check if a portal is still within its rate limit window."""
    if rate_limit_s <= 0 or last_run_at is None:
        return False
    if now is None:
        now = datetime.datetime.now(datetime.UTC)
    elapsed = (now - last_run_at).total_seconds()
    return elapsed < rate_limit_s


def compute_retry_delay(retry_backoff_s: int, retry_count: int) -> int:
    """Compute exponential backoff delay in seconds."""
    return retry_backoff_s * (2 ** retry_count)
