"""Win expectancy from an engine score (ANL-004).

Turns the centipawn/mate score the review already stores into a single 1..99
number the UI can show, so "how good is this position for me" survives being
taken out of the eval bar.

Honesty note, in one place on purpose: this is an **engine expectancy** — the
score probability a logistic on the Elo equivalent of the eval implies — not a
measured win rate for the opening from millions of games. It says what the
position is worth, not what people happen to score with it.

Pure arithmetic: no engine, no database, no HTTP.
"""

from __future__ import annotations

# One pawn of eval is worth about 200 Elo of expectancy. Deliberately
# conservative: the alternative (1 pawn = 400 Elo) claims a 91% score for a
# single pawn, which no master data supports.
ELO_PER_CENTIPOWN = 2.0
# A mate in five or less is effectively decided; longer mates are still close.
MATE_DECISIVE_MOVES = 5
MATE_DECISIVE_PCT = 99
MATE_FAR_PCT = 95
# Expectancy is displayed as a chance, and no position is literally certain.
MIN_PCT = 1
MAX_PCT = 99


def _clamp(pct: int) -> int:
    return max(MIN_PCT, min(MAX_PCT, pct))


def win_pct(cp: int, mate: int | None = None) -> int:
    """White's win expectancy (1..99) for a score from White's perspective.

    ``mate`` follows the engine convention: positive means White forces mate in
    ``abs(mate)`` moves, negative means Black does. When it is present it wins
    over ``cp``, since a forced mate is not a large number of pawns.
    """
    if mate:
        near = abs(mate) <= MATE_DECISIVE_MOVES
        pct = MATE_DECISIVE_PCT if near else MATE_FAR_PCT
        return pct if mate > 0 else 100 - pct

    # Solve the positive side once and mirror it: rounding the magnitude keeps
    # the curve exactly symmetric, so `win_pct(-cp) == 100 - win_pct(cp)`.
    edge = abs(cp) * ELO_PER_CENTIPOWN / 400.0
    upper = int(round(100 * (1.0 / (1.0 + 10.0**-edge))))
    return _clamp(upper if cp >= 0 else 100 - upper)
