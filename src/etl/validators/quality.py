"""Quality scoring and completeness calculation for listings.

Scores are 0.0 to 1.0:
- completeness: what % of fields are filled
- quality: are the values reasonable/consistent
"""


# Field weights for completeness scoring (total = 1.0)
FIELD_WEIGHTS = {
    "price": 0.15,
    "property_type": 0.10,
    "operation": 0.05,
    "state": 0.05,
    "municipality": 0.08,
    "neighborhood": 0.07,
    "bedrooms": 0.08,
    "bathrooms": 0.07,
    "construction_m2": 0.10,
    "land_m2": 0.05,
    "parking_spaces": 0.03,
    "description": 0.05,
    "title": 0.02,
    "images_count": 0.03,
    "zip_code": 0.03,
    "latitude": 0.04,
}


def calculate_completeness(data: dict) -> float:
    """Calculate what fraction of weighted fields are present."""
    score = 0.0
    for field, weight in FIELD_WEIGHTS.items():
        val = data.get(field)
        if val is not None and val != "" and val != 0:
            score += weight
    return round(min(score, 1.0), 3)


def calculate_quality(data: dict) -> float:
    """Calculate quality score based on data consistency and reasonableness."""
    score = 1.0
    penalties = 0.0

    # Price sanity
    price = data.get("price_mxn")
    operation = data.get("operation")
    if price:
        if operation == "venta" and price < 100_000:
            penalties += 0.2  # suspiciously cheap for sale
        if operation == "renta" and price > 1_000_000:
            penalties += 0.1  # very expensive rent, might be sale

    # Area sanity
    construction = data.get("construction_m2")
    land = data.get("land_m2")
    if construction and land:
        if construction > land * 5:
            penalties += 0.15  # construction >> land is suspicious

    # Price per m2 sanity
    price_per_m2 = data.get("price_per_m2")
    if price_per_m2:
        if price_per_m2 < 2_000 or price_per_m2 > 300_000:
            penalties += 0.1

    # Title quality
    title = data.get("title") or ""
    if len(title) < 10:
        penalties += 0.05  # very short title
    if title == title.upper():
        penalties += 0.03  # ALL CAPS

    # Missing critical combination
    if not data.get("state"):
        penalties += 0.15
    if not data.get("price_mxn"):
        penalties += 0.15

    return round(max(score - penalties, 0.0), 3)
