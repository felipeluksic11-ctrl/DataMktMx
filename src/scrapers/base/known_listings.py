"""Known listings cache — fast lookup to detect already-scraped listings.

In incremental mode, we check each listing's external_id against this cache.
When we hit N consecutive known listings, we stop scraping that state/operation.
"""

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.logging import get_logger

logger = get_logger("scrapers.known")


class KnownListingsCache:
    """In-memory set of external_ids for a portal. Loaded once from DB."""

    def __init__(self):
        self._known: set[str] = set()
        self._portal_id: str | None = None

    async def load(self, session: AsyncSession, portal_id: str) -> None:
        """Load all known external_ids for a portal from the DB."""
        self._portal_id = portal_id
        result = await session.execute(
            text("SELECT external_id FROM raw.raw_listings WHERE portal_id = :pid"),
            {"pid": portal_id},
        )
        self._known = {str(row[0]) for row in result}
        logger.info("known.loaded", portal_id=portal_id, count=len(self._known))

    def is_known(self, external_id: str) -> bool:
        """Check if a listing has already been scraped."""
        return str(external_id) in self._known

    def count_known_in_batch(self, external_ids: list[str]) -> int:
        """Count how many IDs in a batch are already known."""
        return sum(1 for eid in external_ids if self.is_known(eid))

    def should_stop(self, external_ids: list[str], threshold: int = 10) -> bool:
        """Check if we should stop scraping — too many known listings in this batch.

        If ≥ threshold listings in this page are already known, we've reached
        the point where all remaining pages are also known.
        """
        known_count = self.count_known_in_batch(external_ids)
        total = len(external_ids)

        if total == 0:
            return True  # empty page = stop

        # Stop if 80%+ of the page is known, or known ≥ threshold
        ratio = known_count / total
        stop = known_count >= threshold or (ratio >= 0.8 and known_count >= 5)

        if stop:
            logger.info(
                "known.stop_signal",
                known=known_count,
                total=total,
                ratio=round(ratio, 2),
            )

        return stop

    @property
    def total_known(self) -> int:
        return len(self._known)
