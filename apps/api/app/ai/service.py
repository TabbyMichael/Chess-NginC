"""Coach assistant service: assemble an answer from long context + RAG + engine.

One function owns the whole pipeline: load the caller's completed review, read
every ply into a long-context pack, recall cross-game facts (RAG) when the
question is about patterns/openings, run a bounded live engine pass when the
question is about *other ways this could go*, then compose a grounded answer.

The optional LLM is applied on top by :func:`answer` and is thrown away unless it
names only moves it was given (the cite-only guard). Everything degrades to the
deterministic composer, so an answer is always produced from real engine facts.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai.compose import (
    Intent,
    allowed_tokens_from,
    compose,
    detect_intent,
    grounded,
)
from app.ai.longcontext.context import (
    Reference,
    ReviewFact,
    fact_by_ply,
    facts_from_payload,
    find_focus_ply,
    full_review_pack,
)
from app.ai.longcontext.whatif import AltLine, alternative_lines
from app.ai.provider import AssistantUnavailableError, open_chat_provider
from app.ai.rag import recall
from app.core.database import settings
from app.models.game_review import GameReview
from app.reviews.service import get_existing

_ENGINE_INTENTS = {Intent.PLAN, Intent.ALTERNATIVES}
_RECALL_INTENTS = {Intent.PATTERNS, Intent.PLAN, Intent.SUMMARY, Intent.OPENING}
_SYSTEM_PROMPT = (
    "You are a chess coach. Use ONLY the supplied facts and moves. Do not invent "
    "any move, evaluation, or opening that is not listed. Be concise and concrete, "
    "and speak from the reviewed player's point of view."
)


class NoReviewError(Exception):
    """The game has no completed review yet (invisible 404 / 409 at the router)."""


@dataclass(frozen=True)
class CoachAnswer:
    """A grounded assistant answer, ready to serialize."""

    answer: str
    intent: str
    mode: str  # 'deterministic' | 'llm'
    provider: str
    references: list[Reference]
    position_fen: str


def ensure_completed_review(db: Session, game_id: int, user_id: int) -> GameReview:
    """The caller's completed review for one game, or a domain error.

    Raises NoReviewError when none is stored (the coach speaks only from analysed
    facts, never an un-analysed game) or when the analysis failed. Game
    ownership/visibility is enforced upstream by the router's game load.
    """
    review = get_existing(db, game_id, user_id)
    if review is None:
        raise NoReviewError("Analyse this game first to ask the coach.")
    if review.status != "completed":
        raise NoReviewError("This game's analysis did not finish.")
    return review


def _facts_for(review: GameReview) -> list[ReviewFact]:
    moves = (review.payload or {}).get("moves", [])
    return facts_from_payload(moves if isinstance(moves, Sequence) else [])


def _build_recall(
    db: Session,
    user_id: int,
    intent: Intent,
    facts: Sequence[ReviewFact],
    focus: ReviewFact | None,
) -> str:
    """Assemble the RAG block for a cross-game / opening question (best-effort)."""
    top_k = settings.coach_recall_top_k
    if intent is Intent.PATTERNS:
        rows = recall.patterns(db, user_id, _hero_of(facts), limit=top_k)
        return recall.patterns_text(rows)
    if intent is Intent.OPENING and focus is not None and focus.opening_family:
        note = recall.opening_note(db, user_id, focus.opening_family)
        rows = recall.patterns(db, user_id, _hero_of(facts), limit=top_k)
        return note or recall.patterns_text(rows)
    if intent in _RECALL_INTENTS:
        rows = recall.patterns(db, user_id, _hero_of(facts), limit=top_k)
        return recall.patterns_text(rows)
    return ""


def _hero_of(facts: Sequence[ReviewFact]) -> str:
    """The pack's hero is implied by the review; default White when there are no plies."""
    return "w"


def build_answer(
    db: Session,
    review: GameReview,
    question: str,
    focus_ply: int | None,
    *,
    user_id: int,
) -> CoachAnswer:
    """Deterministic grounded answer — the always-available path (no LLM, no net)."""
    facts = _facts_for(review)
    hero = review.hero_color
    intent = detect_intent(question)
    focus_ply_resolved = find_focus_ply(facts, focus_ply, hero, question)
    focus = fact_by_ply(facts, focus_ply_resolved)

    lines: list[AltLine] = []
    if intent in _ENGINE_INTENTS and focus is not None:
        lines = alternative_lines(focus.pre_fen, hero)

    recall_block = (
        _build_recall(db, user_id, intent, facts, focus) if intent in _RECALL_INTENTS else ""
    )

    composed = compose(
        intent,
        focus,
        facts,
        hero,
        lines,
        recall_block=recall_block,
        game_id=review.game_id,
    )
    return CoachAnswer(
        answer=composed.answer,
        intent=intent.value,
        mode="deterministic",
        provider="stockfish+book",
        references=composed.references,
        position_fen=composed.position_fen,
    )


def _llm_prompt(
    question: str, facts: Sequence[ReviewFact], answer: CoachAnswer, recall_block: str
) -> str:
    pack, _ = full_review_pack(facts, "w")
    blocks = [f"Question: {question}", f"Facts:\n{pack}"]
    if recall_block:
        blocks.append(f"Cross-game recall:\n{recall_block}")
    blocks.append(f"Deterministic answer to re-phrase (do not add moves): {answer.answer}")
    return "\n\n".join(blocks)


def answer(
    db: Session,
    review: GameReview,
    question: str,
    focus_ply: int | None,
    *,
    user_id: int,
) -> CoachAnswer:
    """The full assistant path: build grounded facts, optionally let an LLM phrase them.

    The LLM output is kept only if :func:`grounded` confirms it names no move the
    facts do not contain; otherwise the deterministic answer stands. Any provider
    error is swallowed the same way — the coach always answers.
    """
    deterministic = build_answer(db, review, question, focus_ply, user_id=user_id)

    pack_facts = _facts_for(review)
    intent = Intent(deterministic.intent)
    focus = fact_by_ply(
        pack_facts, find_focus_ply(pack_facts, focus_ply, review.hero_color, question)
    )
    lines = (
        alternative_lines(focus.pre_fen, review.hero_color)
        if intent in _ENGINE_INTENTS and focus
        else []
    )
    allowed = allowed_tokens_from(pack_facts, lines)

    recall_block = deterministic.answer if intent in (Intent.PATTERNS, Intent.OPENING) else ""
    try:
        provider = open_chat_provider()
    except AssistantUnavailableError:
        return deterministic
    try:
        prose = provider.complete(
            _SYSTEM_PROMPT, _llm_prompt(question, pack_facts, deterministic, recall_block)
        )
    except AssistantUnavailableError:
        return deterministic
    if not grounded(prose, allowed):
        return deterministic
    return dataclasses.replace(deterministic, answer=prose, mode="llm", provider=provider.name)


def describe_position(db: Session, review: GameReview, focus_ply: int | None) -> str:
    """A one-line grounded description of the position at (or nearest to) a ply."""
    facts = _facts_for(review)
    hero = review.hero_color
    resolved = find_focus_ply(facts, focus_ply, hero, "")
    composed = compose(Intent.POSITION, fact_by_ply(facts, resolved), facts, hero)
    return composed.answer


def cross_game_advice(
    db: Session, review: GameReview, user_id: int
) -> tuple[str, list[recall.PatternRow]]:
    """The 'what you keep doing wrong' summary plus the raw pattern rows it came from."""
    rows = recall.patterns(db, user_id, review.hero_color, limit=settings.coach_recall_top_k)
    return recall.patterns_text(rows), rows
