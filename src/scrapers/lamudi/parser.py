"""Parse Lamudi.com.mx HTML into structured data.

Strategy:
1. Search results — parse .property cards with scouted selectors (verified 2026-03-31)
2. JSON-LD (Schema.org) — primary source for structured data on detail pages
3. Detail page HTML — features, amenities, description, gallery

Selectors verified against live site: 2026-03-31.
"""

import re
import json

from playwright.async_api import Page

from scrapers.base import ScrapedItem
from scrapers.lamudi import config
from shared.logging import get_logger

logger = get_logger("scraper.lamudi.parser")


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
    """Parse feature strings like '3 Recámaras', '2 Baños', '120 m²', '2 Estacionamientos'."""
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
                matched = True
                break

        if not matched:
            # "41 años" -> antiquity
            if "año" in text:
                years = _extract_int(text)
                if years:
                    result["antiquity"] = str(years)
                    result["construction_years"] = years
            # bare "m²" without qualifier
            elif "m²" in text or "m2" in text:
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
                // Lamudi may use RealEstateListing, Product, Residence, etc.
                const types = ['RealEstateListing', 'House', 'Apartment',
                               'SingleFamilyResidence', 'LandForm', 'Product',
                               'Place', 'Residence'];
                if (types.includes(data['@type'])) {
                    return data;
                }
                // Handle @graph pattern
                if (data['@graph']) {
                    for (const item of data['@graph']) {
                        if (types.includes(item['@type'])) return item;
                    }
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
        "Apartment": "departamento", "Residence": "departamento",
        "LandForm": "terreno",
    }
    result["property_type_jsonld"] = type_map.get(data.get("@type", ""))

    result["title_jsonld"] = data.get("name", "").strip() or None
    result["description_jsonld"] = data.get("description")
    result["bedrooms_jsonld"] = data.get("numberOfBedrooms")
    result["bathrooms_jsonld"] = data.get("numberOfBathroomsTotal") or data.get("numberOfBathrooms")
    result["rooms_jsonld"] = data.get("numberOfRooms")

    # Floor size
    floor = data.get("floorSize", {})
    if isinstance(floor, dict) and floor.get("unitCode") in ("MTK", "SQM"):
        result["floor_m2_jsonld"] = floor.get("value")
    elif isinstance(floor, dict) and floor.get("value"):
        # Try to parse anyway
        try:
            result["floor_m2_jsonld"] = float(floor["value"])
        except (ValueError, TypeError):
            pass

    # Lot size
    lot = data.get("lotSize", {})
    if isinstance(lot, dict):
        try:
            result["lot_m2_jsonld"] = float(lot.get("value", 0)) or None
        except (ValueError, TypeError):
            pass

    # Address
    addr = data.get("address", {})
    if isinstance(addr, dict):
        result["street_jsonld"] = addr.get("streetAddress")
        result["region_jsonld"] = addr.get("addressRegion")
        result["locality_jsonld"] = addr.get("addressLocality")
        result["postal_code_jsonld"] = addr.get("postalCode")

    # Coordinates
    geo = data.get("geo", {})
    if isinstance(geo, dict):
        lat = geo.get("latitude")
        lng = geo.get("longitude")
        if lat and lng:
            try:
                result["latitude_jsonld"] = float(lat)
                result["longitude_jsonld"] = float(lng)
            except (ValueError, TypeError):
                pass

    # Images
    images = data.get("image") or data.get("photo")
    if isinstance(images, list):
        result["images_count_jsonld"] = len(images)
    elif isinstance(images, str):
        result["images_count_jsonld"] = 1

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


def _parse_location_text(location_text: str) -> dict:
    """Parse location string like 'Col. Roma Norte, Cuauhtémoc, Ciudad de México'."""
    result: dict = {"neighborhood": None, "municipality": None, "city": None}
    if not location_text:
        return result
    parts = [p.strip() for p in location_text.split(",") if p.strip()]
    # Remove common prefixes
    cleaned = []
    for p in parts:
        p = re.sub(r"^(Col\.\s*|Fracc\.\s*|Res\.\s*)", "", p, flags=re.IGNORECASE).strip()
        if p:
            cleaned.append(p)

    if len(cleaned) >= 3:
        result["neighborhood"] = cleaned[0]
        result["municipality"] = cleaned[1]
        result["city"] = cleaned[2]
    elif len(cleaned) == 2:
        result["neighborhood"] = cleaned[0]
        result["municipality"] = cleaned[1]
    elif len(cleaned) == 1:
        result["neighborhood"] = cleaned[0]
    return result


def _parse_locality(locality: str) -> dict:
    """Parse JSON-LD addressLocality like 'Cuajimalpa de Morelos, Ciudad de México'."""
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


def _detect_property_type(text: str) -> str | None:
    """Detect property type from URL path or breadcrumb text."""
    text_lower = text.lower()
    for keyword, ptype in config.PROPERTY_TYPE_FROM_URL.items():
        if keyword in text_lower:
            return ptype
    return None


# ──────────────────────────── Search results page ────────────────────────────


async def parse_search_results(page: Page) -> list[dict]:
    """Parse listing cards from a Lamudi search results page.

    Scouted selectors (2026-03-31):
    - Cards: `.property` divs inside `.listings__cards`
    - Price: `.snippet__content__price`
    - Location: `.snippet__content__location`
    - Description: `.snippet__content__description`
    - Area: `.property__number.area`
    - Bedrooms: `.property__number.bedrooms`
    - Bathrooms: `.property__number.bathrooms`
    - Parking: `.property__number.car_park`
    - Detail links: `a[href*='/detalle/']`
    """
    # Cards are .snippet.js-snippet divs with data-idanuncio
    cards = await page.query_selector_all(".snippet.js-snippet")
    if not cards:
        cards = await page.query_selector_all(config.SELECTORS["listing_card"])
    if not cards:
        cards = await page.query_selector_all(config.SELECTORS["listing_card_fallback"])
    if not cards:
        logger.warning("parser.no_cards_found", url=page.url)
        return []

    results = []
    for card in cards:
        # Detail URL — scouted: a[href*='/detalle/']
        link_el = await card.query_selector("a[href*='/detalle/']")
        if not link_el:
            link_el = await card.query_selector(config.SELECTORS["card_link"])
        if not link_el:
            link_el = await card.query_selector("a[href]")
        detail_url = None
        if link_el:
            href = await link_el.get_attribute("href")
            if href:
                detail_url = href if href.startswith("http") else config.BASE_URL + href

        # External ID from data attribute, then from URL
        external_id = await card.get_attribute("data-idanuncio") or await card.get_attribute("data-listing-id")
        if not external_id and detail_url:
            m = re.search(r"/detalle/([^/]+?)(?:\.html)?$", detail_url)
            if not m:
                m = re.search(r"-id-(\d+)", detail_url)
            if m:
                external_id = m.group(1)
            else:
                import hashlib
                external_id = hashlib.md5(detail_url.encode()).hexdigest()[:12]

        if not external_id:
            continue

        # Price — scouted: .snippet__content__price → "$ 160,000 MXN /mes"
        price_el = await card.query_selector(".snippet__content__price")
        if not price_el:
            price_el = await card.query_selector(config.SELECTORS["price"])
        price_text = (await price_el.text_content() or "").strip() if price_el else ""
        price, currency = _clean_price(price_text)

        # Features — scouted: individual .property__number.{type} elements
        feature_texts = []

        area_el = await card.query_selector(".property__number.area")
        if area_el:
            feature_texts.append((await area_el.text_content() or "").strip())

        bed_el = await card.query_selector(".property__number.bedrooms")
        if bed_el:
            feature_texts.append((await bed_el.text_content() or "").strip())

        bath_el = await card.query_selector(".property__number.bathrooms")
        if bath_el:
            feature_texts.append((await bath_el.text_content() or "").strip())

        park_el = await card.query_selector(".property__number.car_park")
        if park_el:
            feature_texts.append((await park_el.text_content() or "").strip())

        # Fallback: config-based feature selectors
        if not feature_texts:
            feat_els = await card.query_selector_all(config.SELECTORS["feature_item"])
            if not feat_els:
                feat_els = await card.query_selector_all("[class*='feature'] span, [class*='Feature'] span")
            feature_texts = [(await f.text_content() or "").strip() for f in feat_els]

        features = _parse_features([t for t in feature_texts if t])

        # Location — scouted: .snippet__content__location → "Florida, Álvaro Obregón, Ciudad de México"
        loc_el = await card.query_selector(".snippet__content__location")
        if not loc_el:
            loc_el = await card.query_selector(config.SELECTORS["location"])
        loc_text = (await loc_el.text_content() or "").strip() if loc_el else ""
        location = _parse_location_text(loc_text)

        # Description — scouted: .snippet__content__description
        desc_el = await card.query_selector(".snippet__content__description")
        description = (await desc_el.text_content() or "").strip() if desc_el else None
        if description:
            description = _clean_whitespace(description)

        # Title
        title_el = await card.query_selector(config.SELECTORS["card_title"])
        title = (await title_el.text_content() or "").strip() if title_el else None
        if title:
            title = _clean_whitespace(title)

        # Property type from title or URL
        property_type = None
        if title:
            property_type = _detect_property_type(title)
        if not property_type and detail_url:
            property_type = _detect_property_type(detail_url)

        # Images count
        images = await card.query_selector_all(config.SELECTORS["card_images"])

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
            **features,
            "images_count": len(images),
        })

    logger.info("parser.cards_parsed", count=len(results), url=page.url)
    return results


# ──────────────────────────── Detail page ────────────────────────────


async def parse_detail_page(page: Page, partial: dict) -> ScrapedItem:
    """Parse detail page using JSON-LD + HTML features."""

    # --- 1. JSON-LD (best structured source) ---
    jsonld_raw = await _extract_jsonld(page)
    jld = _parse_jsonld(jsonld_raw) if jsonld_raw else {}

    # --- 2. Title ---
    title_el = await page.query_selector(config.SELECTORS["detail_title"])
    title = (await title_el.text_content() or "").strip() if title_el else None
    title = title or jld.get("title_jsonld") or partial.get("title")
    if title:
        title = _clean_whitespace(title)

    # --- 3. Description ---
    desc_el = await page.query_selector(config.SELECTORS["detail_description"])
    description = (await desc_el.text_content() or "").strip() if desc_el else None
    description = description or jld.get("description_jsonld")

    # --- 4. Price ---
    price_el = await page.query_selector(config.SELECTORS["detail_price"])
    price_text = (await price_el.text_content() or "").strip() if price_el else ""
    if price_text:
        price, currency = _clean_price(price_text)
    else:
        price = jld.get("price_jsonld") or partial.get("price")
        currency = jld.get("currency_jsonld") or partial.get("currency")

    # Maintenance
    maint_el = await page.query_selector(config.SELECTORS["detail_maintenance"])
    maintenance_fee = None
    if maint_el:
        maintenance_fee, _ = _clean_price((await maint_el.text_content() or ""))

    # --- 5. Main features (li items: m2, bedrooms, bathrooms, parking, etc.) ---
    feat_lis = await page.query_selector_all(config.SELECTORS["detail_features"])
    feat_texts = [_clean_whitespace(await li.text_content() or "") for li in feat_lis]
    feat_texts = [t for t in feat_texts if t]
    features = _parse_features(feat_texts) if feat_texts else {}

    # Merge with JSON-LD (JSON-LD wins for structured fields)
    bedrooms = jld.get("bedrooms_jsonld") or features.get("bedrooms") or partial.get("bedrooms")
    bathrooms = jld.get("bathrooms_jsonld") or features.get("bathrooms") or partial.get("bathrooms")
    half_bathrooms = features.get("half_bathrooms") or partial.get("half_bathrooms")
    parking_spaces = features.get("parking_spaces") or partial.get("parking_spaces")
    land_m2 = jld.get("lot_m2_jsonld") or features.get("land_m2") or partial.get("land_m2")
    construction_m2 = features.get("construction_m2") or jld.get("floor_m2_jsonld") or partial.get("construction_m2")
    built_levels = features.get("built_levels") or partial.get("built_levels")
    antiquity = features.get("antiquity") or partial.get("antiquity")
    construction_years = features.get("construction_years") or partial.get("construction_years")

    # --- 6. Property type ---
    property_type = jld.get("property_type_jsonld") or partial.get("property_type")
    if not property_type:
        # Try breadcrumb
        bc_el = await page.query_selector(config.SELECTORS["detail_breadcrumb"])
        if bc_el:
            bc_text = (await bc_el.text_content() or "")
            property_type = _detect_property_type(bc_text)

    # --- 7. Location (JSON-LD + HTML) ---
    # From JSON-LD
    street = jld.get("street_jsonld") or partial.get("street_and_number")
    neighborhood = jld.get("region_jsonld") or partial.get("neighborhood")
    zip_code = jld.get("postal_code_jsonld")

    locality = jld.get("locality_jsonld", "")
    loc_parsed = _parse_locality(locality) if locality else {}
    municipality = loc_parsed.get("municipality") or partial.get("municipality")
    city = loc_parsed.get("city") or partial.get("city")
    country = loc_parsed.get("country") or "Mexico"

    # HTML location as fallback
    if not neighborhood:
        loc_el = await page.query_selector(config.SELECTORS["detail_location"])
        if loc_el:
            loc_text = (await loc_el.text_content() or "").strip()
            html_loc = _parse_location_text(loc_text)
            neighborhood = neighborhood or html_loc.get("neighborhood")
            municipality = municipality or html_loc.get("municipality")
            city = city or html_loc.get("city")

    # --- 8. Amenities, services, extras from detail features ---
    amenity_lis = await page.query_selector_all(config.SELECTORS["detail_amenities"])
    amenity_texts = [(await li.text_content() or "").strip() for li in amenity_lis]
    amenity_texts = [t for t in amenity_texts if t]

    # Combine feature texts and amenity texts for classification
    all_feature_texts = feat_texts + amenity_texts
    amenities = _classify_list(all_feature_texts, config.AMENITIES_MAP)
    services = _classify_list(all_feature_texts, config.SERVICES_MAP)
    exteriors = _classify_list(all_feature_texts, config.EXTERIORS_MAP)
    extras = _classify_list(all_feature_texts, config.EXTRAS_MAP)
    extra_rooms = _classify_list(all_feature_texts, config.EXTRA_ROOMS_MAP)

    # Booleans from feature texts
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
    images_count = len(images) or jld.get("images_count_jsonld", 0) or partial.get("images_count", 0)

    video_el = await page.query_selector(config.SELECTORS["detail_video"])
    video_url = await video_el.get_attribute("src") if video_el else None

    tour_el = await page.query_selector(config.SELECTORS["detail_tour"])
    tour_360_url = await tour_el.get_attribute("src") if tour_el else None

    # --- 10. Coordinates (JSON-LD or map element) ---
    latitude = jld.get("latitude_jsonld")
    longitude = jld.get("longitude_jsonld")
    if not latitude:
        map_el = await page.query_selector(config.SELECTORS["detail_map"])
        if map_el:
            lat = await map_el.get_attribute("data-lat") or await map_el.get_attribute("data-latitude")
            lng = await map_el.get_attribute("data-lng") or await map_el.get_attribute("data-longitude")
            if lat and lng:
                try:
                    latitude, longitude = float(lat), float(lng)
                except ValueError:
                    pass

    # --- 11. Internal code ---
    code_el = await page.query_selector(config.SELECTORS["detail_internal_code"])
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
        zip_code=zip_code,
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
