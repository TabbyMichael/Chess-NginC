"""Real-Stockfish opponent seam (Phase 10, PLAY-001..003).

Computer games are answered by Stockfish through the existing provider
interface instead of the custom minimax engine. Kept separate from the
benchmark/analysis path on purpose: play uses the tight resource bounds, and
every failure mode surfaces as EngineUnavailableError (HTTP 503) rather than
silently degrading to a weaker engine.
"""

from __future__ import annotations

from dataclasses import dataclass

import chess

from app.core.telemetry import engine_timer, record_engine_unavailable
from app.engine.factory import open_stockfish_provider
from app.engine.provider import AnalyseRequest
from app.engine.stockfish import (
    StockfishError,
    StockfishUnavailableError,
)
from app.games.domain import Color
from app.games.errors import EngineUnavailableError

# Client depth requests (schemas allow 1..6) map onto Stockfish search depth
# so difficulty survives the engine swap; capped well below the play bound.
DIFFICULTY_MIN_DEPTH = 1
DIFFICULTY_MAX_DEPTH = 8

# Play clock for the opponent: snappy but human-like; the adapter clamps to
# the hard play bound (STOCKFISH_MAX_TIME_MS) anyway.
DEFAULT_PLAY_TIME_MS = 900


@dataclass(frozen=True)
class OpponentMove:
    """One Stockfish answer, shaped for the EngineRun ledger."""

    uci: str
    score_cp: int
    depth: int
    nodes: int
    time_ms: int


def _difficulty_depth(max_depth: int | None) -> int:
    if max_depth is None:
        return 4  # matches the frontend's default depth request
    return max(DIFFICULTY_MIN_DEPTH, min(max_depth, DIFFICULTY_MAX_DEPTH))


def stockfish_move(
    board: chess.Board,
    for_color: Color,
    max_depth: int | None = None,
    max_time_ms: int | None = None,
) -> OpponentMove:
    """Ask Stockfish for one move.

    Raises EngineUnavailableError when no engine is reachable (no binary and no
    hosted key), the engine crashes, or it answers with a move that is not legal
    here — the caller maps that to a 503 so players know the opponent is down.
    """
    request = AnalyseRequest(
        fen=board.fen(),
        depth=_difficulty_depth(max_depth),
        multipv=1,
        max_time_ms=max_time_ms or DEFAULT_PLAY_TIME_MS,
        for_color=for_color,
    )
    try:
        # The provider is opened inside the try: with neither a binary nor a
        # key the factory itself raises, and that still means "the opponent is
        # down" (503), not a 500. One move never needs a held-open engine, so
        # the `with` only hands the connection pool back on the hosted route.
        # engine_timer starts after the open, so the histogram measures answer
        # time, not process startup (MON-003; a failure observes nothing).
        with open_stockfish_provider() as provider, engine_timer(provider.name):
            result = provider.analyse(request)
    except StockfishUnavailableError as exc:
        record_engine_unavailable()
        raise EngineUnavailableError(str(exc)) from exc
    except StockfishError as exc:
        record_engine_unavailable()
        raise EngineUnavailableError(f"Stockfish failed to answer: {exc}") from exc
    best = result.best
    if best is None or not best.move:
        raise EngineUnavailableError("Stockfish returned no move for this position")
    try:
        move = chess.Move.from_uci(best.move)
    except ValueError as exc:
        raise EngineUnavailableError(f"Stockfish sent an unparsable move: {best.move!r}") from exc
    if move not in board.legal_moves:
        raise EngineUnavailableError(f"Stockfish sent an illegal move: {best.move!r}")
    return OpponentMove(
        uci=move.uci(),
        score_cp=best.score_cp,
        depth=result.depth,
        nodes=result.nodes_searched,
        time_ms=result.time_ms,
    )
