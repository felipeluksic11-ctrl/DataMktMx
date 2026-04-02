# Beta3.1 — DataMktMx Data Mining Infrastructure

## Project Overview

Central de mineria de datos inmobiliarios para Mexico. Recopila listings de portales, los limpia, deduplica, y exporta agregados estadisticos a produccion via S3.

**Principio rector:** "El dato tiene valor; el metodo es invisible." Nunca revelar fuentes, URLs de origen, ni metadata de recopilacion.

## Architecture

```
VPS Hetzner (scraping) → S3 (intermediario) → Supabase (produccion)
```

### Components

- **src/scrapers/** — Python 3.12 + Playwright + Camoufox. Un modulo por portal.
- **src/etl/** — Pipeline de limpieza determinista (regex, no LLM). Normaliza, deduplica, valida.
- **src/supervisors/** — Claude Haiku (monitor) + Sonnet (auto-repair selectores).
- **api/** — NestJS backend para admin dashboard.
- **apps/admin/** — Next.js 15 + Tailwind + shadcn/ui. Dark mode. Control total.
- **infrastructure/** — Docker Compose, Dockerfiles, nginx, scripts de VPS/backup.

### Portals

Inmuebles24, Propiedades.com, Lamudi, Vivanuncios, MercadoLibre, EasyBroker

## Tech Stack

### Python (scrapers + ETL)

- Python 3.12, Playwright, Camoufox, httpx
- SQLAlchemy + Alembic (migrations), thefuzz (dedup), Pandas
- anthropic SDK (supervisores IA via Batch API)

### TypeScript (admin dashboard + API)

- Next.js 15 + Tailwind CSS + shadcn/ui (dashboard)
- NestJS + Prisma (API backend)
- NextAuth.js (auth)

### Infrastructure

- PostgreSQL 16 + PostGIS + pgcrypto + pg_trgm
- Redis 7 (cache)
- Docker Compose (all services)
- SOPS + age (secrets)

## Commands

```bash
# Development
docker compose up -d                    # Start all services
docker compose logs -f scraper-core     # Follow scraper logs
docker compose exec postgres psql -U propyte propyte_data  # DB shell

# Python
cd src && python -m pytest              # Run tests
cd src && ruff check .                  # Lint

# Scrapers (VPS)
python -m scrapers inmuebles24 --no-detail --states ciudad-de-mexico --budget 30  # Test
python -m scrapers --mode incremental --no-detail --budget 200                    # Incremental
python -m scrapers --mode full --no-detail --budget 2000                          # Full
python -m scrapers inmuebles24 --enrich --budget 500                              # Detail enrichment

# Admin dashboard
cd apps/admin && npm run dev            # Dev server
cd apps/admin && npm run build          # Build

# API
cd api && npm run start:dev             # Dev server
cd api && npm run test                  # Tests
```

## Code Conventions

### Python

- Async-first (asyncio)
- Type hints everywhere
- One module per portal in src/scrapers/
- No LLM for data cleaning — deterministic regex/rules only
- Structured JSON logging

### TypeScript

- Strict mode enabled
- App Router (Next.js)
- Server components by default, client components only when needed
- shadcn/ui for all UI components

## Security Rules

- NEVER commit secrets (.env, API keys, credentials)
- NEVER export raw URLs, portal IDs, or scraping metadata to S3
- NEVER store personal data (agent names, phones, emails)
- All DB connections via SSL
- Pre-commit hooks: gitleaks blocks exposed secrets
- Secrets encrypted with SOPS + age

## Scraping Strategy (CRITICAL — read before touching scrapers)

El scraping opera en dos fases para optimizar bandwidth y cobertura.

### Fase 1: Cards-only (cobertura masiva, bajo costo)

Recorre paginas de busqueda y extrae datos de las cards sin visitar cada listing.

- **Captura:** precio, ubicacion (estado/municipio/colonia), recamaras (~68%), banos (~72%), m2 (~64%), tipo, estacionamientos
- **Costo:** ~64 KB por pagina, ~30-47 listings por pagina
- **Flag:** `--no-detail` (OBLIGATORIO en cron y tests)
- **Frecuencia:** diario incremental + mensual full

### Fase 2: Detail enrichment (selectivo, solo listings incompletos)

Visita la pagina de detalle SOLO de listings que les falten campos clave.

- **Captura adicional:** coordenadas lat/lng, m2 construccion, antiguedad, descripcion completa, amenidades, servicios, exteriores, extras, cuartos extra, balcon/elevador/bodega, conservacion, cuota mantenimiento, video/tour URLs, codigo interno
- **Costo:** ~200 KB por detail page
- **Flag:** `--enrich` (solo visita listings con campos vacios)
- **Frecuencia:** semanal, con budget controlado
- **Criterio de seleccion:** listings donde construction_m2 IS NULL OR latitude IS NULL OR description IS NULL

### Regla de oro

**NUNCA correr detail para todos los listings.** Solo enriquecer los que tienen campos vacios. Un full scrape con detail de 60K listings cuesta ~12 GB de proxy. Un enrichment selectivo de 20K listings incompletos cuesta ~4 GB.

### Campos por fuente (referencia)

| Campo | Card | Detail |
|-------|------|--------|
| precio, ubicacion, tipo | si | si |
| recamaras, banos, estac. | parcial | completo |
| m2 construccion, terreno | parcial | completo |
| coordenadas lat/lng | no | si (JSON-LD / map) |
| descripcion completa | no | si |
| antiguedad / anos | parcial | completo |
| amenidades, servicios | pills (parcial) | completo (seccion general features) |
| exteriores, extras | pills (parcial) | completo |
| cuartos extra, bodega, balcon | no | si |
| conservacion | no | si |
| cuota mantenimiento | no | si |
| video / tour 360 | no | si (URL only) |

## Proxy & Bandwidth Rules (CRITICAL)

Proxy traffic costs real money ($1/GB). Every scraper run MUST be bandwidth-conscious.

### Mandatory for ALL scraper runs

- **ALWAYS use `--budget` flag.** No exceptions, no default sin limite.
  - Test runs: `--budget 30` (30 MB)
  - Incremental: `--budget 200` (200 MB)
  - Full scrape cards-only: `--budget 2000` (2 GB)
  - Detail enrichment: `--budget 500` (500 MB)
- **ALWAYS use `--no-detail`** para scrapes normales. Detail solo via `--enrich`.
- **ALWAYS use `--states` para testing** — nunca correr 32 estados para probar.

### Resource blocking (automatico en shared/stealth/browser.py)

- Bloqueado: imagenes, fonts, media, stylesheets, trackers (google-analytics, facebook, hotjar, etc.)
- NUNCA desactivar resource blocking.
- NUNCA descargar imagenes a traves del proxy.

### Budget enforcement (automatico en shared/proxy/bandwidth.py)

- `BandwidthTracker` cuenta bytes reales por portal en tiempo real
- `BudgetExhausted` detiene el scraping gracefully al alcanzar el limite
- Logs: buscar `bandwidth.summary` y `bandwidth.warning` events
- El scraper guarda todo lo recopilado antes de detenerse (no pierde datos)

### DataImpulse proxy config

- Provider: DataImpulse residential proxy, plan 50 GB ($50)
- **SIN country targeting** — no hay coeficiente x2. 1 GB usado = 1 GB del plan.
- El panel de DataImpulse debe estar en "Segmentacion predeterminada" sin pais seleccionado
- El codigo NO inyecta `__cr.mx` en la URL (ProxyManager.country = "")
- Propiedades.com y Lamudi funcionan con IPs de cualquier pais
- Inmuebles24 requiere IPs mexicanas (geo-bloquea) — resolver en branch `scraper/inmuebles24-cloudflare`
- Sticky sessions via URL: `username__sd-SESSION` (sin __cr)
- Session rotation: cada 3-7 paginas (configurable por portal)

### Before running ANY scraper

1. Verificar trafico restante en DataImpulse dashboard
2. `docker ps -a | grep scraper` — matar containers huerfanos
3. Incluir `--budget` flag
4. Monitorear `bandwidth.summary` en logs

### Cron jobs (infrastructure/cron/propyte.cron)

- Diario incremental: 8am UTC, `--budget 200 --no-detail`
- Mensual full: 1ro del mes 6am UTC, `--budget 2000 --no-detail`
- Semanal enrichment: miercoles 9am UTC, `--enrich --budget 500`
- **TODOS los cron entries DEBEN incluir `--budget`**

### Estimaciones de consumo (medido, sin x2)

Dato clave medido: **~4.34 MB por pagina de busqueda** (con resource blocking).
Esto incluye HTML + JS. No baja a menos sin romper funcionalidad.

| Operacion | GB plan | Listings estimados |
|-----------|---------|-------------------|
| 1 pagina cards-only | 0.004 GB | 30-47 |
| Incremental diario (20 paginas × 4 portales) | ~0.35 GB | ~500 nuevos |
| Full cards-only Propiedades (850 paginas) | ~3.6 GB | ~40K |
| Full cards-only otros portales (1,332 paginas) | ~5.7 GB | ~40K |
| Enrichment 10K details | ~2 GB | 10K enriquecidos |
| **Total mensual estimado** | **~20 GB** | — |
| **Plan disponible** | **50 GB** | — |
| **Margen** | **~30 GB** | — |

## Data Flow

1. Scrapers (Fase 1: cards) → raw_listings (VPS PostgreSQL, never leaves VPS)
2. Scrapers (Fase 2: enrich) → raw_listings actualizado con campos de detail
3. ETL cleans → clean_listings (still on VPS)
4. Exporter → S3 bucket (only aggregates + anonymized listings)
5. Production job → Supabase (serves website)
