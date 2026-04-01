"""Scout implementation for Propiedades.com."""

from scrapers.propiedades import config
from orchestrator.scout import Scout


class PropiedadesScout(Scout):
    LISTINGS_PER_PAGE = config.LISTINGS_PER_PAGE
    SEARCH_URL_TEMPLATE = config.SEARCH_URL_TEMPLATE
    STATES = config.STATES
    LISTING_CARD_SELECTOR = config.SELECTORS["listing_card"]

    def _portal_slug(self) -> str:
        return "propiedades"

    def _build_url(self, state: str, operation: str, page: int) -> str:
        op_slug = config.OPERATIONS.get(operation, operation)
        return config.SEARCH_URL_TEMPLATE.format(
            operation=op_slug,
            state=state,
            page=page,
        )
