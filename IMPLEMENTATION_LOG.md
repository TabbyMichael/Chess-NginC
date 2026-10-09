# Implementation Log

> Running record of work sessions: task attempted, files changed, tests executed, results, defects, decisions, remaining work, next task.

---

## Session 2026-10-09 — Foundation & planning

**Task.** Inspect the empty repository and establish the planning/tracking foundation (plan, checklist, loops, agents, docs).

**Environment (LOOP A).**
- Directory: `Chess NginC` — empty, not a Git repo.
- Python 3.14.2, Node v25.2.1, npm 11.7.0, psql 14.19 (client), Docker **not installed**, pnpm **not installed**.
- Disk critically full: 99% capacity, ~3.2 GiB free (transient ENOSPC observed, recovered).

**Files created.**
- `PROJECT_CHECKLIST.md` (FND-008) — all 219 requirement IDs across Phases 0–9.
- `docs/PLAN.md` — roadmap, milestones M0–M6, environment reality check.
- `docs/development-loops.md` — LOOP A–H machine + Definition of Done.
- `docs/agents.md` — agent roles + reusable task briefs (recognized by harness as AGENTS.md).
- `README.md`, `CONTRIBUTING.md`.
- `docs/code-standards.md`, `docs/architecture.md`.
- `IMPLEMENTATION_LOG.md` (this file), `TECHNICAL_DEBT_REGISTER.md`.
- `.gitignore`, `.env.example`.

**Tests executed.**
- None (documentation-only session; no code yet). Verification is `git diff --check` + content consistency review (LOOP E).

**Results.**
- Git repo initialized on `main` (FND-002). Planning artifacts committed (see commit log).

**Defects discovered.**
- ENOSPC on write tool during first README/CONTRIBUTING attempt; transient disk-full. Recovered without action.

**Decisions made.**
- Proceed with **npm** (pnpm absent).
- Document both Docker and local-Postgres paths (Docker absent).
- Defer code scaffold (FND-003) until toolchain exists, per spec §5 ("add modules when functionality exists").

**Remaining work.** FND-011/012 (gitignore/env — done this session), then FND-013..FND-017 toolchains, FND-003 scaffold, CHS-* rules domain.

**Next recommended task.** Configure backend toolchain (`pyproject.toml`, Ruff, mypy, pytest) and frontend toolchain (strict TS, ESLint, Prettier, Vitest) — FND-013..FND-017.

---

## Session 2026-10-09 (b) — Toolchain & health endpoint (FND-003, FND-013..FND-017, FND-020..FND-022)

**Task.** Establish and verify the backend and frontend toolchains, plus a minimal health endpoint.

**Files changed.**
- `apps/api/pyproject.toml`, `apps/api/requirements.lock` (pinned), `apps/api/README.md`
- `apps/api/app/main.py`, `app/api/v1/health.py`, `app/core/__init__.py` (+ package `__init__.py`)
- `apps/api/tests/test_health.py`
- `apps/web/package.json`, `package-lock.json`, `tsconfig.json`, `vite.config.ts`, `eslint.config.js`, `.prettierrc`, `.prettierignore`, `index.html`, `README.md`
- `apps/web/src/{main.tsx,App.tsx,App.test.tsx,vite-env.d.ts}`, `src/test/setup.ts`
- Directory scaffold: `apps/`, `infra/docker`, `scripts`, `.github/workflows`, `docs/decisions`.

**Tests executed (all passed).**
- Backend: `ruff check .` ✅ · `ruff format --check .` ✅ · `mypy app` ✅ · `pytest` → **2 passed** (1 warning: starlette TestClient `httpx`→`httpx2` deprecation).
- Backend start: `uvicorn app.main:app` → `/api/v1/health` 200 `{"status":"ok"}`, `/` 200.
- Frontend: `npx tsc --noEmit` ✅ · `npx eslint .` ✅ · `npx prettier --check` ✅ · `npx vitest run` → **1 passed** · `npm run build` ✅ (Vite 8, 15 modules).
- Frontend start: `vite` dev server serves `index.html` on :5173.

**Defects discovered & fixed.**
- ESLint rejected `reactHooks.configs.recommended` (legacy `plugins` array); switched to `reactHooks.configs.flat['recommended-latest']`.
- npm cache `~/.npm` contains root-owned files → `sudo chown` needed (not run); worked around with a temp `--cache` dir.
- Prettier reformatted 6 files (cosmetic); applied `--write`.

**Decisions made.**
- Python 3.14.2 wheels available for all deps (fastapi 0.143, sqlalchemy 2.1.4, psycopg 3.3.6, chess 1.11.2, pydantic 2.14, ruff 0.16.10, mypy 2.4.0).
- `python-chess` on PyPI is now a meta-package (1.999) that installs `chess==1.11.2`; `import chess` is the correct import.
- Used plain `uvicorn` (no `[standard]`) for now — uvloop/httptools 3.14 wheel availability unconfirmed.
- Frontend pinned via `package-lock.json` (React 19.3, Vite 8, TS 6, ESLint 10, Vitest 4).

**Remaining work.** FND-018/019 (Docker Compose + Postgres), FND-023 (CI), FND-024, then Phase 1 chess domain.

**Next recommended task.** Phase 1 chess-rules domain (CHS-001..CHS-006): game modes/status enums, game model, rules adapter over python-chess, board init, UCI validation — with tests.

---

## Session 2026-10-09 (c) — Housekeeping pause (corrected diagnosis)

**Finding.** The earlier npm "root-owned cache files" error is **not** an ownership problem. `~/.npm` and all subdirs are owned by uid 501; `find` shows zero non-user files. However, `touch ~/.npm/...` and `touch ~/...` return `Operation not permitted` while the workspace is writable → this is the assistant's workspace-write sandbox blocking `$HOME` writes. npm misattributed it.

**Decision.** `sudo chown -R 501:20 ~/.npm` is **unnecessary**. The proven fix is `--cache $(mktemp -d)` for future `npm install` (deps are already installed and lockfile committed). Updated TD-009 accordingly.

**Remaining work.** Optional user-side disk housekeeping (disk at 97%, ~6.4 GiB free); then resume Phase 1 (CHS-001..CHS-006).

**Next recommended task.** Resume Phase 1 chess-rules domain.

---

## Session 2026-10-09 (d) — Chess-rules domain core (CHS-001..CHS-010)

**Task.** Implement the chess-rules domain: enums, Game/Move model, and a `ChessRules` adapter over python-chess (board init, UCI validation, SAN, check/checkmate/stalemate).

**Files changed.**
- `apps/api/app/games/domain.py` — `GameMode`/`Color`/`GameStatus` (`StrEnum`), `Move`, `Game`, `STARTING_FEN`.
- `apps/api/app/games/errors.py` — `InvalidMoveError`, `IllegalMoveError`.
- `apps/api/app/games/rules.py` — `ChessRules` adapter (only module importing `chess`).
- `apps/api/app/games/__init__.py`.
- `apps/api/tests/test_domain.py`, `apps/api/tests/test_rules.py`.

**Tests executed (all passed).**
- `ruff check .` ✅ · `ruff format --check .` ✅ · `mypy app` ✅ (10 files) · `pytest` → **22 passed**.

**Defects discovered & fixed.**
- ruff `UP042` → switched `(str, Enum)` to `StrEnum`.
- ruff `I001` import sorting → `ruff check --fix`.
- Promotion test expected `a8=Q` but position gave `a8=Q+` (king on a-file) → used a king-safe FEN.

**Decisions made.**
- `ChessRules` is the single module importing `chess`; domain types are chess-free.
- Fifty-move/threefold repetition deferred to CHS-014/CHS-016 (documented in `status()`).

**Remaining work.** CHS-011..CHS-024 (castling, en passant, promotion, repetition, resignation, draw claims, FEN/PGN, history/replay, undo, invariants, edge/property tests).

**Next recommended task.** CHS-011..CHS-013 (castling, en passant, promotion/underpromotion) + CHS-017 (FEN generate/validate) with targeted tests.

---

## Session 2026-10-09 (e) — Database verification & repair (DB-001..DB-021, FND-019)

**Task.** Verify and complete Step 2 (Phase 2 database): the prior session left uncommitted DB work with empty Alembic stub migrations (upgrade/downgrade were `pass`); DB was stamped at head but contained zero tables.

**Files changed.**
- `alembic/env.py` — import `app.models` so autogenerate sees all tables (was importing only `Base`).
- `alembic/versions/146802a49aef_initial_schema.py` — real autogenerated initial schema (users, games, sessions, game_moves, engine_runs + FKs/indexes); replaced two empty stub revisions.
- `app/core/database.py` — `Generator[Session,None,None]` return type (mypy fix); `SettingsConfigDict` instead of deprecated class-based `Config`.
- `app/engine/engine.py` — typed `termination` Literal + float `_deadline_ms` (mypy fixes).
- `app/games/rules.py` — collapsed nested `if` (ruff SIM102).
- `PROJECT_CHECKLIST.md` — marked FND-019, DB-021 `[x]`; corrected DB-020 evidence.

**Tests executed (all passed).**
- `alembic stamp base && alembic upgrade head` → 6 tables created; `alembic downgrade base && alembic upgrade head` round-trip ✅ (DB-020/DB-021).
- `ruff check .` ✅ · `ruff format --check .` ✅ · `mypy app` ✅ (23 files) · `pytest` → **98 passed** (live Postgres repository tests included).

**Defects discovered & fixed.**
- Empty stub migrations masked as done (checklist DB-003..DB-012 claimed migrated with no tables). Fixed via autogenerate + re-apply; downgrade verified.
- Pre-existing mypy/ruff issues in uncommitted engine/rules files; fixed as gate prerequisites.

**Decisions made.**
- Single squashed initial migration (no prior schema ever shipped, so no upgrade-from-stub path needed).

**Remaining work.** DB-008/DB-009 (benchmark tables), DB-022 (backup docs), FND-023 (CI); then Phase 3 auth (SEC-001+).

**Next recommended task.** Commit this DB step, then Phase 3 authentication (registration/login/session revocation over the now-live `users`/`sessions` tables).

---

## Session 2026-10-09 (f) — Phase 3 authentication (SEC-001..008, SEC-012, SEC-014..017, SEC-020..021)

**Task.** Implement registration, login, session cookies, and supporting
security controls over the live `users`/`sessions` tables.

**Files changed.**
- `app/auth/__init__.py`, `security.py` (bcrypt + token generation),
  `validators.py` (email normalize/validate), `service.py`
  (register/login/authenticate/logout).
- `app/api/v1/schemas.py` (Register/Login/User/Error schemas),
  `deps.py` (rate limit, same-origin check, `get_current_user`),
  `auth.py` (register/login/logout/me routes).
- `app/main.py` — explicit CORS allowlist from settings.
- `app/core/database.py` — auth settings (cookie flags, TTL, rate limit).
- `pyproject.toml` + `requirements.lock` — added `bcrypt==5.0.0`.
- `tests/test_auth.py` — 9 tests (flow, cookies, expiry, rate limit, CSRF).

**Tests executed (all passed).**
- `pytest` → **107 passed** (9 new auth tests, live Postgres).
- `ruff check` ✅ · `ruff format --check` ✅ · `mypy app` ✅ (30 files).

**Defects discovered & fixed.**
- FastAPI `Annotated` forbids defaults inside `Cookie()` — moved `= None`
  to parameter declarations.
- Unvalidated `csrf_token` cookie issued but never checked — removed; CSRF
  defense is SameSite=Lax + Origin/Referer allowlist instead.
- Tests initially relied on ambient DB tables — fixtures now
  create/drop schema per test like `test_game_repository.py`.

**Decisions made.**
- Sessions are opaque random tokens in DB (revocable server-side), 7-day TTL.
- Generic "Invalid email or password" for both failure modes (no enumeration).
- In-memory per-IP rate limiter (10/min); Redis before multi-worker prod.
- SEC-009/010/011/013 deferred: need deployment (Phase 9) / game & engine
  HTTP endpoints (Phase 4/6); repository ownership already enforced.

**Remaining work.** Phase 4 backend API (games CRUD over GameRepository +
auth deps), then SEC-010/011 HTTP ownership tests.

**Next recommended task.** Phase 4 games API (API-005..011, API-016..019):
POST/GET games, POST moves with rules validation + optimistic concurrency.

---

## Session template (copy per session)

**Task.** …
**Files changed.** …
**Tests executed.** (exact commands + results)
**Results.** …
**Defects discovered.** …
**Decisions made.** …
**Remaining work.** …
**Next recommended task.** …
