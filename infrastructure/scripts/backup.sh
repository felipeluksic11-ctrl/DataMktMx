#!/usr/bin/env bash
set -euo pipefail

# Propyte DB Backup to S3
# Usage: ./backup.sh

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/tmp/propyte-backups"
BACKUP_FILE="propyte_data_${TIMESTAMP}.sql.gz"

POSTGRES_USER="${POSTGRES_USER:-propyte}"
POSTGRES_DB="${POSTGRES_DB:-propyte_data}"
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
S3_BUCKET="${S3_BUCKET:?S3_BUCKET is required}"

mkdir -p "$BACKUP_DIR"

echo "[backup] Starting backup of ${POSTGRES_DB}..."

pg_dump \
  -h "$POSTGRES_HOST" \
  -p "$POSTGRES_PORT" \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  --no-owner \
  --no-privileges \
  --format=custom \
  | gzip > "${BACKUP_DIR}/${BACKUP_FILE}"

echo "[backup] Uploading to s3://${S3_BUCKET}/backups/${BACKUP_FILE}..."

aws s3 cp \
  "${BACKUP_DIR}/${BACKUP_FILE}" \
  "s3://${S3_BUCKET}/backups/${BACKUP_FILE}" \
  --storage-class STANDARD_IA

# Keep only last 7 local backups
ls -t "${BACKUP_DIR}"/propyte_data_*.sql.gz 2>/dev/null | tail -n +8 | xargs -r rm

echo "[backup] Done. Size: $(du -h "${BACKUP_DIR}/${BACKUP_FILE}" | cut -f1)"
