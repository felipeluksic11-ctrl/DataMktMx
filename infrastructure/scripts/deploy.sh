#!/usr/bin/env bash
set -euo pipefail

# Propyte — Deploy to VPS
# Usage: ./deploy.sh [user@host]
#
# Prerequisites:
#   - SSH access to VPS
#   - Docker + Docker Compose installed on VPS
#   - age key on VPS at ~/.config/sops/age/keys.txt
#   - SOPS installed on VPS

VPS_HOST="${1:?Usage: ./deploy.sh user@host}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
REMOTE_DIR="/opt/propyte"

echo "=== Deploying Propyte to ${VPS_HOST} ==="

# 1. Sync code to VPS (exclude secrets, .env, volumes)
echo "[deploy] Syncing code..."
rsync -avz --delete \
    --exclude '.git' \
    --exclude '.venv' \
    --exclude 'node_modules' \
    --exclude '.env' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude 'exports/' \
    --exclude 'secrets/*.yaml' \
    --exclude '!secrets/*.example.yaml' \
    --exclude '!secrets/.sops.yaml' \
    "${PROJECT_DIR}/" "${VPS_HOST}:${REMOTE_DIR}/"

# 2. Decrypt secrets on VPS and generate .env
echo "[deploy] Generating .env from encrypted secrets..."
ssh "${VPS_HOST}" bash -s << 'REMOTE_SCRIPT'
cd /opt/propyte

# Decrypt secrets
SECRETS=$(sops --decrypt secrets/production.yaml)

# Generate .env from decrypted YAML
cat > .env << ENV
POSTGRES_USER=$(echo "$SECRETS" | yq '.postgres.user')
POSTGRES_PASSWORD=$(echo "$SECRETS" | yq '.postgres.password')
POSTGRES_DB=$(echo "$SECRETS" | yq '.postgres.db')
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=$(echo "$SECRETS" | yq '.redis.password')
PROXY_DATAIMPLULSE_URL=$(echo "$SECRETS" | yq '.proxies.dataimplulse_url')
PROXY_BRIGHTDATA_URL=$(echo "$SECRETS" | yq '.proxies.brightdata_url')
AWS_ACCESS_KEY_ID=$(echo "$SECRETS" | yq '.aws.access_key_id')
AWS_SECRET_ACCESS_KEY=$(echo "$SECRETS" | yq '.aws.secret_access_key')
S3_BUCKET=$(echo "$SECRETS" | yq '.aws.s3_bucket')
S3_REGION=$(echo "$SECRETS" | yq '.aws.s3_region')
ANTHROPIC_API_KEY=$(echo "$SECRETS" | yq '.anthropic.api_key')
ENVIRONMENT=production
LOG_LEVEL=INFO
NUM_WORKERS=3
ENV

chmod 600 .env
echo "[remote] .env generated"
REMOTE_SCRIPT

# 3. Build and start services
echo "[deploy] Building and starting services..."
ssh "${VPS_HOST}" bash -s << 'REMOTE_SCRIPT'
cd /opt/propyte
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d

# Wait for DB
echo "[remote] Waiting for PostgreSQL..."
sleep 10

# Run migrations
docker compose -f docker-compose.prod.yml exec scraper-core \
    bash -c "cd /app && PYTHONPATH=. alembic upgrade head"

# Seed portals (idempotent)
docker compose -f docker-compose.prod.yml exec scraper-core \
    bash -c "cd /app && PYTHONPATH=. python -m scripts.seed_portals"

echo "[remote] Deploy complete"
docker compose -f docker-compose.prod.yml ps
REMOTE_SCRIPT

echo "=== Deploy finished ==="
