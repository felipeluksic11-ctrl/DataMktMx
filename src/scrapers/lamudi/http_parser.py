"""Parse Lamudi search results from raw HTML (no browser needed).

Lamudi serves full SSR HTML with all card data, including a rich JSON
attribute `data-serp-map-hover-listing` per card with lat/lng, price,
bedrooms, bathrooms, area. This parser extracts that data using
selectolax (C-based HTML parser) instead of Playwright.

Reuses pure functions from the browser-based parser.
"""

import re

from selectolax.parser import HTMLParser

from scrapers.lamudi import config
from scrapers.lamudi.parser import (
    _clean_price,
    _clean_whitespace,
    _detect_property_type,
    _extract_int_from_range,
    _extract_float_from_range,
    _parse_card_hover_data,
    _parse_location_text,
)
from shared.logging import get_logger

logger = get_logger("scraper.lamudi.http_parser")


def parse_search_html(html: str) -> list[dict]:
    """Parse listing cards from raw Lamudi search HTML.

    Equivalent to parser.parse_search_results() but works on raw HTML
    string instead of a Playwright Page object.

    Returns list of partial dicts ready for _partial_to_item().
    """
    tree = HTMLParser(html)
    cards = tree.css(".snippet.js-snippet")
    if not cards:
        cards = tree.css(config.SELECTORS["listing_card_fallback"])
    if not cards:
        logger.warning("http_parser.no_cards_found")
        return []

    results = []
    for card in cards:
        # --- External ID ---
        external_id = (
            card.attributes.get("data-idanuncio")
            or card.attributes.get("data-listing-id")
        )

        # --- Detail URL ---
        link_el = card.css_first("a[href*='/detalle/']")
        if not link_el:
            link_el = card.css_first("a[href*='/desarrollo/']")
        if not link_el:
            link_el = card.css_first("a[href]")

        detail_url = None
        if link_el:
            href = link_el.attributes.get("href", "")
            if href:
                detail_url = (
                    href if href.startswith("http")
                    else config.BASE_URL + href
                )

        # External ID fallback from URL
        if not external_id and detail_url:
            m = re.search(
                r"/(detalle|desarrollo)/([^/]+?)(?:\.html)?$",
                detail_url,
            )
            if m:
                external_id = m.group(2)
            else:
                import hashlib
                external_id = hashlib.md5(
                    detail_url.encode(),
                ).hexdigest()[:12]

        if not external_id:
            continue

        # --- Hover JSON (lat/lng, price, beds, baths, area) ---
        hover_json = card.attributes.get("data-serp-map-hover-listing")
        hover_data = (
            _parse_card_hover_data(hover_json) if hover_json else {}
        )

        # --- Price ---
        price_el = card.css_first(".snippet__content__price")
        price_text = price_el.text(strip=True) if price_el else ""
        price, currency = _clean_price(price_text)
        price = price or hover_data.get("price")
        currency = currency or hover_data.get("currency")

        # --- Features ---
        bedrooms = None
        bathrooms = None
        construction_m2 = None
        parking_spaces = None

        bed_el = card.css_first(".property__number.bedrooms")
        if bed_el:
            bedrooms = _extract_int_from_range(bed_el.text(strip=True))

        bath_el = card.css_first(".property__number.bathrooms")
        if bath_el:
            bathrooms = _extract_int_from_range(bath_el.text(strip=True))

        area_el = card.css_first(".property__number.area")
        if area_el:
            construction_m2 = _extract_float_from_range(
                area_el.text(strip=True),
            )

        park_el = card.css_first(".property__number.car_park")
        if park_el:
            parking_spaces = _extract_int_from_range(
                park_el.text(strip=True),
            )

        # Hover data fills gaps
        bedrooms = bedrooms or hover_data.get("bedrooms")
        bathrooms = bathrooms or hover_data.get("bathrooms")
        construction_m2 = (
            construction_m2 or hover_data.get("construction_m2")
        )

        # --- Location ---
        loc_el = card.css_first(".snippet__content__location")
        loc_text = loc_el.text(strip=True) if loc_el else ""
        location = _parse_location_text(loc_text)

        # --- Description ---
        desc_el = card.css_first(".snippet__content__description")
        description = None
        if desc_el:
            # Check content attribute first (has full text)
            description = desc_el.attributes.get("content")
            if not description:
                description = desc_el.text(strip=True)
            if description:
                description = _clean_whitespace(description)

        # --- Title ---
        title_el = card.css_first(
            ".snippet__content__title, h2",
        )
        title = None
        if title_el:
            title = (
                title_el.attributes.get("content")
                or title_el.text(strip=True)
            )
            if title:
                title = _clean_whitespace(title)

        # --- Property type ---
        property_type = None
        if title:
            property_type = _detect_property_type(title)
        if not property_type and detail_url:
            property_type = _detect_property_type(detail_url)

        # --- Images count ---
        images_count = hover_data.get("images_count", 0)

        results.append({
            "external_id": str(external_id),
            "detail_url": detail_url,
            "url_listing": detail_url,
            "title": title,
            "description": description,
            "price": price,
            "currency": currency,
            "property_type": property_type,
            **location,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "half_bathrooms": None,
            "construction_m2": construction_m2,
            "land_m2": None,
            "parking_spaces": parking_spaces,
            "built_levels": None,
            "antiquity": None,
            "construction_years": None,
            "images_count": images_count,
            "latitude": hover_data.get("latitude"),
            "longitude": hover_data.get("longitude"),
        })

    logger.info("http_parser.cards_parsed", count=len(results))
    return results
