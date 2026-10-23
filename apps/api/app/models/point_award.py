"""Point ledger: every awarded point is recorded (chess.com-style scoring).

Rows are immutable history; `users.points` is a running total kept in sync.
Move awards are unique per (game, move number) so undo/resubmit cannot
farm points from the same slot.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PointAward(Base):
    """One point award: a played move or a finished game's result."""

    __tablename__ = "point_awards"
    __table_args__ = (
        UniqueConstraint("game_id", "reason", "move_number", name="uq_point_award_slot"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False, index=True)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    # One of 'move' | 'win' | 'draw' | 'loss'.
    reason: Mapped[str] = mapped_column(String(20), nullable=False)
    # Set for 'move' awards (dedupe slot); None for result awards.
    move_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
