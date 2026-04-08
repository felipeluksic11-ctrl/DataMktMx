"""iCasas.mx scraper configuration.

iCasas is a real estate aggregator that uses infinite scroll.
Requires Playwright Chromium for JS rendering and scroll simulation.

URL pattern: /renta|venta/habitacionales-{type}-{state}-{city}-2_{type_code}_{state_code}_0_{city_code}_0
- type_code: 3=departamentos, 2=casas
- Prefix always 2 (both renta and venta)
"""

IS_ENABLED = True

BASE_URL = "https://www.icasas.mx"

PROXY_POLICY = "direct"

OPERATIONS = {
    "venta": "venta",
    "renta": "renta",
}

# URLs verified from icasas.mx homepage 2026-04-08
SEARCHES = [
    # ── Quintana Roo ──────────────────────────────────────
    # Cancún
    {"city": "Cancun", "state": "Quintana Roo", "type": "departamento", "operation": "renta",
     "url": "https://www.icasas.mx/renta/habitacionales-departamentos-quintana-roo-cancun-2_3_23_0_2473_0"},
    {"city": "Cancun", "state": "Quintana Roo", "type": "casa", "operation": "renta",
     "url": "https://www.icasas.mx/renta/habitacionales-casas-quintana-roo-cancun-2_2_23_0_2473_0"},
    {"city": "Cancun", "state": "Quintana Roo", "type": "departamento", "operation": "venta",
     "url": "https://www.icasas.mx/venta/habitacionales-departamentos-quintana-roo-cancun-2_3_23_0_2473_0"},
    {"city": "Cancun", "state": "Quintana Roo", "type": "casa", "operation": "venta",
     "url": "https://www.icasas.mx/venta/habitacionales-casas-quintana-roo-cancun-2_2_23_0_2473_0"},
    # Playa del Carmen
    {"city": "Playa del Carmen", "state": "Quintana Roo", "type": "departamento", "operation": "renta",
     "url": "https://www.icasas.mx/renta/habitacionales-departamentos-quintana-roo-playa-carmen-2_3_23_0_2499_0"},
    {"city": "Playa del Carmen", "state": "Quintana Roo", "type": "departamento", "operation": "venta",
     "url": "https://www.icasas.mx/venta/habitacionales-departamentos-quintana-roo-playa-carmen-2_3_23_0_2499_0"},
    {"city": "Playa del Carmen", "state": "Quintana Roo", "type": "casa", "operation": "renta",
     "url": "https://www.icasas.mx/renta/habitacionales-casas-quintana-roo-playa-carmen-2_2_23_0_2499_0"},
    {"city": "Playa del Carmen", "state": "Quintana Roo", "type": "casa", "operation": "venta",
     "url": "https://www.icasas.mx/venta/habitacionales-casas-quintana-roo-playa-carmen-2_2_23_0_2499_0"},
    # Tulum
    {"city": "Tulum", "state": "Quintana Roo", "type": "departamento", "operation": "renta",
     "url": "https://www.icasas.mx/renta/habitacionales-departamentos-quintana-roo-tulum-2_3_23_0_2491_0"},
    {"city": "Tulum", "state": "Quintana Roo", "type": "departamento", "operation": "venta",
     "url": "https://www.icasas.mx/venta/habitacionales-departamentos-quintana-roo-tulum-2_3_23_0_2491_0"},
    {"city": "Tulum", "state": "Quintana Roo", "type": "casa", "operation": "renta",
     "url": "https://www.icasas.mx/renta/habitacionales-casas-quintana-roo-tulum-2_2_23_0_2491_0"},
    {"city": "Tulum", "state": "Quintana Roo", "type": "casa", "operation": "venta",
     "url": "https://www.icasas.mx/venta/habitacionales-casas-quintana-roo-tulum-2_2_23_0_2491_0"},
    # Puerto Morelos
    {"city": "Puerto Morelos", "state": "Quintana Roo", "type": "departamento", "operation": "renta",
     "url": "https://www.icasas.mx/renta/habitacionales-departamentos-quintana-roo-puerto-morelos-2_3_23_0_2481_0"},
    {"city": "Puerto Morelos", "state": "Quintana Roo", "type": "departamento", "operation": "venta",
     "url": "https://www.icasas.mx/venta/habitacionales-departamentos-quintana-roo-puerto-morelos-2_3_23_0_2481_0"},

    # ── Yucatán ───────────────────────────────────────────
    {"city": "Merida", "state": "Yucatan", "type": "departamento", "operation": "renta",
     "url": "https://www.icasas.mx/renta/habitacionales-departamentos-yucatan-merida-2_3_31_0_2337_0"},
    {"city": "Merida", "state": "Yucatan", "type": "departamento", "operation": "venta",
     "url": "https://www.icasas.mx/venta/habitacionales-departamentos-yucatan-merida-2_3_31_0_2337_0"},
    {"city": "Merida", "state": "Yucatan", "type": "casa", "operation": "renta",
     "url": "https://www.icasas.mx/renta/habitacionales-casas-yucatan-merida-2_2_31_0_2337_0"},
    {"city": "Merida", "state": "Yucatan", "type": "casa", "operation": "venta",
     "url": "https://www.icasas.mx/venta/habitacionales-casas-yucatan-merida-2_2_31_0_2337_0"},

    # ── Jalisco ───────────────────────────────────────────
    {"city": "Guadalajara", "state": "Jalisco", "type": "departamento", "operation": "venta",
     "url": "https://www.icasas.mx/venta/habitacionales-departamentos-jalisco-guadalajara-2_3_14_0_568_0"},
    {"city": "Zapopan", "state": "Jalisco", "type": "departamento", "operation": "venta",
     "url": "https://www.icasas.mx/venta/habitacionales-departamentos-jalisco-zapopan-2_3_14_0_647_0"},

    # ── Querétaro ─────────────────────────────────────────
    {"city": "Queretaro", "state": "Queretaro", "type": "departamento", "operation": "venta",
     "url": "https://www.icasas.mx/venta/habitacionales-departamentos-queretaro-santiago-queretaro-2_3_22_0_2452_0"},

    # ── Nuevo León ────────────────────────────────────────
    {"city": "Monterrey", "state": "Nuevo Leon", "type": "departamento", "operation": "venta",
     "url": "https://www.icasas.mx/venta/habitacionales-departamentos-nuevo-leon-monterrey-2_3_19_0_983_0"},
]

PHASE1_STATES = ["quintana-roo", "yucatan", "jalisco", "queretaro", "nuevo-leon"]

MAX_SCROLLS = 80
SCROLL_DELAY_S = 1.5
PAGE_LOAD_TIMEOUT_MS = 20000
