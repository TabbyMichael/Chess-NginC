"""Long-context facts: the whole stored review of one game, read into memory.

The stored payload (`game_reviews.payload`) is already the ground truth for a
single game — every ply with its grade, eval, best line and coaching note. It is
small enough to hold whole, so this module turns it into tidy `ReviewFact` records
and packs them into text for the composer (and, when one is configured, the LLM).

No engine, no database, no HTTP: pure functions over the payload dict. Opening
names are *derived* here through the offline book (they are never stored in the
payload), exactly the way the review API derives them on the way out.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import chess

from app.openings import book

# Material values in centipawns, for "what is actually on the board" descriptions.
_PLY_WINDOW = 6  # half-width of the neighbourhood packed around the focused ply


@dataclass(frozen=True)
class ReviewFact:
    """One graded ply, as the assistant sees it (mover-perspective evals)."""

    ply: int
    move_number: int
    san: str
    uci: str
    pre_fen: str
    color: str  # 'w' | 'b' — the mover, matching the stored payload
    quality: str
    centipawn_loss: int
    best_uci: str
    eval_cp: int
    eval_mate: int | None
    explanation: str
    opening_family: str = ""  # derived on read from the book, e.g. 'Sicilian Defense'


@dataclass(frozen=True)
class Reference:
    """A single cited move: the grounding a coach answer always points back to."""

    ply: int
    san: str
    color: str
    note: str = ""
    game_id: int | None = None


def _int_or_none(value: object) -> int | None:
    """Coerce a stored JSON scalar to an int, or None when it is not one.

    The review payload is read with `dict.get`, so the value is `object`; a bool
    is never a ply/eval, and only digit strings are accepted as numeric.
    """
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lstrip("-").isdigit():
        return int(value)
    return None


def facts_from_payload(moves: Sequence[object]) -> list[ReviewFact]:
    """Convert stored review entries into `ReviewFact`s, deriving opening names.

    Defensive like the rest of the review read path: an entry that is not a dict,
    has no SAN, or has no usable ply is skipped rather than poisoning the pack.
    """
    facts: list[ReviewFact] = []
    for entry in moves:
        if not isinstance(entry, dict):
            continue
        san = str(entry.get("san") or "")
        ply = _int_or_none(entry.get("ply"))
        if not san or ply is None:
            continue
        pre_fen = str(entry.get("pre_fen") or "")
        uci = str(entry.get("uci") or "")
        family = ""
        opening = book.opening_after(pre_fen, uci)
        if opening is not None:
            family = opening.family
        facts.append(
            ReviewFact(
                ply=ply,
                move_number=_int_or_none(entry.get("move_number")) or 0,
                san=san,
                uci=uci,
                pre_fen=pre_fen,
                color=str(entry.get("color") or "w"),
                quality=str(entry.get("quality") or ""),
                centipawn_loss=_int_or_none(entry.get("centipawn_loss")) or 0,
                best_uci=str(entry.get("best_uci") or ""),
                eval_cp=_int_or_none(entry.get("eval_cp")) or 0,
                eval_mate=_int_or_none(entry.get("eval_mate")),
                explanation=str(entry.get("explanation") or ""),
                opening_family=family,
            )
        )
    return facts


def eval_text(cp: int, mate: int | None) -> str:
    """Human eval from the mover's perspective: '#' for mate, pawns otherwise."""
    if mate is not None:
        return f"mate in {abs(mate)}"
    return f"{cp / 100:+.2f}"


def material_imbalance(fen: str) -> int:
    """White-minus-Black material in centipawns for a FEN; 0 when unreadable."""
    values = {"p": 100, "n": 300, "b": 300, "r": 500, "q": 900, "k": 0}
    try:
        board = chess.Board(fen)
    except (ValueError, KeyError):
        return 0
    total = 0
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None:
            continue
        value = values.get(piece.symbol().lower(), 0)
        total += value if piece.color == chess.WHITE else -value
    return total


def side_name(color: str) -> str:
    """Display name for 'w'/'b' (anything else reads as White)."""
    return "Black" if color == "b" else "White"


def position_fen_after(fact: ReviewFact) -> str:
    """FEN the ply left on the board (the position to show for this fact)."""
    try:
        board = chess.Board(fact.pre_fen)
        board.push(chess.Move.from_uci(fact.uci))
    except (ValueError, KeyError):
        return fact.pre_fen
    return board.fen()


def san_for_uci(fen: str, uci: str) -> str:
    """SAN of a UCI move played from `fen`, or '' when it is not legal there.

    The stored `best_uci` has no SAN next to it; recovering it lets an answer say
    "instead of Nf6, play d4" instead of the raw engine coordinates.
    """
    if not uci:
        return ""
    try:
        board = chess.Board(fen)
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            return ""
        return board.san(move)
    except (ValueError, KeyError):
        return ""


def find_focus_ply(
    facts: Sequence[ReviewFact],
    focus_ply: int | None,
    hero_color: str,
    question: str,
) -> int | None:
    """Which ply the question is about: explicit, then board move, then worst own.

    An explicit `focus_ply` (the cursor on the review page) always wins. Failing
    that, a SAN mentioned in the question anchors the answer; failing that, the
    hero's biggest loss is the most useful thing to talk about.
    """
    if focus_ply is not None:
        for fact in facts:
            if fact.ply == focus_ply:
                return fact.ply
    upper = question.upper()
    for fact in facts:
        if fact.san and fact.san.upper() in upper:
            return fact.ply
    own = [f for f in facts if f.color == hero_color and f.quality in ("mistake", "blunder")]
    if own:
        return max(own, key=lambda f: f.centipawn_loss).ply
    return facts[-1].ply if facts else None


def fact_by_ply(facts: Sequence[ReviewFact], ply: int | None) -> ReviewFact | None:
    if ply is None:
        return None
    return next((f for f in facts if f.ply == ply), None)


def reference_for(fact: ReviewFact, *, note: str = "", game_id: int | None = None) -> Reference:
    return Reference(
        ply=fact.ply, san=fact.san, color=fact.color, note=note or fact.quality, game_id=game_id
    )


def _compact_line(fact: ReviewFact, hero_color: str) -> str:
    """One line of the long-context pack: who moved, the grade and the eval."""
    is_hero = fact.color == hero_color
    star = " *" if is_hero else ""
    eval_part = eval_text(fact.eval_cp, fact.eval_mate)
    loss_part = f", {fact.centipawn_loss}cp off best" if is_hero else ""
    return (
        f"{fact.ply}. {side_name(fact.color)} {fact.san}{star} "
        f"[{fact.quality}, {eval_part}{loss_part}]"
    )


def full_review_pack(
    facts: Sequence[ReviewFact], hero_color: str, *, max_plies: int | None = None
) -> tuple[str, list[ReviewFact]]:
    """Pack the whole game into long-context text (bounded by `max_plies`).

    Returns the text and the facts actually included, so references and the
    grounding set always describe exactly what the answer was built from.
    """
    included = list(facts[:max_plies]) if max_plies else list(facts)
    if not included:
        return "", []
    errors = [f for f in included if f.quality in ("mistake", "blunder")]
    head = [
        f"Reviewing {side_name(hero_color)}'s moves (marked *).",
        f"{len(included)} plies; {len(errors)} own mistakes/blunders.",
    ]
    lines = [
        _compact_line(f, hero_color)
        + (f" — best was {san_for_uci(f.pre_fen, f.best_uci) or f.best_uci}" if f.best_uci else "")
        for f in included
    ]
    notes = [f"Note {f.ply} ({f.san}): {f.explanation}" for f in included if f.explanation]
    text = "\n".join([*head, *lines, *notes])
    return text, included


def retrieval_pack(
    facts: Sequence[ReviewFact], focus_ply: int | None, hero_color: str
) -> tuple[str, list[Reference]]:
    """A tight window around the focused ply, for a specific 'this move' question.

    Includes the neighbourhood on both sides so 'what should I have done instead'
    can see the reply the engine expected, but never the whole game.
    """
    if not facts:
        return "", []
    anchor = focus_ply if focus_ply is not None else facts[-1].ply
    window = [f for f in facts if abs(f.ply - anchor) <= _PLY_WINDOW]
    lines = [_compact_line(f, hero_color) for f in window]
    refs = [reference_for(f) for f in window]
    return "\n".join(lines), refs


def allowed_move_strings(facts: Sequence[ReviewFact], extra: Sequence[str] = ()) -> set[str]:
    """Every SAN the answer is allowed to name: played, best, and engine lines.

    This is the grounding set for the cite-only guard — the model may rearrange
    these but never introduce a move that is not here.
    """
    allowed: set[str] = set(extra)
    for fact in facts:
        allowed.add(fact.san)
        if fact.best_uci:
            best_san = san_for_uci(fact.pre_fen, fact.best_uci)
            if best_san:
                allowed.add(best_san)
    return {token for token in allowed if token}


def pack_references(facts: Sequence[ReviewFact], hero_color: str) -> list[Reference]:
    """Citations for a full pack: the hero's own biggest errors, worst first."""
    errors = [f for f in facts if f.color == hero_color and f.quality in ("mistake", "blunder")]
    errors.sort(key=lambda f: f.centipawn_loss, reverse=True)
    return [reference_for(f, note=f.quality) for f in errors]
