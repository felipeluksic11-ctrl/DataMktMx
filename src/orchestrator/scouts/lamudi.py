"""Scout implementation for Lamudi.com.mx."""

from scrapers.lamudi import config
from orchestrator.scout import Scout


class LamudiScout(Scout):
    LISTINGS_PER_PAGE = config.LISTINGS_PER_PAGE
    STATES = config.STATES
    LISTING_CARD_SELECTOR = config.SELECTORS["listing_card"]

    def _portal_slug(self) -> str:
        return "lamudi"

    def _build_url(self, state: str, operation: str, page: int) -> str:
        op_slug = config.OPERATIONS.get(operation, operation)
        url = config.SEARCH_URL_TEMPLATE.format(
            location=state,
            operation=op_slug,
        )
        if page > 1:
            url += f"?page={page}"
        return url
