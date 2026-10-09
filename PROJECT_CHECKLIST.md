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
| FND-019 | Verify PostgreSQL starts & accepts connections | P1 | [ ] | psql client present; server unverified. |
| FND-020 | Verify frontend starts | P1 | [x] | `vite` dev server serves index.html on :5173; production build succeeds. |
| FND-021 | Verify backend starts | P1 | [x] | `uvicorn app.main:app` starts; `/` and `/api/v1/health` return 200. |
| FND-022 | Backend health endpoint | P1 | [x] | GET /api/v1/health → 200 {"status":"ok"} (tested). |
| FND-023 | CI workflows | P1 | [ ] | |
| FND-024 | Verify clean setup on fresh environment | P2 | [ ] | |

---

## Phase 1 — Chess Rules & Domain

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| CHS-001 | Game modes & game-status enums | P1 | [ ] | |
| CHS-002 | Game domain model | P1 | [ ] | |
| CHS-003 | Chess-rules adapter | P1 | [ ] | |
| CHS-004 | Integrate python-chess | P1 | [ ] | |
| CHS-005 | Board initialization | P1 | [ ] | |
| CHS-006 | Validate UCI moves | P0 | [ ] | |
| CHS-007 | SAN move notation | P1 | [ ] | |
| CHS-008 | Detect check | P1 | [ ] | |
| CHS-009 | Detect checkmate | P1 | [ ] | |
| CHS-010 | Detect stalemate | P1 | [ ] | |
| CHS-011 | Castling (kingside & queenside) | P1 | [ ] | |
| CHS-012 | En passant | P1 | [ ] | |
| CHS-013 | Promotion & underpromotion | P1 | [ ] | |
| CHS-014 | Repetition & draw rules | P1 | [ ] | |
| CHS-015 | Resignation | P1 | [ ] | |
| CHS-016 | Draw claims & automatic draws | P1 | [ ] | |
| CHS-017 | Generate & validate FEN | P1 | [ ] | |
| CHS-018 | Generate PGN from move history | P2 | [ ] | |
| CHS-019 | Move history & replay | P1 | [ ] | |
| CHS-020 | Undo semantics | P1 | [ ] | |
| CHS-021 | Verify board invariants | P0 | [ ] | |
| CHS-022 | Edge-case tests | P1 | [ ] | |
| CHS-023 | Property-based legal-move tests | P1 | [ ] | |
| CHS-024 | Terminal positions & special-move tests | P1 | [ ] | |

---

## Phase 2 — Database & Migrations

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| DB-001 | Configure SQLAlchemy | P1 | [ ] | |
| DB-002 | Configure Alembic | P1 | [ ] | |
| DB-003 | users migration | P1 | [ ] | |
| DB-004 | sessions migration | P1 | [ ] | |
| DB-005 | games migration | P1 | [ ] | |
| DB-006 | game_moves migration | P1 | [ ] | |
| DB-007 | engine_runs migration | P1 | [ ] | |
| DB-008 | benchmark_runs migration | P2 | [ ] | |
| DB-009 | benchmark_results migration | P2 | [ ] | |
| DB-010 | Foreign keys | P1 | [ ] | |
| DB-011 | Unique constraints | P1 | [ ] | |
| DB-012 | Necessary indexes | P2 | [ ] | |
| DB-013 | Ownership constraints at service level | P0 | [ ] | |
| DB-014 | Repository interfaces | P1 | [ ] | |
| DB-015 | Transactional game persistence | P0 | [ ] | |
| DB-016 | Atomic move submission + version updates | P0 | [ ] | |
| DB-017 | Game recovery | P1 | [ ] | |
| DB-018 | Test rollback after failed write | P0 | [ ] | |
| DB-019 | Test stale-version conflicts | P0 | [ ] | |
| DB-020 | Test migrations from empty DB | P1 | [ ] | |
| DB-021 | Test upgrades from previous schema | P1 | [ ] | |
| DB-022 | Document backup & restore | P1 | [ ] | |

---

## Phase 3 — Authentication & Security

| ID | Requirement | Pri | Status | Evidence / Location |
|----|-------------|-----|--------|---------------------|
| SEC-001 | Registration | P1 | [ ] | |
| SEC-002 | Normalize & validate email | P1 | [ ] | |
| SEC-003 | Secure password hashing | P0 | [ ] | |
| SEC-004 | Login | P1 | [ ] | |
| SEC-005 | Logout & session revocation | P1 | [ ] | |
| SEC-006 | GET /api/v1/auth/me | P1 | [ ] | |
| SEC-007 | Secure HttpOnly SameSite cookies | P0 | [ ] | |
| SEC-008 | CSRF protection | P0 | [ ] | |
| SEC-009 | Enforce HTTPS in production | P0 | [ ] | |
| SEC-010 | Game ownership on reads | P0 | [ ] | |
| SEC-011 | Game ownership on writes | P0 | [ ] | |
| SEC-012 | Login/registration rate limits | P1 | [ ] | |
| SEC-013 | Engine endpoint resource limits | P0 | [ ] | |
| SEC-014 | Explicit CORS config | P1 | [ ] | |
| SEC-015 | Keep secrets out of source control | P0 | [ ] | |
| SEC-016 | Safe error responses | P1 | [ ] | |
| SEC-017 | No sensitive data in logs | P0 | [ ] | |
| SEC-018 | Email verification (before public release) | P2 | [-] | Deferred; required before public launch. |
| SEC-019 | Password-reset flow (before public release) | P2 | [-] | Deferred; required before public launch. |
| SEC-020 | Test unauthorized & cross-account access | P0 | [ ] | |
| SEC-021 | Test session expiry & revocation | P1 | [ ] | |
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
| AI-001 | ChessEngine interface | P1 | [ ] | |
| AI-002 | Structured engine result | P1 | [ ] | |
| AI-003 | Engine config & limits | P1 | [ ] | |
| AI-004 | Material evaluation | P1 | [ ] | |
| AI-005 | Terminal-position scoring | P1 | [ ] | |
| AI-006 | Piece-square tables | P2 | [ ] | |
| AI-007 | Minimax | P1 | [ ] | |
| AI-008 | Alpha-beta pruning | P1 | [ ] | |
| AI-009 | Move ordering | P2 | [ ] | |
| AI-010 | Iterative deepening | P2 | [ ] | |
| AI-011 | Deadline-aware search | P1 | [ ] | |
| AI-012 | Cancellation | P1 | [ ] | |
| AI-013 | Quiescence search | P2 | [ ] | |
| AI-014 | Transposition table | P2 | [ ] | |
| AI-015 | Reproducible engine configs | P1 | [ ] | |
| AI-016 | Test forced mates | P1 | [ ] | |
| AI-017 | Test material blunders | P1 | [ ] | |
| AI-018 | Test terminal positions | P1 | [ ] | |
| AI-019 | Test legal-move guarantees | P0 | [ ] | |
| AI-020 | Test timeout behavior | P0 | [ ] | |
| AI-021 | Measure nodes & NPS | P2 | [ ] | |
| AI-022 | Tune difficulty settings | P2 | [ ] | |
| AI-023 | Engine + game-service integration tests | P1 | [ ] | |
| AI-024 | Document strength limitations | P1 | [ ] | |

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
- **Implemented & verified (`[x]`):** FND-001..FND-017, FND-020..FND-022 (20 items)
- **Deferred (`[-]`):** SEC-018, SEC-019 (required before public release)
- **Blocked (`[!]`):** none yet (FND-018 Docker Compose and FND-019 Postgres remain `[ ]` — Docker not installed locally)

> Statuses must be updated in this file only after the corresponding acceptance criteria are met and checks pass.
