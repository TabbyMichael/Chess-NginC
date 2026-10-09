"""Benchmark harness: run custom engine vs reference on identical positions.

BEN-010..013: identical positions, recorded config/hardware, recorded
move/score/depth/nodes/time, normalized mate scores. Pure harness — no HTTP
or DB here; persistence lives in the service layer (BEN-019).
"""

from __future__ import annotations

import platform
import time
from dataclasses import dataclass

import chess

from app.engine.domain import EngineConfig
from app.engine.engine import ChessEngine
from app.engine.stockfish import (
    STOCKFISH_APT_PACKAGE,
    STOCKFISH_APT_VERSION,
    StockfishConfig,
    StockfishError,
    StockfishUnavailableError,
    analyse_position,
)
from app.games.domain import Color


@dataclass(frozen=True)
class PositionComparison:
    """One position analysed by both engines (BEN-010/BEN-012)."""

    fen: str
    custom_move: str
    custom_score: int
    custom_depth: int
    custom_nodes: int
    custom_time_ms: int
    reference_move: str
    reference_score: int
    reference_depth: int
    reference_nodes: int
    reference_time_ms: int
    moves_agree: bool
    score_gap_cp: int  # abs(custom - reference), normalized (BEN-013)


@dataclass(frozen=True)
class BenchmarkRunResult:
    """Aggregate of one suite execution."""

    suite_version: str
    comparisons: tuple[PositionComparison, ...]
    hardware: str
    stockfish_version: str


def hardware_fingerprint() -> str:
    """Record config & hardware for repeatability (BEN-011)."""
    uname = platform.uname()
    return f"{uname.system} {uname.release} {uname.machine} | py={platform.python_version()}"


def stockfish_version_label() -> str:
    """Record Stockfish version & provenance (BEN-002/BEN-011)."""
    return f"{STOCKFISH_APT_PACKAGE} {STOCKFISH_APT_VERSION}"


def compare_position(
    fen: str,
    custom_config: EngineConfig | None = None,
    reference_config: StockfishConfig | None = None,
) -> PositionComparison:
    """Run both engines on one identical position (BEN-010)."""
    custom_cfg = custom_config or EngineConfig()
    board = chess.Board(fen)
    for_color = Color.WHITE if board.turn == chess.WHITE else Color.BLACK

    t0 = time.time()
    custom = ChessEngine(custom_cfg).search(board, for_color)
    custom_elapsed = int((time.time() - t0) * 1000)

    try:
        ref = analyse_position(fen, for_color, reference_config)
    except (StockfishUnavailableError, StockfishError):
        # Reference unavailable: record empty reference, keep custom result.
        return PositionComparison(
            fen=fen,
            custom_move=custom.best_move,
            custom_score=custom.score,
            custom_depth=custom.depth,
            custom_nodes=custom.nodes_searched,
            custom_time_ms=custom_elapsed,
            reference_move="",
            reference_score=0,
            reference_depth=0,
            reference_nodes=0,
            reference_time_ms=0,
            moves_agree=False,
            score_gap_cp=abs(custom.score),
        )

    return PositionComparison(
        fen=fen,
        custom_move=custom.best_move,
        custom_score=custom.score,
        custom_depth=custom.depth,
        custom_nodes=custom.nodes_searched,
        custom_time_ms=custom_elapsed,
        reference_move=ref.best_move,
        reference_score=ref.score,
        reference_depth=ref.depth,
        reference_nodes=ref.nodes_searched,
        reference_time_ms=ref.time_ms,
        moves_agree=custom.best_move == ref.best_move and bool(ref.best_move),
        score_gap_cp=abs(custom.score - ref.score),
    )


def agreement_rate(comparisons: tuple[PositionComparison, ...]) -> float:
    """Fraction of positions where both engines chose the same move."""
    if not comparisons:
        return 0.0
    return sum(1 for c in comparisons if c.moves_agree) / len(comparisons)


def mean_score_gap(comparisons: tuple[PositionComparison, ...]) -> float:
    """Mean absolute score gap in centipawns (BEN-013 normalized)."""
    if not comparisons:
        return 0.0
    return sum(c.score_gap_cp for c in comparisons) / len(comparisons)
