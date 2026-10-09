"""GameMove model for move history."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class GameMove(Base):
    """Individual move in a game."""

    __tablename__ = "game_moves"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False, index=True)
    uci: Mapped[str] = mapped_column(String(10), nullable=False)  # UCI notation
    san: Mapped[str] = mapped_column(String(20), nullable=False)  # SAN notation
    move_number: Mapped[int] = mapped_column(Integer, nullable=False)  # Sequence number
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
