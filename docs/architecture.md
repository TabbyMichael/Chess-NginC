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
| `analysis` | Stored evals, win%, graphs, jobs (consumes engine results) | Search algorithms or invented evals |
| `reviews` (`app/reviews`) | Post-game pass: replay stored plies → MultiPV analysis → per-move grade + coaching sentence → stored JSON payload | Search; re-analysing on a read |
| `classification` | Move labels from structured analysis only (`app/engine/classifier.py`) | Guessing without engine proof fields |
| `coaching` | Grounded explanations citing stored fields (`app/reviews/explainer.py`) | Inventing evals/variations |
| `achievements` (`app/achievements`) | Code-defined catalog, stat aggregation from stored rows, per-player unlock records | Any client-supplied counting |
| `tactics` | Pattern detectors over python-chess positions | Engine search or LLM judgement |
| `api` | HTTP schemas, status codes, request handling | Core chess algorithms |
| `web` | User interactions and visual state | Trusted game outcomes |

## Key boundaries

- The **API** never contains chess-search algorithms.
- The **custom engine** never does HTTP or database queries.
- The **analysis/classification/tactics/coaching** modules never invent chess facts:
  they consume stored engine output (evals, PVs, patterns) and cite it.
- The **frontend** never determines authoritative outcomes or validates AI moves.
  Sound, haptics and celebration animations are display-only layers: they read
  the server's events and never influence a game (`lib/game-events.ts`,
  `app/AchievementContext.tsx`).
- **Achievement stats** are aggregated from stored game/move/point/review rows;
  the catalog itself is code, so adding a milestone never needs a migration.
- A **review** is computed once per (game, player) and served from storage;
  reads never touch the engine, and the play path keeps the tight resource
  bounds while review uses the wider `REVIEW_MAX_*` envelope.
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
| D6 | Online human-vs-human play extends the modular monolith: Postgres stays authoritative; lobby queue, socket hub and rate-limiter are in-process state islands | Accepted | Single-replica assumption (online-plan §2): restarts drop queues/sockets but never games; scale-out requires moving ephemeral state to Redis/a broker — tracked as debt |
| D7 | Computer games are answered by Stockfish through `app/engine/opponent.py`, not the custom minimax | Accepted | Difficulty maps client depth (1..6) onto bounded Stockfish depth. `app/engine/factory.py` is the single decision seam (local binary → `StockfishProvider`, else hosted `CloudStockfishProvider` when `STOCKFISH_API_KEY` is set) shared by play and review. An unreachable engine is `503`, never a silent fallback to a weaker opponent |
| D8 | Achievement catalog in code, unlocks in one small table | Accepted | 200+ entries need no per-entry rows or migrations; unlocks ride mutation responses and are acknowledged once (`seen_at`) |
| D9 | Game review runs synchronously and stores its payload | Accepted (debt) | Simple and cached per (game, player), but it holds a worker for up to `REVIEW_MAX_TIME_MS`; job queue + eval cache remain Phase 9 items (ANL-005/008) |

See `docs/decisions/` for full decision records as they arise.
