"""Derived per-ply fields for a stored review (REVIEW-008).

The analysis payload holds engine facts — grade, eval, best line — and those are
frozen when a review is written. The opening name and the win expectancy are
*derived* from those facts instead, computed on the way out of the API, so:

* games already analysed on an install light up without a re-analysis pass;
* there is no second copy of the theory book inside every stored payload;
* no migration is needed for a field that is a pure function of others.

`eval_cp` / `eval_mate` in the payload are from the **mover's** point of view,
while the expectancy this module emits is from **White's**, because the review
graph, the eval bar and the UI all speak White-up.
"""

from __future__ import annotations

from app.engine.win_probability import win_pct
from app.openings.book import Opening, opening_after


def _white_view_expectancy(entry: dict) -> int | None:
    """Win expectancy for White from one mover-perspective ply entry."""
    cp = entry.get("eval_cp")
    mate = entry.get("eval_mate")
    if cp is None and mate is None:
        return None
    mover_is_white = entry.get("color") == "w"
    signed_cp = int(cp or 0)
    signed_mate = int(mate) if mate else None
    if not mover_is_white:
        signed_cp = -signed_cp
        signed_mate = -signed_mate if signed_mate is not None else None
    return win_pct(signed_cp, signed_mate)


def annotate_moves(moves: list[dict]) -> list[dict]:
    """Return copies of ``moves`` with opening and expectancy fields added.

    A book name sticks once found: theory only names a position once the line is
    established, so the ply that leaves the book still belongs to the opening
    that got there. ``in_book`` says which of the two this ply is.
    """
    annotated: list[dict] = []
    deepest: Opening | None = None
    for entry in moves:
        item = dict(entry)
        found = opening_after(str(item.get("pre_fen") or ""), str(item.get("uci") or ""))
        if found is not None:
            deepest = found
        item["opening_eco"] = deepest.eco if deepest else None
        item["opening_name"] = deepest.name if deepest else None
        item["in_book"] = found is not None
        item["win_pct"] = _white_view_expectancy(item)
        annotated.append(item)
    return annotated
