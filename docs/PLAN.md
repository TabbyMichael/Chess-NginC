# Project Plan & Roadmap

> Version 0.1 — last updated 2026-10-09
> This plan is the operational roadmap. It mirrors `PROJECT_CHECKLIST.md`, which is the authoritative status tracker.

## Objective

Build a browser-based chess application: standard chess, player-vs-computer, local two-player, a custom Python chess AI, Stockfish benchmarking, user accounts, PostgreSQL persistence, saved games/move history, and a responsive React + TypeScript frontend — delivered through verified, incremental loops.

## Guiding principles

1. **Correctness first, AI strength second.** An illegal move or corrupted game is a P0 defect.
2. **Modular monolith.** Separate rules, AI search, services, API, persistence, and UI.
3. **python-chess for rules.** Never write a duplicate rules engine.
4. **Verify before claiming done.** No `[x]` without passing checks.
5. **Incremental loops.** INSPECT → PLAN → IMPLEMENT → TEST → REVIEW → FIX → DOCUMENT → VERIFY → REPEAT.

## Milestones (in dependency order)

| # | Milestone | Exit criterion | Target phases |
|---|-----------|----------------|---------------|
| M0 | Foundation & repository | Both apps start, PostgreSQL reachable, checks execute, setup docs accurate | Phase 0 |
| M1 | Chess rules & local gameplay | Complete legal game playable, saved & restored | Phase 1 (+ API subset) |
| M2 | Accounts & persistence | User logs in and resumes own games; cannot see others' | Phases 2–3 |
| M3 | First custom AI | AI returns legal moves within its search budget | Phase 6 |
| M4 | Stockfish & benchmarks | Repeatable custom-vs-Stockfish comparisons | Phase 7 |
| M5 | Hardening & usability | Main journeys reliable; edge cases, a11y, security, backups | Phase 8 |
| M6 | Deployment & first release | Deployed release passes smoke tests; recoverable data | Phase 9 |

## Sequencing rules

- Address any **P0** defect before adding features.
- Do not start Phase 6 (AI) until Phase 1 (rules) is stable.
- Do not start Phase 7 (Stockfish) until the engine interface (AI-001..AI-003) exists.
- `SEC-018` (email verification) and `SEC-019` (password reset) are deferred but **must** land before public registration.

## Immediate next tasks (backlog order)

1. **FND-011/.gitignore + FND-012/.env.example** — protect secrets before any code lands. *(P0)*
2. **FND-013..FND-017** — backend (`pyproject.toml`, Ruff, mypy, pytest) and frontend (`package.json`, tsconfig strict, ESLint, Prettier, Vitest) toolchains.
3. **FND-003** — create the real directory scaffold (`apps/web`, `apps/api`, `docs`, `infra`, etc.) once tooling exists, then FND-004..FND-010 docs.
4. **CHS-001..CHS-024** — chess rules domain behind a `ChessRules` adapter over python-chess.

## Environment reality check (2026-10-09)

| Tool | Status | Impact |
|------|--------|--------|
| Python 3.14.2 | ✅ present | Backend & engine OK |
| Node v25.2.1 / npm 11.7.0 | ✅ present | Frontend OK |
| pnpm | ❌ not installed | Use npm, or install pnpm |
| Docker | ❌ not installed | FND-018/019 need Docker or a local Postgres; document either path |
| PostgreSQL 14.19 | psql client only | Server/connection unverified; FND-019 must be checked |

> **Decision:** proceed with npm unless pnpm is added; document Docker vs. local-Postgres for local dev in `docs/architecture.md` and `README.md`.
