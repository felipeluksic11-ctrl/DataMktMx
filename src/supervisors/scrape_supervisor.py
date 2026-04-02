"""Scrape Supervisor — monitors quality and triggers visual repair.

Workflow:
1. After each portal scrape, check fill rates via quality_check
2. If any field drops below threshold, take a screenshot of the portal
3. Send screenshot + HTML + selectors to VisualAnalyzer
4. Log the suggested repairs (auto-apply is opt-in)
5. Store analysis results for review in the dashboard

Usage:
    # Automatic (integrated with runner)
    supervisor = ScrapeSupervisor()
    repairs = await supervisor.check_and_repair("inmuebles24", session)

    # Manual CLI
    python -m supervisors.scrape_supervisor inmuebles24
    python -m supervisors.scrape_supervisor --all
"""

import asyncio
import json
import datetime

from playwright.async_api import Page

from scrapers.quality_check import check_quality, THRESHOLDS
from supervisors.visual_analyzer import VisualAnalyzer
from shared.config import settings
from shared.logging import get_logger, setup_logging
from shared.proxy.manager import ProxyManager
from shared.stealth.browser import BrowserConfig, create_stealth_browser

logger = get_logger("supervisor")

# Portal configs for screenshot URLs
PORTAL_URLS = {
    "inmuebles24": "https://www.inmuebles24.com/inmuebles-en-venta-en-ciudad-de-mexico.html",
    "propiedades": "https://propiedades.com/inmuebles-en-venta-en-ciudad-de-mexico?pagina=1",
    "lamudi": "https://www.lamudi.com.mx/distrito-federal/for-sale/",
    "vivanuncios": "https://www.vivanuncios.com.mx/s-venta-inmuebles/ciudad-de-mexico/v1c1293l9070p1",
}


def _get_selectors(portal_slug: str) -> dict:
    """Load current selectors for a portal."""
    if portal_slug == "inmuebles24":
        from scrapers.inmuebles24 import config
        return config.SELECTORS
    elif portal_slug == "propiedades":
        from scrapers.propiedades import config
        return config.SELECTORS
    elif portal_slug == "lamudi":
        from scrapers.lamudi import config
        return config.SELECTORS
    elif portal_slug == "vivanuncios":
        from scrapers.vivanuncios import config
        return config.SELECTORS
    return {}


class ScrapeSupervisor:
    """Monitors scrape quality and triggers visual repair when needed."""

    def __init__(self):
        self.analyzer = VisualAnalyzer()
        self.proxy_manager = ProxyManager.from_settings()

    async def check_and_repair(
        self,
        portal_slug: str,
        portal_id: str,
        fill_rates: dict | None = None,
    ) -> dict | None:
        """Check quality and run visual repair if needed.

        Args:
            portal_slug: Portal identifier
            portal_id: Portal UUID
            fill_rates: Pre-computed fill rates (optional, will query if not provided)

        Returns:
            Repair suggestions dict, or None if quality is fine
        """
        # Identify broken fields
        problems = []
        if fill_rates:
            for field, threshold in THRESHOLDS.items():
                rate = fill_rates.get(field, 100)
                if rate < threshold:
                    problems.append({
                        "field": field,
                        "fill_rate": rate,
                        "threshold": threshold,
                    })

        if not problems:
            logger.info("supervisor.quality_ok", portal=portal_slug)
            return None

        logger.warning(
            "supervisor.quality_degraded",
            portal=portal_slug,
            broken_fields=[p["field"] for p in problems],
        )

        # Take screenshot and capture HTML
        screenshot, html_snippet = await self._capture_portal(portal_slug)
        if not screenshot:
            logger.error("supervisor.capture_failed", portal=portal_slug)
            return None

        # Get current selectors
        selectors = _get_selectors(portal_slug)

        # Run visual diagnosis
        result = await self.analyzer.diagnose_and_repair(
            screenshot_bytes=screenshot,
            html_snippet=html_snippet,
            selectors=selectors,
            problems=problems,
            portal_name=portal_slug,
        )

        # Log each repair suggestion
        for repair in result.get("repairs", []):
            logger.info(
                "supervisor.repair_suggested",
                portal=portal_slug,
                field=repair.get("field"),
                data_present=repair.get("data_present"),
                new_selector=repair.get("new_selector"),
                confidence=repair.get("confidence"),
                reason=repair.get("reason"),
            )

        if result.get("portal_changes_detected"):
            logger.warning(
                "supervisor.portal_changed",
                portal=portal_slug,
                changes=result["portal_changes_detected"],
            )

        return result

    async def full_analysis(self, portal_slug: str) -> dict:
        """Run a complete visual analysis of a portal (not just repairs).

        Returns full field map, repairs, and new field suggestions.
        """
        screenshot, html_snippet = await self._capture_portal(portal_slug)
        if not screenshot:
            return {"error": "Failed to capture portal page"}

        selectors = _get_selectors(portal_slug)

        result = await self.analyzer.analyze_page(
            screenshot_bytes=screenshot,
            html_snippet=html_snippet,
            selectors=selectors,
            portal_name=portal_slug,
        )

        # Log field map
        for field, info in result.get("field_map", {}).items():
            if info.get("visible"):
                logger.info(
                    "supervisor.field_detected",
                    portal=portal_slug,
                    field=field,
                    location=info.get("location"),
                    selector=info.get("selector"),
                    confidence=info.get("confidence"),
                )

        return result

    async def _capture_portal(self, portal_slug: str) -> tuple[bytes | None, str]:
        """Navigate to portal and capture screenshot + HTML."""
        url = PORTAL_URLS.get(portal_slug)
        if not url:
            logger.error("supervisor.unknown_portal", portal=portal_slug)
            return None, ""

        browser, context = await create_stealth_browser(
            config=BrowserConfig(headless=True),
            proxy_manager=self.proxy_manager,
        )

        try:
            page = await context.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Wait for cards to render
            card_selectors = {
                "inmuebles24": "[data-posting-type]",
                "propiedades": ".pcom-property-card",
                "lamudi": ".snippet.js-snippet",
                "vivanuncios": "[data-posting-type]",
            }
            card_sel = card_selectors.get(portal_slug, "article")
            try:
                await page.wait_for_selector(card_sel, timeout=15000)
            except Exception:
                logger.warning("supervisor.cards_not_found", portal=portal_slug)

            # Take screenshot
            screenshot = await page.screenshot(full_page=False)

            # Get HTML of first 2 cards
            cards = await page.query_selector_all(card_sel)
            html_parts = []
            for card in cards[:2]:
                html = await card.inner_html()
                html_parts.append(f"<div class='card'>{html}</div>")
            html_snippet = "\n".join(html_parts)

            logger.info(
                "supervisor.captured",
                portal=portal_slug,
                screenshot_kb=len(screenshot) // 1024,
                html_chars=len(html_snippet),
                cards_found=len(cards),
            )

            return screenshot, html_snippet

        except Exception:
            logger.exception("supervisor.capture_error", portal=portal_slug)
            return None, ""
        finally:
            await context.close()
            await browser.close()


async def run_supervisor(portal_slug: str | None = None):
    """CLI entry point — run supervisor for one or all portals."""
    setup_logging()
    supervisor = ScrapeSupervisor()

    if portal_slug:
        logger.info("supervisor.manual_analysis", portal=portal_slug)
        result = await supervisor.full_analysis(portal_slug)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        for slug in PORTAL_URLS:
            logger.info("supervisor.analyzing_portal", portal=slug)
            result = await supervisor.full_analysis(slug)
            print(f"\n{'='*60}")
            print(f"Portal: {slug}")
            print(f"{'='*60}")
            print(json.dumps(result, indent=2, ensure_ascii=False))


def main():
    import sys
    setup_logging()
    slug = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else None
    if sys.argv[-1] == "--all":
        slug = None
    asyncio.run(run_supervisor(slug))


if __name__ == "__main__":
    main()
