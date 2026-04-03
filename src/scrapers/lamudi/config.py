"""Lamudi.com.mx scraper configuration — URLs, selectors, states.

Lamudi is part of EMPG (Emerging Markets Property Group).
Uses a React/Next.js frontend with BEM-style CSS classes.

Selectors need verification: run _scout_lamudi.py to confirm against live site.
"""

# URL patterns
BASE_URL = "https://www.lamudi.com.mx"

# Search URL: /{state}/for-{operation}/?page={page}
# e.g. https://www.lamudi.com.mx/ciudad-de-mexico/for-rent/?page=2
# National: https://www.lamudi.com.mx/for-rent/?page=1
SEARCH_URL_TEMPLATE = BASE_URL + "/{location}/for-{operation}/"
# Sort by newest: append ?sort=newest&page=N
SORT_RECENT_PARAM = "sort=newest"

# Operations
OPERATIONS = {
    "venta": "sale",
    "renta": "rent",
}

# Mexican states — Lamudi uses lowercase-hyphenated slugs in URL path
STATES = [
    "distrito-federal",  # CDMX
    "mexico",  # Estado de México
    "jalisco",
    "nuevo-leon",
    "puebla",
    "queretaro-arteaga",  # Querétaro
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

# ─────────────────────── CSS Selectors ───────────────────────
# Lamudi uses a React frontend. Cards are typically <div> with
# listing-related class names. Run the scout to verify these.
# The AI supervisor (Sonnet) auto-repairs these when they break.

SELECTORS = {
    # Search results — verified 2026-03-31
    # Cards are .snippet.js-snippet divs inside .listings__cards
    "listing_card": ".snippet.js-snippet",
    "listing_card_fallback": ".listings__cards > div",

    # Card link
    "card_link": "a[href*='/detalle/']",

    # Price
    "price": ".snippet__content__price",

    # Features (inside card)
    "feature_area": ".property__number.area",
    "feature_parking": ".property__number.car_park",
    "feature_bathrooms": ".property__number.bathrooms",
    "feature_bedrooms": ".property__number.bedrooms",

    # Location
    "location": ".snippet__content__location",

    # Description
    "card_description": ".snippet__content__description",

    # Title
    "card_title": ".snippet__content__title, h2",

    # Images
    "card_images": "img[src*='lamudi'], img[data-src], picture img",

    # Pagination — page param in URL
    "next_page": "a[rel='next'], [class*='pagination'] a",

    # ─── Detail page selectors ───
    "detail_title": "h1",
    "detail_price": "[class*='price']",
    "detail_maintenance": "[class*='maintenance'], [class*='expensa']",
    "detail_location": "[class*='location'], [itemprop='address']",
    "detail_description": "[class*='description'], [itemprop='description']",
    "detail_features": "[class*='feature'] li, [class*='detail'] li, [class*='attribute'] li",
    "detail_gallery": "[class*='gallery'] img, [class*='slider'] img",
    "detail_map": "[class*='map'], [id*='map']",
    "detail_video": "iframe[src*='youtube'], iframe[src*='vimeo'], video source",
    "detail_tour": "iframe[src*='360'], iframe[src*='matterport']",
    "detail_amenities": "[class*='ameniti'] li, [class*='wl-amenities'] li",
    "detail_internal_code": "[class*='code'], [class*='listing-id']",
    "detail_breadcrumb": "[class*='breadcrumb']",
}

# ─────────────────────── Feature parsing patterns ───────────────────────
# Features come as short strings like "3 Recámaras", "2 Baños", "120 m²"

FEATURE_PATTERNS = {
    # pattern → field_name (checked in order; first match wins)
    "rec.": "bedrooms",
    "recámara": "bedrooms",
    "recamara": "bedrooms",
    "dormitorio": "bedrooms",
    "habitaci": "bedrooms",

    "medio baño": "half_bathrooms",
    "medios baños": "half_bathrooms",
    "½ baño": "half_bathrooms",

    "baño": "bathrooms",

    "estac.": "parking_spaces",
    "estacionamiento": "parking_spaces",
    "cochera": "parking_spaces",
    "parking": "parking_spaces",
    "garage": "parking_spaces",

    "m² lote": "land_m2",
    "m² tot": "land_m2",
    "m² terreno": "land_m2",
    "terreno": "land_m2",

    "m² cub": "construction_m2",
    "m² const": "construction_m2",
    "m² construido": "construction_m2",
    "superficie construida": "construction_m2",
    "área construida": "construction_m2",

    "nivel": "built_levels",
    "piso": "built_levels",
    "pisos": "built_levels",
}

# Normalized values for property type detection from URL or breadcrumb
PROPERTY_TYPE_FROM_URL = {
    "departamento": "departamento",
    "apartment": "departamento",
    "casa": "casa",
    "house": "casa",
    "casa-en-condominio": "casa_condominio",
    "terreno": "terreno",
    "land": "terreno",
    "lote": "terreno",
    "oficina": "oficina",
    "office": "oficina",
    "local": "local_comercial",
    "commercial": "local_comercial",
    "bodega": "bodega",
    "warehouse": "bodega",
    "edificio": "edificio",
    "building": "edificio",
    "hotel": "hotel",
    "villa": "villa",
    "rancho": "rancho",
    "ph": "departamento",
    "penthouse": "departamento",
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
    "seguridad 24 horas": "seguridad_privada",
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
    "salon de eventos": "area_eventos",
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
    "balcón": "balcon",
    "balcon": "balcon",
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
    "nuevo": "a_estrenar",
    "new": "a_estrenar",
}

# Proxy policy: "direct" = use VPS IP (no proxy needed), "proxy_required" = must use proxy
# Lamudi works from any country IP — no geo-blocking
PROXY_POLICY = "direct"

# Scraping behavior
MAX_PAGES_PER_SEARCH = 50
LISTINGS_PER_PAGE = 30
REQUEST_DELAY_MIN_MS = 2500
REQUEST_DELAY_MAX_MS = 6000
PAGE_LOAD_TIMEOUT_MS = 30000
MAX_RETRIES = 3
