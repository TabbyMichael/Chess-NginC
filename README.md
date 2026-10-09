# Chess Engine

A browser-based chess application with a custom Python chess AI, Stockfish benchmarking, user accounts, PostgreSQL persistence, and a React + TypeScript interface.

> **Status:** Planning/foundation phase. See `PROJECT_CHECKLIST.md` for authoritative progress and `docs/PLAN.md` for the roadmap.

## What this project will provide

- Fully playable standard chess (python-chess for rules).
- Player-vs-computer (custom AI) and local two-player on one device.
- Custom search-based chess AI in Python (minimax → alpha-beta → iterative deepening).
- Stockfish via UCI for benchmarking and optional play.
- Registration, login, logout, saved games, move history, recovery, statistics.
- PostgreSQL persistence with Alembic migrations.
- Responsive, accessible React + TypeScript UI.
- Automated tests, CI, security controls, and deployment readiness.

## Repository layout

```
apps/web/       React + TypeScript + Vite frontend
apps/api/       FastAPI backend (modular monolith)
docs/           architecture, plan, loops, agents, standards
infra/          Docker and deployment artifacts
```

> Modules are added as their functionality lands (see `docs/architecture.md`).

## Getting started

> Work in progress. Full setup instructions land with the toolchain (FND-013..FND-024).

1. **Prerequisites:** Python 3.12+, Node 20+, PostgreSQL 14+ (or Docker).
2. **Backend:** configure `apps/api/pyproject.toml`, install deps, run migrations, start Uvicorn.
3. **Frontend:** configure `apps/web/package.json`, install deps, run the Vite dev server.
4. Copy `.env.example` to `.env` and set non-secret local values.

## Development workflow

Every change follows the loops in `docs/development-loops.md` and reports using the format in `docs/agents.md`. See `CONTRIBUTING.md` before contributing.

## Documentation

- `docs/PLAN.md` — roadmap and milestones
- `docs/development-loops.md` — the LOOP A–H execution machine
- `docs/agents.md` — agent roles and reusable task briefs
- `docs/architecture.md` — module boundaries
- `docs/code-standards.md` — coding, testing, and review standards

## License

Third-party licensing (notably Stockfish, GPL-3.0) must be reviewed before distribution (BEN-003). This repository does not yet distribute any engine binaries.
