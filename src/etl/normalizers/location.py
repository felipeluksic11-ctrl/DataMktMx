"""Location normalizer — state, municipality, neighborhood.

Handles the mess of different formats across portals:
- Inmuebles24: municipality="Benito Juárez", state="Ciudad De Mexico"
- Propiedades.com: municipality="Hilario Pérez de León #84 Depto 202, Américas Unidas, 03610, Benito Juárez, CDMX"
- Lamudi: neighborhood="Florida", municipality="Álvaro Obregón", state="Distrito Federal"

Strategy:
1. Normalize state using alias lookup (fast, deterministic)
2. For CDMX: detect alcaldía from municipality text
3. Extract zip code if embedded in address text
4. Clean neighborhood name
"""

import re

from etl.catalogs import (
    CDMX_ALCALDIAS_LOWER,
    STATE_ALIASES,
    STATES,
)
from etl.normalizers.text import extract_zip_code, normalize_text, title_case_mx


def normalize_state(raw: str | None) -> tuple[str | None, str | None]:
    """Normalize state to (code, name). Returns (None, None) if unknown.

    >>> normalize_state("Ciudad De Mexico")
    ('CMX', 'Ciudad de México')
    >>> normalize_state("Distrito Federal")
    ('CMX', 'Ciudad de México')
    >>> normalize_state("DF / CDMX")
    ('CMX', 'Ciudad de México')
    """
    if not raw:
        return None, None

    key = normalize_text(raw)

    # Direct lookup
    code = STATE_ALIASES.get(key)
    if code:
        return code, STATES[code]["name"]

    # Try partial matching for complex strings like "DF / CDMX"
    for alias, code in STATE_ALIASES.items():
        if alias in key:
            return code, STATES[code]["name"]

    return None, None


def normalize_municipality(
    raw_municipality: str | None,
    state_code: str | None,
) -> tuple[str | None, str | None]:
    """Normalize municipality. Returns (clean_name, extracted_zip_code).

    For CDMX: validates against official alcaldía list.
    For Propiedades.com: extracts the alcaldía from long address strings.
    """
    if not raw_municipality:
        return None, None

    text = raw_municipality.strip()
    zip_code = extract_zip_code(text)

    # For CDMX, try to find the alcaldía in the text
    if state_code == "CMX":
        text_lower = normalize_text(text)
        for alcaldia_lower, alcaldia_proper in CDMX_ALCALDIAS_LOWER.items():
            if normalize_text(alcaldia_lower) in text_lower:
                return alcaldia_proper, zip_code

    # For other states or if no alcaldía found: clean up the text
    # If it's a long address (Propiedades.com), try to extract municipality name
    if len(text) > 80:
        # Pattern: "..., DelegaciónName, CDMX" or "..., DelegaciónName, Ciudad de México"
        parts = [p.strip() for p in text.split(",")]
        # Walk backwards looking for an alcaldía or short name
        for part in reversed(parts):
            part_lower = normalize_text(part)
            if state_code == "CMX":
                for alc_lower, alc_proper in CDMX_ALCALDIAS_LOWER.items():
                    if normalize_text(alc_lower) in part_lower:
                        return alc_proper, zip_code
            # If it's a short clean name (not a number, not an address)
            if 3 < len(part) < 40 and not re.search(r"\d{3,}", part):
                return title_case_mx(part), zip_code

    # Clean short municipality name
    clean = re.sub(r"\s*,\s*$", "", text)  # trailing comma
    if len(clean) < 80:
        return title_case_mx(clean), zip_code

    return None, zip_code


def normalize_neighborhood(raw: str | None) -> str | None:
    """Clean neighborhood/colony name."""
    if not raw:
        return None

    text = raw.strip()
    if not text or len(text) > 200:
        return None

    # Remove "Col." prefix
    text = re.sub(r"^Col\.?\s*", "", text, flags=re.IGNORECASE)
    # Remove trailing comma
    text = re.sub(r"\s*,\s*$", "", text)
    # Title case
    return title_case_mx(text) if text else None
