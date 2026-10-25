"""Point ledger: every awarded point is recorded (chess.com-style scoring).

Rows are immutable history; `users.points` is a running total kept in sync.
Move awards are unique per (game, move number) so undo/resubmit cannot
farm points from the same slot.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PointAward(Base):
    """One point award: a played move, a finished game's result, or a drill."""

    __tablename__ = "point_awards"
    __table_args__ = (
        UniqueConstraint("game_id", "reason", "move_number", name="uq_point_award_slot"),
        # Gameless awards (drill/theme) dedupe on slot_key. A NULL slot_key never
        # collides under Postgres, so the uniqueness is expressed as a *partial*
        # index that only covers rows that actually carry a slot.
        Index(
            "uq_point_award_slot_key",
            "user_id",
            "reason",
            "slot_key",
            unique=True,
            postgresql_where=text("slot_key IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # Gameless awards exist (drill/theme point slots), so the FK is nullable.
    game_id: Mapped[int | None] = mapped_column(ForeignKey("games.id"), nullable=True, index=True)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    # One of 'move' | 'win' | 'draw' | 'loss' | 'drill' | 'theme_clear'.
    reason: Mapped[str] = mapped_column(String(20), nullable=False)
    # Set for 'move' awards (dedupe slot); None for result awards.
    move_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Dedupe slot for gameless awards ('drill:fork-1', 'theme:mate'). Unique
    # per (user, reason) via a partial index; NULL for every game award, which
    # the (game_id, reason, move_number) constraint still guards.
    slot_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
