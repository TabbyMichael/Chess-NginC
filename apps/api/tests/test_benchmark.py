"""Tests for the benchmark harness (BEN-009..013, BEN-018, BEN-022).

Reference engine is stubbed: repeatability and regression tests must not
require a Stockfish binary.
"""

import chess

from app.engine import benchmark as bench_mod
from app.engine.benchmark import (
    agreement_rate,
    compare_position,
    hardware_fingerprint,
    mean_score_gap,
    stockfish_version_label,
)
from app.engine.benchmark_suite import BENCHMARK_POSITIONS, BENCHMARK_SUITE_VERSION, get_suite
from app.engine.domain import EngineConfig, EngineResult
from app.engine.stockfish import StockfishConfig


def test_suite_is_versioned_and_valid() -> None:
    assert BENCHMARK_SUITE_VERSION == "v1"
    positions = get_suite()
    assert len(positions) >= 10
    for fen, _desc in positions:
        board = chess.Board(fen)  # raises on invalid FEN
        assert len(list(board.legal_moves)) > 0


def test_compare_position_without_reference_binary(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("PATH", "/nonexistent")
    fen = BENCHMARK_POSITIONS[0][0]
    comp = compare_position(
        fen,
        custom_config=EngineConfig(max_depth=1, max_time_ms=500),
        reference_config=StockfishConfig(path=""),
    )
    assert comp.fen == fen
    assert comp.custom_move in [m.uci() for m in chess.Board(fen).legal_moves]
    assert comp.reference_move == ""
    assert comp.moves_agree is False


def test_compare_position_with_stubbed_reference(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def fake_analyse(fen: str, for_color, config=None, engine_config=None) -> EngineResult:  # type: ignore[no-untyped-def]
        return EngineResult(
            best_move="e2e4",
            score=20,
            depth=10,
            nodes_searched=100,
            time_ms=5,
            termination="completed",
        )

    monkeypatch.setattr(bench_mod, "analyse_position", fake_analyse)
    comp = compare_position(
        BENCHMARK_POSITIONS[0][0], custom_config=EngineConfig(max_depth=1, max_time_ms=500)
    )
    assert comp.reference_move == "e2e4"
    assert comp.reference_score == 20
    assert comp.reference_depth == 10


def test_agreement_and_gap_metrics() -> None:
    comps = (
        bench_mod.PositionComparison(
            fen="f",
            custom_move="e2e4",
            custom_score=10,
            custom_depth=1,
            custom_nodes=5,
            custom_time_ms=1,
            reference_move="e2e4",
            reference_score=20,
            reference_depth=2,
            reference_nodes=9,
            reference_time_ms=2,
            moves_agree=True,
            score_gap_cp=10,
        ),
        bench_mod.PositionComparison(
            fen="g",
            custom_move="d2d4",
            custom_score=0,
            custom_depth=1,
            custom_nodes=5,
            custom_time_ms=1,
            reference_move="e2e4",
            reference_score=50,
            reference_depth=2,
            reference_nodes=9,
            reference_time_ms=2,
            moves_agree=False,
            score_gap_cp=50,
        ),
    )
    assert agreement_rate(comps) == 0.5
    assert mean_score_gap(comps) == 30.0
    assert agreement_rate(()) == 0.0
    assert mean_score_gap(()) == 0.0


def test_repeatability_custom_engine_deterministic() -> None:
    """Same config + position → same custom move (BEN-022)."""
    fen = BENCHMARK_POSITIONS[1][0]
    cfg = EngineConfig(max_depth=2, max_time_ms=2000)
    ref = StockfishConfig(path="/nope")
    first = compare_position(fen, custom_config=cfg, reference_config=ref)
    second = compare_position(fen, custom_config=cfg, reference_config=ref)
    assert first.custom_move == second.custom_move


def test_hardware_and_version_labels_recorded() -> None:
    assert hardware_fingerprint()
    assert "stockfish" in stockfish_version_label()
