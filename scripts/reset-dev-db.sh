#!/usr/bin/env bash
# Rebuild the dev `chess` schema from migrations.
#
# Needed because tests/conftest.py runs against the dev database and calls
# Base.metadata.drop_all() after every test, which leaves alembic_version
# stamped at head while the domain tables are gone.
set -euo pipefail

cd "$(dirname "$0")/../apps/api"
source .venv/bin/activate

echo "Dropping all tables in chess..."
psql -U "${PGUSER:-tabbymichael}" -h "${PGHOST:-localhost}" -p "${PGPORT:-5432}" \
     -d chess -c 'DROP TABLE IF EXISTS game_moves, engine_runs, sessions, games, users, alembic_version CASCADE;' >/dev/null

echo "Re-applying migrations..."
alembic upgrade head

echo "Tables now present:"
psql -U "${PGUSER:-tabbymichael}" -h "${PGHOST:-localhost}" -p "${PGPORT:-5432}" \
     -d chess -tAc "select tablename from pg_tables where schemaname='public' order by tablename;"
