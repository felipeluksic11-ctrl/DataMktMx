"""Price normalizer — currency conversion + price per m².

Rules:
- Convert USD to MXN using a fixed rate (updated periodically)
- Calculate price_per_m2 when construction_m2 is available
- Validate: reject unrealistic prices (< $10,000 MXN for sale, > $500M MXN)
"""

# Fixed exchange rate — update periodically via API or manual config
# Using a conservative rate to avoid overestimating
USD_TO_MXN = 17.5  # as of 2026-03


def normalize_price(
    price: float | None,
    currency: str | None,
    operation: str | None,
) -> tuple[float | None, float | None]:
    """Normalize price to MXN and USD.

    Returns (price_mxn, price_usd).
    """
    if price is None or price <= 0:
        return None, None

    currency = (currency or "MXN").upper()

    if currency == "USD":
        price_mxn = round(price * USD_TO_MXN, 2)
        price_usd = round(price, 2)
    else:
        price_mxn = round(price, 2)
        price_usd = round(price / USD_TO_MXN, 2)

    # Sanity checks
    if operation == "venta":
        if price_mxn < 50_000 or price_mxn > 500_000_000:
            return None, None  # unrealistic sale price
    elif operation == "renta":
        if price_mxn < 500 or price_mxn > 5_000_000:
            return None, None  # unrealistic rent price

    return price_mxn, price_usd


def calculate_price_per_m2(
    price_mxn: float | None,
    construction_m2: float | None,
    land_m2: float | None,
) -> float | None:
    """Calculate price per m². Prefers construction area, falls back to land."""
    if price_mxn is None:
        return None

    area = construction_m2 or land_m2
    if not area or area <= 0:
        return None

    result = round(price_mxn / area, 2)

    # Sanity: price/m2 should be between $1,000 and $500,000 MXN
    if result < 1_000 or result > 500_000:
        return None

    return result
