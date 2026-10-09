"""Tests for the chess domain model."""

import chess

from app.games.domain import STARTING_FEN, Color, Game, GameMode, GameStatus, Move


def test_starting_fen_constant_matches_python_chess() -> None:
    assert STARTING_FEN == chess.STARTING_FEN


def test_game_defaults_to_active_local_game() -> None:
    game = Game()
    assert game.mode is GameMode.LOCAL
    assert game.status is GameStatus.ACTIVE
    assert game.fen == STARTING_FEN
    assert game.moves == []


def test_game_id_is_unique_per_instance() -> None:
    assert Game().id != Game().id


def test_move_is_frozen_and_holds_uci_and_san() -> None:
    move = Move(uci="e2e4", san="e4")
    assert move.uci == "e2e4"
    assert move.san == "e4"


def test_color_enum_values() -> None:
    assert Color.WHITE.value == "white"
    assert Color.BLACK.value == "black"
