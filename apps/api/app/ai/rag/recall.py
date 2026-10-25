"""Coach recall: full-text hits and cross-game error patterns.

The retrieval half of the RAG layer. Everything is *player-scoped* (a query can
only ever see the caller's own indexed plies) and *best-effort*: if the coach
index is missing or the search column is not populated yet, recall returns
nothing and the answer falls back to the long-context facts — the assistant never
fails just because retrieval did.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import TSQUERY
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.ai.rag.models import CoachIndex

_HERO_SIDES = ("w", "white")
_ERROR_QUALITIES = ("mistake", "blunder")


@dataclass(frozen=True)
class PatternRow:
    """Aggregate of the hero's errors inside one opening family, across games."""

    opening_family: str
    mistakes: int
    blunders: int
    total_errors: int
    avg_loss_cp: int


@dataclass(frozen=True)
class ErrorHit:
    """One indexed mistake/blunder, for free-text recall."""

    game_id: int
    ply: int
    san: str
    color: str
    quality: str
    note: str


def _hero_clause(hero_color: str) -> ColumnElement[bool]:
    """Match the stored color however the writer chose to spell it ('w' or 'white')."""
    if hero_color in _HERO_SIDES:
        return CoachIndex.color.in_(("w", "white"))
    return CoachIndex.color.in_(("b", "black"))


def patterns(
    db: Session, user_id: int, hero_color: str, *, limit: int = 6, min_errors: int = 1
) -> list[PatternRow]:
    """Group the hero's mistakes/blunders by opening family, worst families first.

    This is the honest answer to "what do I keep doing wrong": not a vibe, but a
    count of real graded errors the review pass already recorded, bucketed by the
    opening they happened in.
    """
    stmt = (
        select(
            CoachIndex.opening_family,
            func.count().filter(CoachIndex.quality == "mistake").label("mistakes"),
            func.count().filter(CoachIndex.quality == "blunder").label("blunders"),
            func.avg(CoachIndex.centipawn_loss).label("avg_loss"),
        )
        .where(
            CoachIndex.user_id == user_id,
            CoachIndex.quality.in_(_ERROR_QUALITIES),
            _hero_clause(hero_color),
        )
        .group_by(CoachIndex.opening_family)
        .order_by(func.count().desc())
        .limit(limit)
    )
    try:
        rows = db.execute(stmt).all()
    except SQLAlchemyError:
        db.rollback()
        return []

    out: list[PatternRow] = []
    for family, mistakes, blunders, avg_loss in rows:
        total = int(mistakes) + int(blunders)
        if total < min_errors:
            continue
        out.append(
            PatternRow(
                opening_family=str(family or "Ungrouped"),
                mistakes=int(mistakes),
                blunders=int(blunders),
                total_errors=total,
                avg_loss_cp=int(avg_loss or 0),
            )
        )
    return out


def free_text_hits(db: Session, user_id: int, query: str, *, limit: int = 6) -> list[ErrorHit]:
    """The player's own graded errors whose note matches a full-text query.

    Uses `websearch_to_tsquery` (tolerant of junk input) against the generated
    tsvector, ranked by relevance. Returns nothing on any DB hiccup so an answer
    degrades to the current game's facts rather than erroring.
    """
    query = query.strip()
    if not query:
        return []
    tsq = func.websearch_to_tsquery("english", query)
    stmt = (
        select(CoachIndex)
        .where(
            CoachIndex.user_id == user_id,
            CoachIndex.quality.in_(_ERROR_QUALITIES),
            CoachIndex.search.op("@@")(tsq.cast(TSQUERY)),
        )
        .order_by(func.ts_rank(CoachIndex.search, tsq).desc())
        .limit(limit)
    )
    try:
        rows = db.execute(stmt).scalars().all()
    except SQLAlchemyError:
        db.rollback()
        return []
    return [
        ErrorHit(
            game_id=row.game_id,
            ply=row.ply,
            san=row.san,
            color=row.color,
            quality=row.quality,
            note=row.note,
        )
        for row in rows
    ]


def opening_note(db: Session, user_id: int, family: str) -> str:
    """A book-anchored line about one opening family the player has reached.

    Grounded in the offline theory book for the *name* and in the player's own
    graded plies for the counts — it never states theory the book does not hold.
    Returns '' when the family is unknown or unindexed for this player.
    """
    if not family:
        return ""
    stmt = select(
        func.count().label("plies"),
        func.count().filter(CoachIndex.quality.in_(_ERROR_QUALITIES)).label("errors"),
    ).where(CoachIndex.user_id == user_id, CoachIndex.opening_family == family)
    try:
        plies, errors = db.execute(stmt).one()
    except SQLAlchemyError:
        db.rollback()
        return ""
    if not int(plies):
        return ""
    return f"In the {family}, {int(errors)} of your {int(plies)} recorded plies were errors."


def patterns_text(rows: list[PatternRow], *, min_games_hint: int = 2) -> str:
    """Render pattern rows as a coach-readable summary (empty when nothing solid).

    `min_games_hint` is only wording: the counts themselves come from the DB, so
    a single-family hit still reads honestly as 'you erred N times in ...'.
    """
    if not rows:
        return ""
    lead = (
        "Across your reviewed games"
        if len(rows) >= min_games_hint or rows[0].total_errors >= min_games_hint
        else "In the games reviewed so far"
    )
    parts = [
        f"{lead}, your most error-heavy opening is {row.opening_family} "
        f"({row.blunders} blunders, {row.mistakes} mistakes, ~{row.avg_loss_cp}cp lost on average)"
        if index == 0
        else f"{row.opening_family}: {row.total_errors} errors (~{row.avg_loss_cp}cp)"
        for index, row in enumerate(rows[:3])
    ]
    return "; ".join(parts) + "."
