"""Parse Propiedades.com search results from raw HTML (no browser needed).

Propiedades.com uses itemprop microdata on cards (latitude, longitude,
streetAddress, addressLocality, etc.) which is always present in SSR HTML.

Reuses pure functions from the browser-based parser.
"""

from selectolax.parser import HTMLParser

from scrapers.propiedades import config
from scrapers.propiedades.parser import (
    _clean_price,
    _detect_operation_from_badges,
    _detect_property_type_from_badges,
    _extract_external_id,
    _parse_card_features,
    _safe_float,
)
from shared.logging import get_logger

logger = get_logger("scraper.propiedades.http_parser")


def parse_search_html(html: str) -> list[dict]:
    """Parse listing cards from raw Propiedades.com search HTML.

    Equivalent to parser.parse_search_results() but works on raw HTML
    string instead of a Playwright Page object.
    """
    tree = HTMLParser(html)
    cards = tree.css(config.SELECTORS["listing_card"])
    if not cards:
        logger.warning("http_parser.no_cards_found")
        return []

    results = []
    for card in cards:
        # Detail URL
        link_el = card.css_first(config.SELECTORS["card_link"])
        if not link_el:
            continue
        href = link_el.attributes.get("href", "")
        if not href:
            continue
        detail_url = (
            href if href.startswith("http")
            else config.BASE_URL + href
        )

        # External ID
        external_id = _extract_external_id(detail_url)
        if not external_id:
            continue

        # Coordinates from meta itemprop tags
        latitude = None
        longitude = None
        lat_el = card.css_first(config.SELECTORS["card_latitude"])
        lng_el = card.css_first(config.SELECTORS["card_longitude"])
        if lat_el:
            latitude = _safe_float(lat_el.attributes.get("content"))
        if lng_el:
            longitude = _safe_float(lng_el.attributes.get("content"))

        # Type badges (property type + operation)
        badge_els = card.css(config.SELECTORS["card_type_badges"])
        badge_texts = [
            el.text(strip=True) for el in badge_els
            if el.text(strip=True)
        ]
        property_type = _detect_property_type_from_badges(badge_texts)
        badge_operation = _detect_operation_from_badges(badge_texts)

        # Price
        price_el = card.css_first(config.SELECTORS["card_price_fallback"])
        if not price_el:
            price_el = card.css_first(config.SELECTORS["card_price"])
        price_text = price_el.text(strip=True) if price_el else ""
        price, currency = _clean_price(price_text)

        # Location via itemprop attributes
        street_el = card.css_first(
            config.SELECTORS["card_street_address"],
        )
        locality_el = card.css_first(config.SELECTORS["card_locality"])
        postal_el = card.css_first(config.SELECTORS["card_postal_code"])

        street_raw = ""
        if street_el:
            street_raw = street_el.attributes.get("content", "").strip()
        municipality = None
        if locality_el:
            municipality = (
                locality_el.attributes.get("content", "").strip()
                or None
            )
        region_el = card.css_first(config.SELECTORS["card_region"])
        region = None
        if region_el:
            region = (
                region_el.attributes.get("content", "").strip()
                or None
            )
        zip_code = None
        if postal_el:
            zip_code = (
                postal_el.attributes.get("content", "").strip()
                or None
            )

        # Parse street for neighborhood
        street = None
        neighborhood = None
        if street_raw:
            parts = [p.strip() for p in street_raw.split(",") if p.strip()]
            if len(parts) >= 2:
                street = parts[0]
                neighborhood = (
                    parts[-1]
                    .replace("Col. ", "")
                    .replace("Col.", "")
                    .strip()
                )
            elif len(parts) == 1:
                street = parts[0]

        # Features from card amenities
        feat_els = card.css(config.SELECTORS["card_features"])
        feat_texts = [
            el.text(strip=True) for el in feat_els
            if el.text(strip=True)
        ]
        features = _parse_card_features(feat_texts)

        # Title
        title_text = None
        if link_el:
            title_text = link_el.attributes.get("title", "").strip()
        if not title_text:
            title_text = street_raw or None

        results.append({
            "external_id": external_id,
            "detail_url": detail_url,
            "url_listing": detail_url,
            "title": title_text,
            "price": price,
            "currency": currency,
            "property_type": property_type,
            "badge_operation": badge_operation,
            "street_and_number": street,
            "neighborhood": neighborhood,
            "municipality": municipality,
            "region": region,  # addressRegion from HTML — real state of the listing
            "zip_code": zip_code,
            "latitude": latitude,
            "longitude": longitude,
            "country": "México",
            **features,
        })

    logger.info("http_parser.cards_parsed", count=len(results))
    return results
