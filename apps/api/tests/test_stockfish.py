"""Tests for the analysis provider seam + Stockfish MultiPV (Phase 9, ANL-001/002/007).

Uses the shared fake UCI engine fixture (conftest) so no Stockfish binary is
required.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import chess
import pytest

from app.engine.provider import AnalyseRequest, AnalysisResult, PrincipalVariation
from app.engine.stockfish import (
    REVIEW_MAX_DEPTH,
    REVIEW_MAX_TIME_MS,
    STOCKFISH_APT_PACKAGE,
    STOCKFISH_APT_VERSION,
    STOCKFISH_MAX_DEPTH,
    STOCKFISH_MAX_TIME_MS,
    STOCKFISH_PACKAGE_PATHS,
    STOCKFISH_STARTUP_ATTEMPTS,
    STOCKFISH_STARTUP_TIMEOUT_S,
    STOCKFISH_UPSTREAM,
    STOCKFISH_UPSTREAM_REPO,
    StockfishConfig,
    StockfishError,
    StockfishProvider,
    StockfishUnavailableError,
    _start_engine,
    analyse_position,
    resolve_binary,
)
from app.games.domain import Color

STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


@pytest.fixture()
def no_stockfish_anywhere(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neither PATH nor the distro-package probe may find an engine."""
    monkeypatch.setenv("PATH", "/nonexistent")
    monkeypatch.setattr("app.engine.stockfish.STOCKFISH_PACKAGE_PATHS", ())


def test_provenance_constants_record_official_source() -> None:
    assert STOCKFISH_UPSTREAM == "https://stockfishchess.org"
    assert STOCKFISH_UPSTREAM_REPO == "https://github.com/official-stockfish/Stockfish"
    assert STOCKFISH_APT_PACKAGE == "stockfish"
    assert STOCKFISH_APT_VERSION  # recorded version string


def test_config_bounds_clamp_depth_time_threads_hash() -> None:
    cfg = StockfishConfig(max_depth=99, max_time_ms=99999, threads=8, hash_mb=9999).bounded()
    assert cfg.max_depth <= 15
    assert cfg.max_time_ms <= 1000
    assert cfg.threads == 1
    assert cfg.hash_mb <= 64


def test_config_bounds_multipv_clamped() -> None:
    assert StockfishConfig(multipv=99).bounded().multipv == 5
    assert StockfishConfig(multipv=0).bounded().multipv == 1


def test_review_bounds_deeper_than_play() -> None:
    play = StockfishConfig(max_depth=99, max_time_ms=99999).bounded()
    review = StockfishConfig(max_depth=99, max_time_ms=99999).bounded(for_review=True)
    assert REVIEW_MAX_DEPTH == 25
    assert REVIEW_MAX_TIME_MS == 5000
    assert review.max_depth == REVIEW_MAX_DEPTH
    assert review.max_time_ms == REVIEW_MAX_TIME_MS
    assert play.max_depth == STOCKFISH_MAX_DEPTH
    assert play.max_time_ms == STOCKFISH_MAX_TIME_MS


def test_missing_binary_raises_unavailable(no_stockfish_anywhere: None) -> None:
    with pytest.raises(StockfishUnavailableError):
        resolve_binary("")


def test_packaged_paths_are_absolute_constants() -> None:
    """The probe list is fixed config, never client input (BEN-020)."""
    assert "/usr/games/stockfish" in STOCKFISH_PACKAGE_PATHS
    assert all(path.startswith("/") for path in STOCKFISH_PACKAGE_PATHS)


def test_finds_packaged_binary_that_sits_off_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Debian/Ubuntu ship the apt binary in /usr/games, which slim images keep
    off PATH — the image that installs Stockfish must still resolve it."""
    monkeypatch.setenv("PATH", "/nonexistent")
    packaged = tmp_path / "stockfish"
    packaged.write_text("#!/bin/sh\n")
    packaged.chmod(0o755)
    monkeypatch.setattr(
        "app.engine.stockfish.STOCKFISH_PACKAGE_PATHS",
        (str(packaged), "/nonexistent/stockfish"),
    )
    assert resolve_binary("") == str(packaged)


def test_configured_path_beats_the_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    """STOCKFISH_PATH is explicit intent and is used verbatim."""
    monkeypatch.setattr("app.engine.stockfish.STOCKFISH_PACKAGE_PATHS", ("/usr/games/stockfish",))
    assert resolve_binary("/opt/custom/stockfish") == "/opt/custom/stockfish"


def test_slow_handshake_is_retried_then_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stalled UCI handshake (bare TimeoutError from python-chess) must get its
    second attempt before the player is told the engine is unavailable."""
    seen: list[float | None] = []

    def always_stall(command: str, *, timeout: float | None = None) -> None:
        seen.append(timeout)
        raise TimeoutError

    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", always_stall)
    monkeypatch.setattr("app.engine.stockfish.STOCKFISH_STARTUP_RETRY_DELAY_S", 0.0)
    with pytest.raises(StockfishUnavailableError):
        _start_engine("/usr/games/stockfish")
    assert len(seen) == STOCKFISH_STARTUP_ATTEMPTS
    # The tolerant timeout is what makes the retry worth having.
    assert seen == [STOCKFISH_STARTUP_TIMEOUT_S] * STOCKFISH_STARTUP_ATTEMPTS


def test_startup_recovers_on_the_retry(fake_binary: str, monkeypatch: pytest.MonkeyPatch) -> None:
    real = chess.engine.SimpleEngine.popen_uci
    state = {"calls": 0}

    def stall_once(command: str, **kwargs: object) -> chess.engine.SimpleEngine:
        state["calls"] += 1
        if state["calls"] == 1:
            raise TimeoutError
        return real(command, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", stall_once)
    monkeypatch.setattr("app.engine.stockfish.STOCKFISH_STARTUP_RETRY_DELAY_S", 0.0)
    engine = _start_engine(fake_binary)
    try:
        assert state["calls"] == 2
    finally:
        engine.quit()


def test_analyse_starting_position_with_fake_binary(fake_binary: str) -> None:
    result = analyse_position(STARTING_FEN, Color.WHITE, StockfishConfig(path=fake_binary))
    assert result.best_move in [m.uci() for m in chess.Board(STARTING_FEN).legal_moves]
    assert result.termination == "completed"
    assert result.time_ms >= 0


def test_analyse_unavailable_binary_raises(no_stockfish_anywhere: None) -> None:
    with pytest.raises(StockfishUnavailableError):
        analyse_position(STARTING_FEN, Color.WHITE, StockfishConfig(path=""))


def test_provider_returns_ranked_multipv_lines(fake_binary: str) -> None:
    provider = StockfishProvider(StockfishConfig(path=fake_binary))
    result = provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=1, multipv=3))
    assert isinstance(result, AnalysisResult)
    assert result.provider == "stockfish"
    assert len(result.lines) == 3
    assert [line.move for line in result.lines] == ["e2e4", "d2d4", "g1f3"]
    assert result.lines[0].score_cp > result.lines[1].score_cp > result.lines[2].score_cp
    assert result.best is not None
    assert result.best.move == "e2e4"
    assert result.best.pv == ("e2e4", "e7e5")


def test_provider_single_line_when_multipv_one(fake_binary: str) -> None:
    provider = StockfishProvider(StockfishConfig(path=fake_binary))
    result = provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=1, multipv=1))
    assert len(result.lines) == 1
    assert isinstance(result.lines[0], PrincipalVariation)


def test_provider_review_mode_uses_deeper_bounds(fake_binary: str) -> None:
    provider = StockfishProvider(StockfishConfig(path=fake_binary), for_review=True)
    result = provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=99, multipv=1))
    assert result.depth <= REVIEW_MAX_DEPTH


def test_provider_unavailable_binary_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "/nonexistent")
    provider = StockfishProvider(StockfishConfig(path=""))
    with pytest.raises(StockfishUnavailableError):
        provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=1, multipv=1))


# --- Warm engine batches (ANL-003) ------------------------------------------------

SECOND_FEN = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"


class _CrashOnceEngine:
    """UCI engine double that dies on the first analysis it is asked for."""

    def __init__(self) -> None:
        self.quit_calls = 0
        self.analyse_calls = 0

    def configure(self, _options: dict[str, object]) -> None:
        pass

    def analyse(self, *_a: object, **_k: object) -> list[object]:
        self.analyse_calls += 1
        if self.analyse_calls == 1:
            raise chess.engine.EngineTerminatedError("process gone")
        return []

    def quit(self) -> None:
        self.quit_calls += 1


def _counting_start(monkeypatch: pytest.MonkeyPatch, engine: object) -> list[str]:
    """Replace process spawn with a counter — the seam warm mode exists to use."""
    calls: list[str] = []

    def fake_start(binary: str) -> object:
        calls.append(binary)
        return engine

    monkeypatch.setattr("app.engine.stockfish._start_engine", fake_start)
    return calls


def test_warm_batch_starts_one_process_for_many_positions(
    fake_binary: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The point of ANL-003: a whole review pass pays engine startup once."""
    real_start = _start_engine
    spawned: list[str] = []

    def counting_start(binary: str) -> chess.engine.SimpleEngine:
        engine = real_start(binary)
        spawned.append(binary)
        return engine

    monkeypatch.setattr("app.engine.stockfish._start_engine", counting_start)
    with StockfishProvider(StockfishConfig(path=fake_binary), for_review=True) as provider:
        first = provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=1, multipv=1))
        second = provider.analyse(AnalyseRequest(fen=SECOND_FEN, depth=1, multipv=1))
        assert provider._engine is not None  # still holding the process mid-batch
    assert spawned == [fake_binary]
    assert first.lines and second.lines


def test_review_mode_without_the_context_manager_stays_per_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`for_review` alone does not hold a process: only entering the provider does,
    so a batch that forgot its `with` still leaks nothing."""
    engine = _CrashOnceEngine()
    calls = _counting_start(monkeypatch, engine)
    provider = StockfishProvider(StockfishConfig(path="/bin/true"), for_review=True)
    with pytest.raises(StockfishError):
        provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=1, multipv=1))
    assert calls == ["/bin/true"]
    assert engine.quit_calls == 1


def test_warm_batch_reuses_the_process_it_started(monkeypatch: pytest.MonkeyPatch) -> None:
    """A crashed engine is replaced, never reused — warm mode keeps the process
    only when the analysis actually succeeded."""
    engine = _CrashOnceEngine()
    calls = _counting_start(monkeypatch, engine)
    with StockfishProvider(StockfishConfig(path="/bin/true"), for_review=True) as provider:
        for _ in range(3):
            with contextlib.suppress(StockfishError):
                provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=1, multipv=1))
    # First call crashed the double, so it was replaced; the rest share that one.
    assert len(calls) == 2
    assert engine.quit_calls == 2  # each retired process got a quit


def test_per_call_mode_starts_a_process_for_every_position(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _CrashOnceEngine()
    calls = _counting_start(monkeypatch, engine)
    provider = StockfishProvider(StockfishConfig(path="/bin/true"))
    for _ in range(2):
        with contextlib.suppress(StockfishError):
            provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=1, multipv=1))
    assert len(calls) == 2
    assert engine.quit_calls == 2


def test_warm_process_is_handled_back_on_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _CrashOnceEngine()
    _counting_start(monkeypatch, engine)
    provider = StockfishProvider(StockfishConfig(path="/bin/true"), for_review=True)
    with provider, contextlib.suppress(StockfishError):
        provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=1, multipv=1))
    assert provider._engine is None
    # close() is idempotent — the review path and the context manager both call it.
    provider.close()


def test_warm_provider_switches_when_the_binary_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _CrashOnceEngine()
    calls = _counting_start(monkeypatch, engine)
    provider = StockfishProvider(StockfishConfig(path="/bin/true"), for_review=True)
    with provider:
        for _ in range(2):
            with contextlib.suppress(StockfishError):
                provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=1, multipv=1))
        provider._config = StockfishConfig(path="/bin/false")
        with contextlib.suppress(StockfishError):
            provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=1, multipv=1))
    assert calls[-1] == "/bin/false"  # not quietly reused from the previous binary
