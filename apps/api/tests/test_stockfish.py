"""Tests for the Stockfish UCI adapter (BEN-004..007).

Uses a fake UCI engine script so no Stockfish binary is required.
"""

import stat
import sys
from pathlib import Path

import chess
import pytest

from app.engine.stockfish import (
    STOCKFISH_APT_PACKAGE,
    STOCKFISH_APT_VERSION,
    STOCKFISH_UPSTREAM,
    STOCKFISH_UPSTREAM_REPO,
    StockfishConfig,
    StockfishUnavailableError,
    analyse_position,
    resolve_binary,
)
from app.games.domain import Color

STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

FAKE_UCI = """#!/usr/bin/env -S {python} -u
import sys
def main():
    for line in sys.stdin:
        line = line.strip()
        if line == "uci":
            print("id name FakeStockfish")
            print("id author test")
            print("option name Threads type spin default 1 min 1 max 1")
            print("option name Hash type spin default 16 min 1 max 64")
            print("uciok")
        elif line == "isready":
            print("readyok")
        elif line.startswith("setoption"):
            pass
        elif line.startswith("position"):
            pass
        elif line.startswith("go"):
            print("info depth 1 score cp 20 nodes 10 time 1")
            print("bestmove e2e4")
        elif line == "quit":
            return
        sys.stdout.flush()
main()
"""


@pytest.fixture()
def fake_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    script = tmp_path / "fake-stockfish"
    script.write_text(FAKE_UCI.format(python=sys.executable))
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", str(tmp_path))
    return str(script)


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


def test_missing_binary_raises_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "/nonexistent")
    with pytest.raises(StockfishUnavailableError):
        resolve_binary("")


def test_analyse_starting_position_with_fake_binary(fake_binary: str) -> None:
    result = analyse_position(STARTING_FEN, Color.WHITE, StockfishConfig(path=fake_binary))
    assert result.best_move in [m.uci() for m in chess.Board(STARTING_FEN).legal_moves]
    assert result.termination == "completed"
    assert result.time_ms >= 0


def test_analyse_unavailable_binary_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "/nonexistent")
    with pytest.raises(StockfishUnavailableError):
        analyse_position(STARTING_FEN, Color.WHITE, StockfishConfig(path=""))
