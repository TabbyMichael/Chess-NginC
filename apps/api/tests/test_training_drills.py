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


def test_catalog_is_at_least_750_across_all_themes() -> None:
    assert len(DRILLS) > 750
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


def test_every_sequence_drill_forces_a_win() -> None:
    """Multi-move puzzles: a genuinely long, unambiguous, winning forced line.

    Replays each ``moves`` line from the start FEN and asserts, ply by ply, that
    every own move is legal, every opponent reply is forced (exactly one legal
    move — which is what makes the line deterministic and the win honest without
    an engine), the position does not resolve before the last player move, and it
    ends in checkmate or a decisive material gain.
    """
    for drill in _by_theme("sequence"):
        moves = drill.moves
        assert len(moves) >= 3 and len(moves) % 2 == 1, f"{drill.key}: bad line shape"
        assert drill.solution == moves[0], f"{drill.key}: solution != first line ply"
        board = chess.Board(drill.fen)
        mover = board.turn
        before = material_balance(board)
        last = len(moves) - 1
        for i, uci in enumerate(moves):
            move = chess.Move.from_uci(uci)
            assert move in board.legal_moves, f"{drill.key}: ply {i} {uci} illegal"
            if i % 2 == 1:
                assert len(list(board.legal_moves)) == 1, f"{drill.key}: reply {i} not forced"
            board.push(move)
            if i < last:
                assert not (board.is_checkmate() or board.is_stalemate()), (
                    f"{drill.key}: resolves early at ply {i}"
                )
        gained = material_balance(board)
        gained = gained - before if mover == chess.WHITE else before - gained
        assert board.is_checkmate() or gained >= 100, f"{drill.key}: no mate or gain"


def _flipped(board: chess.Board) -> chess.Board:
    fields = board.fen().split(" ")
    fields[1] = "w" if fields[1] == "b" else "b"
    fields[2] = "-"
    fields[3] = "-"
    return chess.Board(" ".join(fields))
