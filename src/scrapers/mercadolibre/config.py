"""MercadoLibre scraper configuration.

Uses LD+JSON structured data from inmuebles.mercadolibre.com.mx.
Pure HTTP (no browser needed) — SSR with Schema.org RealEstateListing.
"""

IS_ENABLED = True

BASE_URL = "https://inmuebles.mercadolibre.com.mx"

PROXY_POLICY = "direct"

# Operations: MercadoLibre uses URL path segments
OPERATIONS = {
    "venta": "venta",
    "renta": "renta",
}

# States with URL slugs for search
PHASE1_STATES = [
    "ciudad-de-mexico",
    "estado-de-mexico",
    "jalisco",
    "queretaro",
    "quintana-roo",
    "yucatan",
    "nuevo-leon",
    "puebla",
]

# Property types in URL
PROPERTY_TYPES = ["departamentos", "casas"]

# Search URL template
SEARCH_URL_TEMPLATE = BASE_URL + "/{property_type}/{operation}/{state}/"

MAX_PAGES_PER_SEARCH = 10
LISTINGS_PER_PAGE = 48

REQUEST_DELAY_MIN_MS = 2000
REQUEST_DELAY_MAX_MS = 4000
