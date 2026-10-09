"""Tests for special moves: castling, en passant, and promotion."""

import pytest

from app.games.domain import Move
from app.games.errors import IllegalMoveError
from app.games.rules import ChessRules

CASTLING_FEN = "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"
PROMOTION_FEN = "8/P7/8/8/8/8/8/1k5K w - - 0 1"


def test_kingside_castle() -> None:
    rules = ChessRules(CASTLING_FEN)
    move = rules.apply_move("e1g1")
    assert move == Move(uci="e1g1", san="O-O")


def test_queenside_castle() -> None:
    rules = ChessRules(CASTLING_FEN)
    move = rules.apply_move("e1c1")
    assert move == Move(uci="e1c1", san="O-O-O")


def test_castle_while_in_check_is_illegal() -> None:
    # Black rook on e2 gives check to the white king on e1.
    rules = ChessRules("r3k2r/8/8/8/8/8/4r3/R3K2R w KQkq - 0 1")
    assert rules.is_legal("e1g1") is False
    with pytest.raises(IllegalMoveError):
        rules.apply_move("e1g1")


def test_castle_without_rights_is_illegal() -> None:
    rules = ChessRules("r3k2r/8/8/8/8/8/8/R3K2R w - - 0 1")
    assert rules.is_legal("e1g1") is False


def test_en_passant_capture() -> None:
    rules = ChessRules()
    for uci in ("e2e4", "a7a6", "e4e5", "d7d5"):
        rules.apply_move(uci)
    assert rules.is_legal("e5d6") is True
    move = rules.apply_move("e5d6")
    assert move == Move(uci="e5d6", san="exd6")


def test_en_passant_lost_after_other_move() -> None:
    rules = ChessRules()
    for uci in ("e2e4", "a7a6", "e4e5", "d7d5", "g1f3", "b7b6"):
        rules.apply_move(uci)
    assert rules.is_legal("e5d6") is False


def test_promotion_to_queen() -> None:
    rules = ChessRules(PROMOTION_FEN)
    move = rules.apply_move("a7a8q")
    assert move == Move(uci="a7a8q", san="a8=Q")


@pytest.mark.parametrize(
    ("promotion", "san"),
    [("n", "a8=N"), ("r", "a8=R"), ("b", "a8=B")],
)
def test_underpromotion(promotion: str, san: str) -> None:
    rules = ChessRules(PROMOTION_FEN)
    move = rules.apply_move(f"a7a8{promotion}")
    assert move == Move(uci=f"a7a8{promotion}", san=san)


@pytest.mark.parametrize("uci", ["a7a8", "a7a8k"])
def test_invalid_promotion_is_illegal(uci: str) -> None:
    rules = ChessRules(PROMOTION_FEN)
    with pytest.raises(IllegalMoveError):
        rules.apply_move(uci)
