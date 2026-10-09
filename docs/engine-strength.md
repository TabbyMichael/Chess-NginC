# Chess Engine Strength & Limitations

## Current Implementation

The custom chess engine (`app/engine/`) implements a basic search-based AI with the following components:

- **Evaluation:** Material-based evaluation with piece values
- **Search:** Minimax algorithm with alpha-beta pruning
- **Depth:** Configurable search depth (default: 3 plies)
- **Time Control:** Deadline-aware search with configurable time limits
- **Cancellation:** Support for cancelling in-progress searches

## Strengths

- **Correctness:** The engine only returns legal moves and correctly identifies terminal positions (checkmate, stalemate, draws).
- **Deterministic:** With the same configuration and position, the engine returns consistent results.
- **Safety:** Time limits and cancellation prevent runaway searches.
- **Test Coverage:** All core functionality has unit tests (128 backend tests passing, incl. 11 Stockfish/benchmark tests).

## Stockfish reference & benchmarking (Phase 7, BEN-001..022)

- **Source:** official upstream `https://stockfishchess.org` / `https://github.com/official-stockfish/Stockfish`;
  packaged as Ubuntu `stockfish 16-1build1` (provenance recorded in `app/engine/stockfish.py`
  + `stockfish_version_label()`).
- **Licensing (BEN-003):** Stockfish is GPL-3.0. The binary is **not** distributed with this repo —
  the adapter discovers it via `STOCKFISH_PATH` or `PATH` at runtime only. Review redistribution
  obligations (provide corresponding source + license notices) before shipping any image/installer
  that bundles the binary.
- **Adapter (`app/engine/stockfish.py`, BEN-004..008):** UCI via `chess.engine.SimpleEngine`,
  hard bounds depth ≤ 15 / time ≤ 1000 ms / threads = 1 / hash ≤ 64 MB, graceful
  `StockfishUnavailableError` / `StockfishError` handling, score normalized to centipawns
  from the mover's perspective (mate → `20000 − 10·plies`).
- **Suite (`app/engine/benchmark_suite.py`, BEN-009):** versioned `v1` suite, 12 validated FEN
  positions (openings, middlegame structures, tactics, endgames).
- **Harness (`app/engine/benchmark.py`, BEN-010..013):** `compare_position()` runs both engines on
  identical FENs, records move/score/depth/nodes/time, `agreement_rate()` + `mean_score_gap()`
  metrics, `hardware_fingerprint()` per run. Degrades to custom-only when no binary is present.
- **Persistence (BEN-019):** `benchmark_runs` + `benchmark_results` tables (migration `5a0dcdb13bb3`).
- **Repeatability (BEN-022):** custom engine deterministic per config+position (tested).
- **Remaining:** head-to-head games with alternating colors + W/D/L (BEN-014..016), rating estimate
  (BEN-017, P3), benchmark user docs (BEN-021).

## Limitations

### Evaluation Function

The current evaluation is purely material-based:
- No positional considerations (piece-square tables)
- No pawn structure evaluation
- No king safety evaluation
- No mobility or activity scoring
- No endgame-specific knowledge

**Impact:** The engine plays tactically sound but positionally weak. It will miss strategic advantages like controlling key squares, pawn breaks, and king safety.

### Search Depth

Default depth is 3 plies (1.5 moves ahead). This is very shallow:
- Cannot see tactical combinations beyond 1.5 moves
- Misses simple 2-move tactics
- No iterative deepening to find better moves within time limits

**Impact:** Against a stronger engine or experienced player, the engine will frequently fall into tactical traps.

### Performance

Pure Python implementation without optimizations:
- No transposition table (repeated position evaluation)
- No move ordering (inefficient alpha-beta pruning)
- No quiescence search (horizon effect on captures)
- No bitboards or other low-level optimizations

**Impact:** Search speed is limited, constraining practical depth even with generous time limits.

### Estimated Strength

Based on the limitations above:
- **ELO estimate:** ~800-1000 (beginner level)
- **Comparable to:** A player who knows the rules and basic tactics but lacks strategic understanding
- **Suitable for:** Casual play, learning chess, testing the application
- **Not suitable for:** Competitive play, serious analysis, or challenging experienced players

## Planned Improvements (P2)

The following improvements are marked as P2 in the checklist and would significantly increase strength:

1. **Piece-square tables (AI-006):** Add positional bonuses for pieces
2. **Move ordering (AI-009):** Sort moves to improve alpha-beta efficiency
3. **Iterative deepening (AI-010):** Search incrementally deeper within time limits
4. **Quiescence search (AI-013):** Extend search beyond captures to avoid horizon effect
5. **Transposition table (AI-014):** Cache evaluated positions to avoid redundant computation

These improvements could potentially raise the engine to ~1200-1500 ELO.

## Comparison to Stockfish

Stockfish (Phase 7) is a world-class engine (~3500+ ELO) that uses:
- Sophisticated evaluation with hundreds of features
- Very deep search (20+ plies) with aggressive pruning
- Extensive optimization (C++, bitboards, SIMD)
- Massive opening books and endgame tablebases

Our custom engine is not intended to compete with Stockfish. Instead, Stockfish will be used for:
- Benchmarking our engine's accuracy
- Providing optional strong play for users who want it
- Position analysis and evaluation

## Usage Recommendations

- **Easy mode (depth 1):** For complete beginners
- **Medium mode (depth 3):** Default, suitable for casual play
- **Hard mode (depth 5):** For players who want a modest challenge
- **Stockfish integration:** For strong play and analysis (when Phase 7 is implemented)
