# Architecture

> Modular monolith. One deployable FastAPI app, one PostgreSQL database, one React frontend. Each domain has a single responsibility.

## System overview

```
React + TypeScript (web)
   Pages · Board · Game state · API client
              │  HTTP /api/v1
FastAPI application (api)
   REST API · validation · authentication · authorization
              │
   ┌──────────┼────────────┬────────────┬──────────────┐
   ▼          ▼            ▼            ▼              ▼
 Game domain  Engine domain  Identity    History/Stats  Benchmark
 rules,turns, our AI,       users,       saved games,    suites,
 status,      Stockfish     sessions,    statistics      metrics
 move history adapter       credentials
              └─────────────┴────────────┴──────────────┘
                              │
                         PostgreSQL
           transactions · migrations · indexes · constraints
```

## Module responsibilities

| Module | Owns | Must NOT own |
|--------|------|--------------|
| `game` | Legal moves, turns, results, FEN, PGN | AI strategy or HTTP handling |
| `engine` | Move search and evaluation | User accounts or DB access |
| `identity` | Password hashing, sessions, authorization | Chess rules |
| `history` | Saving/retrieving games | Engine search |
| `benchmark` | Position suites, comparisons, metrics | Normal game state |
| `api` | HTTP schemas, status codes, request handling | Core chess algorithms |
| `web` | User interactions and visual state | Trusted game outcomes |

## Key boundaries

- The **API** never contains chess-search algorithms.
- The **custom engine** never does HTTP or database queries.
- The **frontend** never determines authoritative outcomes or validates AI moves.
- Use **dependency injection** to provide engines and repositories to services.
- Versioned API under `/api/v1`; all contracts explicit, validated, documented.

## Rules & engine split

- `python-chess` supplies legal move generation and position management.
- Our AI supplies evaluation and search only.
- Never write a second, independent rules engine.

## Proposed repository layout

```
apps/web/       React + TypeScript + Vite
apps/api/       FastAPI app, migrations, tests
docs/           architecture, plan, loops, agents, standards, decisions
infra/          Docker, deployment artifacts
scripts/        maintenance/utility scripts
.github/        CI workflows
compose.yaml    local Docker Compose
```

> This is a logical structure, not a requirement to create every folder on day one. Modules are added as functionality lands. Deviations are documented here.

## Decisions log

| # | Decision | Status | Note |
|---|----------|--------|------|
| D1 | Use python-chess for rules; own search algorithm | Accepted | No duplicate rules engine |
| D2 | Authenticated games saved to PostgreSQL from the first playable version | Accepted | "Local two-player" = who plays, not where state lives |
| D3 | Stockfish isolated behind the engine interface, bounded execution | Accepted | Licensing reviewed before distribution |
| D4 | npm as JS package manager (pnpm not installed) | Pending | Revisit if pnpm is added |
| D5 | Docker Compose for local dev; document local-Postgres fallback (Docker not installed) | Pending | FND-018/019 |

See `docs/decisions/` for full decision records as they arise.
