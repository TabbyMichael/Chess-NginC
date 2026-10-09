"""Stockfish UCI adapter (Phase 7, BEN-004..007).

Isolated behind the engine interface: bounded execution (depth/time caps),
graceful handling of missing binaries and crashes. Never imported by the
custom search engine; only services/benchmark harnesses use it.
"""

from __future__ import annotations

import contextlib
import shutil
import time
from dataclasses import dataclass
from typing import Literal

import chess
import chess.engine

from app.engine.domain import EngineConfig, EngineResult
from app.games.domain import Color

# Provenance (BEN-001/BEN-002): official upstream + packaged version.
# Binary itself is NOT distributed with this repo (BEN-003: GPL-3.0).
STOCKFISH_UPSTREAM = "https://stockfishchess.org"
STOCKFISH_UPSTREAM_REPO = "https://github.com/official-stockfish/Stockfish"
STOCKFISH_APT_PACKAGE = "stockfish"
STOCKFISH_APT_VERSION = "16-1build1"  # Ubuntu noble/universe at time of writing

# Hard bounds (BEN-006): adapter never exceeds these even if asked for more.
STOCKFISH_MAX_DEPTH = 15
STOCKFISH_MAX_TIME_MS = 1000


@dataclass(frozen=True)
class StockfishConfig:
    """Configuration for the Stockfish UCI adapter."""

    path: str = ""  # absolute path to binary; empty = auto-detect via PATH
    max_depth: int = 10
    max_time_ms: int = 500
    threads: int = 1
    hash_mb: int = 16

    def bounded(self) -> StockfishConfig:
        """Return a copy clamped to the hard resource bounds."""
        return StockfishConfig(
            path=self.path,
            max_depth=max(1, min(self.max_depth, STOCKFISH_MAX_DEPTH)),
            max_time_ms=max(1, min(self.max_time_ms, STOCKFISH_MAX_TIME_MS)),
            threads=1,  # single-threaded: keep concurrency bounded (TD-007)
            hash_mb=max(1, min(self.hash_mb, 64)),
        )


class StockfishUnavailableError(Exception):
    """Stockfish binary missing or failed to start (mapped to 503/422)."""


class StockfishError(Exception):
    """Stockfish crashed or misbehaved during analysis."""


def resolve_binary(configured_path: str = "") -> str:
    """Return the Stockfish binary path or raise StockfishUnavailableError."""
    if configured_path:
        return configured_path
    found = shutil.which("stockfish")
    if found:
        return found
    raise StockfishUnavailableError(
        "Stockfish binary not found. Install the 'stockfish' package or set STOCKFISH_PATH."
    )


def analyse_position(
    fen: str,
    for_color: Color,
    config: StockfishConfig | None = None,
    engine_config: EngineConfig | None = None,
) -> EngineResult:
    """Analyse a position with Stockfish within bounded resources (BEN-008).

    Returns an EngineResult-compatible struct (move, score, depth, nodes,
    elapsed). Raises StockfishUnavailableError if no binary, StockfishError
    on crash/timeout-misbehavior. Never raises on legal-position input.
    """
    cfg = (config or StockfishConfig()).bounded()
    binary = resolve_binary(cfg.path)
    start = time.time()
    try:
        engine = chess.engine.SimpleEngine.popen_uci(binary)
    except Exception as exc:
        raise StockfishUnavailableError(f"Could not start Stockfish at {binary!r}: {exc}") from exc
    try:
        with contextlib.suppress(chess.engine.EngineError):
            engine.configure({"Threads": cfg.threads, "Hash": cfg.hash_mb})
        board = chess.Board(fen)
        limit = chess.engine.Limit(depth=cfg.max_depth, time=cfg.max_time_ms / 1000.0)
        try:
            result = engine.play(board, limit)
        except chess.engine.EngineTerminatedError as exc:
            raise StockfishError(f"Stockfish terminated during analysis: {exc}") from exc
        elapsed_ms = int((time.time() - start) * 1000)
        move = result.move.uci() if result.move else ""
        info: chess.engine.InfoDict = {}
        try:
            info = engine.analyse(board, limit)  # rich info: score/depth/nodes
        except Exception:
            info = {}
        score = _extract_score(info, board, for_color)
        depth = int(info.get("depth", cfg.max_depth))
        nodes = int(info.get("nodes", 0))
        termination: Literal["completed", "timeout", "cancelled"] = "completed"
        if elapsed_ms > cfg.max_time_ms * 2:
            termination = "timeout"
        _ = engine_config  # reserved: difficulty mapping (AI-022 follow-up)
        return EngineResult(
            best_move=move,
            score=score,
            depth=depth,
            nodes_searched=nodes,
            time_ms=elapsed_ms,
            termination=termination,
        )
    finally:
        with contextlib.suppress(Exception):
            engine.quit()


def _extract_score(info: chess.engine.InfoDict, board: chess.Board, for_color: Color) -> int:
    """Normalize Stockfish score to centipawns from for_color's perspective."""
    score_obj = info.get("score")
    if score_obj is None:
        return 0
    try:
        pov = score_obj.pov(board.turn)
        if pov.is_mate():
            mate_in = pov.mate()
            if mate_in is None:
                return 0
            # Mate scores: large magnitude, sign by side to move (BEN-013).
            value = 20000 - abs(mate_in) * 10
            cp = value if mate_in > 0 else -value
        else:
            cp_obj = pov.score()
            cp = int(cp_obj) if cp_obj is not None else 0
        if (board.turn == chess.WHITE) != (for_color == Color.WHITE):
            cp = -cp
        return cp
    except Exception:
        return 0
