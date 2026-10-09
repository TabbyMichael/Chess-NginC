"""Tests for the ChessRules adapter over python-chess."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.games.domain import STARTING_FEN, Color, GameStatus, Move
from app.games.errors import IllegalMoveError, InvalidFenError, InvalidMoveError
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


def test_validate_fen_accepts_valid_position() -> None:
    ChessRules.validate_fen(STARTING_FEN)  # does not raise
    assert ChessRules.is_valid_fen(STARTING_FEN) is True


@pytest.mark.parametrize(
    "fen",
    [
        "",
        "invalid",
        "8/8/8/8/8/8/8 w - - 0 1",
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR x KQkq - 0 1",
    ],
)
def test_validate_fen_rejects_invalid_position(fen: str) -> None:
    with pytest.raises(InvalidFenError):
        ChessRules.validate_fen(fen)
    assert ChessRules.is_valid_fen(fen) is False


def test_init_with_invalid_fen_raises() -> None:
    with pytest.raises(InvalidFenError):
        ChessRules("invalid")


def test_fen_round_trip() -> None:
    rules = ChessRules()
    for uci in ("e2e4", "e7e5", "g1f3"):
        rules.apply_move(uci)
    fen = rules.fen
    replayed = ChessRules(fen)
    assert replayed.fen == fen
    assert replayed.turn is Color.BLACK


def test_status_detects_fifty_move_rule() -> None:
    # Position after 50 moves without pawn move or capture
    rules = ChessRules("r1bqkbnr/pppppppp/2n5/8/8/5N2/PPPPPPPP/R1BQKB1R w KQkq - 99 50")
    assert rules.status() is GameStatus.DRAW


def test_status_detects_threefold_repetition() -> None:
    # Known threefold repetition position (knight dance)
    rules = ChessRules()
    # Repeat the same position three times
    moves = [
        "g1f3",
        "g8f6",
        "f3g1",
        "f6g8",
        "g1f3",
        "g8f6",
        "f3g1",
        "f6g8",
        "g1f3",
        "g8f6",
        "f3g1",
        "f6g8",
    ]
    for uci in moves:
        rules.apply_move(uci)
    assert rules.status() is GameStatus.DRAW


def test_replay_moves_applies_sequence() -> None:
    rules = ChessRules()
    moves = rules.replay_moves(["e2e4", "e7e5", "g1f3"])
    assert len(moves) == 3
    assert moves[0] == Move(uci="e2e4", san="e4")
    assert moves[1] == Move(uci="e7e5", san="e5")
    assert moves[2] == Move(uci="g1f3", san="Nf3")
    assert rules.turn is Color.BLACK


def test_replay_moves_empty_list() -> None:
    rules = ChessRules()
    moves = rules.replay_moves([])
    assert moves == []
    assert rules.turn is Color.WHITE


def test_replay_moves_invalid_move_raises() -> None:
    rules = ChessRules()
    with pytest.raises(IllegalMoveError):
        rules.replay_moves(["e2e4", "e2e5"])


def test_undo_move_reverts_last_move() -> None:
    rules = ChessRules()
    rules.apply_move("e2e4")
    undone = rules.undo_move()
    assert undone.uci == "e2e4"
    assert rules.fen == STARTING_FEN
    assert rules.turn is Color.WHITE


def test_undo_move_multiple_times() -> None:
    rules = ChessRules()
    rules.replay_moves(["e2e4", "e7e5", "g1f3"])
    rules.undo_move()
    assert rules.turn is Color.WHITE
    rules.undo_move()
    assert rules.turn is Color.BLACK
    rules.undo_move()
    assert rules.fen == STARTING_FEN


def test_undo_move_when_no_moves_raises() -> None:
    rules = ChessRules()
    with pytest.raises(ValueError, match="No moves to undo"):
        rules.undo_move()


def test_verify_invariants_valid_starting_position() -> None:
    rules = ChessRules()
    assert rules.verify_invariants() == []


def test_verify_invariants_after_legal_moves() -> None:
    rules = ChessRules()
    rules.replay_moves(["e2e4", "e7e5", "g1f3", "b8c6"])
    assert rules.verify_invariants() == []


def test_verify_invariants_after_special_moves() -> None:
    # Test after castling and promotion
    rules = ChessRules("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    rules.apply_move("e1g1")  # Kingside castling
    assert rules.verify_invariants() == []

    rules = ChessRules("8/P7/8/8/8/8/8/1k5K w - - 0 1")
    rules.apply_move("a7a8q")  # Promotion
    assert rules.verify_invariants() == []


def test_edge_case_empty_move_list_replay() -> None:
    rules = ChessRules()
    moves = rules.replay_moves([])
    assert moves == []
    assert rules.fen == STARTING_FEN


def test_edge_case_long_move_sequence() -> None:
    rules = ChessRules()
    # Replay a longer sequence to ensure no state corruption
    moves = ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "a7a6", "e1g1"]
    result = rules.replay_moves(moves)
    assert len(result) == 7
    assert rules.verify_invariants() == []


def test_edge_case_status_checkmate_after_many_moves() -> None:
    # Ensure status detection works after many moves
    rules = ChessRules()
    # Scholar's mate in UCI notation
    moves = ["e2e4", "e7e5", "f1c4", "b8c6", "d1h5", "g8f6", "h5f7"]
    rules.replay_moves(moves)
    assert rules.status() is GameStatus.CHECKMATE


def test_edge_case_turn_alternation() -> None:
    rules = ChessRules()
    assert rules.turn is Color.WHITE
    rules.apply_move("e2e4")
    assert rules.turn is Color.BLACK
    rules.apply_move("e7e5")
    assert rules.turn is Color.WHITE
    # Undo should restore turn
    rules.undo_move()
    assert rules.turn is Color.BLACK
    rules.undo_move()
    assert rules.turn is Color.WHITE


def test_edge_case_fen_persistence_through_undo() -> None:
    rules = ChessRules()
    original_fen = rules.fen
    rules.apply_move("e2e4")
    rules.undo_move()
    assert rules.fen == original_fen


@given(st.sampled_from(["e2e4", "d2d4", "g1f3", "b1c3"]))
def test_property_legal_move_is_in_legal_moves(uci: str) -> None:
    """Any move that is_legal should be in legal_move_ucis."""
    rules = ChessRules()
    if rules.is_legal(uci):
        assert uci in rules.legal_move_ucis


@given(st.integers(min_value=0, max_value=19))
def test_property_legal_moves_count_at_start(_index: int) -> None:
    """Starting position always has exactly 20 legal moves."""
    rules = ChessRules()
    assert len(rules.legal_move_ucis) == 20


def test_property_apply_legal_move_succeeds() -> None:
    """Applying a legal move should not raise."""
    rules = ChessRules()
    for uci in rules.legal_move_ucis:
        new_rules = ChessRules()
        new_rules.apply_move(uci)  # Should not raise


def test_property_undo_restore_fen() -> None:
    """Undoing a move should restore the previous FEN."""
    rules = ChessRules()
    original_fen = rules.fen
    for uci in rules.legal_move_ucis[:5]:  # Test first 5 legal moves
        test_rules = ChessRules()
        test_rules.apply_move(uci)
        test_rules.undo_move()
        assert test_rules.fen == original_fen


def test_terminal_checkmate_fools_mate() -> None:
    """Fool's mate terminal position."""
    rules = ChessRules()
    rules.replay_moves(["f2f3", "e7e5", "g2g4", "d8h4"])
    assert rules.status() is GameStatus.CHECKMATE
    assert rules.is_check() is True


def test_terminal_stalemate() -> None:
    """Stalemate terminal position."""
    rules = ChessRules("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    assert rules.status() is GameStatus.STALEMATE
    assert rules.is_check() is False


def test_terminal_insufficient_material_kk() -> None:
    """King vs King is insufficient material."""
    rules = ChessRules("8/4k3/8/8/8/8/4K3/8 w - - 0 1")
    assert rules.status() is GameStatus.DRAW


def test_terminal_insufficient_material_kb() -> None:
    """King + Bishop vs King is insufficient material."""
    rules = ChessRules("8/4k3/8/8/8/8/4KB2/8 w - - 0 1")
    assert rules.status() is GameStatus.DRAW


def test_special_move_castling_kingside() -> None:
    """Kingside castling preserves invariants."""
    rules = ChessRules("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    move = rules.apply_move("e1g1")
    assert move.san == "O-O"
    assert rules.verify_invariants() == []


def test_special_move_castling_queenside() -> None:
    """Queenside castling preserves invariants."""
    rules = ChessRules("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    move = rules.apply_move("e1c1")
    assert move.san == "O-O-O"
    assert rules.verify_invariants() == []


def test_special_move_en_passant_capture() -> None:
    """En passant capture works correctly."""
    rules = ChessRules("rnbqkbnr/ppp1pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 3")
    move = rules.apply_move("e5d6")
    assert "x" in move.san  # Capture notation
    assert rules.verify_invariants() == []


def test_special_move_promotion_to_queen() -> None:
    """Promotion to queen."""
    rules = ChessRules("8/P7/8/8/8/8/8/1k5K w - - 0 1")
    move = rules.apply_move("a7a8q")
    assert move.san == "a8=Q"
    assert rules.verify_invariants() == []


def test_special_move_promotion_to_knight() -> None:
    """Underpromotion to knight."""
    rules = ChessRules("8/P7/8/8/8/8/8/1k5K w - - 0 1")
    move = rules.apply_move("a7a8n")
    assert move.san == "a8=N"
    assert rules.verify_invariants() == []
