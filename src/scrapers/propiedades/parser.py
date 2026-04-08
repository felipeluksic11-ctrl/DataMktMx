"""Parse Propiedades.com HTML into structured data.

Strategy:
1. JSON-LD (Schema.org) — primary source for structured data on detail pages
   - Types: Apartment, House, RealEstateListing, Offer
   - Contains: numberOfBathroomsTotal, floorSize, numberOfRooms, price, address
2. Characteristics section (.characteristic) — "BAÑOS 2", "ÁREA TERRENO 250 m2"
3. Amenities section (.amenities) — "3 Recámaras", "2.5 Baños", "430 m2"
4. Card-level data — fallback for search results without detail visit

Selectors verified against live site: 2026-03-31.
"""

import re
import json

from playwright.async_api import Page

from scrapers.base import ScrapedItem
from scrapers.propiedades import config
from shared.logging import get_logger

logger = get_logger("scraper.propiedades.parser")


# ──────────────────────────── Text utilities ────────────────────────────


def _clean_price(text: str) -> tuple[float | None, str | None]:
    """Extract numeric price and currency from text like '$3,848,000 MXN'."""
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
    """Extract first integer from text."""
    match = re.search(r"(\d+)", text)
    return int(match.group(1)) if match else None


def _extract_float(text: str) -> float | None:
    """Extract first float from text."""
    match = re.search(r"([\d,]+(?:\.\d+)?)", text)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _normalize(text: str, mapping: dict[str, str]) -> str | None:
    """Check if text matches any key in the mapping, return normalized value."""
    text_lower = text.lower().strip()
    for keyword, normalized in mapping.items():
        if keyword in text_lower:
            return normalized
    return None


def _classify_list(texts: list[str], mapping: dict[str, str]) -> list[str] | None:
    """Classify a list of text items using a mapping."""
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
    """Parse feature strings from card or amenities section."""
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

        for pattern, field_name in config.FEATURE_PATTERNS.items():
            if pattern in text:
                if field_name in ("bedrooms", "bathrooms", "half_bathrooms", "parking_spaces", "built_levels"):
                    result[field_name] = _extract_int(text)
                elif field_name in ("land_m2", "construction_m2"):
                    result[field_name] = _extract_float(text)
                matched = True
                break

        if not matched:
            # "41 años" -> antiquity
            if "año" in text:
                years = _extract_int(text)
                if years:
                    result["antiquity"] = str(years)
                    result["construction_years"] = years
            # Bare "m²" or "m2" without qualifier
            elif "m²" in text or "m2" in text:
                val = _extract_float(text)
                if val:
                    if result["land_m2"] is None:
                        result["land_m2"] = val
                    elif result["construction_m2"] is None:
                        result["construction_m2"] = val

    return result


# ──────────────────────────── Card feature parsing ────────────────────────────


def _parse_card_features(texts: list[str]) -> dict:
    """Parse card amenity items like '2 Recámaras', '1 Baño', '74 m²'."""
    result: dict = {
        "bedrooms": None,
        "bathrooms": None,
        "half_bathrooms": None,
        "construction_m2": None,
        "land_m2": None,
        "parking_spaces": None,
    }

    for raw in texts:
        text = _clean_whitespace(raw).lower()

        if "recámara" in text or "recamara" in text or "habitaci" in text:
            result["bedrooms"] = _extract_int(text)
        elif "medio baño" in text or "½ baño" in text:
            result["half_bathrooms"] = _extract_int(text)
        elif "baño" in text:
            val = _extract_float(text)
            if val and val != int(val):
                # 2.5 baños → 2 baños + 1 medio baño
                result["bathrooms"] = int(val)
                result["half_bathrooms"] = 1
            else:
                result["bathrooms"] = _extract_int(text)
        elif "estac" in text or "cochera" in text or "garage" in text:
            result["parking_spaces"] = _extract_int(text)
        elif "terreno" in text or "lote" in text:
            result["land_m2"] = _extract_float(text)
        elif "const" in text:
            result["construction_m2"] = _extract_float(text)
        elif "m²" in text or "m2" in text:
            # Bare m² without qualifier → construction
            result["construction_m2"] = _extract_float(text)

    return result


# ──────────────────────────── Characteristic parsing (detail page) ────────────────────────────


def _parse_characteristics(texts: list[str]) -> dict:
    """Parse .characteristic items like 'BAÑOS 2', 'ÁREA TERRENO 250 m2', 'ID DEL INMUEBLE 30327506'."""
    result: dict = {
        "bedrooms": None,
        "bathrooms": None,
        "half_bathrooms": None,
        "parking_spaces": None,
        "land_m2": None,
        "construction_m2": None,
        "built_levels": None,
        "antiquity": None,
        "construction_years": None,
        "internal_code": None,
    }

    for raw in texts:
        text = _clean_whitespace(raw).lower()

        for pattern, field_name in config.CHARACTERISTIC_PATTERNS.items():
            if pattern in text:
                if field_name == "internal_code":
                    code_match = re.search(r"(\d+)", text)
                    if code_match:
                        result["internal_code"] = code_match.group(1)
                elif field_name in ("bedrooms", "bathrooms", "half_bathrooms", "parking_spaces", "built_levels"):
                    result[field_name] = _extract_int(text)
                elif field_name in ("land_m2", "construction_m2"):
                    result[field_name] = _extract_float(text)
                elif field_name == "antiquity":
                    years = _extract_int(text)
                    if years:
                        result["antiquity"] = str(years)
                elif field_name == "construction_years":
                    result["construction_years"] = _extract_int(text)
                break

    return result


# ──────────────────────────── JSON-LD extraction ────────────────────────────


async def _extract_jsonld_all(page: Page) -> list[dict]:
    """Extract all JSON-LD objects from the page."""
    return await page.evaluate("""() => {
        const scripts = document.querySelectorAll('script[type="application/ld+json"]');
        const results = [];
        for (const s of scripts) {
            try {
                const data = JSON.parse(s.textContent);
                results.push(data);
            } catch(e) {}
        }
        return results;
    }""")


def _parse_jsonld_items(items: list[dict]) -> dict:
    """Extract fields from all Schema.org JSON-LD objects on a Propiedades.com detail page.

    Propiedades.com typically has multiple JSON-LD blocks:
    - Type Apartment/House with numberOfBathroomsTotal, floorSize, address, geo
    - Type Offer with price, priceCurrency
    - Type RealEstateListing with nested itemOffered containing the property
    """
    result: dict = {}

    for data in items:
        ld_type = data.get("@type", "")

        # --- Apartment / House / SingleFamilyResidence ---
        if ld_type in ("Apartment", "House", "SingleFamilyResidence", "LandForm"):
            type_map = {
                "House": "casa",
                "SingleFamilyResidence": "casa",
                "Apartment": "departamento",
                "LandForm": "terreno",
            }
            result.setdefault("property_type", type_map.get(ld_type))
            result.setdefault("title", (data.get("name") or "").split(" - ")[0].strip() or None)
            result.setdefault("description", data.get("description"))
            result.setdefault("bedrooms", _safe_int(data.get("numberOfRooms")))
            result.setdefault("bathrooms", _safe_int(data.get("numberOfBathroomsTotal")))
            result.setdefault("pets_allowed", data.get("petsAllowed"))

            floor = data.get("floorSize", {})
            if isinstance(floor, dict):
                unit = (floor.get("unitCode") or floor.get("unitText") or "").upper()
                if unit in ("MTK", "M2", "M²", "SQM"):
                    result.setdefault("floor_m2", _safe_float(floor.get("value")))

            _extract_address(data, result)
            _extract_geo(data, result)

        # --- Offer ---
        elif ld_type == "Offer":
            price_val = _safe_float(data.get("price"))
            if price_val:
                result.setdefault("price", price_val)
            result.setdefault("currency", data.get("priceCurrency"))

        # --- RealEstateListing ---
        elif ld_type == "RealEstateListing":
            result.setdefault("title", (data.get("name") or "").split(" - ")[0].strip() or None)
            result.setdefault("description", data.get("description"))
            result.setdefault("url", data.get("url"))

            # Nested itemOffered (House or Apartment)
            offered = data.get("itemOffered", {})
            if isinstance(offered, dict):
                offered_type = offered.get("@type", "")
                type_map = {
                    "House": "casa",
                    "SingleFamilyResidence": "casa",
                    "Apartment": "departamento",
                    "LandForm": "terreno",
                }
                result.setdefault("property_type", type_map.get(offered_type))
                result.setdefault("bedrooms", _safe_int(offered.get("numberOfRooms")))
                result.setdefault("bathrooms", _safe_int(offered.get("numberOfBathroomsTotal")))
                result.setdefault("pets_allowed", offered.get("petsAllowed"))

                floor = offered.get("floorSize", {})
                if isinstance(floor, dict):
                    unit = (floor.get("unitCode") or floor.get("unitText") or "").upper()
                    if unit in ("MTK", "M2", "M²", "SQM"):
                        result.setdefault("floor_m2", _safe_float(floor.get("value")))

                _extract_address(offered, result)
                _extract_geo(offered, result)

                # Nested offers inside itemOffered
                offers = offered.get("offers", {})
                if isinstance(offers, dict):
                    price_val = _safe_float(offers.get("price"))
                    if price_val:
                        result.setdefault("price", price_val)
                    result.setdefault("currency", offers.get("priceCurrency"))

    return result


def _extract_address(data: dict, result: dict) -> None:
    """Extract address fields from a JSON-LD object into result dict."""
    addr = data.get("address", {})
    if isinstance(addr, dict):
        result.setdefault("street", addr.get("streetAddress"))
        result.setdefault("neighborhood", addr.get("addressRegion"))
        result.setdefault("locality", addr.get("addressLocality"))
        result.setdefault("zip_code", addr.get("postalCode"))
        result.setdefault("country_jsonld", addr.get("addressCountry"))


def _extract_geo(data: dict, result: dict) -> None:
    """Extract geo coordinates from a JSON-LD object into result dict."""
    geo = data.get("geo", {})
    if isinstance(geo, dict):
        lat = _safe_float(geo.get("latitude"))
        lng = _safe_float(geo.get("longitude"))
        if lat and lng:
            result.setdefault("latitude", lat)
            result.setdefault("longitude", lng)


def _safe_int(val) -> int | None:
    """Safely convert a value to int."""
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _safe_float(val) -> float | None:
    """Safely convert a value to float."""
    if val is None:
        return None
    try:
        return float(str(val).replace(",", ""))
    except (ValueError, TypeError):
        return None


# ──────────────────────────── Location parsing ────────────────────────────


def _parse_location_spans(span_texts: list[str]) -> dict:
    """Parse location spans from .pcom-property-card-body-main-info-street.

    Spans typically contain: delegación, ", DF / CDMX", ", México", ", C.P. 09740"
    """
    result: dict = {
        "municipality": None,
        "state_name": None,
        "country": None,
        "zip_code": None,
    }

    clean = []
    for t in span_texts:
        t = t.strip().strip(",").strip()
        if t:
            clean.append(t)

    for t in clean:
        # Zip code
        cp_match = re.search(r"C\.?P\.?\s*(\d{5})", t)
        if cp_match:
            result["zip_code"] = cp_match.group(1)
            continue

        # Country
        if t.lower() in ("méxico", "mexico"):
            result["country"] = "México"
            continue

        # State abbreviation / name
        if t.lower() in ("df", "cdmx", "df / cdmx"):
            result["state_name"] = "Ciudad de México"
            continue

        # First unmatched becomes municipality
        if not result["municipality"]:
            result["municipality"] = t

    return result


def _parse_locality_string(locality: str) -> dict:
    """Parse JSON-LD addressLocality like 'Cuajimalpa de Morelos, Ciudad de México, Mexico'."""
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


def _detect_operation_from_badges(badge_texts: list[str]) -> str | None:
    """Detect operation type from card badge texts like 'Venta', 'Renta'."""
    for t in badge_texts:
        t_lower = t.strip().lower()
        if "venta" in t_lower:
            return "venta"
        if "renta" in t_lower:
            return "renta"
    return None


def _detect_property_type_from_badges(badge_texts: list[str]) -> str | None:
    """Detect property type from card badge texts like 'Departamento', 'Casa'."""
    for t in badge_texts:
        val = _normalize(t, config.PROPERTY_TYPE_MAP)
        if val:
            return val
    return None


# ──────────────────────────── Search results page ────────────────────────────


async def parse_search_results(page: Page) -> list[dict]:
    """Parse listing cards from a Propiedades.com search results page."""
    cards = await page.query_selector_all(config.SELECTORS["listing_card"])
    if not cards:
        logger.warning("parser.no_cards_found", url=page.url)
        return []

    results = []
    for card in cards:
        # Detail URL
        link_el = await card.query_selector(config.SELECTORS["card_link"])
        if not link_el:
            continue
        href = await link_el.get_attribute("href")
        if not href:
            continue
        detail_url = href if href.startswith("http") else config.BASE_URL + href

        # External ID from URL (last path segment or a unique identifier)
        external_id = _extract_external_id(detail_url)
        if not external_id:
            continue

        # Coordinates from meta tags
        lat_el = await card.query_selector(config.SELECTORS["card_latitude"])
        lng_el = await card.query_selector(config.SELECTORS["card_longitude"])
        latitude = None
        longitude = None
        if lat_el:
            lat_val = await lat_el.get_attribute("content")
            latitude = _safe_float(lat_val)
        if lng_el:
            lng_val = await lng_el.get_attribute("content")
            longitude = _safe_float(lng_val)

        # Type badges (property type + operation)
        badge_els = await card.query_selector_all(config.SELECTORS["card_type_badges"])
        badge_texts = [(await b.text_content() or "").strip() for b in badge_els]
        badge_texts = [t for t in badge_texts if t]

        property_type = _detect_property_type_from_badges(badge_texts)
        badge_operation = _detect_operation_from_badges(badge_texts)

        # Price
        price_el = await card.query_selector(config.SELECTORS["card_price_fallback"])
        if not price_el:
            price_el = await card.query_selector(config.SELECTORS["card_price"])
        price_text = (await price_el.text_content() or "").strip() if price_el else ""
        price, currency = _clean_price(price_text)

        # Location via itemprop attributes (structured)
        street_el = await card.query_selector(config.SELECTORS["card_street_address"])
        locality_el = await card.query_selector(config.SELECTORS["card_locality"])
        region_el = await card.query_selector(config.SELECTORS["card_region"])
        postal_el = await card.query_selector(config.SELECTORS["card_postal_code"])

        street_raw = (await street_el.get_attribute("content") or "").strip() if street_el else ""
        municipality = (await locality_el.get_attribute("content") or "").strip() if locality_el else None
        region = (await region_el.get_attribute("content") or "").strip() if region_el else None
        zip_code = (await postal_el.get_attribute("content") or "").strip() if postal_el else None

        # Parse street: extract neighborhood from "Calle, Colonia, Delegación, CP Ciudad, CDMX"
        street = None
        neighborhood = None
        if street_raw:
            parts = [p.strip() for p in street_raw.split(",") if p.strip()]
            if len(parts) >= 2:
                street = parts[0]
                neighborhood = parts[-1].replace("Col. ", "").replace("Col.", "").strip()
            elif len(parts) == 1:
                street = parts[0]

        # Features from card amenities (li.amenities)
        feat_els = await card.query_selector_all(config.SELECTORS["card_features"])
        feat_texts = [(await f.text_content() or "").strip() for f in feat_els]
        feat_texts = [t for t in feat_texts if t]
        features = _parse_card_features(feat_texts)

        # Title
        title_text = (await link_el.get_attribute("title") or "").strip() if link_el else None
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

    logger.info("parser.cards_parsed", count=len(results), url=page.url)
    return results


def _extract_external_id(url: str) -> str | None:
    """Extract a unique identifier from a Propiedades.com listing URL.

    URLs look like: /inmuebles/departamento-en-venta-en-benito-juarez-30327506
    The trailing number is the listing ID.
    """
    match = re.search(r"-(\d{5,})(?:\?|$|#)", url)
    if match:
        return match.group(1)
    # Fallback: use the last path segment
    parts = url.rstrip("/").split("/")
    if parts:
        return parts[-1]
    return None


# ──────────────────────────── Detail page ────────────────────────────


async def parse_detail_page(page: Page, partial: dict) -> ScrapedItem:
    """Parse a Propiedades.com detail page using JSON-LD + HTML characteristics."""

    # ─── 1. JSON-LD (best structured source) ───
    jsonld_items = await _extract_jsonld_all(page)
    jld = _parse_jsonld_items(jsonld_items) if jsonld_items else {}

    # ─── 2. Title ───
    title_el = await page.query_selector(config.SELECTORS["detail_title"])
    title = (await title_el.text_content() or "").strip() if title_el else None
    title = title or jld.get("title") or partial.get("title")

    # ─── 3. Subtitle (municipality, state) ───
    subtitle_el = await page.query_selector(config.SELECTORS["detail_subtitle"])
    subtitle = (await subtitle_el.text_content() or "").strip() if subtitle_el else ""

    # ─── 4. Description ───
    desc_el = await page.query_selector(config.SELECTORS["detail_description"])
    description = (await desc_el.text_content() or "").strip() if desc_el else None
    description = description or jld.get("description")

    # ─── 5. Price (from JSON-LD, already parsed) ───
    price = jld.get("price") or partial.get("price")
    currency = jld.get("currency") or partial.get("currency")

    # ─── 6. Characteristics section ───
    char_els = await page.query_selector_all(config.SELECTORS["detail_characteristics"])
    char_texts = [_clean_whitespace(await el.text_content() or "") for el in char_els]
    char_texts = [t for t in char_texts if t]
    chars = _parse_characteristics(char_texts) if char_texts else {}

    # ─── 7. Amenities section (feature items) ───
    amenity_els = await page.query_selector_all(config.SELECTORS["detail_amenities"])
    amenity_texts = [_clean_whitespace(await el.text_content() or "") for el in amenity_els]
    amenity_texts = [t for t in amenity_texts if t]

    # Parse numeric features from amenities (e.g., "3 Recámaras", "2.5 Baños")
    amenity_features = _parse_features(amenity_texts) if amenity_texts else {}

    # ─── 8. Merge fields: JSON-LD > characteristics > amenities > card partial ───
    property_type = jld.get("property_type") or partial.get("property_type")
    bedrooms = (
        jld.get("bedrooms")
        or chars.get("bedrooms")
        or amenity_features.get("bedrooms")
        or partial.get("bedrooms")
    )
    bathrooms = (
        jld.get("bathrooms")
        or chars.get("bathrooms")
        or amenity_features.get("bathrooms")
        or partial.get("bathrooms")
    )
    half_bathrooms = (
        chars.get("half_bathrooms")
        or amenity_features.get("half_bathrooms")
        or partial.get("half_bathrooms")
    )
    parking_spaces = (
        chars.get("parking_spaces")
        or amenity_features.get("parking_spaces")
        or partial.get("parking_spaces")
    )
    land_m2 = (
        chars.get("land_m2")
        or amenity_features.get("land_m2")
        or partial.get("land_m2")
    )
    construction_m2 = (
        chars.get("construction_m2")
        or jld.get("floor_m2")
        or amenity_features.get("construction_m2")
        or partial.get("construction_m2")
    )
    built_levels = (
        chars.get("built_levels")
        or amenity_features.get("built_levels")
        or partial.get("built_levels")
    )
    antiquity = chars.get("antiquity") or partial.get("antiquity")
    construction_years = chars.get("construction_years") or partial.get("construction_years")
    internal_code = chars.get("internal_code") or partial.get("internal_code")

    # ─── 9. Location ───
    street = jld.get("street") or partial.get("street_and_number")
    neighborhood = jld.get("neighborhood") or partial.get("neighborhood")
    zip_code = jld.get("zip_code") or partial.get("zip_code")

    locality = jld.get("locality", "")
    loc_parsed = _parse_locality_string(locality) if locality else {}
    municipality = loc_parsed.get("municipality") or partial.get("municipality")
    city = loc_parsed.get("city")
    country = loc_parsed.get("country") or partial.get("country") or "México"

    # Subtitle often has "Municipio, Estado" format
    if subtitle and not municipality:
        sub_parts = [p.strip() for p in subtitle.split(",") if p.strip()]
        if len(sub_parts) >= 1:
            municipality = sub_parts[0]

    # ─── 10. Coordinates ───
    latitude = jld.get("latitude") or partial.get("latitude")
    longitude = jld.get("longitude") or partial.get("longitude")

    # ─── 11. Pets allowed ───
    pets_allowed = jld.get("pets_allowed")

    # ─── 12. Classify amenity texts into categories ───
    all_feature_texts = char_texts + amenity_texts
    amenities = _classify_list(all_feature_texts, config.AMENITIES_MAP)
    services = _classify_list(all_feature_texts, config.SERVICES_MAP)
    exteriors = _classify_list(all_feature_texts, config.EXTERIORS_MAP)
    extras = _classify_list(all_feature_texts, config.EXTRAS_MAP)
    extra_rooms = _classify_list(all_feature_texts, config.EXTRA_ROOMS_MAP)

    # Add pets from JSON-LD
    if pets_allowed is True:
        if extras is None:
            extras = ["permite_mascotas"]
        elif "permite_mascotas" not in extras:
            extras.append("permite_mascotas")

    # Booleans from feature texts
    all_lower = " ".join(t.lower() for t in all_feature_texts)
    has_balcony = True if "balcón" in all_lower or "balcon" in all_lower else None
    has_elevator = True if "elevador" in all_lower else None
    has_storage = True if "bodega" in all_lower else None

    # Conservation
    conservation = None
    for t in all_feature_texts:
        conservation = _normalize(t, config.CONSERVATION_MAP)
        if conservation:
            break

    # Antiquity from feature texts
    for t in all_feature_texts:
        ant = _normalize(t, config.ANTIQUITY_MAP)
        if ant:
            antiquity = ant
            break

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
        street_and_number=street,
        neighborhood=neighborhood,
        city=city,
        municipality=municipality,
        state=partial.get("state"),
        country=country,
        zip_code=zip_code,
        latitude=latitude,
        longitude=longitude,
        images_count=0,
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
        raw_json=jsonld_items if jsonld_items else None,
    )
