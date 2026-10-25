"""Walkable-line tests (Phase 11b): lines must be legal and FEN-correct offline.

A coach answer is only trustworthy if the variation it puts on the board is real.
These tests prove the two line sources — the recorded plies and a live engine PV —
stitch into steps whose FENs chain move-to-move, that an illegal step truncates the
walk rather than corrupting it, and that with no engine the line honestly degrades to
what was actually played. No binary, no key, no network.
"""

import chess

from app.ai.longcontext.context import facts_from_payload
from app.ai.longcontext.lines import engine_line, line_from_alt, played_line
from app.ai.longcontext.whatif import AltLine
from app.games.domain import STARTING_FEN

AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"


def _payload() -> list[dict]:
    return [
        {
            "ply": 1,
            "move_number": 1,
            "uci": "e2e4",
            "san": "e4",
            "pre_fen": STARTING_FEN,
            "color": "w",
            "quality": "best",
            "centipawn_loss": 0,
            "best_uci": "e2e4",
            "eval_cp": 20,
            "eval_mate": None,
            "explanation": "e4 is exactly what the engine wants.",
        },
        {
            "ply": 2,
            "move_number": 1,
            "uci": "e7e5",
            "san": "e5",
            "pre_fen": AFTER_E4,
            "color": "b",
            "quality": "good",
            "centipawn_loss": 25,
            "best_uci": "c7c5",
            "eval_cp": -20,
            "eval_mate": None,
            "explanation": "e5 is solid, just off the best line.",
        },
    ]


def test_played_line_stitches_legal_steps_with_chaining_fens() -> None:
    facts = facts_from_payload(_payload())
    steps = played_line(facts, 1, limit=8)
    assert [s.san for s in steps] == ["e4", "e5"]
    assert steps[0].fen_before == STARTING_FEN
    # Each step's after-position holds the same pieces the next step starts from
    # (compared by layout, since the stored pre-FEN may carry an ep square the
    # recomputed after-FEN legitimately drops).
    assert str(chess.Board(steps[0].fen_after)) == str(chess.Board(steps[1].fen_before))
    assert steps[0].source == "played" and steps[0].ply == 1
    # Every emitted FEN is a real, parseable board (after e4 e5 it is White to move).
    assert chess.Board(steps[-1].fen_after).turn == chess.WHITE


def test_played_line_starts_from_the_requested_ply() -> None:
    facts = facts_from_payload(_payload())
    steps = played_line(facts, 2)
    assert [s.san for s in steps] == ["e5"]


def test_played_line_respects_the_limit() -> None:
    facts = facts_from_payload(_payload())
    assert len(played_line(facts, 1, limit=1)) == 1


def test_engine_line_truncates_at_the_first_illegal_pv_move() -> None:
    alt = AltLine(
        san="e5",
        uci="e7e5",
        score_cp_hero=20,
        mate_in_hero=None,
        pv_san=("e5", "??"),
        pv_uci=("e7e5", "e1e1"),  # e1-e1 is never a legal push
    )
    steps = engine_line(AFTER_E4, alt, limit=8)
    # Only the first (legal) move survives; the walk stops at the illegality.
    assert len(steps) == 1
    assert steps[0].san == "e5"
    assert steps[0].source == "engine"
    assert steps[0].ply is None
    assert steps[0].comment.startswith("engine")


def test_engine_line_is_empty_for_an_unparseable_start() -> None:
    alt = AltLine(
        san="e5",
        uci="e7e5",
        score_cp_hero=20,
        mate_in_hero=None,
        pv_san=("e5",),
        pv_uci=("e7e5",),
    )
    assert engine_line("not a real fen", alt) == []


def test_line_from_alt_falls_back_to_played_without_an_engine() -> None:
    facts = facts_from_payload(_payload())
    # With no live PV (the offline default), the honest line is what was recorded.
    steps = line_from_alt(AFTER_E4, None, facts, 2)
    assert steps and steps[0].san == "e5"
    assert steps[0].source == "played"


def test_line_from_alt_prefers_a_live_engine_variation() -> None:
    facts = facts_from_payload(_payload())
    alt = AltLine(
        san="d6",
        uci="d7d6",
        score_cp_hero=30,
        mate_in_hero=None,
        pv_san=("d6",),
        pv_uci=("d7d6",),
    )
    steps = line_from_alt(AFTER_E4, alt, facts, 2)
    assert steps[0].source == "engine"
    assert steps[0].san == "d6"
