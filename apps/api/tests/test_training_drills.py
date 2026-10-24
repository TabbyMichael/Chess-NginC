"""Drill catalog soundness (LEARN-001).

The single most important guarantee for hand-authored content: every position
does what its theme claims, proved by python-chess at test time. A new or edited
drill that is unsound fails this test rather than quietly mis-teaching a player.
"""

from __future__ import annotations

import chess

from app.training.drills import DRILLS, THEME_ORDER
from app.training.verify import (
    mate_in_one_exists,
    material_balance,
    verify_all,
)


def _by_theme(theme: str) -> list:
    return [d for d in DRILLS if d.theme == theme]


def test_catalog_is_at_least_300_across_all_themes() -> None:
    assert len(DRILLS) > 300
    assert {d.theme for d in DRILLS} == set(THEME_ORDER)
    for theme in THEME_ORDER:
        rows = _by_theme(theme)
        assert len(rows) >= 3, f"{theme} needs three levels"
        assert {d.level for d in rows} >= {1, 2, 3}, f"{theme} lacks an easy->hard ramp"


def test_keys_are_unique() -> None:
    keys = [d.key for d in DRILLS]
    assert len(keys) == len(set(keys))


def test_verify_all_is_clean() -> None:
    # The load-bearing guarantee for a generated catalog: every position, curated
    # or machine-built, does what its theme claims. This is what makes generating
    # hundreds of drills safe rather than a source of quietly wrong puzzles.
    assert verify_all(DRILLS) == []


def test_every_mate_drill_delivers_checkmate() -> None:
    for drill in _by_theme("mate"):
        board = chess.Board(drill.fen)
        board.push(chess.Move.from_uci(drill.solution))
        assert board.is_checkmate(), f"{drill.key} does not mate"


def test_every_material_drill_gains_at_least_a_pawn() -> None:
    material = (
        _by_theme("hanging")
        + _by_theme("fork")
        + _by_theme("pin")
        + _by_theme("skewer")
        + _by_theme("discovered")
        + _by_theme("endgame")
    )
    for drill in material:
        board = chess.Board(drill.fen)
        mover = board.turn
        before = material_balance(board)
        board.push(chess.Move.from_uci(drill.solution))
        for uci in drill.line:
            board.push(chess.Move.from_uci(uci))
        after = material_balance(board)
        gain = after - before if mover == chess.WHITE else before - after
        assert gain >= 100, f"{drill.key} nets only {gain}"


def test_every_backrank_drill_defuses_a_real_mate() -> None:
    for drill in _by_theme("backrank"):
        board = chess.Board(drill.fen)
        # Opponent, if it were their move, could mate before the escape...
        threat = _flipped(board)
        assert mate_in_one_exists(threat), f"{drill.key} had no mate threat to escape"
        # ...and cannot any more after it.
        board.push(chess.Move.from_uci(drill.solution))
        assert not mate_in_one_exists(_flipped(board)), f"{drill.key} escape fails"


def _flipped(board: chess.Board) -> chess.Board:
    fields = board.fen().split(" ")
    fields[1] = "w" if fields[1] == "b" else "b"
    fields[2] = "-"
    fields[3] = "-"
    return chess.Board(" ".join(fields))
