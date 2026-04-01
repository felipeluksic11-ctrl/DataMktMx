"""Scout implementation for Vivanuncios."""

from scrapers.vivanuncios import config
from orchestrator.scout import Scout


class VivanunciosScout(Scout):
    LISTINGS_PER_PAGE = 30
    STATES = config.STATES
    LISTING_CARD_SELECTOR = config.SELECTORS["listing_card"]

    def _portal_slug(self) -> str:
        return "vivanuncios"

    def _build_url(self, state: str, operation: str, page: int) -> str:
        op_slug = config.OPERATIONS.get(operation, operation)
        loc_code = config.STATE_CODES.get(state, "")
        return f"{config.BASE_URL}/s-{op_slug}-inmuebles/{state}/v1{config.CATEGORY_CODE}{loc_code}p{page}"
