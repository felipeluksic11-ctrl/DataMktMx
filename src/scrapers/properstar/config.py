"""Properstar.com.mx scraper configuration — URLs, selectors, states.

Properstar is part of ListGlobally (Switzerland).
Uses a React SSR frontend behind Azure WAF (JS challenge).
Cards are server-rendered — parse HTML after WAF challenge completes.

Rate limiting is aggressive: 3-4 rapid page loads trigger "Service unavailable".
Use longer delays between requests.
"""

# URL patterns
BASE_URL = "https://www.properstar.com.mx"

# Search URL: /mexico/{state}/{operation}?p={page}
# e.g. https://www.properstar.com.mx/mexico/jalisco/comprar?p=2
# All property types (piso + casa + terreno + etc.)
SEARCH_URL_TEMPLATE = BASE_URL + "/mexico/{state}/{operation}"

# Operations (internal name -> URL slug)
OPERATIONS = {
    "venta": "comprar",
    "renta": "alquiler",
}

# Portal status — set to False to disable without removing code
IS_ENABLED = True

# Phase 1: 8 priority states (by listing volume on Properstar)
# Used as default when --states is not passed
PHASE1_STATES = [
    "quintana-roo",        # ~39,867
    "yucatan",             # ~19,408
    "ciudad-de-mexico",    # ~17,148
    "queretaro",           # ~12,221
    "estado-de-mexico",    # ~12,200
    "nuevo-leon",          # ~8,161
    "veracruz",            # ~7,202
    "jalisco",             # ~4,713
]

# All 25 indexed states on Properstar
# Note: some slugs have -l1 suffix to disambiguate from city names
STATES = [
    "quintana-roo",
    "yucatan",
    "ciudad-de-mexico",
    "queretaro",
    "estado-de-mexico",
    "nuevo-leon",
    "veracruz",
    "jalisco",
    "morelos",
    "puebla-l1",
    "guanajuato-l1",
    "tamaulipas",
    "chihuahua",
    "baja-california",
    "baja-california-sur",
    "sinaloa",
    "san-luis-potosi",
    "aguascalientes",
    "coahuila-de-zaragoza",
    "guerrero",
    "michoacan",
    "sonora",
    "oaxaca-l1",
    "durango-l1",
    "hidalgo",
]

# ─────────────────────── CSS Selectors ───────────────────────
# Properstar uses React SSR. Cards are <article> elements.
# Azure WAF JS challenge must complete before cards render.

SELECTORS = {
    # Search results
    "listing_card": "article.item-adaptive.card-full",
    "card_link": "a.listing-title",
    "price": ".listing-price-main span",
    "title": "a.listing-title",
    "location": ".item-location",
    "highlights": ".item-highlights",
    "card_images": ".image-gallery-picture img",
    "results_container": "div.results-list",

    # Pagination
    "pagination": "ul.search-pagination",
    "next_page": "ul.search-pagination li.page-link a",

    # ─── Detail page selectors ───
    "detail_title": "h1",
    "detail_price": ".listing-price-main span",
    "detail_location": ".item-location, [class*='location']",
    "detail_description": "[class*='description']",
    "detail_features": ".listing-feature, [class*='feature'] li",
    "detail_gallery": "[class*='gallery'] img, [class*='slider'] img",
    "detail_video": "iframe[src*='youtube'], iframe[src*='vimeo'], video source",
    "detail_tour": "iframe[src*='360'], iframe[src*='matterport']",
    "detail_amenities": "[class*='ameniti'] li",
}

# ─────────────────────── Property type mapping ───────────────────────
# From highlights text (first segment before bullet)
PROPERTY_TYPE_MAP = {
    "casa": "casa",
    "casa independiente": "casa",
    "casa con terraza": "casa",
    "villa": "villa",
    "bungalow": "casa",
    "granja": "rancho",
    "piso": "departamento",
    "apartamento": "departamento",
    "departamento": "departamento",
    "terreno": "terreno",
    "edificio": "edificio",
    "local": "local_comercial",
    "oficina": "oficina",
    "penthouse": "departamento",
    "loft": "departamento",
    "estudio": "departamento",
}

# From URL path
PROPERTY_TYPE_FROM_URL = {
    "casa": "casa",
    "piso": "departamento",
    "piso-casa": None,  # mixed — don't assign
    "terreno": "terreno",
    "edificio": "edificio",
    "local": "local_comercial",
    "oficina": "oficina",
}

# ─────────────────────── Feature parsing patterns ───────────────────────
FEATURE_PATTERNS = {
    "dormitorio": "bedrooms",
    "habitaci": "rooms",

    "medio baño": "half_bathrooms",
    "½ baño": "half_bathrooms",

    "baño": "bathrooms",

    "estacionamiento": "parking_spaces",
    "cochera": "parking_spaces",
    "garaje": "parking_spaces",

    "m² lote": "land_m2",
    "m² terreno": "land_m2",
    "terreno": "land_m2",

    "m² construido": "construction_m2",
    "m² const": "construction_m2",
    "superficie construida": "construction_m2",
    "superficie útil": "construction_m2",
}

# ─────────────────────── Normalization maps ───────────────────────
EXTRA_ROOMS_MAP = {
    "cocina integral": "cocina_integral",
    "cuarto de juegos": "cuarto_juegos",
    "cuarto de servicio": "cuarto_servicio",
    "cuarto de tv": "cuarto_tv",
    "estudio": "estudio",
    "oficina": "oficina",
    "sótano": "sotano",
    "sotano": "sotano",
    "ático": "atico",
    "atico": "atico",
}

SERVICES_MAP = {
    "acceso a personas con discapacidad": "acceso_discapacidad",
    "aire acondicionado": "aire_acondicionado",
    "caseta de seguridad": "caseta_seguridad",
    "internet": "internet",
    "seguridad privada": "seguridad_privada",
    "seguridad": "seguridad_privada",
    "seguridad 24 horas": "seguridad_privada",
    "circuito cerrado": "seguridad_privada",
    "servicios básicos": "servicios_basicos",
    "servicios basicos": "servicios_basicos",
    "calefacción": "calefaccion",
    "calefaccion": "calefaccion",
}

AMENITIES_MAP = {
    "alberca": "alberca",
    "piscina": "alberca",
    "área de eventos": "area_eventos",
    "area de eventos": "area_eventos",
    "salón de eventos": "area_eventos",
    "área de juegos infantiles": "area_juegos",
    "area de juegos": "area_juegos",
    "juegos infantiles": "area_juegos",
    "área de lavado": "area_lavado",
    "lavandería": "area_lavado",
    "gimnasio": "gimnasio",
    "gym": "gimnasio",
    "jacuzzi": "jacuzzi",
    "cancha de tenis": "cancha_tenis",
    "coworking": "coworking",
    "roof garden": "terraza",
    "spa": "spa",
}

EXTERIORS_MAP = {
    "asador": "asador",
    "jardín privado": "jardin_privado",
    "jardin privado": "jardin_privado",
    "jardín": "jardin_privado",
    "patio": "patio",
    "terraza": "terraza",
    "roof garden": "terraza",
    "balcón": "balcon",
    "balcon": "balcon",
}

EXTRAS_MAP = {
    "amueblado": "amueblado",
    "closet": "closet",
    "escuela cercana": "escuela_cercana",
    "frente a parque": "frente_parque",
    "línea blanca": "linea_blanca",
    "linea blanca": "linea_blanca",
    "permite mascotas": "permite_mascotas",
    "pet friendly": "permite_mascotas",
    "chimenea": "chimenea",
    "dúplex": "duplex",
    "duplex": "duplex",
    "vista al mar": "vista_mar",
    "vista a la montaña": "vista_montana",
}

CONSERVATION_MAP = {
    "excelente": "excelente",
    "bueno": "bueno",
    "regular": "regular",
    "malo": "malo",
    "remodelado": "remodelado",
    "para remodelar": "para_remodelar",
}

ANTIQUITY_MAP = {
    "preventa": "preventa",
    "pre-venta": "preventa",
    "en construcción": "en_construccion",
    "en construccion": "en_construccion",
    "a estrenar": "a_estrenar",
    "estrenar": "a_estrenar",
    "entrega inmediata": "a_estrenar",
    "nuevo": "a_estrenar",
    "new": "a_estrenar",
}

# Proxy policy: "direct" = use VPS IP (no proxy needed)
# Properstar works from any country IP — no geo-blocking detected
PROXY_POLICY = "direct"

# Scraping behavior
# Azure WAF is aggressive — use longer delays
MAX_PAGES_PER_SEARCH = 200
LISTINGS_PER_PAGE = 20
REQUEST_DELAY_MIN_MS = 3500
REQUEST_DELAY_MAX_MS = 7000
PAGE_LOAD_TIMEOUT_MS = 45000   # Longer timeout for Azure WAF challenge
CARD_WAIT_TIMEOUT_MS = 20000   # Wait for cards after WAF
MAX_RETRIES = 2
