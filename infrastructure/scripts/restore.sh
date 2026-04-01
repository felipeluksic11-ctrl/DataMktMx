#!/usr/bin/env bash
set -euo pipefail

# Propyte DB Restore from S3
# Usage: ./restore.sh [backup_filename]
# If no filename given, restores the latest backup.

BACKUP_DIR="/tmp/propyte-backups"

POSTGRES_USER="${POSTGRES_USER:-propyte}"
POSTGRES_DB="${POSTGRES_DB:-propyte_data}"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
S3_BUCKET="${S3_BUCKET:?S3_BUCKET is required}"

mkdir -p "$BACKUP_DIR"

if [ -n "${1:-}" ]; then
  BACKUP_FILE="$1"
else
  echo "[restore] Finding latest backup..."
  BACKUP_FILE=$(aws s3 ls "s3://${S3_BUCKET}/backups/" \
    | sort -r \
    | head -1 \
    | awk '{print $4}')

  if [ -z "$BACKUP_FILE" ]; then
    echo "[restore] ERROR: No backups found in s3://${S3_BUCKET}/backups/"
    exit 1
  fi
fi

echo "[restore] Downloading ${BACKUP_FILE}..."

aws s3 cp \
  "s3://${S3_BUCKET}/backups/${BACKUP_FILE}" \
  "${BACKUP_DIR}/${BACKUP_FILE}"

echo "[restore] Restoring to ${POSTGRES_DB}..."

gunzip -c "${BACKUP_DIR}/${BACKUP_FILE}" | pg_restore \
  -h "$POSTGRES_HOST" \
  -p "$POSTGRES_PORT" \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  --no-owner \
  --no-privileges \
  --clean \
  --if-exists

echo "[restore] Done."
