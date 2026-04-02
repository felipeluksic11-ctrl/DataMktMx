# Beta3.1 — Propyte Data Mining Infrastructure

## Project Overview
Central de mineria de datos inmobiliarios para Mexico. Recopila listings de 7 portales, los limpia, deduplica, y exporta agregados estadisticos a produccion via S3.

**Principio rector:** "El dato tiene valor; el metodo es invisible." Nunca revelar fuentes, URLs de origen, ni metadata de recopilacion.

## Architecture

```
VPS Hetzner (scraping) → S3 (intermediario) → Supabase (produccion)
```

### Components
- **src/scrapers/** — Python 3.12 + Crawlee + Playwright. Un sub-agente por portal.
- **src/etl/** — Pipeline de limpieza determinista (regex, no LLM). Normaliza, deduplica, valida.
- **src/supervisors/** — Claude Haiku (monitor) + Sonnet (auto-repair selectores).
- **api/** — NestJS backend para admin dashboard.
- **apps/admin/** — Next.js 15 + Tailwind + shadcn/ui. Dark mode. Control total.
- **infrastructure/** — Docker Compose, Dockerfiles, nginx, scripts de VPS/backup.

### Portals
Inmuebles24, Propiedades.com, EasyBroker, Segundamano, Lamudi, Vivanuncios, Facebook Marketplace (via Apify)

## Tech Stack

### Python (scrapers + ETL)
- Python 3.12, Crawlee, Playwright, Camoufox, httpx, Dramatiq, Redis
- SQLAlchemy + Alembic (migrations), thefuzz (dedup), Pandas
- anthropic SDK (supervisores IA via Batch API)

### TypeScript (admin dashboard + API)
- Next.js 15 + Tailwind CSS + shadcn/ui (dashboard)
- NestJS + Prisma (API backend)
- NextAuth.js (auth)

### Infrastructure
- PostgreSQL 16 + PostGIS + pgcrypto + pg_trgm
- Redis 7 (cola Dramatiq + cache)
- Docker Compose (all services)
- SOPS + age (secrets)
- Prometheus (metrics)

## Commands

```bash
# Development
docker compose up -d                    # Start all services
docker compose logs -f scraper-core     # Follow scraper logs
docker compose exec postgres psql -U propyte propyte_data  # DB shell

# Python
cd src && python -m pytest              # Run tests
cd src && ruff check .                  # Lint

# Admin dashboard
cd apps/admin && npm run dev            # Dev server
cd apps/admin && npm run build          # Build

# API
cd api && npm run start:dev             # Dev server
cd api && npm run test                  # Tests

# Infrastructure
./infrastructure/scripts/backup.sh      # Backup DB to S3
./infrastructure/scripts/restore.sh     # Restore from S3
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

## Proxy & Bandwidth Rules (CRITICAL)

Proxy traffic costs real money. Every scraper run MUST be bandwidth-conscious.

### Mandatory for ALL scraper runs
- **ALWAYS use `--budget` flag** when running scrapers manually or via cron. No exceptions.
  - Test runs: `--budget 30` (30 MB)
  - Incremental: `--budget 200` (200 MB)
  - Full scrape: `--budget 2000` (2 GB)
- **ALWAYS use `--no-detail`** unless detail pages are explicitly needed
- **ALWAYS use `--states` for testing** — never run a full 32-state test

### Resource blocking (automatic)
- Images, fonts, media, trackers are blocked in Playwright (see `shared/stealth/browser.py`)
- This reduces per-page transfer from ~2.5 MB to ~100-200 KB
- NEVER disable resource blocking
- NEVER download images through the proxy

### Budget enforcement
- `BandwidthTracker` (shared/proxy/bandwidth.py) counts real bytes per portal
- `BudgetExhausted` exception stops scraping gracefully when limit is reached
- Budget is set via `--budget` CLI flag or `PROXY_BUDGET_MB` env var (default 500 MB)

### DataImpulse proxy config
- Provider: DataImpulse residential proxy
- Country targeting MX adds x2 bandwidth coefficient (required — portals geo-block non-MX IPs)
- Country + sticky session injected via URL format: `username__cr.mx__sd-SESSION`
- Plan: 50 GB, with x2 = 25 GB effective
- NEVER run scrapers without checking remaining budget on DataImpulse dashboard first

### Before running ANY scraper on VPS
1. Check DataImpulse dashboard for remaining traffic
2. Check `docker ps -a | grep scraper` for running containers — kill orphans
3. Use `--budget` flag
4. Monitor bandwidth in logs: look for `bandwidth.summary` events

### Cron jobs (infrastructure/cron/propyte.cron)
- Daily incremental at 8am UTC with `--budget 200`
- Monthly full at 6am UTC with `--budget 2000`
- ALL cron entries MUST include `--budget` flag

## Data Flow
1. Scrapers → raw_listings (VPS PostgreSQL, never leaves VPS)
2. ETL cleans → clean_listings (still on VPS)
3. Exporter → S3 bucket (only aggregates + anonymized listings)
4. Production job → Supabase (serves website)
