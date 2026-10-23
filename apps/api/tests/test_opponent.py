"""Stockfish opponent seam tests (PLAY-001..003).

All against the shared fake UCI engine (conftest) — CI never needs a real
Stockfish binary, but the answers must be legal for the side to move.
"""

import chess
import pytest

from app.engine.opponent import _difficulty_depth, stockfish_move
from app.games.domain import Color
from app.games.errors import EngineUnavailableError

STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def test_difficulty_depth_clamped_to_play_range() -> None:
    assert _difficulty_depth(None) == 4
    assert _difficulty_depth(0) == 1
    assert _difficulty_depth(6) == 6
    assert _difficulty_depth(99) == 8


def test_stockfish_move_is_legal_for_side_to_move(fake_binary: str) -> None:
    board = chess.Board(STARTING_FEN)
    move = stockfish_move(board, Color.WHITE, max_depth=2, max_time_ms=200)
    assert move.uci in [m.uci() for m in board.legal_moves]
    assert move.depth >= 1


def test_stockfish_move_answers_for_black_too(fake_binary: str) -> None:
    board = chess.Board(STARTING_FEN)
    board.push(chess.Move.from_uci("e2e4"))
    move = stockfish_move(board, Color.BLACK, max_depth=2, max_time_ms=200)
    assert move.uci in [m.uci() for m in board.legal_moves]


def test_stockfish_move_missing_binary_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "/nonexistent")
    with pytest.raises(EngineUnavailableError):
        stockfish_move(chess.Board(STARTING_FEN), Color.WHITE)
