#!/bin/sh
set -eu

if [ -z "${PGPASSWORD:-}" ] && [ -n "${PGPASSWORD_FILE:-}" ]; then
  export PGPASSWORD="$(tr -d '\r' < "$PGPASSWORD_FILE")"
fi

POSTGRES_HOST="${POSTGRES_HOST:-postgres}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-interview}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
BACKUP_INTERVAL_SECONDS="${BACKUP_INTERVAL_SECONDS:-86400}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"

mkdir -p "$BACKUP_DIR"

echo "Starting PostgreSQL backup loop for ${POSTGRES_DB}..."

while true; do
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  backup_file="${BACKUP_DIR}/${POSTGRES_DB}-${timestamp}.dump"

  echo "Creating backup: ${backup_file}"
  pg_dump \
    --format=custom \
    --host="$POSTGRES_HOST" \
    --port="$POSTGRES_PORT" \
    --username="$POSTGRES_USER" \
    --dbname="$POSTGRES_DB" \
    --file="$backup_file"

  find "$BACKUP_DIR" -type f -name '*.dump' -mtime +"$BACKUP_RETENTION_DAYS" -delete

  sleep "$BACKUP_INTERVAL_SECONDS"
done
