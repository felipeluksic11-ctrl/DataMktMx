"""Property type and operation normalizer."""

from etl.catalogs import OPERATIONS, PROPERTY_TYPE_ALIASES, PROPERTY_TYPES
from etl.normalizers.text import normalize_text


def normalize_property_type(raw: str | None) -> str | None:
    """Normalize property type to standard key.

    >>> normalize_property_type("departamento")
    'departamento'
    >>> normalize_property_type("PH")
    'departamento'
    >>> normalize_property_type("Terreno / Lote")
    'terreno'
    """
    if not raw:
        return None

    key = normalize_text(raw)

    # Direct match
    if key in PROPERTY_TYPES:
        return key

    # Alias match
    if key in PROPERTY_TYPE_ALIASES:
        return PROPERTY_TYPE_ALIASES[key]

    # Partial match
    for alias, normalized in PROPERTY_TYPE_ALIASES.items():
        if alias in key:
            return normalized

    return raw.lower().strip()


def normalize_operation(raw: str | None) -> str | None:
    """Normalize operation to standard key (venta/renta/vacacional).

    >>> normalize_operation("venta")
    'venta'
    >>> normalize_operation("sale")
    'venta'
    >>> normalize_operation("Renta")
    'renta'
    """
    if not raw:
        return None

    key = normalize_text(raw)

    for op_key, op_display in OPERATIONS.items():
        if key == normalize_text(op_key) or key == normalize_text(op_display):
            # Return the normalized key
            if op_display == "Venta":
                return "venta"
            elif op_display == "Renta":
                return "renta"
            elif op_display == "Vacacional":
                return "vacacional"

    return raw.lower().strip()
