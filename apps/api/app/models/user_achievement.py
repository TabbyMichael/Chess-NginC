"""UserAchievement model: one row per unlocked achievement (ACH-004).

The catalog itself lives in code (`app.achievements.catalog`), so a new
achievement never needs a migration; this table records only what a player
has actually earned. `seen_at` marks a celebration as delivered, which keeps
the toast from replaying on every page load.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserAchievement(Base):
    """An achievement a player has unlocked."""

    __tablename__ = "user_achievements"
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_user_achievement_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # Stable catalog key, e.g. 'moves_total-100'.
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    unlocked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    # NULL until the client has celebrated it (GET /me/achievements/new).
    seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
