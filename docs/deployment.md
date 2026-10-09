# Deployment & Operations (Phase 9, REL-001..017)

> How to ship this project: production config, secrets, HTTPS, backups,
> migrations, health checks, logging, monitoring, Stockfish licensing, CORS,
> smoke tests, rollback, and release notes.

## 1. Production configuration (REL-001)

| Setting | Source | Production value |
|---------|--------|------------------|
| `APP_ENV` | env | `production` |
| `SECRET_KEY` | env/secret store | unique ≥32 random chars (app refuses to start without it, REL-002) |
| `DATABASE_URL` / `database_url` | env | managed Postgres DSN (psycopg URL) |
| `CORS_ORIGINS` | env | exact public origin(s), e.g. `https://chess.example.com` (REL-012) |
| `COOKIE_SECURE` | env | `true` (cookies only over HTTPS, REL-012) |
| `LOG_LEVEL` | env | `INFO` (or `WARNING`) |
| `STOCKFISH_PATH` | env | absolute path or empty (PATH lookup); never from clients |

Copy `.env.example` → `.env` for local dev only. **Never commit `.env`.**

## 2. Secret management (REL-002)

- Secrets live in the deployment platform's secret store (Compose `env_file`,
  Docker secrets, or cloud KMS) — never in git, images, or logs.
- Rotate `SECRET_KEY` by: set new value → rolling restart → all sessions
  re-login (opaque tokens; rotation safely invalidates old ones).
- DB passwords rotate at the database, then update the secret and restart.

## 3. HTTPS (REL-003)

TLS terminates at the reverse proxy / load balancer in front of `web` + `api`:

1. Provision a certificate (e.g. Let's Encrypt) for the public hostname.
2. Uncomment the `return 301 https://...` redirect in `apps/web/nginx.conf`.
3. Set `COOKIE_SECURE=true` and exact `CORS_ORIGINS` (no wildcards with cookies).
4. Verify: `curl -sI http://<host>` → `301`; `https://<host>` → `200`.

## 4. Backups & restoration (REL-004/REL-005)

- **Backup:** `./scripts/backup-db.sh` — timestamped `pg_dump` into `./backups/`,
  keeps the newest 14 (`BACKUP_KEEP`). Schedule nightly via cron/scheduler.
- **Restore:** `./scripts/restore-db.sh <backup.sql> [target_db]` — creates the
  target, loads the dump, prints row counts. **Backup before restoring live.**
- Verified this release: 16 kB dump → restore preserved 1 game + 2 moves (QA-025).

## 5. Migrations as a controlled deployment step (REL-006)

Migrations run **before** the new code serves traffic, as an explicit step:

- Compose: the `api` service command is `alembic upgrade head && uvicorn …`
  (`compose.yaml`), so a container never serves on a stale schema.
- The `api` image ships `alembic/` + `alembic.ini` (`apps/api/Dockerfile`).
- CI proves the model↔schema contract stays in lockstep: `alembic upgrade head`
  then `alembic check` (`.github/workflows/ci.yml`) — a model change with no
  migration fails the build.
- **Rollout rule:** expand/contract — add columns nullable, backfill, then
  enforce. Never drop/rename in the same release that needs the new code.
- **Rollback a migration:** `alembic downgrade -1` (each migration has a tested
  `downgrade`); for destructive changes, restore from the last backup instead.

## 6. Health checks (REL-007)

- `GET /api/v1/health` — liveness: returns `{"status":"ok"}` if the process is up.
- `GET /api/v1/ready` — readiness: `{"status":"ready"}` only if the DB answers
  `SELECT 1`; otherwise `{"status":"not-ready"}` (used by the load balancer to
  hold traffic until the DB is reachable).
- Compose `api.healthcheck` polls `/health`; `db` uses `pg_isready`. The `api`
  waits for `db: condition: service_healthy`.

## 7. Structured logs (REL-008)

- Single-line, timestamped records to **stdout** (`app/core/database.py`):
  `%(asctime)s %(levelname)s [%(name)s] %(message)s` — container/log-agent friendly.
- Level via `LOG_LEVEL` (`INFO` default). No secrets or session tokens are logged;
  auth errors return opaque messages (QA-019).

## 8. Monitoring & error reporting (REL-009)

- **Metrics to wire** (P2, pluggable): request rate/latency/error rate on the API,
  engine-move latency, and 5xx rate — exported via stdout and scraped by the host.
- **Alerting targets:** `/ready` failing (DB down), sustained 5xx, engine-move
  timeouts (503s), backup-job failures.
- **Error reporting:** FastAPI's default 500 handler logs the traceback server-side
  and returns a generic `{"detail":"Internal server error"}` to clients (no stack
  traces leak). Hook an APM (Sentry/OTel) at `app/main.py` if desired — out of
  scope for this repo but the seam exists.

## 9. Production dependency install (REL-010)

- `pip install .` builds a clean wheel from `pyproject.toml` (verified: builds
  `chess_engine_api-0.1.0-py3-none-any.whl`, 32 kB). Runtime deps are pinned with
  `>=` floors; the `dev` extra (pytest/ruff/mypy) is **not** installed in prod.
- Frontend: `npm ci` (lockfile-exact) → `npm run build` produces `dist/` served by
  nginx. Dependency vulnerabilities are scanned with `pip-audit` + `npm audit`
  (QA-018, both clean this release).

## 10. Stockfish deployment & licensing (REL-011)

- The Stockfish **binary is not distributed** with this repo — it is **GPL-3.0**,
  and bundling it would impose GPL on the whole service (`app/engine/stockfish.py`).
- The adapter finds the binary via `PATH` or an explicit `STOCKFISH_PATH`; if it is
  missing, engine moves fail cleanly (503/422) and the custom engine still runs.
- **Install at deploy time** from the distro or upstream, not from this repo:
  `apt-get install stockfish` (Ubuntu `stockfish 16`), or build from
  <https://github.com/official-stockfish/Stockfish>. Review GPL-3.0 obligations
  (source availability) before redistributing the binary in a product.

## 11. CORS & cookie settings (REL-012)

- `CORS_ORIGINS` is an explicit allowlist (comma-separated) — never `*` when
  credentials are allowed. `allow_credentials=True` is set in `app/main.py`.
- `COOKIE_SECURE=true` in production so the session cookie is sent only over HTTPS.
  Verified in the production smoke run (register → play → engine reply, cookies
  first-party under TLS).

## 12. Production smoke tests (REL-013)

- `./scripts/smoke-prod.sh` (point `API_BASE` at the deployed host) runs the full
  loop: `health` → `register` → `create game` → submit `e2e4` → engine replies
  (version 3). Exits non-zero on any unexpected status. Run it as the final gate
  after deploy/rollback.

## 13. Rollback procedures (REL-014)

- **App rollback:** redeploy the previous image tag; Compose `restart:
  unless-stopped` + the healthcheck gate the swap. Schema must be
  backward-compatible (expand/contract, §5) so old code runs on the new schema.
- **Data rollback:** take a fresh backup, then `./scripts/restore-db.sh <backup.sql>`
  into a scratch DB, verify row counts, and only then restore live.
- **Order:** app rollback first (fast, reversible); data restore only if the
  migration corrupted data. Always backup before any live restore.

## 14. Release notes & final status (REL-015..017)

- **Version:** API `0.1.0` (`pyproject.toml`, `apps/web/package.json`). Tag
  releases `v0.1.0` on `main` after all gates are green.
- **This release ships:** rules engine + custom AI (Phases 1/6), Postgres schema
  (Phase 2), auth/sessions (Phase 3), games API (Phase 4), React client (Phase 5),
  Stockfish adapter + benchmarks (Phase 7), QA sweep (Phase 8), and this deploy
  surface (Phase 9).
- **Final status:** see `PROJECT_CHECKLIST.md` Summary — all P0/P1 items complete;
  QA-026 release sign-off is recorded there. Deferred P2/P3 items (analysis UX,
  extra benchmark suites, APM) are listed, not blocking.

