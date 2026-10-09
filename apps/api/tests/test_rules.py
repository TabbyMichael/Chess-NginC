"""Tests for the ChessRules adapter over python-chess."""

import pytest

from app.games.domain import STARTING_FEN, Color, GameStatus, Move
from app.games.errors import IllegalMoveError, InvalidMoveError
from app.games.rules import ChessRules


def test_initial_fen_is_starting_position() -> None:
    assert ChessRules().fen == STARTING_FEN
    assert ChessRules.initial_fen() == STARTING_FEN


def test_initial_position_has_twenty_legal_moves() -> None:
    assert len(ChessRules().legal_move_ucis) == 20


def test_turn_is_white_at_start() -> None:
    assert ChessRules().turn is Color.WHITE


def test_parse_and_apply_legal_move() -> None:
    rules = ChessRules()
    move = rules.apply_move("e2e4")
    assert move == Move(uci="e2e4", san="e4")
    assert rules.turn is Color.BLACK


def test_apply_move_updates_fen() -> None:
    rules = ChessRules()
    rules.apply_move("e2e4")
    assert rules.fen == "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"


def test_is_legal_true_for_legal_move() -> None:
    assert ChessRules().is_legal("e2e4") is True


def test_is_legal_false_for_illegal_move() -> None:
    assert ChessRules().is_legal("e2e5") is False


def test_apply_illegal_move_raises() -> None:
    rules = ChessRules()
    with pytest.raises(IllegalMoveError):
        rules.apply_move("e2e5")


def test_parse_invalid_uci_raises() -> None:
    rules = ChessRules()
    for bad in ("not-a-move", "e9e4", "", "e2"):
        with pytest.raises(InvalidMoveError):
            rules.apply_move(bad)


def test_status_active_at_start() -> None:
    assert ChessRules().status() is GameStatus.ACTIVE


def test_is_check_false_at_start() -> None:
    assert ChessRules().is_check() is False


def test_status_detects_checkmate() -> None:
    # Fool's mate: 1. f3 e5 2. g4 Qh4#
    rules = ChessRules()
    for uci in ("f2f3", "e7e5", "g2g4", "d8h4"):
        rules.apply_move(uci)
    assert rules.is_check() is True
    assert rules.status() is GameStatus.CHECKMATE


def test_status_detects_stalemate() -> None:
    rules = ChessRules("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    assert rules.is_check() is False
    assert rules.status() is GameStatus.STALEMATE


def test_san_for_promotion() -> None:
    rules = ChessRules("8/P7/8/8/8/8/8/1k5K w - - 0 1")
    move = rules.apply_move("a7a8q")
    assert move == Move(uci="a7a8q", san="a8=Q")


def test_san_for_castling() -> None:
    rules = ChessRules("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    move = rules.apply_move("e1g1")
    assert move.san == "O-O"
