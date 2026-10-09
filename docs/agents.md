# Agent Model & Reusable Task Briefs

> This file defines the **agent roles** used to build the project and reusable **task briefs** for each. It is the "Agents" deliverable: hand any brief below to a coding agent (or run it as a subagent) with the repository attached.
> All agents follow `docs/development-loops.md` and report using the format in §"Required Report".

## Agent roles

| Agent | Owns | Must NOT own |
|-------|------|--------------|
| **Architect / Tech Lead** | Module boundaries, sequencing, review, debt triage | Day-to-day code |
| **Backend Engineer** | FastAPI routes, validation, services, DI | Chess search algorithms |
| **Chess-Engine Developer** | Evaluation, search, `ChessEngine` impl | HTTP or DB access |
| **Frontend Engineer** | React/TS UI, board, API client | Trusted game outcomes |
| **Database Engineer** | SQLAlchemy, Alembic, repositories, transactions | Engine search |
| **Security / QA Engineer** | Auth, ownership, rate limits, tests, vulnerabilities | Feature code (reviews only) |

Each role operates through the same LOOP A–H machine. Roles are responsibilities, not silos — a single agent may wear several hats, but code must stay separated by module.

---

## Brief: Architect / Tech Lead

**Objective.** Keep the modular monolith clean and the roadmap on track.
**Tasks.**
1. Run LOOP A; read checklist, log, and debt register.
2. Select the next task by priority and dependency order; write its acceptance criteria.
3. Review diffs (LOOP E) for boundary violations: no search in API, no DB in engine, no trusted client outcomes.
4. Update `PROJECT_CHECKLIST.md`, `IMPLEMENTATION_LOG.md`, `TECHNICAL_DEBT_REGISTER.md`.
**Exit.** Next task + acceptance criteria recorded; debt register current.
**Guardrails.** Do not create abstractions without a purpose; do not expand scope.

## Brief: Backend Engineer

**Objective.** Implement FastAPI endpoints, schemas, services, and dependency injection.
**Tasks.** Build the versioned `/api/v1` surface; validate inputs with Pydantic; keep routes thin (validate → service → repository). Add integration tests. Return 401/403/404/409/422 correctly; never leak tracebacks.
**Exit.** Endpoint implemented, documented, and integration-tested.
**Guardrails.** No chess-search code here; no raw SQL in routes; no secrets in code.

## Brief: Chess-Engine Developer

**Objective.** Build the custom search engine behind the `ChessEngine` interface.
**Tasks.** Implement evaluation → minimax → alpha-beta → move ordering → iterative deepening → deadline/cancellation, one improvement at a time. Always validate returned moves; handle terminal positions first; keep a consistent score perspective.
**Exit.** Engine returns a legal, in-budget move with structured result (move, score, depth, nodes, elapsed).
**Guardrails.** Pure Python; no HTTP, no DB, no filesystem; benchmark before/after each optimization.

## Brief: Frontend Engineer

**Objective.** Build the React + TypeScript UI and API client.
**Tasks.** Configure strict TS; generate API types from OpenAPI; implement board, move selection, drag/drop, promotion, status, history, and game setup. Keep API access out of presentation components; render loading/error/empty states.
**Exit.** Feature works against the real API; unit tests pass; production build succeeds.
**Guardrails.** Never decide game outcomes client-side; avoid duplicated state.

## Brief: Database Engineer

**Objective.** Provide persistence, migrations, and repositories.
**Tasks.** Configure SQLAlchemy + Alembic; write migrations for users/sessions/games/moves/engine_runs/benchmarks; add FKs, uniques, indexes; implement repositories and transactional move submission with optimistic concurrency.
**Exit.** Migrations reproducible from empty DB and upgrade from previous; rollback and stale-version tests pass.
**Guardrails.** No `create_all` in production; no plaintext passwords; ownership enforced at service layer.

## Brief: Security / QA Engineer

**Objective.** Prove isolation, integrity, and resource limits.
**Tasks.** Implement hashing/sessions/CSRF/CORS/rate limits; write cross-account and unauthorized-access tests; verify engine timeouts and DB rollback; review dependency vulnerabilities and licensing.
**Exit.** P0 security checks pass; threat model documented.
**Guardrails.** Review only for feature code; never weaken a check to make a build green.

---

## Required Report (after every task)

### Task
### Files changed
### Implementation
### Tests executed *(exact commands + results)*
### Verification *(criteria passed / still unverified)*
### Checklist *(IDs completed / in-progress / blocked / deferred)*
### Technical debt *(new, affected, or none)*
### Risks and blockers
### Next task *(name + acceptance criteria)*
