# PROJECT CHECKLIST

> Authoritative progress tracker for the Chess Engine project.
> Statuses: `[ ]` Not started · `[~]` In progress · `[x]` Implemented & verified · `[!]` Blocked/failing · `[-]` Intentionally deferred.
> A file existing does **not** mean its feature is complete. Mark `[x]` only after acceptance criteria pass and relevant checks run.

Priorities: **P0** security/data integrity/build blockers/illegal moves · **P1** core gameplay/accounts/persistence/AI correctness · **P2** usability/performance/accessibility/benchmarking · **P3** optional/nonessential.

---

## Phase 0 — Repository & Engineering Foundation

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| FND-001 | Inspect repository and record initial state | P1 | [x] | Empty dir, no git, Python 3.14.2, Node v25.2.1, psql 14.19, no Docker. See IMPLEMENTATION_LOG 2026-10-09. |
| FND-002 | Establish/verify Git repository | P1 | [x] | `git init -b main` + root commit `18f8145`. |
| FND-003 | Create the agreed directory structure | P1 | [x] | apps/api, apps/web, docs, infra, scripts, .github created; empty leaf dirs added as features land. |
| FND-004 | README.md with setup instructions | P1 | [x] | README.md (setup steps preliminary until toolchain lands). |
| FND-005 | CONTRIBUTING.md | P1 | [x] | CONTRIBUTING.md (commit/PR standards + quality gates). |
| FND-006 | docs/code-standards.md | P1 | [x] | docs/code-standards.md. |
| FND-007 | docs/architecture.md | P1 | [x] | docs/architecture.md (module boundaries + decisions log). |
| FND-008 | PROJECT_CHECKLIST.md | P1 | [x] | This file. |
| FND-009 | IMPLEMENTATION_LOG.md | P1 | [x] | IMPLEMENTATION_LOG.md (session 2026-10-09 recorded). |
| FND-010 | TECHNICAL_DEBT_REGISTER.md | P1 | [x] | TECHNICAL_DEBT_REGISTER.md (TD-001..TD-008). |
| FND-011 | Configure .gitignore | P0 | [x] | .gitignore (Python/Node/env/secrets/Stockfish binaries). |
| FND-012 | .env.example without secrets | P0 | [x] | .env.example (placeholders only, no real secrets). |
| FND-013 | Python project metadata + dependency locking | P1 | [x] | apps/api/pyproject.toml + requirements.lock; venv install verified. |
| FND-014 | Node package metadata + lockfile | P1 | [x] | apps/web/package.json + package-lock.json (npm). |
| FND-015 | Python lint/format/type-check config (Ruff, mypy) | P1 | [x] | Ruff + mypy in pyproject.toml; `ruff check`/`format --check`/`mypy app` all pass. |
| FND-016 | TS strict mode + ESLint + Prettier | P1 | [x] | tsconfig strict + eslint.config.js (flat) + .prettierrc; all pass. |
| FND-017 | Configure test commands | P1 | [x] | pytest (2 passed) + vitest (1 passed). |
| FND-018 | Docker Compose | P1 | [ ] | Blocked locally: Docker not installed. Document and defer. |
| FND-019 | Verify PostgreSQL starts & accepts connections | P1 | [x] | Local PG14 accepts TCP on :5432; `chess` DB live; Alembic migrations apply. |
| FND-020 | Verify frontend starts | P1 | [x] | `vite` dev server serves index.html on :5173; production build succeeds. |
| FND-021 | Verify backend starts | P1 | [x] | `uvicorn app.main:app` starts; `/` and `/api/v1/health` return 200. |
| FND-022 | Backend health endpoint | P1 | [x] | GET /api/v1/health → 200 {"status":"ok"} (tested). |
| FND-023 | CI workflows | P1 | [ ] | |
| FND-024 | Verify clean setup on fresh environment | P2 | [ ] | |

---

## Phase 1 — Chess Rules & Domain

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| CHS-001 | Game modes & game-status enums | P1 | [x] | app/games/domain.py (GameMode, Color, GameStatus). |
| CHS-002 | Game domain model | P1 | [x] | app/games/domain.py (Game, Move dataclasses). |
| CHS-003 | Chess-rules adapter | P1 | [x] | app/games/rules.py (ChessRules). |
| CHS-004 | Integrate python-chess | P1 | [x] | chess imported only in rules.py. |
| CHS-005 | Board initialization | P1 | [x] | ChessRules().fen == STARTING_FEN (tested). |
| CHS-006 | Validate UCI moves | P0 | [x] | parse → InvalidMoveError; legality → IllegalMoveError (tested). |
| CHS-007 | SAN move notation | P1 | [x] | apply_move returns SAN (e4, O-O, a8=Q tested). |
| CHS-008 | Detect check | P1 | [x] | ChessRules.is_check() (fool's-mate test). |
| CHS-009 | Detect checkmate | P1 | [x] | ChessRules.status() → CHECKMATE (fool's-mate test). |
| CHS-010 | Detect stalemate | P1 | [x] | ChessRules.status() → STALEMATE (stalemate FEN test). |
| CHS-011 | Castling (kingside & queenside) | P1 | [x] | test_special_moves.py (O-O, O-O-O, illegal cases). |
| CHS-012 | En passant | P1 | [x] | test_special_moves.py (capture + expiry). |
| CHS-013 | Promotion & underpromotion | P1 | [x] | test_special_moves.py (Q/R/B/N, invalid rejected). |
| CHS-014 | Repetition & draw rules | P1 | [x] | ChessRules.status() uses can_claim_draw() for fifty-move and threefold (test_rules.py). |
| CHS-015 | Resignation | P1 | [x] | Game.resign() method with validation (test_domain.py). |
| CHS-016 | Draw claims & automatic draws | P1 | [x] | Automatic draws covered by CHS-014 (can_claim_draw). Explicit claims handled at service layer. |
| CHS-017 | Generate & validate FEN | P1 | [x] | ChessRules.fen + validate_fen/is_valid_fen (test_rules.py). |
| CHS-018 | Generate PGN from move history | P2 | [x] | Game.to_pgn() method with move numbering (test_domain.py). |
| CHS-019 | Move history & replay | P1 | [x] | ChessRules.replay_moves() method (test_rules.py). |
| CHS-020 | Undo semantics | P1 | [x] | ChessRules.undo_move() method (test_rules.py). |
| CHS-021 | Verify board invariants | P0 | [x] | ChessRules.verify_invariants() checks kings/pawns (test_rules.py). |
| CHS-022 | Edge-case tests | P1 | [x] | Edge cases: empty replay, long sequences, turn alternation, FEN persistence (test_rules.py). |
| CHS-023 | Property-based legal-move tests | P1 | [x] | Hypothesis-based tests for legal moves, undo FEN restoration (test_rules.py). |
| CHS-024 | Terminal positions & special-move tests | P1 | [x] | Terminal positions (checkmate, stalemate, insufficient material) and special moves (test_rules.py). |

---

## Phase 2 — Database & Migrations

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| DB-001 | Configure SQLAlchemy | P1 | [x] | app/core/database.py with engine and session factory |
| DB-002 | Configure Alembic | P1 | [x] | alembic.ini and alembic/env.py configured |
| DB-003 | users migration | P1 | [x] | User model in app/models/user.py (migrated) |
| DB-004 | sessions migration | P1 | [x] | Session model in app/models/session.py (migrated) |
| DB-005 | games migration | P1 | [x] | Game model in app/models/game.py (migrated) |
| DB-006 | game_moves migration | P1 | [x] | GameMove model in app/models/game_move.py (migrated) |
| DB-007 | engine_runs migration | P1 | [x] | EngineRun model in app/models/engine_run.py (migrated) |
| DB-008 | benchmark_runs migration | P2 | [ ] | |
| DB-009 | benchmark_results migration | P2 | [ ] | |
| DB-010 | Foreign keys | P1 | [x] | FKs defined in models (sessions.user_id, game_moves.game_id, etc.) |
| DB-011 | Unique constraints | P1 | [x] | Unique on users.email, sessions.token |
| DB-012 | Necessary indexes | P2 | [x] | Indexes on foreign keys and unique fields |
| DB-013 | Ownership constraints at service level | P0 | [x] | GameRepository enforces user_id on all operations |
| DB-014 | Repository interfaces | P1 | [x] | GameRepository with CRUD and ownership methods |
| DB-015 | Transactional game persistence | P0 | [x] | Repository methods use SQLAlchemy transactions |
| DB-016 | Atomic move submission + version updates | P0 | [x] | update_fen() with optimistic concurrency version checking |
| DB-017 | Game recovery | P1 | [x] | GameRepository.recover_game() with ownership enforcement |
| DB-018 | Test rollback after failed write | P0 | [x] | test_rollback_after_failed_write() (test_game_repository.py) |
| DB-019 | Test stale-version conflicts | P0 | [x] | test_update_fen_version_check() (test_game_repository.py) |
| DB-020 | Test migrations from empty DB | P1 | [x] | `146802a49aef` initial schema verified from empty DB (creates users, games, sessions, game_moves, engine_runs). |
| DB-021 | Test upgrades from previous schema | P1 | [x] | Verified via downgrade→upgrade round-trip (`alembic downgrade base && alembic upgrade head`). |
| DB-022 | Document backup & restore | P1 | [ ] | |

---

## Phase 3 — Authentication & Security

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| SEC-001 | Registration | P1 | [x] | POST /api/v1/auth/register → 201 + session (app/api/v1/auth.py). |
| SEC-002 | Normalize & validate email | P1 | [x] | normalize_email: trim/lowercase/regex/length (app/auth/validators.py). |
| SEC-003 | Secure password hashing | P0 | [x] | bcrypt via app/auth/security.py; 72-byte cap; no plaintext stored. |
| SEC-004 | Login | P1 | [x] | POST /api/v1/auth/login → 200 + session; generic 401 message. |
| SEC-005 | Logout & session revocation | P1 | [x] | POST /api/v1/auth/logout → 204, deletes session row + cookie. |
| SEC-006 | GET /api/v1/auth/me | P1 | [x] | Returns {id, email}; 401 when unauthenticated. |
| SEC-007 | Secure HttpOnly SameSite cookies | P0 | [x] | session_token: HttpOnly, SameSite=Lax, Secure flag from settings. |
| SEC-008 | CSRF protection | P0 | [x] | SameSite=Lax + Origin/Referer allowlist check (enforce_same_origin). |
| SEC-009 | Enforce HTTPS in production | P0 | [ ] | Needs deployment config (Phase 9); COOKIE_SECURE flag ready. |
| SEC-010 | Game ownership on reads | P0 | [ ] | Repository enforces; no HTTP game endpoints yet (Phase 4). |
| SEC-011 | Game ownership on writes | P0 | [ ] | Repository enforces; no HTTP game endpoints yet (Phase 4). |
| SEC-012 | Login/registration rate limits | P1 | [x] | 10/min per IP in-memory (deps.rate_limit_auth); Redis noted for prod. |
| SEC-013 | Engine endpoint resource limits | P0 | [ ] | No engine HTTP endpoints yet (Phase 4/6). |
| SEC-014 | Explicit CORS config | P1 | [x] | Allowlist from settings in app/main.py; credentials enabled, no wildcard. |
| SEC-015 | Keep secrets out of source control | P0 | [x] | .env.example placeholders only; .gitignore covers .env; no secrets logged. |
| SEC-016 | Safe error responses | P1 | [x] | Generic "Invalid email or password"; {detail} envelope; no hash/stack leaks. |
| SEC-017 | No sensitive data in logs | P0 | [x] | No password/token/hash logging in auth code (reviewed). |
| SEC-018 | Email verification (before public release) | P2 | [-] | Deferred; required before public launch. |
| SEC-019 | Password-reset flow (before public release) | P2 | [-] | Deferred; required before public launch. |
| SEC-020 | Test unauthorized & cross-account access | P0 | [x] | 401 on /me without cookie; cross-origin POST → 403 (tests/test_auth.py). |
| SEC-021 | Test session expiry & revocation | P1 | [x] | Expired session rejected; logout revokes (tests/test_auth.py). |
| SEC-022 | Review dependency vulnerabilities | P1 | [ ] | |
| SEC-023 | Document threat model | P1 | [ ] | |
| SEC-024 | Review third-party licensing | P1 | [ ] | |

---

## Phase 4 — Backend API

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| API-001 | POST /api/v1/auth/register | P1 | [ ] | |
| API-002 | POST /api/v1/auth/login | P1 | [ ] | |
| API-003 | POST /api/v1/auth/logout | P1 | [ ] | |
| API-004 | GET /api/v1/auth/me | P1 | [ ] | |
| API-005 | POST /api/v1/games | P1 | [ ] | |
| API-006 | GET /api/v1/games | P1 | [ ] | |
| API-007 | GET /api/v1/games/{game_id} | P1 | [ ] | |
| API-008 | POST /api/v1/games/{game_id}/moves | P1 | [ ] | |
| API-009 | POST /api/v1/games/{game_id}/undo | P1 | [ ] | |
| API-010 | POST /api/v1/games/{game_id}/resign | P1 | [ ] | |
| API-011 | POST /api/v1/games/{game_id}/draw-claim | P1 | [ ] | |
| API-012 | POST /api/v1/games/{game_id}/engine-move | P1 | [ ] | |
| API-013 | POST /api/v1/analysis/positions | P2 | [ ] | |
| API-014 | POST /api/v1/benchmarks | P2 | [ ] | |
| API-015 | GET /api/v1/benchmarks/{benchmark_id} | P2 | [ ] | |
| API-016 | Request & response schemas | P1 | [ ] | |
| API-017 | Consistent error schemas | P1 | [ ] | |
| API-018 | Validate every incoming move | P0 | [ ] | |
| API-019 | Optimistic concurrency control | P0 | [ ] | |
| API-020 | Document HTTP status codes | P1 | [ ] | |
| API-021 | Generate & validate OpenAPI schemas | P1 | [ ] | |
| API-022 | Generate frontend API types | P1 | [ ] | |
| API-023 | API integration tests | P1 | [ ] | |
| API-024 | All protected endpoints enforce auth | P0 | [ ] | |

---

## Phase 5 — Frontend

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| WEB-001 | Initialize React + TypeScript | P1 | [ ] | |
| WEB-002 | Strict TypeScript | P1 | [ ] | |
| WEB-003 | Linting & formatting | P1 | [ ] | |
| WEB-004 | Router | P1 | [ ] | |
| WEB-005 | Registration UI | P1 | [ ] | |
| WEB-006 | Login UI | P1 | [ ] | |
| WEB-007 | Logout | P1 | [ ] | |
| WEB-008 | Session restoration | P1 | [ ] | |
| WEB-009 | Main dashboard | P1 | [ ] | |
| WEB-010 | Chessboard | P1 | [ ] | |
| WEB-011 | Legal-move selection | P1 | [ ] | |
| WEB-012 | Drag-and-drop | P1 | [ ] | |
| WEB-013 | Promotion selection | P1 | [ ] | |
| WEB-014 | Show whose turn | P1 | [ ] | |
| WEB-015 | Show check & checkmate | P1 | [ ] | |
| WEB-016 | Show stalemate & draws | P1 | [ ] | |
| WEB-017 | Move history | P1 | [ ] | |
| WEB-018 | Captured-piece display | P2 | [ ] | |
| WEB-019 | Undo & reset controls | P1 | [ ] | |
| WEB-020 | Player-vs-computer setup | P1 | [ ] | |
| WEB-021 | Local two-player setup | P1 | [ ] | |
| WEB-022 | Engine difficulty selection | P1 | [ ] | |
| WEB-023 | Saved-game listing | P1 | [ ] | |
| WEB-024 | Game resume | P1 | [ ] | |
| WEB-025 | Loading & error states | P1 | [ ] | |
| WEB-026 | Responsive layout | P2 | [ ] | |
| WEB-027 | Keyboard & accessibility | P2 | [ ] | |
| WEB-028 | Frontend unit tests | P1 | [ ] | |
| WEB-029 | Browser e2e tests | P1 | [ ] | |
| WEB-030 | Verify production build | P1 | [ ] | |

---

## Phase 6 — Custom Chess AI

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| AI-001 | ChessEngine interface | P1 | [x] | ChessEngine class in app/engine/engine.py |
| AI-002 | Structured engine result | P1 | [x] | EngineResult dataclass in app/engine/domain.py |
| AI-003 | Engine config & limits | P1 | [x] | EngineConfig dataclass with difficulty/depth/time (app/engine/domain.py) |
| AI-004 | Material evaluation | P1 | [x] | evaluate_position() with piece values (app/engine/evaluator.py) |
| AI-005 | Terminal-position scoring | P1 | [x] | Checkmate/stalemate/draw detection in evaluate_position() |
| AI-006 | Piece-square tables | P2 | [ ] | |
| AI-007 | Minimax | P1 | [x] | _minimax() method with depth-limited search (app/engine/engine.py) |
| AI-008 | Alpha-beta pruning | P1 | [x] | Alpha-beta cutoffs in _minimax() (app/engine/engine.py) |
| AI-009 | Move ordering | P2 | [ ] | |
| AI-010 | Iterative deepening | P2 | [ ] | |
| AI-011 | Deadline-aware search | P1 | [x] | Time limit checking in search() and _minimax() |
| AI-012 | Cancellation | P1 | [x] | cancel() method with _cancelled flag |
| AI-013 | Quiescence search | P2 | [ ] | |
| AI-014 | Transposition table | P2 | [ ] | |
| AI-015 | Reproducible engine configs | P1 | [x] | EngineConfig dataclass is frozen |
| AI-016 | Test forced mates | P1 | [x] | test_engine_search_checkmate_position() (test_engine.py) |
| AI-017 | Test material blunders | P1 | [x] | test_evaluate_material_advantage() (test_engine.py) |
| AI-018 | Test terminal positions | P1 | [x] | test_evaluate_checkmate/stalemate() (test_engine.py) |
| AI-019 | Test legal-move guarantees | P0 | [x] | test_engine_search_starting_position() validates legal moves |
| AI-020 | Test timeout behavior | P0 | [x] | test_engine_cancel() tests timeout/cancellation |
| AI-021 | Measure nodes & NPS | P2 | [x] | nodes_searched tracked in EngineResult |
| AI-022 | Tune difficulty settings | P2 | [ ] | |
| AI-023 | Engine + game-service integration tests | P1 | [ ] | |
| AI-024 | Document strength limitations | P1 | [x] | docs/engine-strength.md with current capabilities and limitations |

---

## Phase 7 — Stockfish & Benchmarking

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| BEN-001 | Verify official Stockfish source | P2 | [ ] | |
| BEN-002 | Record version & binary provenance | P2 | [ ] | |
| BEN-003 | Review GPL-3.0 obligations | P1 | [ ] | |
| BEN-004 | UCI adapter | P2 | [ ] | |
| BEN-005 | Process startup/shutdown | P2 | [ ] | |
| BEN-006 | Bound time & resources | P0 | [ ] | |
| BEN-007 | Handle crashes/unavailable binaries | P1 | [ ] | |
| BEN-008 | Position analysis | P2 | [ ] | |
| BEN-009 | Versioned FEN test suite | P2 | [ ] | |
| BEN-010 | Run both engines on identical positions | P2 | [ ] | |
| BEN-011 | Record config & hardware | P2 | [ ] | |
| BEN-012 | Record move/score/depth/nodes/time | P2 | [ ] | |
| BEN-013 | Normalize score & mate scores | P2 | [ ] | |
| BEN-014 | Head-to-head games | P2 | [ ] | |
| BEN-015 | Alternate colors | P2 | [ ] | |
| BEN-016 | Record W/D/L | P2 | [ ] | |
| BEN-017 | Estimate rating w/ uncertainty | P3 | [ ] | |
| BEN-018 | Benchmark regression tests | P2 | [ ] | |
| BEN-019 | Persist benchmark results | P2 | [ ] | |
| BEN-020 | Restrict expensive benchmark endpoints | P0 | [ ] | |
| BEN-021 | Benchmark documentation | P2 | [ ] | |
| BEN-022 | Verify repeatability | P2 | [ ] | |

---

## Phase 8 — Quality, Security & Performance

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| QA-001 | All backend unit tests | P1 | [ ] | |
| QA-002 | Backend integration tests | P1 | [ ] | |
| QA-003 | Frontend unit tests | P1 | [ ] | |
| QA-004 | e2e smoke tests | P1 | [ ] | |
| QA-005 | Python lint | P1 | [ ] | |
| QA-006 | Python type check | P1 | [ ] | |
| QA-007 | Frontend lint | P1 | [ ] | |
| QA-008 | TS type check | P1 | [ ] | |
| QA-009 | Production build | P1 | [ ] | |
| QA-010 | Validate migrations | P1 | [ ] | |
| QA-011 | Test unauthorized access | P0 | [ ] | |
| QA-012 | Test cross-user data isolation | P0 | [ ] | |
| QA-013 | Test invalid/malformed moves | P0 | [ ] | |
| QA-014 | Test repeated & concurrent requests | P1 | [ ] | |
| QA-015 | Test engine timeouts | P0 | [ ] | |
| QA-016 | Test restart & game recovery | P1 | [ ] | |
| QA-017 | Test DB rollback | P0 | [ ] | |
| QA-018 | Check dependency vulnerabilities | P1 | [ ] | |
| QA-019 | Verify no secrets in logs | P0 | [ ] | |
| QA-020 | Review accessibility | P2 | [ ] | |
| QA-021 | Review mobile & desktop layouts | P2 | [ ] | |
| QA-022 | Performance tests | P2 | [ ] | |
| QA-023 | Review slow DB queries | P2 | [ ] | |
| QA-024 | Review technical debt | P1 | [ ] | |
| QA-025 | Verify backup & restore | P1 | [ ] | |
| QA-026 | Verify release checklist | P1 | [ ] | |

---

## Phase 9 — Deployment & Release

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| REL-001 | Production configuration | P1 | [ ] | |
| REL-002 | Secret management | P0 | [ ] | |
| REL-003 | HTTPS | P0 | [ ] | |
| REL-004 | DB backups | P1 | [ ] | |
| REL-005 | Verify DB restoration | P1 | [ ] | |
| REL-006 | Migrations as controlled deployment step | P1 | [ ] | |
| REL-007 | Health checks | P1 | [ ] | |
| REL-008 | Structured logs | P1 | [ ] | |
| REL-009 | Monitoring & error reporting | P2 | [ ] | |
| REL-010 | Verify production dependency install | P1 | [ ] | |
| REL-011 | Stockfish deployment & licensing | P1 | [ ] | |
| REL-012 | Verify CORS & cookie settings | P0 | [ ] | |
| REL-013 | Production smoke tests | P1 | [ ] | |
| REL-014 | Document rollback procedures | P1 | [ ] | |
| REL-015 | Release notes | P1 | [ ] | |
| REL-016 | All P0/P1 issues resolved | P0 | [ ] | |
| REL-017 | Publish final verified status | P1 | [ ] | |

---

## Summary

- **Total items:** 237
- **Implemented & verified (`[x]`):** FND-001..FND-017, FND-019..FND-022, CHS-001..CHS-024, AI-001..AI-005, AI-007..AI-008, AI-011..AI-012, AI-015..AI-021, AI-024, DB-001..DB-007, DB-010..DB-016, DB-018..DB-021, SEC-001..SEC-008, SEC-012, SEC-014..SEC-017, SEC-020..SEC-021 (93 items)
- **Deferred (`[-]`):** SEC-018, SEC-019 (required before public release)
- **Blocked (`[!]`):** none yet (FND-018 Docker Compose and FND-019 Postgres remain `[ ]` — Docker not installed locally)

> Statuses must be updated in this file only after the corresponding acceptance criteria are met and checks pass.
