"""Walkable lines: turn engine PVs and recorded plies into board steps.

A coach answer is only useful if the player can *see* the idea, not just read it.
This module materialises a variation as an ordered list of `LineStep`s — each a
real move with the FEN before and after it — so the front end can drive the board
through it one ply at a time.

Two honest sources, both grounded:

* :func:`played_line` stitches plies the player actually recorded (always
  available, even offline — it reads only the stored review);
* :func:`engine_line` replays a live engine principal variation (present only
  when an engine answered the what-if pass).

Both validate every push and truncate at the first illegal move, so a stale
cached FEN yields a shorter true line rather than a fabricated one.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import chess

from app.ai.longcontext.context import (
    ReviewFact,
    eval_text,
    position_fen_after,
)
from app.ai.longcontext.whatif import AltLine


@dataclass(frozen=True)
class LineStep:
    """One move of a walkable variation, with the board before and after it."""

    san: str
    uci: str
    color: str  # 'w' | 'b' — the mover of this step
    fen_before: str
    fen_after: str
    comment: str
    source: str  # 'played' | 'engine'
    ply: int | None  # recorded ply when this maps back to the game, else None


def _board(fen: str) -> chess.Board | None:
    try:
        return chess.Board(fen)
    except (ValueError, KeyError):
        return None


def _colour(board: chess.Board) -> str:
    return "w" if board.turn == chess.WHITE else "b"


def best_alt(lines: Sequence[AltLine]) -> AltLine | None:
    """The top-ranked alternative (the engine's preferred continuation)."""
    return lines[0] if lines else None


def played_line(facts: Sequence[ReviewFact], from_ply: int, *, limit: int = 8) -> list[LineStep]:
    """Stitch the recorded plies from ``from_ply`` forward into board steps.

    Uses only stored facts, so it works with no engine; a ply whose move is not
    legal on its own recorded position ends the line there rather than corrupting
    the walk.
    """
    steps: list[LineStep] = []
    for fact in facts:
        if fact.ply < from_ply:
            continue
        board = _board(fact.pre_fen)
        if board is None:
            break
        try:
            move = chess.Move.from_uci(fact.uci)
        except ValueError:
            break
        if move not in board.legal_moves:
            break
        steps.append(
            LineStep(
                san=fact.san,
                uci=fact.uci,
                color=fact.color,
                fen_before=fact.pre_fen,
                fen_after=position_fen_after(fact),
                comment=f"{fact.quality}, {eval_text(fact.eval_cp, fact.eval_mate)}".strip(", "),
                source="played",
                ply=fact.ply,
            )
        )
        if len(steps) >= limit:
            break
    return steps


def engine_line(start_fen: str, alt: AltLine, *, limit: int = 8) -> list[LineStep]:
    """Replay an engine principal variation from ``start_fen`` into board steps.

    The first step carries the engine's verdict in its comment; the walk stops at
    the first move that is not legal in the position it is played from.
    """
    board = _board(start_fen)
    if board is None:
        return []
    verdict = (
        f"engine: forces mate ({alt.mate_in_hero:+d})"
        if alt.mate_in_hero is not None
        else f"engine: {alt.score_cp_hero / 100:+.2f}"
    )
    steps: list[LineStep] = []
    for index, uci in enumerate(alt.pv_uci[:limit]):
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            break
        if move not in board.legal_moves:
            break
        san = board.san(move)
        color = _colour(board)
        fen_before = board.fen()
        board.push(move)
        steps.append(
            LineStep(
                san=san,
                uci=uci,
                color=color,
                fen_before=fen_before,
                fen_after=board.fen(),
                comment=verdict if index == 0 else "",
                source="engine",
                ply=None,
            )
        )
    return steps


def line_from_alt(
    start_fen: str,
    alt: AltLine | None,
    facts: Sequence[ReviewFact],
    from_ply: int,
    *,
    limit: int = 8,
) -> list[LineStep]:
    """Engine line when a live variation exists, else the recorded continuation.

    This is the single decision the composer makes so the board always has a
    truthful line to walk: prefer the engine's idea, fall back to what was played.
    """
    if alt is not None and alt.pv_uci:
        engine = engine_line(start_fen, alt, limit=limit)
        if engine:
            return engine
    return played_line(facts, from_ply, limit=limit)
