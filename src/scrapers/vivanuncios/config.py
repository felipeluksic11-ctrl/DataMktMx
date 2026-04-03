"""Vivanuncios scraper configuration.

Vivanuncios uses the same frontend as Inmuebles24 (both Navent/OLX group).
We reuse I24's selectors and parser, only changing the URLs.

Verified: 2026-03-31
"""

from scrapers.inmuebles24 import config as i24_config

BASE_URL = "https://www.vivanuncios.com.mx"

# URL pattern: /s-venta-inmuebles/ciudad-de-mexico/v1c1097l1012p{page}
# Vivanuncios uses location codes (l-codes) instead of slugs
# Main search: /s-{operation}-inmuebles/v1c1097p{page}

# State location codes
STATE_CODES = {
    "ciudad-de-mexico": "l1012",
    "estado-de-mexico": "l1013",
    "jalisco": "l1017",
    "nuevo-leon": "l1022",
    "puebla": "l1024",
    "queretaro": "l1025",
    "quintana-roo": "l1026",
    "yucatan": "l1032",
    "guanajuato": "l1015",
    "baja-california-sur": "l1004",
    "baja-california": "l1003",
    "chihuahua": "l1009",
    "coahuila": "l1006",
    "sonora": "l1028",
    "sinaloa": "l1027",
    "veracruz": "l1031",
    "guerrero": "l1016",
    "morelos": "l1020",
    "aguascalientes": "l1002",
    "san-luis-potosi": "l1027",
    "michoacan": "l1019",
    "tabasco": "l1029",
    "tamaulipas": "l1030",
    "hidalgo": "l1014",
    "nayarit": "l1021",
    "colima": "l1007",
    "chiapas": "l1008",
    "campeche": "l1005",
    "durango": "l1011",
    "tlaxcala": "l1030",
    "zacatecas": "l1033",
    "oaxaca": "l1023",
}

OPERATIONS = {
    "venta": "venta",
    "renta": "renta",
}

# Category codes
CATEGORY_CODE = "c1097"  # inmuebles (all)

STATES = list(STATE_CODES.keys())

# Reuse I24 selectors — identical frontend
SELECTORS = i24_config.SELECTORS
FEATURE_PATTERNS = i24_config.FEATURE_PATTERNS
PROPERTY_TYPE_FROM_URL = i24_config.PROPERTY_TYPE_FROM_URL
EXTRA_ROOMS_MAP = i24_config.EXTRA_ROOMS_MAP
SERVICES_MAP = i24_config.SERVICES_MAP
AMENITIES_MAP = i24_config.AMENITIES_MAP
EXTERIORS_MAP = i24_config.EXTERIORS_MAP
EXTRAS_MAP = i24_config.EXTRAS_MAP
CONSERVATION_MAP = i24_config.CONSERVATION_MAP
ANTIQUITY_MAP = i24_config.ANTIQUITY_MAP

# Proxy policy: "proxy_preferred" = use proxy if available, but may work direct
PROXY_POLICY = "proxy_preferred"

MAX_PAGES_PER_SEARCH = 50
REQUEST_DELAY_MIN_MS = 2000
REQUEST_DELAY_MAX_MS = 5000
PAGE_LOAD_TIMEOUT_MS = 30000
