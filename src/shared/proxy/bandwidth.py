"""Bandwidth tracking and budget enforcement for proxy usage.

Tracks real bytes transferred through the proxy and enforces
a configurable budget limit. When exceeded, raises BudgetExhausted
to stop all scraping before burning through proxy credits.

Usage:
    tracker = BandwidthTracker.get_instance()
    tracker.add_bytes(1024)

    if tracker.is_over_budget():
        raise BudgetExhausted(...)
"""

import time
from dataclasses import dataclass, field
from threading import Lock

from shared.logging import get_logger

logger = get_logger("proxy.bandwidth")


class BudgetExhausted(Exception):
    """Raised when proxy bandwidth budget is exceeded."""

    def __init__(self, used_mb: float, budget_mb: float):
        self.used_mb = used_mb
        self.budget_mb = budget_mb
        super().__init__(
            f"Proxy bandwidth budget exhausted: {used_mb:.1f} MB used "
            f"of {budget_mb:.1f} MB budget"
        )


@dataclass
class BandwidthTracker:
    """Singleton tracker for proxy bandwidth usage across all scrapers.

    Tracks bytes per scrape session with budget enforcement.
    """

    # Budget in MB for this scrape session (default 500 MB = 0.5 GB)
    budget_mb: float = 500.0

    # Warning threshold (percentage of budget)
    warning_threshold: float = 0.8  # warn at 80%

    # Internal state
    _total_bytes: int = 0
    _bytes_by_portal: dict[str, int] = field(default_factory=dict)
    _request_count: int = 0
    _blocked_count: int = 0  # requests blocked by resource filter
    _start_time: float = field(default_factory=time.time)
    _warned: bool = False
    _lock: Lock = field(default_factory=Lock)

    # Singleton
    _instance: "BandwidthTracker | None" = None

    @classmethod
    def get_instance(cls, budget_mb: float | None = None) -> "BandwidthTracker":
        if cls._instance is None:
            cls._instance = cls(budget_mb=budget_mb or 500.0)
        elif budget_mb is not None:
            cls._instance.budget_mb = budget_mb
        return cls._instance

    @classmethod
    def reset(cls):
        cls._instance = None

    @property
    def total_mb(self) -> float:
        return self._total_bytes / (1024 * 1024)

    @property
    def budget_remaining_mb(self) -> float:
        return self.budget_mb - self.total_mb

    @property
    def budget_used_pct(self) -> float:
        if self.budget_mb <= 0:
            return 100.0
        return (self.total_mb / self.budget_mb) * 100

    @property
    def avg_bytes_per_request(self) -> float:
        if self._request_count == 0:
            return 0
        return self._total_bytes / self._request_count

    def add_bytes(self, byte_count: int, portal: str = "unknown") -> None:
        """Track bytes transferred. Call from response handler."""
        with self._lock:
            self._total_bytes += byte_count
            self._request_count += 1
            self._bytes_by_portal[portal] = (
                self._bytes_by_portal.get(portal, 0) + byte_count
            )

        # Check thresholds
        if not self._warned and self.budget_used_pct >= self.warning_threshold * 100:
            self._warned = True
            logger.warning(
                "bandwidth.warning",
                used_mb=round(self.total_mb, 1),
                budget_mb=self.budget_mb,
                pct=round(self.budget_used_pct, 1),
                requests=self._request_count,
            )

    def add_blocked(self) -> None:
        """Track a request that was blocked by resource filter."""
        with self._lock:
            self._blocked_count += 1

    def is_over_budget(self) -> bool:
        return self.total_mb >= self.budget_mb

    def check_budget(self) -> None:
        """Raise BudgetExhausted if over budget."""
        if self.is_over_budget():
            raise BudgetExhausted(
                used_mb=round(self.total_mb, 1),
                budget_mb=self.budget_mb,
            )

    def get_stats(self) -> dict:
        """Return usage stats for logging/dashboard."""
        elapsed = time.time() - self._start_time
        return {
            "total_mb": round(self.total_mb, 2),
            "budget_mb": self.budget_mb,
            "budget_remaining_mb": round(self.budget_remaining_mb, 2),
            "budget_used_pct": round(self.budget_used_pct, 1),
            "requests": self._request_count,
            "blocked_requests": self._blocked_count,
            "avg_kb_per_request": round(self.avg_bytes_per_request / 1024, 1),
            "elapsed_minutes": round(elapsed / 60, 1),
            "mb_per_minute": round(self.total_mb / (elapsed / 60), 2) if elapsed > 60 else 0,
            "by_portal": {
                portal: round(bytes_ / (1024 * 1024), 2)
                for portal, bytes_ in self._bytes_by_portal.items()
            },
        }

    def log_summary(self) -> None:
        """Log a summary of bandwidth usage."""
        stats = self.get_stats()
        logger.info("bandwidth.summary", **stats)
