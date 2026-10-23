"""GameReview model: stored post-game engine review (REVIEW-005).

One review per game per reviewing user: the assembled classification +
coaching JSON produced by the review service. `payload` is the full review
(moves, eval graph, summary) so the API can serve it without re-analysis.
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class GameReview(Base):
    """A finished analysis of one game, owned by the requesting player."""

    __tablename__ = "game_reviews"
    __table_args__ = (UniqueConstraint("game_id", "user_id", name="uq_game_review_per_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # 'completed' | 'failed' — failed rows keep the error for display.
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="completed")
    provider: Mapped[str] = mapped_column(String(30), nullable=False, default="stockfish")
    # Search depth actually achieved for the per-move analysis.
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Which color the reviewer was shown the review from: 'w' | 'b'.
    hero_color: Mapped[str] = mapped_column(String(1), nullable=False, default="w")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
