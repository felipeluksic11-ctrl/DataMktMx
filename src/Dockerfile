FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System dependencies for Playwright + PostGIS + Camoufox (GTK3 for headless Firefox)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    libgeos-dev \
    libgtk-3-0 \
    libdbus-glib-1-2 \
    libasound2t64 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libxtst6 \
    libxshmfence1 \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies directly (avoid hatchling build backend issues)
RUN pip install --upgrade pip && pip install \
    "sqlalchemy[asyncio]>=2.0.30" \
    "asyncpg>=0.29.0" \
    "alembic>=1.13.0" \
    "geoalchemy2>=0.15.0" \
    "pydantic>=2.8.0" \
    "pydantic-settings>=2.3.0" \
    "structlog>=24.1.0" \
    "redis>=5.0.0" \
    "tenacity>=8.3.0" \
    "boto3>=1.34.0" \
    "httpx>=0.27.0" \
    "shapely>=2.0.0" \
    "playwright>=1.45.0" \
    "camoufox>=0.4.0" \
    "thefuzz[speedup]>=0.22.0" \
    "pandas>=2.2.0" \
    "anthropic>=0.30.0" \
    "dramatiq[redis]>=1.17.0"

# Install Playwright browsers
RUN playwright install chromium --with-deps

COPY . .

CMD ["python", "-m", "scrapers"]
