"""Stockfish UCI adapter (Phase 7, BEN-004..007).

Isolated behind the engine interface: bounded execution (depth/time caps),
graceful handling of missing binaries and crashes. Never imported by the
custom search engine; only services/benchmark harnesses use it.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import time
from dataclasses import dataclass
from typing import Literal

import chess
import chess.engine

from app.engine.domain import EngineConfig, EngineResult
from app.engine.provider import (
    AnalyseRequest,
    AnalysisResult,
    PrincipalVariation,
)
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

# Engine startup: a cold process has to handshake and load its eval network, and
# on a busy container that can outlast python-chess' 10 s default — it then raises
# a bare TimeoutError and the player gets a 503 for a perfectly good engine. Allow
# a longer handshake and one bounded retry so a transient stall does not fail the
# move. Warm batches (ANL-003) pay this once per pass instead of once per position.
STOCKFISH_STARTUP_TIMEOUT_S = 20.0
STOCKFISH_STARTUP_ATTEMPTS = 2
STOCKFISH_STARTUP_RETRY_DELAY_S = 0.25

# Review bounds (ANL-007): post-game analysis may search deeper/longer than
# live play. Still bounded — never unbounded. Play path uses the tight bounds.
REVIEW_MAX_DEPTH = 25
REVIEW_MAX_TIME_MS = 5000


@dataclass(frozen=True)
class StockfishConfig:
    """Configuration for the Stockfish UCI adapter."""

    path: str = ""  # absolute path to binary; empty = auto-detect via PATH
    max_depth: int = 10
    max_time_ms: int = 500
    threads: int = 1
    hash_mb: int = 16
    multipv: int = 1  # ANL-002: principal variations to return (1-5)

    def bounded(self, *, for_review: bool = False) -> StockfishConfig:
        """Return a copy clamped to the hard resource bounds.

        Review analyses (ANL-007) get deeper bounds than live play so
        post-game truth is stronger while interactive play stays snappy.
        """
        max_depth = REVIEW_MAX_DEPTH if for_review else STOCKFISH_MAX_DEPTH
        max_time = REVIEW_MAX_TIME_MS if for_review else STOCKFISH_MAX_TIME_MS
        return StockfishConfig(
            path=self.path,
            max_depth=max(1, min(self.max_depth, max_depth)),
            max_time_ms=max(1, min(self.max_time_ms, max_time)),
            threads=1,  # single-threaded: keep concurrency bounded (TD-007)
            hash_mb=max(1, min(self.hash_mb, 64)),
            multipv=max(1, min(self.multipv, 5)),
        )


class StockfishUnavailableError(Exception):
    """Stockfish binary missing or failed to start (mapped to 503/422)."""


class StockfishError(Exception):
    """Stockfish crashed or misbehaved during analysis."""


# Distro packages do not always land on PATH: Debian/Ubuntu install Stockfish to
# /usr/games/stockfish, and slim container images keep /usr/games off PATH — so an
# image that ships the package can still report it missing. Probing these
# well-known locations makes that image work with zero configuration. They are
# constants, never client input (BEN-020); an explicit STOCKFISH_PATH still wins.
STOCKFISH_PACKAGE_PATHS: tuple[str, ...] = (
    "/usr/games/stockfish",  # Debian/Ubuntu apt package
    "/usr/bin/stockfish",  # Alpine / Homebrew / symlinked installs
    "/usr/local/bin/stockfish",
    "/opt/homebrew/bin/stockfish",  # macOS Homebrew on Apple Silicon
)


class StockfishProvider:
    """Stockfish-backed EngineProvider (ANL-001/ANL-002/ANL-007).

    Two lifetimes behind one seam: used bare, each `analyse` opens and retires a
    process; used as a context manager, one warm process serves the whole batch
    (ANL-003) — which is what a review pass is.
    """

    name = "stockfish"

    def __init__(self, config: StockfishConfig | None = None, *, for_review: bool = False) -> None:
        self._config = config or StockfishConfig()
        self._for_review = for_review
        # Warm mode (ANL-003): inside `with`, one process serves every analyse in
        # the batch instead of paying startup + eval-net load per position.
        self._warm = False
        self._engine: chess.engine.SimpleEngine | None = None
        self._engine_binary = ""

    def __enter__(self) -> StockfishProvider:
        """Reuse one engine process for the calls that follow (a review pass).

        The instance belongs to this batch and this thread: it is not shared
        across requests and not safe to use concurrently.
        """
        self._warm = True
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._warm = False
        self.close()

    def close(self) -> None:
        """Quit the held process, if any. Idempotent (EngineProvider contract)."""
        engine, self._engine, self._engine_binary = self._engine, None, ""
        if engine is not None:
            with contextlib.suppress(Exception):
                engine.quit()

    def _acquire(self, binary: str) -> chess.engine.SimpleEngine:
        """The shared process when warm, a freshly started one when not."""
        if self._engine is not None and self._engine_binary != binary:
            # The configured engine changed under us: start over rather than
            # quietly keep talking to a different binary.
            self.close()
        if self._engine is None:
            self._engine = _start_engine(binary)
            self._engine_binary = binary
        return self._engine

    def analyse(self, request: AnalyseRequest) -> AnalysisResult:
        """Analyse a position, returning up to ``multipv`` ranked lines."""
        cfg = StockfishConfig(
            path=self._config.path,
            max_depth=request.depth,
            max_time_ms=request.max_time_ms,
            threads=self._config.threads,
            hash_mb=self._config.hash_mb,
            multipv=request.multipv,
        ).bounded(for_review=self._for_review)
        binary = resolve_binary(cfg.path)
        start = time.time()
        engine = self._acquire(binary)
        completed = False
        try:
            with contextlib.suppress(chess.engine.EngineError):
                engine.configure(
                    {"Threads": cfg.threads, "Hash": cfg.hash_mb, "MultiPV": cfg.multipv}
                )
            board = chess.Board(request.fen)
            limit = chess.engine.Limit(depth=cfg.max_depth, time=cfg.max_time_ms / 1000.0)
            try:
                infos = engine.analyse(board, limit, multipv=cfg.multipv)
            except chess.engine.EngineTerminatedError as exc:
                raise StockfishError(f"Stockfish terminated during analysis: {exc}") from exc
            elapsed_ms = int((time.time() - start) * 1000)
            if isinstance(infos, dict):
                infos = [infos]
            dict_infos = [info for info in infos if isinstance(info, dict)]
            lines = tuple(_line_from_info(info, board, request.for_color) for info in dict_infos)
            depth = max(
                (int(i.get("depth", cfg.max_depth)) for i in dict_infos), default=cfg.max_depth
            )
            nodes = max((int(i.get("nodes", 0)) for i in dict_infos), default=0)
            completed = True
            return AnalysisResult(
                fen=request.fen,
                lines=lines,
                depth=depth,
                nodes_searched=nodes,
                time_ms=elapsed_ms,
                provider=self.name,
            )
        finally:
            # Per-call mode always hands the process back; warm mode keeps it
            # alive only when the analysis actually succeeded, so a crashed
            # engine is replaced on the next position instead of reused.
            if not self._warm or not completed:
                self.close()


def _line_from_info(
    info: chess.engine.InfoDict, board: chess.Board, for_color: Color
) -> PrincipalVariation:
    """Convert one MultiPV info dict to a PrincipalVariation (side-to-move POV)."""
    pv_moves = info.get("pv") or []
    move = pv_moves[0].uci() if pv_moves else ""
    score_obj = info.get("score")
    score_cp, mate_in = _score_parts(score_obj, board, for_color)
    return PrincipalVariation(
        move=move,
        score_cp=score_cp,
        mate_in=mate_in,
        pv=tuple(m.uci() for m in pv_moves),
    )


def _score_parts(
    score_obj: chess.engine.PovScore | None, board: chess.Board, for_color: Color
) -> tuple[int, int | None]:
    """Normalize a POV score to (centipawns, mate_in) from for_color's view."""
    if score_obj is None:
        return 0, None
    try:
        pov = score_obj.pov(board.turn)
        if pov.is_mate():
            mate_in = pov.mate()
            if mate_in is None:
                return 0, None
            value = 20000 - abs(mate_in) * 10
            cp = value if mate_in > 0 else -value
            if (board.turn == chess.WHITE) != (for_color == Color.WHITE):
                cp = -cp
                mate_in = -mate_in
            return cp, mate_in
        cp_obj = pov.score()
        cp = int(cp_obj) if cp_obj is not None else 0
        if (board.turn == chess.WHITE) != (for_color == Color.WHITE):
            cp = -cp
        return cp, None
    except Exception:
        return 0, None


def resolve_binary(configured_path: str = "") -> str:
    """Return the Stockfish binary path or raise StockfishUnavailableError."""
    if configured_path:
        return configured_path
    found = shutil.which("stockfish")
    if found:
        return found
    for candidate in STOCKFISH_PACKAGE_PATHS:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    raise StockfishUnavailableError(
        "Stockfish binary not found. Install the 'stockfish' package or set STOCKFISH_PATH."
    )


def _start_engine(binary: str) -> chess.engine.SimpleEngine:
    """Open a UCI engine with a tolerant, bounded startup (see bounds above).

    Only the *startup* is retried — an engine that dies mid-analysis stays a
    StockfishError, because replaying a search is not the same failure.
    """
    last: Exception | None = None
    for attempt in range(STOCKFISH_STARTUP_ATTEMPTS):
        try:
            return chess.engine.SimpleEngine.popen_uci(binary, timeout=STOCKFISH_STARTUP_TIMEOUT_S)
        except Exception as exc:
            last = exc
            if attempt + 1 < STOCKFISH_STARTUP_ATTEMPTS:
                time.sleep(STOCKFISH_STARTUP_RETRY_DELAY_S)
    raise StockfishUnavailableError(f"Could not start Stockfish at {binary!r}: {last}")


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
    engine = _start_engine(binary)
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
