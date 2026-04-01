#!/usr/bin/env bash
set -euo pipefail

# Propyte — First-time setup
# Levanta Docker, corre migrations, seed portals

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "=== Propyte Setup ==="

# 1. Check .env exists
if [ ! -f .env ]; then
    echo "[setup] Copying .env.example → .env (edit with real values!)"
    cp .env.example .env
fi

# 2. Start Docker services
echo "[setup] Starting PostgreSQL + Redis..."
docker compose up -d postgres redis
echo "[setup] Waiting for services to be healthy..."
sleep 5

# Wait for postgres to be ready
until docker compose exec postgres pg_isready -U "${POSTGRES_USER:-propyte}" -d "${POSTGRES_DB:-propyte_data}" > /dev/null 2>&1; do
    echo "[setup] Waiting for PostgreSQL..."
    sleep 2
done
echo "[setup] PostgreSQL is ready."

# 3. Install Python dependencies
echo "[setup] Installing Python dependencies..."
cd src
pip install -e ".[dev]" --quiet

# 4. Install Playwright browsers
echo "[setup] Installing Playwright browsers..."
playwright install chromium

# 5. Run Alembic migrations
echo "[setup] Running database migrations..."
alembic upgrade head

# 6. Seed portals
echo "[setup] Seeding portals..."
python -m scripts.seed_portals

echo ""
echo "=== Setup complete ==="
echo "To run the Inmuebles24 scraper:"
echo "  cd src && python -m scrapers inmuebles24"
echo ""
echo "To run all active scrapers:"
echo "  cd src && python -m scrapers"
