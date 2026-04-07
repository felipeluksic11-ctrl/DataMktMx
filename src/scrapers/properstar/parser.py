"""Parse Properstar.com.mx HTML into structured data.

Strategy:
1. Search results — parse article.item-adaptive.card-full cards (SSR)
2. Highlights string — split by bullet (•) for property type, beds, baths, m2
3. JSON-LD (Schema.org) — ItemList on search pages (numberOfItems for total count),
   RealEstateListing on detail pages
4. Detail page HTML — features, description, gallery

Properstar is React SSR behind Azure WAF. Cards are in initial HTML after WAF
challenge completes. No need for JS rendering of card content.
"""

import re
import json

from playwright.async_api import Page

from scrapers.base import ScrapedItem
from scrapers.properstar import config
from shared.logging import get_logger

logger = get_logger("scraper.properstar.parser")


# ──────────────────────────── Text utilities ────────────────────────────


def _clean_price(text: str) -> tuple[float | None, str | None]:
    if not text:
        return None, None
    text = text.strip()
    currency = "USD" if "USD" in text.upper() or "US$" in text or "U$S" in text else "MXN"
    digits = re.sub(r"[^\d.]", "", text.replace(",", ""))
    if not digits:
        return None, None
    try:
        return float(digits), currency
    except ValueError:
        return None, None


def _extract_int(text: str) -> int | None:
    match = re.search(r"(\d+)", text)
    return int(match.group(1)) if match else None


def _extract_float(text: str) -> float | None:
    match = re.search(r"([\d,]+(?:\.\d+)?)", text)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _clean_whitespace(text: str) -> str:
    """Collapse tabs/newlines/spaces into single spaces."""
    return re.sub(r"\s+", " ", text).strip()


def _normalize(text: str, mapping: dict[str, str]) -> str | None:
    text_lower = text.lower().strip()
    for keyword, normalized in mapping.items():
        if keyword in text_lower:
            return normalized
    return None


def _classify_list(texts: list[str], mapping: dict[str, str]) -> list[str] | None:
    result = []
    for text in texts:
        val = _normalize(text, mapping)
        if val and val not in result:
            result.append(val)
    return result or None


# ──────────────────────────── Highlights parsing ────────────────────────────


def _detect_property_type(text: str) -> str | None:
    """Detect property type from highlights text or title."""
    text_lower = text.lower().strip()
    for keyword, ptype in config.PROPERTY_TYPE_MAP.items():
        if keyword == text_lower or text_lower.startswith(keyword):
            return ptype
    return None


def _parse_highlights(text: str) -> dict:
    """Parse the item-highlights string.

    Format: '{type} • {N} dormitorio(s) • {N} baño. • {N} m²'
    Some cards may omit segments or have 'habitaciones' before 'dormitorios'.
    """
    result: dict = {
        "property_type": None,
        "bedrooms": None,
        "bathrooms": None,
        "construction_m2": None,
    }

    if not text:
        return result

    # Split by bullet character
    parts = [p.strip() for p in text.split("\u2022")]
    if not parts:
        return result

    # First part is always the property type
    result["property_type"] = _detect_property_type(parts[0])

    for part in parts[1:]:
        part_lower = part.lower()

        if "dormitorio" in part_lower:
            result["bedrooms"] = _extract_int(part)
        elif "baño" in part_lower or "bano" in part_lower:
            result["bathrooms"] = _extract_int(part)
        elif "m²" in part_lower or "m2" in part_lower:
            result["construction_m2"] = _extract_float(part)
        # "habitaciones" = total rooms — skip, less useful than dormitorios

    return result


# ──────────────────────────── JSON-LD extraction ────────────────────────────


async def _extract_jsonld_itemlist(page: Page) -> dict | None:
    """Extract the ItemList JSON-LD from search results page.

    Returns dict with 'numberOfItems' (total results) and 'items' list
    (first 5 listings with structured data).
    """
    return await page.evaluate("""() => {
        const scripts = document.querySelectorAll('script[type="application/ld+json"]');
        for (const s of scripts) {
            try {
                const data = JSON.parse(s.textContent);
                if (data['@type'] === 'ItemList') {
                    return data;
                }
            } catch(e) {}
        }
        return null;
    }""")


async def _extract_jsonld_listing(page: Page) -> dict | None:
    """Extract RealEstateListing JSON-LD from detail page."""
    return await page.evaluate("""() => {
        const scripts = document.querySelectorAll('script[type="application/ld+json"]');
        for (const s of scripts) {
            try {
                const data = JSON.parse(s.textContent);
                if (data['@type'] === 'RealEstateListing') {
                    return data;
                }
                if (data['@graph']) {
                    for (const item of data['@graph']) {
                        if (item['@type'] === 'RealEstateListing') return item;
                    }
                }
            } catch(e) {}
        }
        return null;
    }""")


def _parse_jsonld_listing(data: dict) -> dict:
    """Extract fields from a RealEstateListing JSON-LD object."""
    result: dict = {}

    # Main entity (House, Apartment, etc.)
    entity = data.get("mainEntity", {})
    if not isinstance(entity, dict):
        entity = {}

    # Type
    type_map = {
        "House": "casa",
        "SingleFamilyResidence": "casa",
        "Apartment": "departamento",
        "Residence": "departamento",
        "LandForm": "terreno",
    }
    result["property_type_jsonld"] = type_map.get(entity.get("@type", ""))

    result["title_jsonld"] = data.get("name", "").strip() or None
    result["date_posted_jsonld"] = data.get("datePosted")
    result["bedrooms_jsonld"] = entity.get("numberOfBedrooms")
    result["bathrooms_jsonld"] = entity.get("numberOfBathroomsTotal") or entity.get("numberOfBathrooms")

    # Floor size
    floor = entity.get("floorSize", {})
    if isinstance(floor, dict) and floor.get("value"):
        try:
            result["floor_m2_jsonld"] = float(floor["value"])
        except (ValueError, TypeError):
            pass

    # Address
    addr = entity.get("address", {})
    if isinstance(addr, dict):
        result["locality_jsonld"] = addr.get("addressLocality")
        result["region_jsonld"] = addr.get("addressRegion")
        result["country_jsonld"] = addr.get("addressCountry")

    # Offers / price
    offers = data.get("offers", {})
    if isinstance(offers, dict):
        try:
            result["price_jsonld"] = float(offers.get("price", 0)) or None
        except (ValueError, TypeError):
            pass
        result["currency_jsonld"] = offers.get("priceCurrency")

    return result


# ──────────────────────────── Location parsing ────────────────────────────


def _parse_location_text(location_text: str, state_name: str = "") -> dict:
    """Parse location from card text and state context.

    Cards show city name only (e.g., 'Puerto Vallarta').
    State comes from the search URL context.
    """
    result: dict = {"neighborhood": None, "municipality": None, "city": None}
    if not location_text:
        return result

    text = location_text.strip()
    # Remove common prefixes
    text = re.sub(r"^(Col\.\s*|Fracc\.\s*|Res\.\s*)", "", text, flags=re.IGNORECASE).strip()

    parts = [p.strip() for p in text.split(",") if p.strip()]

    if len(parts) >= 3:
        result["neighborhood"] = parts[0]
        result["municipality"] = parts[1]
        result["city"] = parts[2]
    elif len(parts) == 2:
        result["municipality"] = parts[0]
        result["city"] = parts[1]
    elif len(parts) == 1:
        result["city"] = parts[0]

    return result


# ──────────────────────────── Feature parsing (detail page) ────────────────


def _parse_features(feature_texts: list[str]) -> dict:
    """Parse feature strings from detail page."""
    result: dict = {
        "bedrooms": None,
        "bathrooms": None,
        "half_bathrooms": None,
        "construction_m2": None,
        "land_m2": None,
        "parking_spaces": None,
        "built_levels": None,
        "antiquity": None,
        "construction_years": None,
    }

    for raw in feature_texts:
        text = _clean_whitespace(raw).lower()
        matched = False

        for pattern, field in config.FEATURE_PATTERNS.items():
            if pattern in text:
                if field in ("bedrooms", "bathrooms", "half_bathrooms", "parking_spaces", "built_levels"):
                    result[field] = _extract_int(text)
                elif field in ("land_m2", "construction_m2"):
                    result[field] = _extract_float(text)
                elif field == "rooms":
                    pass  # skip total rooms
                matched = True
                break

        if not matched:
            if "año" in text:
                years = _extract_int(text)
                if years:
                    result["antiquity"] = str(years)
                    result["construction_years"] = years
            elif "m²" in text or "m2" in text:
                val = _extract_float(text)
                if val:
                    if result["construction_m2"] is None:
                        result["construction_m2"] = val
                    elif result["land_m2"] is None:
                        result["land_m2"] = val

    return result


# ──────────────────────────── Search results page ────────────────────────────


async def parse_search_results(page: Page) -> list[dict]:
    """Parse listing cards from a Properstar search results page.

    Each card is an <article class="item-adaptive card-full"> containing:
    - a.listing-title (href → /vivienda/{id}, text → title)
    - .listing-price-main span (price text like 'MXN 9,058,721')
    - .item-location (city name)
    - .item-highlights (type • beds • baths • m2)
    - .image-gallery-picture img (images)
    """
    cards = await page.query_selector_all(config.SELECTORS["listing_card"])
    if not cards:
        logger.warning("parser.no_cards_found", url=page.url)
        return []

    results = []
    for card in cards:
        # --- Detail URL and external ID ---
        link_el = await card.query_selector("a.listing-title")
        if not link_el:
            continue

        href = await link_el.get_attribute("href")
        if not href:
            continue

        detail_url = href if href.startswith("http") else config.BASE_URL + href

        # Extract numeric ID from /vivienda/{id}
        m = re.search(r"/vivienda/(\d+)", href)
        if m:
            external_id = m.group(1)
        else:
            import hashlib
            external_id = hashlib.md5(href.encode()).hexdigest()[:12]

        # --- Title ---
        title = (await link_el.text_content() or "").strip()
        if title:
            title = _clean_whitespace(title)

        # --- Price ---
        price_el = await card.query_selector(".listing-price-main span")
        price_text = (await price_el.text_content() or "").strip() if price_el else ""
        price, currency = _clean_price(price_text)

        # --- Highlights (property type, beds, baths, m2) ---
        highlights_el = await card.query_selector(".item-highlights")
        highlights_text = (await highlights_el.text_content() or "").strip() if highlights_el else ""
        highlights = _parse_highlights(highlights_text)

        # --- Property type from highlights or title ---
        property_type = highlights.get("property_type")
        if not property_type and title:
            property_type = _detect_property_type(title)

        # --- Location ---
        loc_el = await card.query_selector(".item-location")
        loc_text = (await loc_el.text_content() or "").strip() if loc_el else ""
        location = _parse_location_text(loc_text)

        # --- Images count ---
        images = await card.query_selector_all(".image-gallery-picture img")
        images_count = len(images)

        results.append({
            "external_id": str(external_id),
            "detail_url": detail_url,
            "url_listing": detail_url,
            "title": title or None,
            "description": None,  # not available in cards
            "price": price,
            "currency": currency,
            "property_type": property_type,
            **location,
            "bedrooms": highlights.get("bedrooms"),
            "bathrooms": highlights.get("bathrooms"),
            "half_bathrooms": None,
            "construction_m2": highlights.get("construction_m2"),
            "land_m2": None,
            "parking_spaces": None,  # not in cards
            "built_levels": None,
            "antiquity": None,
            "construction_years": None,
            "images_count": images_count,
            "latitude": None,  # not available on Properstar
            "longitude": None,
        })

    logger.info("parser.cards_parsed", count=len(results), url=page.url)
    return results


async def get_total_results(page: Page) -> int | None:
    """Extract total result count from JSON-LD ItemList numberOfItems."""
    itemlist = await _extract_jsonld_itemlist(page)
    if itemlist and "numberOfItems" in itemlist:
        try:
            return int(itemlist["numberOfItems"])
        except (ValueError, TypeError):
            pass
    return None


# ──────────────────────────── Detail page ────────────────────────────


async def parse_detail_page(page: Page, partial: dict) -> ScrapedItem:
    """Parse detail page using JSON-LD + HTML features."""

    # --- 1. JSON-LD ---
    jsonld_raw = await _extract_jsonld_listing(page)
    jld = _parse_jsonld_listing(jsonld_raw) if jsonld_raw else {}

    # --- 2. Title ---
    title_el = await page.query_selector(config.SELECTORS["detail_title"])
    title = (await title_el.text_content() or "").strip() if title_el else None
    title = title or jld.get("title_jsonld") or partial.get("title")
    if title:
        title = _clean_whitespace(title)

    # --- 3. Description ---
    desc_el = await page.query_selector(config.SELECTORS["detail_description"])
    description = (await desc_el.text_content() or "").strip() if desc_el else None
    if description:
        description = _clean_whitespace(description)

    # --- 4. Price ---
    price_el = await page.query_selector(config.SELECTORS["detail_price"])
    price_text = (await price_el.text_content() or "").strip() if price_el else ""
    if price_text:
        price, currency = _clean_price(price_text)
    else:
        price = jld.get("price_jsonld") or partial.get("price")
        currency = jld.get("currency_jsonld") or partial.get("currency")

    # --- 5. Features ---
    feat_lis = await page.query_selector_all(config.SELECTORS["detail_features"])
    feat_texts = [_clean_whitespace(await li.text_content() or "") for li in feat_lis]
    feat_texts = [t for t in feat_texts if t]
    features = _parse_features(feat_texts) if feat_texts else {}

    # Merge: JSON-LD > detail features > card partial
    bedrooms = jld.get("bedrooms_jsonld") or features.get("bedrooms") or partial.get("bedrooms")
    bathrooms = jld.get("bathrooms_jsonld") or features.get("bathrooms") or partial.get("bathrooms")
    half_bathrooms = features.get("half_bathrooms") or partial.get("half_bathrooms")
    parking_spaces = features.get("parking_spaces") or partial.get("parking_spaces")
    land_m2 = features.get("land_m2") or partial.get("land_m2")
    construction_m2 = features.get("construction_m2") or jld.get("floor_m2_jsonld") or partial.get("construction_m2")
    built_levels = features.get("built_levels") or partial.get("built_levels")
    antiquity = features.get("antiquity") or partial.get("antiquity")
    construction_years = features.get("construction_years") or partial.get("construction_years")

    # --- 6. Property type ---
    property_type = jld.get("property_type_jsonld") or partial.get("property_type")

    # --- 7. Location ---
    locality = jld.get("locality_jsonld", "")
    region = jld.get("region_jsonld", "")
    city = locality or partial.get("city")
    municipality = partial.get("municipality")
    neighborhood = partial.get("neighborhood")

    # --- 8. Amenities & features ---
    amenity_lis = await page.query_selector_all(config.SELECTORS["detail_amenities"])
    amenity_texts = [(await li.text_content() or "").strip() for li in amenity_lis]
    amenity_texts = [t for t in amenity_texts if t]

    all_feature_texts = feat_texts + amenity_texts
    amenities = _classify_list(all_feature_texts, config.AMENITIES_MAP)
    services = _classify_list(all_feature_texts, config.SERVICES_MAP)
    exteriors = _classify_list(all_feature_texts, config.EXTERIORS_MAP)
    extras = _classify_list(all_feature_texts, config.EXTRAS_MAP)
    extra_rooms = _classify_list(all_feature_texts, config.EXTRA_ROOMS_MAP)

    # Booleans
    all_lower = " ".join(t.lower() for t in all_feature_texts)
    has_balcony = True if "balcón" in all_lower or "balcon" in all_lower else None
    has_elevator = True if "elevador" in all_lower or "ascensor" in all_lower else None
    has_storage = True if "bodega" in all_lower else None

    # Conservation
    conservation = None
    for t in all_feature_texts:
        conservation = _normalize(t, config.CONSERVATION_MAP)
        if conservation:
            break

    # Antiquity from features
    for t in all_feature_texts:
        ant = _normalize(t, config.ANTIQUITY_MAP)
        if ant:
            antiquity = ant
            break

    # --- 9. Media ---
    images = await page.query_selector_all(config.SELECTORS["detail_gallery"])
    images_count = len(images) or partial.get("images_count", 0)

    video_el = await page.query_selector(config.SELECTORS["detail_video"])
    video_url = await video_el.get_attribute("src") if video_el else None

    tour_el = await page.query_selector(config.SELECTORS["detail_tour"])
    tour_360_url = await tour_el.get_attribute("src") if tour_el else None

    return ScrapedItem(
        external_id=partial["external_id"],
        url_listing=partial.get("url_listing"),
        title=title,
        description=description,
        operation=partial.get("operation"),
        property_type=property_type,
        listing_type=partial.get("operation"),
        price=price,
        currency=currency,
        neighborhood=neighborhood,
        city=city,
        municipality=municipality,
        state=partial.get("state"),
        country="Mexico",
        latitude=None,   # Properstar doesn't expose coordinates
        longitude=None,
        video_url=video_url,
        tour_360_url=tour_360_url,
        images_count=images_count,
        land_m2=land_m2,
        construction_m2=construction_m2,
        antiquity=antiquity,
        construction_years=construction_years,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        half_bathrooms=half_bathrooms,
        parking_spaces=parking_spaces,
        extra_rooms=extra_rooms,
        services=services,
        amenities=amenities,
        exteriors=exteriors,
        extras=extras,
        conservation_status=conservation,
        has_balcony=has_balcony,
        has_elevator=has_elevator,
        has_storage=has_storage,
        built_levels=built_levels,
        raw_json=jsonld_raw,
    )
