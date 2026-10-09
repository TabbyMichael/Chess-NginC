"""Tests for the custom chess engine."""

import chess

from app.engine.domain import EngineConfig, EngineDifficulty, EngineResult
from app.engine.engine import ChessEngine
from app.engine.evaluator import evaluate_position
from app.games.domain import Color


def test_engine_config_defaults() -> None:
    config = EngineConfig()
    assert config.difficulty == EngineDifficulty.MEDIUM
    assert config.max_depth == 3
    assert config.max_time_ms == 5000


def test_engine_config_custom() -> None:
    config = EngineConfig(difficulty=EngineDifficulty.HARD, max_depth=5, max_time_ms=10000)
    assert config.difficulty == EngineDifficulty.HARD
    assert config.max_depth == 5
    assert config.max_time_ms == 10000


def test_evaluate_starting_position() -> None:
    board = chess.Board()
    score = evaluate_position(board, Color.WHITE)
    assert score == 0  # Equal material


def test_evaluate_material_advantage() -> None:
    board = chess.Board()
    board.remove_piece_at(chess.E2)  # Remove white pawn
    score = evaluate_position(board, Color.WHITE)
    assert score < 0  # Black has material advantage


def test_evaluate_checkmate() -> None:
    # Fool's mate position
    board = chess.Board()
    for move in ["f2f3", "e7e5", "g2g4", "d8h4"]:
        board.push_uci(move)
    score = evaluate_position(board, Color.WHITE)
    assert score < -10000  # White is checkmated


def test_evaluate_stalemate() -> None:
    board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    score = evaluate_position(board, Color.WHITE)
    assert score == 0


def test_engine_search_starting_position() -> None:
    engine = ChessEngine(EngineConfig(max_depth=2))
    board = chess.Board()
    result = engine.search(board, Color.WHITE)
    assert result.best_move in [m.uci() for m in board.legal_moves]
    assert result.depth == 2
    assert result.nodes_searched > 0
    assert result.termination == "completed"


def test_engine_search_checkmate_position() -> None:
    engine = ChessEngine(EngineConfig(max_depth=3))
    board = chess.Board()
    # Fool's mate - one move from mate
    for move in ["f2f3", "e7e5", "g2g4"]:
        board.push_uci(move)
    result = engine.search(board, Color.BLACK)
    assert result.best_move == "d8h4"  # The mating move
    assert result.score > 10000


def test_engine_search_no_legal_moves() -> None:
    engine = ChessEngine(EngineConfig(max_depth=2))
    board = chess.Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")  # Stalemate
    result = engine.search(board, Color.BLACK)
    assert result.best_move == ""
    assert result.termination == "completed"


def test_engine_cancel() -> None:
    engine = ChessEngine(EngineConfig(max_depth=10, max_time_ms=1))  # Very short time
    board = chess.Board()
    engine.cancel()
    result = engine.search(board, Color.WHITE)
    # Either cancelled or timeout is acceptable for this test
    assert result.termination in ["cancelled", "timeout"]


def test_engine_nodes_searched_increases() -> None:
    engine = ChessEngine(EngineConfig(max_depth=2))
    board = chess.Board()
    result = engine.search(board, Color.WHITE)
    assert result.nodes_searched > 0


def test_engine_result_structure() -> None:
    result = EngineResult(
        best_move="e2e4",
        score=100,
        depth=3,
        nodes_searched=1000,
        time_ms=100,
        termination="completed",
    )
    assert result.best_move == "e2e4"
    assert result.score == 100
    assert result.depth == 3
    assert result.nodes_searched == 1000
    assert result.time_ms == 100
    assert result.termination == "completed"
