"""Inmuebles24 scraper configuration — URLs, selectors, search parameters.

Selectors last verified: 2026-03-30 against live site.
"""

# URL patterns
BASE_URL = "https://www.inmuebles24.com"
SEARCH_URL_TEMPLATE = BASE_URL + "/{property_type}-en-{operation}-en-{location}-pagina-{page}.html"
# Sort by newest: append this before -pagina-
SEARCH_URL_RECENT_TEMPLATE = BASE_URL + "/{property_type}-en-{operation}-en-{location}-ordenado-por-fechaonline-descendente-pagina-{page}.html"

# Property types in URL
PROPERTY_TYPES = {
    "departamento": "departamentos",
    "casa": "casas",
    "terreno": "terrenos",
    "oficina": "oficinas",
    "local": "locales-comerciales",
    "bodega": "bodegas",
    "edificio": "edificios",
    "hotel": "hoteles",
    "local_comercial": "locales-comerciales",
    "nave_industrial": "naves-industriales",
    "terreno_comercial": "terrenos-comerciales",
    "terreno_industrial": "terrenos-industriales",
    "villa": "villas",
    "rancho": "ranchos",
    "quinta": "quintas",
    "all": "inmuebles",
}

# Operations in URL
OPERATIONS = {
    "venta": "venta",
    "renta": "renta",
    "vacacional": "renta-vacacional",
}

# Mexican states for crawl (slug format for URLs)
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

# ─────────────────────── CSS Selectors (verified 2026-03-30) ───────────────────────
# Module-based classes from Inmuebles24's React frontend.
# The AI supervisor (Sonnet) auto-repairs these when they break.

SELECTORS = {
    # Search results page — listing cards
    "listing_card": "[data-posting-type]",
    "listing_card_property": "[data-posting-type='PROPERTY']",
    "listing_card_development": "[data-posting-type='DEVELOPMENT']",

    # Card data attributes
    "card_id_attr": "data-id",
    "card_url_attr": "data-to-posting",
    "card_type_attr": "data-posting-type",

    # Price (inside card)
    "price_container": "[class*='postingPrices-module__price-container']",
    "price_from": "[class*='postingPrices-module__price-from']",  # "Departamentos desde"

    # Features (inside card) — each span is a feature
    "features_span": "[class*='postingMainFeatures-module__posting-main-features-span']",

    # Location (inside card)
    "location_address": "[class*='postingLocations-module__location-address']",  # street/address
    "location_text": "[class*='postingLocations-module__location-text']",  # "Colonia, Delegación"

    # Pills (amenities/extras shown as tags)
    "pills": "[class*='postingCard-module__pill-item-feature'], [class*='pills-module__trigger-pill-item'] span",

    # Images count
    "gallery_images": "[class*='postingGallery-module'] img",

    # Pagination
    "next_page": "[data-qa='PAGING_NEXT']",
    "next_page_fallback": "a[class*='paging'][class*='next']",

    # Detail page selectors
    "detail_title": "h1[class*='title'], [data-qa='POSTING_TITLE'], h1",
    "detail_price": "[class*='price-value'], [data-qa='POSTING_PRICE']",
    "detail_expenses": "[class*='expenses'], [data-qa='POSTING_EXPENSES']",
    "detail_location": "[data-qa='POSTING_LOCATION'], [class*='location']",
    "detail_description": "#description-text, [class*='description-content']",
    "detail_features": "[class*='section-main-features'] li, [class*='features-list'] li",
    "detail_gallery": "[data-qa='POSTING_GALLERY'] img, [class*='gallery'] img",
    "detail_map": "[data-qa='POSTING_MAP'], [class*='static-map']",
    "detail_video": "iframe[src*='youtube'], iframe[src*='vimeo'], video source",
    "detail_tour": "iframe[src*='360'], iframe[src*='matterport']",
    "detail_code": "[data-qa='POSTING_CODE'], [class*='posting-code']",
    "detail_amenities": "[class*='amenities'] li, [class*='section-amenities'] li",
    "detail_services": "[class*='services'] li, [class*='section-services'] li",
    "detail_environments": "[class*='environments'] li, [class*='section-environments'] li",
    "detail_extra_features": "[class*='extras'] li, [class*='section-extras'] li",
}

# ─────────────────────── Feature parsing patterns ───────────────────────
# Features come as short strings like "3 rec.", "2 baños", "120 m² lote"

FEATURE_PATTERNS = {
    # pattern → field_name
    # Checked in order; first match wins
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

    "m² cub": "construction_m2",
    "m² const": "construction_m2",
    "m² construido": "construction_m2",

    # If it says just "m²" without qualifier and land_m2 already set, it's construction
    # Handled in parser logic

    "nivel": "built_levels",
    "piso": "built_levels",

    "un.": "units",  # development units, skip
}

# Normalized values for property type detection from URL
PROPERTY_TYPE_FROM_URL = {
    "departamento": "departamento",
    "casa": "casa",
    "casa-en-condominio": "casa_condominio",
    "terreno": "terreno",
    "lote": "terreno",
    "oficina": "oficina",
    "local": "local_comercial",
    "bodega": "bodega",
    "edificio": "edificio",
    "hotel": "hotel",
    "villa": "villa",
    "rancho": "rancho",
    "quinta": "quinta",
    "nave-industrial": "nave_industrial",
    "ph": "departamento",  # penthouse
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

# Scraping behavior
MAX_PAGES_PER_SEARCH = 50
REQUEST_DELAY_MIN_MS = 2000
REQUEST_DELAY_MAX_MS = 5000
PAGE_LOAD_TIMEOUT_MS = 30000
MAX_RETRIES = 3
