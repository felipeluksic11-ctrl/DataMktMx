"""Official catalogs for normalizing Mexican real estate data.

Sources:
- INEGI catalog of Mexican states (32 entidades federativas)
- INEGI catalog of municipalities (alcaldías for CDMX)
- Common aliases and misspellings from portals

These are deterministic lookups — no fuzzy matching needed for states.
"""

# ──────────────────────────── States ────────────────────────────
# Official INEGI codes + name + common aliases from portals

STATES: dict[str, dict] = {
    "AGU": {"name": "Aguascalientes", "code": "AGU", "inegi": "01"},
    "BCN": {"name": "Baja California", "code": "BCN", "inegi": "02"},
    "BCS": {"name": "Baja California Sur", "code": "BCS", "inegi": "03"},
    "CAM": {"name": "Campeche", "code": "CAM", "inegi": "04"},
    "CHP": {"name": "Chiapas", "code": "CHP", "inegi": "07"},
    "CHH": {"name": "Chihuahua", "code": "CHH", "inegi": "08"},
    "COA": {"name": "Coahuila de Zaragoza", "code": "COA", "inegi": "05"},
    "COL": {"name": "Colima", "code": "COL", "inegi": "06"},
    "CMX": {"name": "Ciudad de México", "code": "CMX", "inegi": "09"},
    "DUR": {"name": "Durango", "code": "DUR", "inegi": "10"},
    "GUA": {"name": "Guanajuato", "code": "GUA", "inegi": "11"},
    "GRO": {"name": "Guerrero", "code": "GRO", "inegi": "12"},
    "HID": {"name": "Hidalgo", "code": "HID", "inegi": "13"},
    "JAL": {"name": "Jalisco", "code": "JAL", "inegi": "14"},
    "MEX": {"name": "Estado de México", "code": "MEX", "inegi": "15"},
    "MIC": {"name": "Michoacán de Ocampo", "code": "MIC", "inegi": "16"},
    "MOR": {"name": "Morelos", "code": "MOR", "inegi": "17"},
    "NAY": {"name": "Nayarit", "code": "NAY", "inegi": "18"},
    "NLE": {"name": "Nuevo León", "code": "NLE", "inegi": "19"},
    "OAX": {"name": "Oaxaca", "code": "OAX", "inegi": "20"},
    "PUE": {"name": "Puebla", "code": "PUE", "inegi": "21"},
    "QUE": {"name": "Querétaro", "code": "QUE", "inegi": "22"},
    "ROO": {"name": "Quintana Roo", "code": "ROO", "inegi": "23"},
    "SLP": {"name": "San Luis Potosí", "code": "SLP", "inegi": "24"},
    "SIN": {"name": "Sinaloa", "code": "SIN", "inegi": "25"},
    "SON": {"name": "Sonora", "code": "SON", "inegi": "26"},
    "TAB": {"name": "Tabasco", "code": "TAB", "inegi": "27"},
    "TAM": {"name": "Tamaulipas", "code": "TAM", "inegi": "28"},
    "TLA": {"name": "Tlaxcala", "code": "TLA", "inegi": "29"},
    "VER": {"name": "Veracruz de Ignacio de la Llave", "code": "VER", "inegi": "30"},
    "YUC": {"name": "Yucatán", "code": "YUC", "inegi": "31"},
    "ZAC": {"name": "Zacatecas", "code": "ZAC", "inegi": "32"},
}

# Lookup: alias → state code. Lowercase, no accents.
STATE_ALIASES: dict[str, str] = {
    # Official names (lowercase, no accents)
    "aguascalientes": "AGU",
    "baja california": "BCN",
    "baja california sur": "BCS",
    "campeche": "CAM",
    "chiapas": "CHP",
    "chihuahua": "CHH",
    "coahuila": "COA",
    "coahuila de zaragoza": "COA",
    "colima": "COL",
    "ciudad de mexico": "CMX",
    "durango": "DUR",
    "guanajuato": "GUA",
    "guerrero": "GRO",
    "hidalgo": "HID",
    "jalisco": "JAL",
    "estado de mexico": "MEX",
    "mexico": "MEX",
    "michoacan": "MIC",
    "michoacan de ocampo": "MIC",
    "morelos": "MOR",
    "nayarit": "NAY",
    "nuevo leon": "NLE",
    "oaxaca": "OAX",
    "puebla": "PUE",
    "queretaro": "QUE",
    "quintana roo": "ROO",
    "san luis potosi": "SLP",
    "sinaloa": "SIN",
    "sonora": "SON",
    "tabasco": "TAB",
    "tamaulipas": "TAM",
    "tlaxcala": "TLA",
    "veracruz": "VER",
    "veracruz de ignacio de la llave": "VER",
    "yucatan": "YUC",
    "zacatecas": "ZAC",
    # Portal-specific aliases
    "cdmx": "CMX",
    "df": "CMX",
    "distrito federal": "CMX",
    "df / cdmx": "CMX",
    "ciudad de mexico / cdmx": "CMX",
    "edo. de mexico": "MEX",
    "edo de mexico": "MEX",
    "edomex": "MEX",
    "bc": "BCN",
    "b.c.": "BCN",
    "bcs": "BCS",
    "b.c.s.": "BCS",
    "n.l.": "NLE",
    "nl": "NLE",
    "qro": "QUE",
    "q. roo": "ROO",
    "slp": "SLP",
    "s.l.p.": "SLP",
}

# CDMX alcaldías (delegaciones) — the 16 municipalities within CDMX
CDMX_ALCALDIAS = [
    "Álvaro Obregón",
    "Azcapotzalco",
    "Benito Juárez",
    "Coyoacán",
    "Cuajimalpa de Morelos",
    "Cuauhtémoc",
    "Gustavo A. Madero",
    "Iztacalco",
    "Iztapalapa",
    "La Magdalena Contreras",
    "Miguel Hidalgo",
    "Milpa Alta",
    "Tláhuac",
    "Tlalpan",
    "Venustiano Carranza",
    "Xochimilco",
]

# Lowercase lookup for alcaldías
CDMX_ALCALDIAS_LOWER = {a.lower(): a for a in CDMX_ALCALDIAS}

# ──────────────────────────── Property Types ────────────────────────────

PROPERTY_TYPES: dict[str, str] = {
    # normalized_key → display_name
    "departamento": "Departamento",
    "casa": "Casa",
    "casa_condominio": "Casa en Condominio",
    "terreno": "Terreno",
    "oficina": "Oficina",
    "local_comercial": "Local Comercial",
    "bodega": "Bodega",
    "edificio": "Edificio",
    "hotel": "Hotel",
    "villa": "Villa",
    "rancho": "Rancho",
    "quinta": "Quinta",
    "nave_industrial": "Nave Industrial",
    "terreno_comercial": "Terreno Comercial",
    "terreno_industrial": "Terreno Industrial",
    "local_centro_comercial": "Local en Centro Comercial",
}

# Aliases for property types from different portals
PROPERTY_TYPE_ALIASES: dict[str, str] = {
    "depto": "departamento",
    "depa": "departamento",
    "penthouse": "departamento",
    "ph": "departamento",
    "loft": "departamento",
    "suite": "departamento",
    "casa en condominio": "casa_condominio",
    "casa condominio": "casa_condominio",
    "townhouse": "casa",
    "lote": "terreno",
    "terreno / lote": "terreno",
    "local": "local_comercial",
    "comercial": "local_comercial",
    "nave": "nave_industrial",
    "industrial": "nave_industrial",
    "consultorio": "oficina",
}

# ──────────────────────────── Operations ────────────────────────────

OPERATIONS: dict[str, str] = {
    "venta": "Venta",
    "renta": "Renta",
    "vacacional": "Vacacional",
    # Aliases
    "sale": "Venta",
    "rent": "Renta",
    "rental": "Renta",
    "buy": "Venta",
    "compra": "Venta",
    "alquiler": "Renta",
}
