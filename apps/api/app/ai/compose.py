"""Deterministic answer composer and the cite-only grounding guard.

This is the honest core of the assistant: it turns engine/book facts into a
coach's answer *without any model*, so the reply is fully grounded and always
available. An LLM, when one is configured, is asked to re-phrase these very facts
— and :func:`grounded` throws away anything that names a move it was not given.

Two invariants hold no matter who wrote the sentence:

* every move named traces to a stored fact, a fresh engine line, or the book;
* the deterministic answer is what the user gets when no LLM is present (always,
  in the offline test/CI world).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

import chess

from app.ai.longcontext.context import (
    Reference,
    ReviewFact,
    eval_text,
    material_imbalance,
    position_fen_after,
    san_for_uci,
    side_name,
)
from app.ai.longcontext.whatif import AltLine


class Intent(StrEnum):
    """What the player is actually asking the coach for."""

    SUMMARY = "summary"  # how did the game go, overall
    PLAN = "plan"  # what is the best way to proceed here
    ALTERNATIVES = "alternatives"  # what other ways could this have gone
    POSITION = "position"  # what is on the board / where are the pieces
    EXPLAIN = "explain"  # why was this move a mistake
    PATTERNS = "patterns"  # what do I keep doing wrong across games
    OPENING = "opening"  # opening theory for these positions
    GENERAL = "general"  # anything else: answer with the focus move


@dataclass(frozen=True)
class Composed:
    """A grounded answer ready to send: prose, citations, and the board to show."""

    answer: str
    references: list[Reference]
    position_fen: str


# Word order matters: earlier intents win when a question trips two of them, so
# the most specific signals (across games, else/however) are checked first.
_INTENT_MARKERS: tuple[tuple[Intent, tuple[str, ...]], ...] = (
    (
        Intent.PATTERNS,
        ("keep doing", "always do", "pattern", "across my games", "every game", "often", "tend to"),
    ),
    (
        Intent.OPENING,
        ("opening", "theory", "eco", "variation", "book line", "gambit", "defense"),
    ),
    (
        Intent.ALTERNATIVES,
        ("other way", "else could", "instead", "alternative", "what if", "another line", "or did"),
    ),
    (
        Intent.POSITION,
        (
            "position",
            "on the board",
            "what pieces",
            "material",
            "evaluate the position",
            "describe",
        ),
    ),
    (
        Intent.PLAN,
        ("best", "should i", "proceed", "next move", "what do i do", "plan", "correct"),
    ),
    (
        Intent.EXPLAIN,
        ("why", "explain", "was that", "mistake because", "punish", "because"),
    ),
    (
        Intent.SUMMARY,
        ("summary", "how did", "overall", "go wrong", "turning point", "how'd"),
    ),
)


def detect_intent(question: str) -> Intent:
    """Route a free-text question to one intent by its strongest signal."""
    lowered = question.lower()
    for intent, markers in _INTENT_MARKERS:
        if any(marker in lowered for marker in markers):
            return intent
    return Intent.GENERAL


def _refs(facts: Sequence[ReviewFact], *, game_id: int | None, limit: int = 6) -> list[Reference]:
    seen: set[int] = set()
    refs: list[Reference] = []
    for fact in facts:
        if fact.ply in seen:
            continue
        seen.add(fact.ply)
        refs.append(
            Reference(
                ply=fact.ply,
                san=fact.san,
                color=fact.color,
                note=fact.quality,
                game_id=game_id,
            )
        )
        if len(refs) >= limit:
            break
    return refs


def _own_errors(facts: Sequence[ReviewFact], hero_color: str) -> list[ReviewFact]:
    errors = [f for f in facts if f.color == hero_color and f.quality in ("mistake", "blunder")]
    errors.sort(key=lambda f: f.centipawn_loss, reverse=True)
    return errors


def _hero_eval(fact: ReviewFact, hero_color: str) -> str:
    """The eval after a ply, spoken from the hero's side of the board."""
    cp, mate = fact.eval_cp, fact.eval_mate
    if fact.color != hero_color:
        cp, mate = -cp, None if mate is None else -mate
    return eval_text(cp, mate)


def _best_move(fact: ReviewFact) -> str:
    return san_for_uci(fact.pre_fen, fact.best_uci) or fact.best_uci


def _summary(focus: ReviewFact | None, facts: Sequence[ReviewFact], hero: str) -> str:
    if not facts:
        return "There is no analysed game to summarise yet."
    errors = _own_errors(facts, hero)
    if errors:
        worst = errors[0]
        return (
            f"You played {len(facts)} recorded plies as {side_name(hero)}. "
            f"Your steepest slip was {worst.san} on move {worst.ply} "
            f"({worst.centipawn_loss} cp off best); the position afterward was "
            f"{_hero_eval(worst, hero)}. Start by replaying that move."
        )
    return (
        f"Across {len(facts)} recorded plies as {side_name(hero)}, none of your moves "
        f"were graded a mistake or blunder — you matched the engine's plan."
    )


def _plan(focus: ReviewFact | None, facts: Sequence[ReviewFact], hero: str) -> str:
    if focus is None:
        return _summary(focus, facts, hero)
    if focus.color == hero:
        best = _best_move(focus)
        if best and best != focus.san:
            return (
                f"On move {focus.ply} you played {focus.san}. The engine's line was {best} — "
                f"that is the way to proceed; it left {eval_text(focus.eval_cp, focus.eval_mate)} "
                f"for you versus {focus.centipawn_loss} cp less after your move."
            )
        return (
            f"{focus.san} (move {focus.ply}) already matched the engine's best line — keep the "
            f"plan going; your position stands at {_hero_eval(focus, hero)}."
        )
    # The cursor sits on an opponent ply: the best reply is the next own ply's engine move.
    for later in facts:
        if later.ply > focus.ply and later.color == hero:
            return (
                f"After {side_name(focus.color)}'s {focus.san}, the engine wanted {later.san} "
                f"(move {later.ply}); you played it as {later.quality}. "
                f"That reply left {_hero_eval(later, hero)} for you."
            )
    return f"Against {focus.san}, keep the position balanced — no own reply is recorded after it."


def _alternatives(focus: ReviewFact | None, lines: Sequence[AltLine], hero: str) -> str:
    if focus is None:
        return "Pick a move on the board and I can show how else that position could have gone."
    if not lines:
        return (
            f"On {focus.san} (move {focus.ply}) I have no live engine line to offer right now, "
            f"so I won't guess one — the stored review is what I can speak from."
        )
    rendered = "; ".join(
        (" ".join(line.pv_san))
        + (
            " (forces mate)"
            if line.mate_in_hero is not None
            else f" ({line.score_cp_hero / 100:+.2f})"
        )
        for line in lines[:3]
    )
    return (
        f"From the position before your {focus.san}, the engine's other tries for "
        f"{side_name(hero)} were: {rendered}."
    )


def _position(focus: ReviewFact | None, hero: str) -> str:
    if focus is None:
        return "There is no position on the board to describe yet."
    try:
        board = chess.Board(focus.pre_fen)
    except (ValueError, KeyError):
        board = None
    imbalance = material_imbalance(focus.pre_fen)
    parts = [f"Material balance before {focus.san}: {imbalance / 100:+.2f} for White."]
    if board is not None:
        parts.append(f"{side_name('w' if board.turn == chess.WHITE else 'b')} to move")
        parts.append("(you are in check)" if board.is_check() else "(checks are not on you)")
    parts.append(f"your eval here {_hero_eval(focus, hero)}")
    return "Position on move " + str(focus.ply) + ": " + ", ".join(parts) + "."


def _explain(focus: ReviewFact | None, facts: Sequence[ReviewFact], hero: str) -> str:
    if focus is None:
        return "Select a move on the board and I'll explain what the engine thought of it."
    note = focus.explanation or f"It was graded {focus.quality}."
    best = _best_move(focus)
    extra = f" The engine preferred {best}." if best and best != focus.san else ""
    return (
        f"{focus.san} (move {focus.ply}, {focus.quality}) — {note}{extra} "
        f"It left your position at {_hero_eval(focus, hero)}."
    )


_NO_RECALL = (
    "I don't have enough of your cross-game history indexed to generalise yet "
    "— review more games to build it up."
)


def _recall_or_empty(recall_block: str) -> str:
    return recall_block or _NO_RECALL


def compose(
    intent: Intent,
    focus: ReviewFact | None,
    facts: Sequence[ReviewFact],
    hero: str,
    lines: Sequence[AltLine] = (),
    *,
    recall_block: str = "",
    game_id: int | None = None,
) -> Composed:
    """Build a fully grounded answer from facts alone (no model involved)."""
    if intent is Intent.PATTERNS or intent is Intent.OPENING:
        answer = _recall_or_empty(recall_block)
        refs = _refs([focus] if focus else [], game_id=game_id)
    elif intent is Intent.ALTERNATIVES:
        answer = _alternatives(focus, lines, hero)
        refs = _refs([focus] if focus else [], game_id=game_id)
    elif intent is Intent.POSITION:
        answer = _position(focus, hero)
        refs = _refs([focus] if focus else [], game_id=game_id)
    elif intent is Intent.PLAN:
        answer = _plan(focus, facts, hero)
        refs = _refs(
            [f for f in facts if f.color == hero and f.quality in ("mistake", "blunder")][:2]
            + ([focus] if focus else []),
            game_id=game_id,
        )
    elif intent is Intent.EXPLAIN:
        answer = _explain(focus, facts, hero)
        refs = _refs([focus] if focus else [], game_id=game_id)
    elif intent is Intent.SUMMARY:
        answer = _summary(focus, facts, hero)
        refs = _refs(_own_errors(facts, hero)[:3], game_id=game_id)
    else:  # GENERAL: explain the focus move, or summarise when nothing is selected
        answer = _explain(focus, facts, hero) if focus else _summary(focus, facts, hero)
        refs = _refs([focus] if focus else _own_errors(facts, hero)[:1], game_id=game_id)

    position = (
        position_fen_after(focus) if focus else (position_fen_after(facts[-1]) if facts else "")
    )
    return Composed(answer=answer, references=refs, position_fen=position)


# SAN-shaped token, scanned case-insensitively: a piece move ([KQRBN] + optional
# disambiguation/capture + a full destination square), an explicit pawn promotion
# (e8=Q), or a capture to a full square (exd5). A bare "e5" is deliberately NOT
# matched — in prose it is indistinguishable from noise, so only unambiguous
# move tokens are held to the cite-only rule (piece letters never start a word).
_SAN_RE = re.compile(
    r"\b(?:[KQRBN][a-h]?[x:-]?[a-h]?[1-8]|e[1-8]=[QRBN]|[a-h]x[a-h][1-8])\b",
    re.IGNORECASE,
)


def allowed_tokens_from(facts: Sequence[ReviewFact], lines: Sequence[AltLine] = ()) -> set[str]:
    """The only move-names a model may utter: played, best, and the live lines.

    Both the exact SAN and its uppercase form are allowed, so a pawn move echoed
    in either case ("e5" / "E5") passes while an invented piece move is rejected.
    """
    allowed: set[str] = set()
    for san in (f.san for f in facts if f.san):
        allowed.update((san, san.upper()))
    for fact in facts:
        if fact.best_uci:
            best = san_for_uci(fact.pre_fen, fact.best_uci)
            if best:
                allowed.update((best, best.upper()))
    for line in lines:
        for san in line.pv_san:
            if san:
                allowed.update((san, san.upper()))
    return allowed


def grounded(text: str, allowed: set[str]) -> bool:
    """Whether a model answer names only moves it was given (cite-only guard).

    Any unambiguous SAN-shaped token outside the allowed set means the model
    invented chess, and the caller discards its prose for the deterministic
    answer. Plain prose (words that are not move tokens) is unconstrained.
    """
    if not text:
        return False
    for token in _SAN_RE.findall(text):
        if token not in allowed and token.upper() not in allowed:
            return False
    return True
