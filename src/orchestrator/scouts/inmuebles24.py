"""Scout implementation for Inmuebles24."""

from scrapers.inmuebles24 import config
from orchestrator.scout import Scout


class Inmuebles24Scout(Scout):
    LISTINGS_PER_PAGE = 30
    SEARCH_URL_TEMPLATE = config.SEARCH_URL_TEMPLATE
    STATES = config.STATES
    LISTING_CARD_SELECTOR = config.SELECTORS["listing_card"]

    def _portal_slug(self) -> str:
        return "inmuebles24"

    def _build_url(self, state: str, operation: str, page: int) -> str:
        op_slug = config.OPERATIONS.get(operation, operation)
        return config.SEARCH_URL_TEMPLATE.format(
            property_type="inmuebles",
            operation=op_slug,
            location=state,
            page=page,
        )
