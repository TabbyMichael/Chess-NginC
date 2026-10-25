"""Move-quality classifier (REVIEW-002).

Pure chess judgment: given the engine's best line and the line the player
actually played (both from the mover's perspective), assign a Chess.com-style
grade. No HTTP, no DB — the review service feeds this from provider output
and stores the result.

Grades, from the mover's view:
  brilliant  best move AND a material sacrifice (chess.com-style sparkly)
  best       the engine's top choice
  excellent  near-best loss (< 10 cp)
  good       small loss (< 50 cp)
  inaccuracy moderate loss (< 150 cp)
  mistake    large loss (< 400 cp)
  blunder    huge loss, or throwing away a forced mate
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

# Centipawn loss thresholds, strictly ascending (upper bound of each band).
EXCELLENT_CP = 10
GOOD_CP = 50
INACCURACY_CP = 150
MISTAKE_CP = 400
# A mate score is worth ~∞ cp; used to blend mate distances into thresholds.
MATE_CP = 100_000


class MoveQuality(StrEnum):
    """The seven grades shown on the review board."""

    BRILLIANT = "brilliant"
    BEST = "best"
    EXCELLENT = "excellent"
    GOOD = "good"
    INACCURACY = "inaccuracy"
    MISTAKE = "mistake"
    BLUNDER = "blunder"


@dataclass(frozen=True)
class MoveContext:
    """Extra chess facts that can upgrade/downgrade a grade."""

    is_forced: bool = False  # only legal move in the position
    captures_value_cp: int = 0  # material gained by the move (p100 n300 b300 r500 q900)
    was_checked: bool = False  # the mover was in check before playing


def _mate_to_cp(mate_in: int) -> int:
    """Signed centipawn value of a mate distance (+ = mover gets mated)."""
    if mate_in > 0:
        return MATE_CP - (mate_in - 1) * 1000
    return -MATE_CP - (mate_in + 1) * 1000


def centipawn_loss(
    best_cp: int,
    played_cp: int,
    best_mate: int | None = None,
    played_mate: int | None = None,
) -> int:
    """Loss vs the engine's top line, from the mover's perspective.

    Mate distances dominate centipawns: any drop from a forced mate to a
    non-mate (or to a slower mate) is a colossal loss by construction.
    """
    best = _mate_to_cp(best_mate) if best_mate is not None else best_cp
    played = _mate_to_cp(played_mate) if played_mate is not None else played_cp
    return max(0, best - played)


def classify_move(
    loss_cp: int,
    played_is_best: bool,
    context: MoveContext | None = None,
) -> MoveQuality:
    """Grade one already-computed centipawn loss.

    `played_is_best` short-circuits to best/brilliant: the engine's top line
    can never be a mistake. Forced moves (no real choice) are graded as good
    at worst — the player had no alternative to be judged against.
    """
    ctx = context or MoveContext()
    if played_is_best:
        # A sacrifice that the engine endorses as top is the sparkly one.
        if ctx.captures_value_cp >= 300 and loss_cp == 0 and not ctx.is_forced:
            return MoveQuality.BRILLIANT
        return MoveQuality.BEST
    if ctx.is_forced:
        return MoveQuality.GOOD
    if loss_cp >= MISTAKE_CP:
        return MoveQuality.BLUNDER
    if loss_cp >= INACCURACY_CP:
        return MoveQuality.MISTAKE
    if loss_cp >= GOOD_CP:
        return MoveQuality.INACCURACY
    if loss_cp >= EXCELLENT_CP:
        return MoveQuality.GOOD
    return MoveQuality.EXCELLENT
