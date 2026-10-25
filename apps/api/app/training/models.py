"""TrainingAttempt model: the append-only log of every drill/puzzle try.

One row per attempt, correct or not. Keeping attempts (rather than a mutable
"best level" column) is what lets the ramp, the streak and the per-theme
progress be recomputed from history without any state to drift out of sync.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TrainingAttempt(Base):
    """One recorded attempt at one puzzle."""

    __tablename__ = "training_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # Stable puzzle key: 'fork-1' for a curated drill, 'mine:{game}:{ply}' for
    # a personal one. Doubles as the point-award slot.
    puzzle_key: Mapped[str] = mapped_column(String(64), nullable=False)
    # 'drill' (curated catalog) | 'game' (mined from the player's own reviews).
    source: Mapped[str] = mapped_column(String(8), nullable=False)
    theme: Mapped[str] = mapped_column(String(32), nullable=False)
    # Difficulty rung at the time of the attempt (1..3).
    level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    solved: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # The UCI the player actually played.
    uci: Mapped[str] = mapped_column(String(5), nullable=False)
    # Populated only for 'game' puzzles, so a solved one links back to its review.
    game_id: Mapped[int | None] = mapped_column(ForeignKey("games.id"), nullable=True)
    ply: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
