#!/usr/bin/env bash
# Nightly/offline DB backup (REL-004). Writes a timestamped pg_dump to ./backups/.
# Usage: POSTGRES_USER=chess POSTGRES_DB=chess_engine ./scripts/backup-db.sh
set -euo pipefail

cd "$(dirname "$0")/.."

PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${POSTGRES_USER:-chess}"
PGDB="${POSTGRES_DB:-chess_engine}"
OUT_DIR="${BACKUP_DIR:-./backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_FILE="${OUT_DIR}/${PGDB}-${STAMP}.sql"

mkdir -p "${OUT_DIR}"
echo "Backing up ${PGDB} → ${OUT_FILE} ..."
pg_dump -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${PGDB}" -F p -f "${OUT_FILE}"
echo "Backup complete: ${OUT_FILE} ($(du -h "${OUT_FILE}" | cut -f1))"

# Keep only the newest 14 backups by default (REL-014 retention note).
KEEP="${BACKUP_KEEP:-14}"
ls -t "${OUT_DIR}/${PGDB}-"*.sql 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f
echo "Retention: keeping newest ${KEEP} backups."
