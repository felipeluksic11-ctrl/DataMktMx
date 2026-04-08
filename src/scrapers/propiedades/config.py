"""Propiedades.com scraper configuration — URLs, selectors, search parameters.

Selectors last verified: 2026-03-31 against live site.
"""

# URL patterns
BASE_URL = "https://propiedades.com"
SEARCH_URL_TEMPLATE = BASE_URL + "/inmuebles-en-{operation}-en-{state}?pagina={page}"
# Sort by newest: add &ordenar=recientes
SORT_RECENT_PARAM = "ordenar=recientes"

# Operations in URL
OPERATIONS = {
    "venta": "venta",
    "renta": "renta",
}

# Portal status — set to False to disable without removing code
IS_ENABLED = True

# Phase 1: 8 priority states (high-volume markets)
PHASE1_STATES = [
    "ciudad-de-mexico",
    "estado-de-mexico",
    "jalisco",
    "queretaro",
    "quintana-roo",
    "yucatan",
    "nayarit",
    "baja-california-sur",
]

# All 32 Mexican states for crawl (slug format for URLs)
STATES = [
    "ciudad-de-mexico",
    "estado-de-mexico",
    "jalisco",
    "nuevo-leon",
    "puebla",
    "queretaro",
    "quintana-roo",
    "yucatan",
    "guanajuato",
    "baja-california-sur",
    "baja-california",
    "chihuahua",
    "coahuila",
    "sonora",
    "sinaloa",
    "veracruz",
    "guerrero",
    "oaxaca",
    "morelos",
    "aguascalientes",
    "san-luis-potosi",
    "michoacan",
    "tabasco",
    "tamaulipas",
    "hidalgo",
    "nayarit",
    "colima",
    "chiapas",
    "campeche",
    "durango",
    "tlaxcala",
    "zacatecas",
]

# ─────────────────────── CSS Selectors (verified 2026-03-31) ───────────────────────

SELECTORS = {
    # Search results page — listing cards
    "listing_card": ".pcom-property-card",

    # Card internals
    "card_link": "a[href*='inmuebles']",
    "card_latitude": "meta[itemprop='latitude']",
    "card_longitude": "meta[itemprop='longitude']",
    "card_type_badges": ".section-labels div",
    "card_price": ".pcom-property-card-body-main-info > div:nth-child(2)",
    "card_price_fallback": "[class*='bxbIOz']",
    "card_location_street": ".pcom-property-card-body-main-info-street",
    "card_location_spans": ".pcom-property-card-body-main-info-street span",
    "card_features": "li.amenities",
    "card_street_address": "[itemprop='streetAddress']",
    "card_locality": "[itemprop='addressLocality']",
    "card_region": "[itemprop='addressRegion']",
    "card_postal_code": "[itemprop='postalCode']",

    # Pagination — total count from H1
    "total_count_h1": "h1",

    # Detail page selectors
    "detail_title": "h1",
    "detail_subtitle": "h2",
    "detail_characteristics": ".characteristic",
    "detail_amenities": ".amenities",
    "detail_description": "[class*='description']",
    "detail_jsonld": "script[type='application/ld+json']",
}

# ─────────────────────── Listings per page ───────────────────────
LISTINGS_PER_PAGE = 47

# ─────────────────────── Characteristic parsing patterns ───────────────────────
# Characteristics on detail page: "BAÑOS 2", "ESTACIONAMIENTOS 2", "ÁREA TERRENO 250 m2", etc.

CHARACTERISTIC_PATTERNS = {
    "recámara": "bedrooms",
    "recamara": "bedrooms",
    "habitacion": "bedrooms",

    "medio baño": "half_bathrooms",
    "medios baños": "half_bathrooms",
    "½ baño": "half_bathrooms",

    "baño": "bathrooms",

    "estacionamiento": "parking_spaces",
    "cochera": "parking_spaces",

    "área terreno": "land_m2",
    "area terreno": "land_m2",
    "terreno": "land_m2",

    "área construida": "construction_m2",
    "area construida": "construction_m2",
    "construcción": "construction_m2",
    "construccion": "construction_m2",

    "nivel": "built_levels",
    "piso": "built_levels",

    "antigüedad": "antiquity",
    "antiguedad": "antiquity",
    "año": "construction_years",

    "id del inmueble": "internal_code",
}

# Amenity parsing from detail page items like "3 Recámaras", "2.5 Baños", "430 m2"
AMENITY_FEATURE_PATTERNS = {
    "recámara": "bedrooms",
    "recamara": "bedrooms",

    "medio baño": "half_bathrooms",

    "baño": "bathrooms",

    "m2": "area_m2",
    "m²": "area_m2",
}

# ─────────────────────── Feature parsing patterns (from card) ───────────────────────

FEATURE_PATTERNS = {
    "rec.": "bedrooms",
    "recámara": "bedrooms",
    "recamaras": "bedrooms",
    "dormitorio": "bedrooms",

    "medio baño": "half_bathrooms",
    "medios baños": "half_bathrooms",
    "½ baño": "half_bathrooms",

    "baño": "bathrooms",

    "estac.": "parking_spaces",
    "estacionamiento": "parking_spaces",
    "cochera": "parking_spaces",

    "m² lote": "land_m2",
    "m² tot": "land_m2",
    "m² terreno": "land_m2",
    "m2 terreno": "land_m2",

    "m² cub": "construction_m2",
    "m² const": "construction_m2",
    "m² construido": "construction_m2",
    "m2 const": "construction_m2",

    "nivel": "built_levels",
    "piso": "built_levels",
}

# Normalized values for property type detection
PROPERTY_TYPE_MAP = {
    "departamento": "departamento",
    "casa": "casa",
    "casa en condominio": "casa_condominio",
    "terreno": "terreno",
    "lote": "terreno",
    "oficina": "oficina",
    "local": "local_comercial",
    "local comercial": "local_comercial",
    "bodega": "bodega",
    "edificio": "edificio",
    "hotel": "hotel",
    "villa": "villa",
    "rancho": "rancho",
    "quinta": "quinta",
    "nave industrial": "nave_industrial",
    "penthouse": "departamento",
    "ph": "departamento",
    "consultorio": "consultorio",
    "suite": "departamento",
}

# Normalized values for extra rooms
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

# Normalized values for services
SERVICES_MAP = {
    "acceso a personas con discapacidad": "acceso_discapacidad",
    "aire acondicionado": "aire_acondicionado",
    "caseta de seguridad": "caseta_seguridad",
    "internet": "internet",
    "seguridad privada": "seguridad_privada",
    "seguridad": "seguridad_privada",
    "circuito cerrado": "seguridad_privada",
    "servicios básicos": "servicios_basicos",
    "servicios basicos": "servicios_basicos",
    "calefacción": "calefaccion",
    "calefaccion": "calefaccion",
}

# Normalized values for amenities
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
    "area de lavado": "area_lavado",
    "lavandería": "area_lavado",
    "gimnasio": "gimnasio",
    "gym": "gimnasio",
    "jacuzzi": "jacuzzi",
    "cancha de squash": "cancha_squash",
    "cancha de tenis": "cancha_tenis",
    "coworking": "coworking",
    "co-working": "coworking",
    "roof garden": "terraza",
}

EXTERIORS_MAP = {
    "asador": "asador",
    "jardín privado": "jardin_privado",
    "jardin privado": "jardin_privado",
    "jardín": "jardin_privado",
    "patio": "patio",
    "terraza": "terraza",
    "roof garden": "terraza",
}

EXTRAS_MAP = {
    "amueblado": "amueblado",
    "closet": "closet",
    "escuela cercana": "escuela_cercana",
    "escuelas cercanas": "escuela_cercana",
    "frente a parque": "frente_parque",
    "línea blanca": "linea_blanca",
    "linea blanca": "linea_blanca",
    "permite mascotas": "permite_mascotas",
    "pet friendly": "permite_mascotas",
    "chimenea": "chimenea",
    "dúplex": "duplex",
    "duplex": "duplex",
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
}

# Proxy policy: "direct" = use VPS IP (no proxy needed), "proxy_required" = must use proxy
# Propiedades.com works from any country IP — no geo-blocking
PROXY_POLICY = "direct"

# Scraping behavior
MAX_PAGES_PER_SEARCH = 200
REQUEST_DELAY_MIN_MS = 2000
REQUEST_DELAY_MAX_MS = 5000
PAGE_LOAD_TIMEOUT_MS = 30000
MAX_RETRIES = 3
