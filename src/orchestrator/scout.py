"""Scout — pre-analyzes a portal before mining.

Visits 1 page per state/operation to determine:
- Total listings per state
- Pages per state
- Anti-bot detection level
- HTML structure health (are selectors still working?)
- Estimated time, cost, and recommended worker count

Output: a ScoutReport that feeds into WorkPlan generation.
"""

import asyncio
import re
import time
from dataclasses import dataclass, field

from shared.logging import get_logger
from shared.stealth.browser import create_stealth_browser, BrowserConfig
from shared.proxy.manager import ProxyManager

logger = get_logger("orchestrator.scout")


@dataclass
class StateReport:
    """Scout results for a single state + operation combination."""
    state: str
    operation: str
    total_listings: int = 0
    total_pages: int = 0
    listings_per_page: int = 0
    url: str = ""
    is_accessible: bool = True
    anti_bot_detected: bool = False
    selectors_healthy: bool = True
    error: str | None = None


@dataclass
class ScoutReport:
    """Complete scout report for a portal."""
    portal_slug: str
    operation: str
    timestamp: float = 0.0
    duration_seconds: float = 0.0

    # Aggregates
    total_listings: int = 0
    total_pages: int = 0
    states_accessible: int = 0
    states_blocked: int = 0
    selectors_healthy: bool = True
    anti_bot_level: str = "none"  # none | low | medium | high

    # Per-state breakdown
    state_reports: list[StateReport] = field(default_factory=list)

    # Recommendations
    recommended_workers: int = 1
    estimated_hours_cards_only: float = 0.0
    estimated_hours_with_detail: float = 0.0
    estimated_cost_usd: float = 0.0
    worker_assignments: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "portal": self.portal_slug,
            "operation": self.operation,
            "total_listings": self.total_listings,
            "total_pages": self.total_pages,
            "states_accessible": self.states_accessible,
            "states_blocked": self.states_blocked,
            "selectors_healthy": self.selectors_healthy,
            "anti_bot_level": self.anti_bot_level,
            "recommended_workers": self.recommended_workers,
            "estimated_hours_cards_only": round(self.estimated_hours_cards_only, 1),
            "estimated_hours_with_detail": round(self.estimated_hours_with_detail, 1),
            "estimated_cost_usd": round(self.estimated_cost_usd, 2),
            "worker_assignments": self.worker_assignments,
            "state_reports": [
                {
                    "state": sr.state,
                    "total_listings": sr.total_listings,
                    "total_pages": sr.total_pages,
                    "is_accessible": sr.is_accessible,
                    "anti_bot_detected": sr.anti_bot_detected,
                    "error": sr.error,
                }
                for sr in self.state_reports
            ],
        }


class Scout:
    """Pre-analyzes a portal to generate a ScoutReport."""

    # Overridable per-portal — subclasses can customize
    LISTINGS_PER_PAGE = 30
    SEARCH_URL_TEMPLATE = ""
    STATES: list[str] = []
    LISTING_CARD_SELECTOR = ""
    ANTI_BOT_INDICATORS = [
        "captcha", "challenge", "cf-browser-verification",
        "blocked", "rate limit", "too many requests",
    ]

    def __init__(self, proxy_manager: ProxyManager | None = None):
        self.proxy_manager = proxy_manager

    async def run(self, operation: str = "venta") -> ScoutReport:
        """Run scout analysis across all states for a given operation."""
        start = time.time()
        report = ScoutReport(
            portal_slug=self._portal_slug(),
            operation=operation,
            timestamp=start,
        )

        browser, context = await create_stealth_browser(
            config=BrowserConfig(headless=True),
            proxy_manager=self.proxy_manager,
        )

        try:
            for state in self.STATES:
                state_report = await self._scout_state(context, state, operation)
                report.state_reports.append(state_report)

                # Small delay between states
                await asyncio.sleep(1.5 + 1.5 * asyncio.get_event_loop().time() % 1)

        finally:
            await context.close()
            await browser.close()

        report.duration_seconds = time.time() - start
        self._compute_aggregates(report)
        self._compute_recommendations(report)

        logger.info(
            "scout.completed",
            portal=report.portal_slug,
            operation=operation,
            total_listings=report.total_listings,
            recommended_workers=report.recommended_workers,
            duration=round(report.duration_seconds, 1),
        )

        return report

    async def _scout_state(self, context, state: str, operation: str) -> StateReport:
        """Scout a single state — visit page 1 to get total count."""
        url = self._build_url(state, operation, page=1)
        sr = StateReport(state=state, operation=operation, url=url)

        page = await context.new_page()
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=20000)

            if not response:
                sr.is_accessible = False
                sr.error = "no_response"
                return sr

            if response.status >= 400:
                sr.is_accessible = False
                sr.error = f"http_{response.status}"
                return sr

            await page.wait_for_timeout(2000)

            # Check for anti-bot
            body_text = (await page.text_content("body") or "").lower()
            for indicator in self.ANTI_BOT_INDICATORS:
                if indicator in body_text:
                    sr.anti_bot_detected = True
                    break

            # Get total count from H1
            h1 = await page.query_selector("h1")
            h1_text = (await h1.text_content() or "").strip() if h1 else ""

            match = re.search(r"([\d,.]+)\s+(?:Propiedad|Inmueble)", h1_text, re.IGNORECASE)
            if match:
                sr.total_listings = int(match.group(1).replace(",", "").replace(".", ""))
                sr.total_pages = (sr.total_listings + self.LISTINGS_PER_PAGE - 1) // self.LISTINGS_PER_PAGE

            # Check if listing cards render (selectors still work)
            if self.LISTING_CARD_SELECTOR:
                cards = await page.query_selector_all(self.LISTING_CARD_SELECTOR)
                sr.listings_per_page = len(cards)
                if sr.total_listings > 0 and len(cards) == 0:
                    sr.selectors_healthy = False

            logger.info(
                "scout.state_done",
                state=state,
                listings=sr.total_listings,
                pages=sr.total_pages,
                accessible=sr.is_accessible,
            )

        except Exception as e:
            sr.is_accessible = False
            sr.error = str(e)[:200]
            logger.exception("scout.state_error", state=state)
        finally:
            await page.close()

        return sr

    def _compute_aggregates(self, report: ScoutReport) -> None:
        report.total_listings = sum(sr.total_listings for sr in report.state_reports)
        report.total_pages = sum(sr.total_pages for sr in report.state_reports)
        report.states_accessible = sum(1 for sr in report.state_reports if sr.is_accessible)
        report.states_blocked = sum(1 for sr in report.state_reports if not sr.is_accessible)
        report.selectors_healthy = all(sr.selectors_healthy for sr in report.state_reports if sr.is_accessible)

        anti_bot_count = sum(1 for sr in report.state_reports if sr.anti_bot_detected)
        if anti_bot_count == 0:
            report.anti_bot_level = "none"
        elif anti_bot_count < len(report.state_reports) * 0.3:
            report.anti_bot_level = "low"
        elif anti_bot_count < len(report.state_reports) * 0.6:
            report.anti_bot_level = "medium"
        else:
            report.anti_bot_level = "high"

    def _compute_recommendations(self, report: ScoutReport) -> None:
        """Compute worker count, time, and cost estimates."""
        total = report.total_listings
        pages = report.total_pages

        # Time per listing
        sec_per_page_card = 8  # load + parse
        sec_per_listing_detail = 5  # load detail + parse + delay

        # Single worker times
        hours_cards = (pages * sec_per_page_card) / 3600
        hours_detail = (total * sec_per_listing_detail) / 3600

        # Recommended workers based on volume
        if total < 5_000:
            workers = 1
        elif total < 20_000:
            workers = 2
        elif total < 50_000:
            workers = 3
        elif total < 100_000:
            workers = 4
        else:
            workers = 5

        # Adjust for anti-bot
        if report.anti_bot_level == "high":
            workers = max(1, workers - 1)  # fewer workers, more cautious

        report.recommended_workers = workers
        report.estimated_hours_cards_only = hours_cards / workers
        report.estimated_hours_with_detail = hours_detail / workers

        # Cost: ~200KB per listing with detail, at $1.5/GB residential
        bytes_per_listing = 200 * 1024
        total_gb = (total * bytes_per_listing) / (1024**3)
        report.estimated_cost_usd = total_gb * 1.5

        # Worker assignments: partition states by listing count
        self._assign_workers(report, workers)

    def _assign_workers(self, report: ScoutReport, num_workers: int) -> None:
        """Partition states across workers, balancing by listing count."""
        # Sort states by listing count descending
        states_with_count = [
            (sr.state, sr.total_listings)
            for sr in report.state_reports
            if sr.is_accessible and sr.total_listings > 0
        ]
        states_with_count.sort(key=lambda x: -x[1])

        # Greedy partition: assign each state to the worker with least load
        buckets: list[list[tuple[str, int]]] = [[] for _ in range(num_workers)]
        bucket_totals = [0] * num_workers

        for state, count in states_with_count:
            # Find bucket with least total
            min_idx = bucket_totals.index(min(bucket_totals))
            buckets[min_idx].append((state, count))
            bucket_totals[min_idx] += count

        report.worker_assignments = [
            {
                "worker_id": f"worker-{i+1}",
                "states": [s for s, _ in bucket],
                "total_listings": sum(c for _, c in bucket),
                "estimated_hours": sum(c for _, c in bucket) * 5 / 3600,
            }
            for i, bucket in enumerate(buckets)
        ]

    def _portal_slug(self) -> str:
        return "unknown"

    def _build_url(self, state: str, operation: str, page: int) -> str:
        raise NotImplementedError
