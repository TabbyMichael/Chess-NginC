#!/usr/bin/env bash
# Restore a DB backup into a target database (REL-005/REL-014).
# Usage: ./scripts/restore-db.sh <backup.sql> [target_db]
# NEVER restore over production without a fresh backup first.
set -euo pipefail

cd "$(dirname "$0")/.."

BACKUP="${1:?usage: restore-db.sh <backup.sql> [target_db]}"
TARGET="${2:-${POSTGRES_DB:-chess_engine}_restore}"
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${POSTGRES_USER:-chess}"

test -f "${BACKUP}" || { echo "Backup not found: ${BACKUP}" >&2; exit 1; }

echo "Creating restore target ${TARGET} ..."
psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d postgres \
  -c "DROP DATABASE IF EXISTS \"${TARGET}\";" \
  -c "CREATE DATABASE \"${TARGET}\";"

echo "Restoring ${BACKUP} → ${TARGET} ..."
psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${TARGET}" -f "${BACKUP}" >/dev/null

echo "Row counts after restore:"
psql -h "${PGHOST}" -p "${PGPORT}" -U "${PGUSER}" -d "${TARGET}" -tAc \
  "select 'users=' || count(*) from users; select 'games=' || count(*) from games; select 'game_moves=' || count(*) from game_moves;" \
  2>/dev/null || echo "(table counts unavailable — schema may differ; inspect manually)"
echo "Restore complete: ${TARGET}"
