"""Coach index writer: project a stored review into searchable ply rows.

Called best-effort after a completed review is written (see `reviews/service.py`):
indexing is an acceleration structure over facts that already live in
`game_reviews.payload`, so a failure here must never fail the review that
triggered it. It rolls its own transaction and reports "nothing indexed".

Re-indexing a game replaces its whole row set (a forced re-analysis can shrink
the game), and only completed reviews are indexed — a failed analysis has no
facts worth recalling.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.ai.longcontext.context import facts_from_payload
from app.ai.rag.models import CoachIndex
from app.models.game_review import GameReview


def _color_long(short: str) -> str:
    """'w'/'b' (stored payload) -> 'white'/'black' (indexed, reads better in notes)."""
    return "black" if short == "b" else "white"


def upsert_review(db: Session, review: GameReview) -> int:
    """Replace the indexed rows for one (game, user) review; return rows written.

    Derives the opening for each ply through the offline book (it is not stored in
    the payload), then deletes and re-inserts so a shrunk re-analysis leaves no
    stale plies behind.
    """
    if review.status != "completed":
        return 0
    moves = (review.payload or {}).get("moves", [])
    facts = facts_from_payload(moves if isinstance(moves, Sequence) else [])

    db.execute(
        delete(CoachIndex).where(
            CoachIndex.game_id == review.game_id, CoachIndex.user_id == review.user_id
        )
    )
    written = 0
    for fact in facts:
        note = f"{fact.explanation} {fact.opening_family}".strip()
        db.add(
            CoachIndex(
                game_id=review.game_id,
                user_id=review.user_id,
                ply=fact.ply,
                move_number=fact.move_number,
                san=fact.san,
                color=_color_long(fact.color),
                quality=fact.quality,
                centipawn_loss=fact.centipawn_loss,
                opening_family=fact.opening_family,
                note=note,
            )
        )
        written += 1
    db.commit()
    return written


def index_review_safe(db: Session, review: GameReview) -> int:
    """Index a review, swallowing every failure (rollback + report zero).

    The review endpoint's contract is the stored analysis; the coach index is a
    bonus. A projection error must not turn a successful review into an error.
    """
    try:
        return upsert_review(db, review)
    except Exception:  # noqa: BLE001 - best-effort by design; never break a review
        db.rollback()
        return 0


def indexed_count(db: Session, user_id: int) -> int:
    """How many plies are searchable for this player (0 when nothing indexed)."""
    stmt = select(func.count()).select_from(CoachIndex).where(CoachIndex.user_id == user_id)
    return int(db.execute(stmt).scalar_one())
