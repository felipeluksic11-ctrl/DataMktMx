"""iCasas.mx scraper configuration.

iCasas is a real estate aggregator that uses infinite scroll.
Requires Playwright Chromium for JS rendering and scroll simulation.
"""

IS_ENABLED = True

BASE_URL = "https://www.icasas.mx"

PROXY_POLICY = "direct"

OPERATIONS = {
    "venta": "venta",
    "renta": "renta",
}

# Pre-defined search URLs by city, state, type, operation
# iCasas URL pattern: /renta/habitacionales-{type}-{state}-{city}-{codes}
SEARCHES = [
    # QRoo — departamentos renta
    {"city": "Cancun", "state": "Quintana Roo", "type": "departamento", "operation": "renta",
     "url": "https://www.icasas.mx/renta/habitacionales-departamentos-quintana-roo-cancun-2_3_23_0_2473_0"},
    {"city": "Playa del Carmen", "state": "Quintana Roo", "type": "departamento", "operation": "renta",
     "url": "https://www.icasas.mx/renta/habitacionales-departamentos-quintana-roo-solidaridad-2_3_23_0_1090_0"},
    {"city": "Tulum", "state": "Quintana Roo", "type": "departamento", "operation": "renta",
     "url": "https://www.icasas.mx/renta/habitacionales-departamentos-quintana-roo-tulum-2_3_23_0_2489_0"},
    {"city": "Puerto Morelos", "state": "Quintana Roo", "type": "departamento", "operation": "renta",
     "url": "https://www.icasas.mx/renta/habitacionales-departamentos-quintana-roo-puerto-morelos-2_3_23_0_2481_0"},
    # QRoo — casas renta
    {"city": "Cancun", "state": "Quintana Roo", "type": "casa", "operation": "renta",
     "url": "https://www.icasas.mx/renta/habitacionales-casas-quintana-roo-cancun-2_2_23_0_2473_0"},
    {"city": "Playa del Carmen", "state": "Quintana Roo", "type": "casa", "operation": "renta",
     "url": "https://www.icasas.mx/renta/habitacionales-casas-quintana-roo-solidaridad-2_2_23_0_1090_0"},
    {"city": "Tulum", "state": "Quintana Roo", "type": "casa", "operation": "renta",
     "url": "https://www.icasas.mx/renta/habitacionales-casas-quintana-roo-tulum-2_2_23_0_2489_0"},
    # Yucatan
    {"city": "Merida", "state": "Yucatan", "type": "departamento", "operation": "renta",
     "url": "https://www.icasas.mx/renta/habitacionales-departamentos-yucatan-merida-2_3_31_0_2337_0"},
    {"city": "Merida", "state": "Yucatan", "type": "casa", "operation": "renta",
     "url": "https://www.icasas.mx/renta/habitacionales-casas-yucatan-merida-2_2_31_0_2337_0"},
    # QRoo — venta
    {"city": "Cancun", "state": "Quintana Roo", "type": "departamento", "operation": "venta",
     "url": "https://www.icasas.mx/venta/habitacionales-departamentos-quintana-roo-cancun-1_3_23_0_2473_0"},
    {"city": "Playa del Carmen", "state": "Quintana Roo", "type": "departamento", "operation": "venta",
     "url": "https://www.icasas.mx/venta/habitacionales-departamentos-quintana-roo-solidaridad-1_3_23_0_1090_0"},
    {"city": "Tulum", "state": "Quintana Roo", "type": "departamento", "operation": "venta",
     "url": "https://www.icasas.mx/venta/habitacionales-departamentos-quintana-roo-tulum-1_3_23_0_2489_0"},
    {"city": "Merida", "state": "Yucatan", "type": "departamento", "operation": "venta",
     "url": "https://www.icasas.mx/venta/habitacionales-departamentos-yucatan-merida-1_3_31_0_2337_0"},
    {"city": "Merida", "state": "Yucatan", "type": "casa", "operation": "venta",
     "url": "https://www.icasas.mx/venta/habitacionales-casas-yucatan-merida-1_2_31_0_2337_0"},
]

PHASE1_STATES = ["quintana-roo", "yucatan"]

MAX_SCROLLS = 80
SCROLL_DELAY_S = 1.5
PAGE_LOAD_TIMEOUT_MS = 20000
