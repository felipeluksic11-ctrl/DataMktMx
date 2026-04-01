"""Parse Inmuebles24 HTML into structured data.

Strategy:
1. JSON-LD (Schema.org) — primary source for structured data on detail pages
2. Main features section (li items) — bedrooms, bathrooms, m², years, etc.
3. General features section — amenities, services, exteriors
4. Card-level data — fallback for search results without detail visit

Selectors verified against live site: 2026-03-30.
"""

import re
import json

from playwright.async_api import Page

from scrapers.base import ScrapedItem
from scrapers.inmuebles24 import config
from shared.logging import get_logger

logger = get_logger("scraper.inmuebles24.parser")


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


def _clean_whitespace(text: str) -> str:
    """Collapse tabs/newlines/spaces into single spaces."""
    return re.sub(r"\s+", " ", text).strip()


# ──────────────────────────── Feature parsing ────────────────────────────


def _parse_features(feature_texts: list[str]) -> dict:
    """Parse feature strings like '3 rec.', '2 baños', '120 m² lote', '41 años'."""
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
                if field == "units":
                    matched = True
                    break
                if field in ("bedrooms", "bathrooms", "half_bathrooms", "parking_spaces", "built_levels"):
                    result[field] = _extract_int(text)
                elif field in ("land_m2", "construction_m2"):
                    result[field] = _extract_float(text)
                matched = True
                break

        if not matched:
            # "41 años" → antiquity
            if "año" in text:
                years = _extract_int(text)
                if years:
                    result["antiquity"] = str(years)
                    result["construction_years"] = years
            # bare "m²" without qualifier
            elif "m²" in text:
                val = _extract_float(text)
                if val:
                    if result["land_m2"] is None:
                        result["land_m2"] = val
                    elif result["construction_m2"] is None:
                        result["construction_m2"] = val

    return result


# ──────────────────────────── JSON-LD extraction ────────────────────────────


async def _extract_jsonld(page: Page) -> dict | None:
    """Extract the real estate JSON-LD object from the page."""
    return await page.evaluate("""() => {
        const scripts = document.querySelectorAll('script[type="application/ld+json"]');
        for (const s of scripts) {
            try {
                const data = JSON.parse(s.textContent);
                if (['House', 'Apartment', 'RealEstateListing', 'SingleFamilyResidence',
                     'LandForm', 'Product', 'Place'].includes(data['@type'])) {
                    return data;
                }
            } catch(e) {}
        }
        return null;
    }""")


def _parse_jsonld(data: dict) -> dict:
    """Extract fields from Schema.org JSON-LD."""
    result: dict = {}

    # Type
    type_map = {
        "House": "casa", "SingleFamilyResidence": "casa",
        "Apartment": "departamento",
        "LandForm": "terreno",
    }
    result["property_type_jsonld"] = type_map.get(data.get("@type", ""))

    result["title_jsonld"] = data.get("name", "").split(" - ")[0].strip() or None
    result["description_jsonld"] = data.get("description")
    result["bedrooms_jsonld"] = data.get("numberOfBedrooms")
    result["bathrooms_jsonld"] = data.get("numberOfBathroomsTotal")
    result["rooms_jsonld"] = data.get("numberOfRooms")

    # Floor size
    floor = data.get("floorSize", {})
    if isinstance(floor, dict) and floor.get("unitCode") == "MTK":
        result["floor_m2_jsonld"] = floor.get("value")

    # Address
    addr = data.get("address", {})
    if isinstance(addr, dict):
        result["street_jsonld"] = addr.get("streetAddress")
        result["region_jsonld"] = addr.get("addressRegion")  # colonia
        result["locality_jsonld"] = addr.get("addressLocality")  # delegación, ciudad

    # Coordinates
    geo = data.get("geo", {})
    if isinstance(geo, dict):
        result["latitude_jsonld"] = geo.get("latitude")
        result["longitude_jsonld"] = geo.get("longitude")

    return result


# ──────────────────────────── Location parsing ────────────────────────────


def _parse_location_text(address: str, area: str) -> dict:
    result: dict = {"street_and_number": None, "neighborhood": None, "municipality": None}
    if address:
        result["street_and_number"] = address.strip()
    if area:
        parts = [p.strip() for p in area.split(",") if p.strip()]
        if len(parts) >= 2:
            result["neighborhood"] = parts[0]
            result["municipality"] = parts[1]
        elif len(parts) == 1:
            result["neighborhood"] = parts[0]
    return result


def _parse_locality(locality: str) -> dict:
    """Parse JSON-LD addressLocality like 'Cuajimalpa de Morelos, Ciudad de México, Mexico, '"""
    parts = [p.strip() for p in locality.split(",") if p.strip()]
    result: dict = {"municipality": None, "city": None, "country": None}
    if len(parts) >= 3:
        result["municipality"] = parts[0]
        result["city"] = parts[1]
        result["country"] = parts[2]
    elif len(parts) == 2:
        result["municipality"] = parts[0]
        result["city"] = parts[1]
    elif len(parts) == 1:
        result["municipality"] = parts[0]
    return result


def _detect_property_type_from_url(url: str) -> str | None:
    url_lower = url.lower()
    for keyword, ptype in config.PROPERTY_TYPE_FROM_URL.items():
        if keyword in url_lower:
            return ptype
    return None


# ──────────────────────────── Search results page ────────────────────────────


async def parse_search_results(page: Page) -> list[dict]:
    """Parse listing cards from a search results page."""
    cards = await page.query_selector_all(config.SELECTORS["listing_card"])
    if not cards:
        logger.warning("parser.no_cards_found", url=page.url)
        return []

    results = []
    for card in cards:
        external_id = await card.get_attribute(config.SELECTORS["card_id_attr"])
        detail_path = await card.get_attribute(config.SELECTORS["card_url_attr"])
        if not external_id or not detail_path:
            continue

        detail_url = detail_path if detail_path.startswith("http") else config.BASE_URL + detail_path

        # Price
        price_el = await card.query_selector(config.SELECTORS["price_container"])
        price_text = (await price_el.text_content() or "").strip() if price_el else ""
        price_from_el = await card.query_selector(config.SELECTORS["price_from"])
        if price_from_el:
            prefix = (await price_from_el.text_content() or "").strip()
            price_text = price_text.replace(prefix, "").strip()
        price, currency = _clean_price(price_text)

        # Features
        feat_els = await card.query_selector_all(config.SELECTORS["features_span"])
        feat_texts = [(await f.text_content() or "").strip() for f in feat_els]
        features = _parse_features([t for t in feat_texts if t])

        # Location
        addr_el = await card.query_selector(config.SELECTORS["location_address"])
        area_el = await card.query_selector(config.SELECTORS["location_text"])
        addr = (await addr_el.text_content() or "").strip() if addr_el else ""
        area = (await area_el.text_content() or "").strip() if area_el else ""
        location = _parse_location_text(addr, area)

        # Property type from URL
        property_type = _detect_property_type_from_url(detail_url)

        # Title from image alt
        first_img = await card.query_selector("img[alt]")
        title = None
        if first_img:
            alt = (await first_img.get_attribute("alt") or "").strip()
            if "·" in alt:
                title = alt.split("·", 1)[1].strip()
            elif alt and not alt.endswith((".jpg", ".png", ".jpeg")):
                title = alt

        # Images
        images = await card.query_selector_all(config.SELECTORS["gallery_images"])

        # Pills
        pill_els = await card.query_selector_all(config.SELECTORS["pills"])
        pills = []
        for p in pill_els:
            t = (await p.text_content() or "").strip()
            if t and t not in pills:
                pills.append(t)

        results.append({
            "external_id": str(external_id),
            "detail_url": detail_url,
            "url_listing": detail_url,
            "title": title,
            "price": price,
            "currency": currency,
            "property_type": property_type,
            **location,
            **features,
            "images_count": len(images),
            "pills": pills,
            "amenities": _classify_list(pills, config.AMENITIES_MAP),
            "services": _classify_list(pills, config.SERVICES_MAP),
            "extras": _classify_list(pills, config.EXTRAS_MAP),
            "exteriors": _classify_list(pills, config.EXTERIORS_MAP),
        })

    logger.info("parser.cards_parsed", count=len(results), url=page.url)
    return results


# ──────────────────────────── Detail page ────────────────────────────


async def parse_detail_page(page: Page, partial: dict) -> ScrapedItem:
    """Parse detail page using JSON-LD + HTML features + general features."""

    # ─── 1. JSON-LD (best structured source) ───
    jsonld_raw = await _extract_jsonld(page)
    jld = _parse_jsonld(jsonld_raw) if jsonld_raw else {}

    # ─── 2. Title ───
    title_el = await page.query_selector("[class*='section-title']")
    title = (await title_el.text_content() or "").strip() if title_el else None
    title = title or jld.get("title_jsonld") or partial.get("title")

    # ─── 3. Description ───
    desc_el = await page.query_selector("[class*='description']")
    description = (await desc_el.text_content() or "").strip() if desc_el else None

    # ─── 4. Price ───
    price_el = await page.query_selector("[class*='price-value']")
    price_text = (await price_el.text_content() or "").strip() if price_el else ""
    if price_text:
        price, currency = _clean_price(price_text)
    else:
        price, currency = partial.get("price"), partial.get("currency")

    # Maintenance
    exp_el = await page.query_selector("[class*='expenses']")
    maintenance_fee = None
    if exp_el:
        maintenance_fee, _ = _clean_price((await exp_el.text_content() or ""))

    # ─── 5. Main features (li items: m², rec., baños, años) ───
    feat_lis = await page.query_selector_all("[class*='section-icon-features'] li, [class*='section-main-features'] li")
    feat_texts = [_clean_whitespace(await li.text_content() or "") for li in feat_lis]
    feat_texts = [t for t in feat_texts if t]
    features = _parse_features(feat_texts) if feat_texts else {}

    # Merge with JSON-LD (JSON-LD wins for structured fields)
    bedrooms = jld.get("bedrooms_jsonld") or features.get("bedrooms") or partial.get("bedrooms")
    bathrooms = jld.get("bathrooms_jsonld") or features.get("bathrooms") or partial.get("bathrooms")
    half_bathrooms = features.get("half_bathrooms") or partial.get("half_bathrooms")
    parking_spaces = features.get("parking_spaces") or partial.get("parking_spaces")
    land_m2 = features.get("land_m2") or partial.get("land_m2")
    construction_m2 = features.get("construction_m2") or jld.get("floor_m2_jsonld") or partial.get("construction_m2")
    built_levels = features.get("built_levels") or partial.get("built_levels")
    antiquity = features.get("antiquity") or partial.get("antiquity")
    construction_years = features.get("construction_years") or partial.get("construction_years")

    # ─── 6. Property type ───
    property_type = jld.get("property_type_jsonld") or partial.get("property_type")

    # ─── 7. Location (JSON-LD + HTML) ───
    # HTML location
    loc_el = await page.query_selector("[class*='section-location']")
    loc_h4s = await loc_el.query_selector_all("h4") if loc_el else []
    loc_texts = [(await h.text_content() or "").strip() for h in loc_h4s]

    # From JSON-LD
    street = jld.get("street_jsonld") or partial.get("street_and_number")
    neighborhood = jld.get("region_jsonld") or partial.get("neighborhood")

    locality = jld.get("locality_jsonld", "")
    loc_parsed = _parse_locality(locality) if locality else {}
    municipality = loc_parsed.get("municipality") or partial.get("municipality")
    city = loc_parsed.get("city")
    country = loc_parsed.get("country") or "México"

    # If HTML has more detail, use it
    if loc_texts:
        full_loc = loc_texts[0] if loc_texts else ""
        parts = [p.strip() for p in full_loc.split(",") if p.strip()]
        if len(parts) >= 1 and not street:
            # First part before comma is usually street
            first_part = parts[0].strip()
            # Check if it looks like an address (has a number or is short)
            if first_part and not neighborhood:
                street = first_part

    # ─── 8. General features section (amenities, services, exteriors) ───
    gen_items = await page.query_selector_all("[class*='generalFeaturesProperty-module__descript']")
    gen_texts = [(await item.text_content() or "").strip() for item in gen_items]
    gen_texts = [t for t in gen_texts if t]

    # Categorize general features
    amenities = _classify_list(gen_texts + (partial.get("pills") or []), config.AMENITIES_MAP) or partial.get("amenities")
    services = _classify_list(gen_texts + (partial.get("pills") or []), config.SERVICES_MAP) or partial.get("services")
    exteriors = _classify_list(gen_texts + (partial.get("pills") or []), config.EXTERIORS_MAP) or partial.get("exteriors")
    extras = _classify_list(gen_texts + (partial.get("pills") or []), config.EXTRAS_MAP) or partial.get("extras")
    extra_rooms = _classify_list(gen_texts, config.EXTRA_ROOMS_MAP)

    # Booleans from general features
    gen_lower = " ".join(t.lower() for t in gen_texts)
    has_balcony = True if "balcón" in gen_lower or "balcon" in gen_lower else None
    has_elevator = True if "elevador" in gen_lower else None
    has_storage = True if "bodega" in gen_lower else None

    # Built levels from general features ("Niveles construidos : 2")
    for t in gen_texts:
        if "nivel" in t.lower():
            n = _extract_int(t)
            if n:
                built_levels = n

    # Conservation
    conservation = None
    for t in gen_texts + feat_texts:
        conservation = _normalize(t, config.CONSERVATION_MAP)
        if conservation:
            break

    # Antiquity from general features
    for t in gen_texts:
        ant = _normalize(t, config.ANTIQUITY_MAP)
        if ant:
            antiquity = ant

    # ─── 9. Media ───
    images = await page.query_selector_all("[class*='gallery'] img, [class*='Gallery'] img")
    images_count = len(images) or partial.get("images_count", 0)

    video_el = await page.query_selector("iframe[src*='youtube'], iframe[src*='vimeo'], video source")
    video_url = await video_el.get_attribute("src") if video_el else None

    tour_el = await page.query_selector("iframe[src*='360'], iframe[src*='matterport']")
    tour_360_url = await tour_el.get_attribute("src") if tour_el else None

    # ─── 10. Coordinates (JSON-LD or map element) ───
    latitude = jld.get("latitude_jsonld")
    longitude = jld.get("longitude_jsonld")
    if not latitude:
        map_el = await page.query_selector("[class*='static-map']")
        if map_el:
            lat = await map_el.get_attribute("data-lat") or await map_el.get_attribute("data-latitude")
            lng = await map_el.get_attribute("data-lng") or await map_el.get_attribute("data-longitude")
            if lat and lng:
                try:
                    latitude, longitude = float(lat), float(lng)
                except ValueError:
                    pass

    # ─── 11. Internal code ───
    code_el = await page.query_selector("[class*='posting-code'], [class*='code']")
    internal_code = None
    if code_el:
        ct = (await code_el.text_content() or "").strip()
        m = re.search(r"(\d+)", ct)
        internal_code = m.group(1) if m else None

    return ScrapedItem(
        external_id=partial["external_id"],
        url_listing=partial.get("url_listing"),
        internal_code=internal_code,
        title=title,
        description=description,
        operation=partial.get("operation"),
        property_type=property_type,
        listing_type=partial.get("operation"),
        price=price,
        currency=currency,
        maintenance_fee=maintenance_fee,
        street_and_number=street,
        neighborhood=neighborhood,
        city=city,
        municipality=municipality,
        state=partial.get("state"),
        country=country,
        latitude=latitude,
        longitude=longitude,
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
