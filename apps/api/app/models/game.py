"""Game model for chess games."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Game(Base):
    """Chess game state."""

    __tablename__ = "games"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # Online games only: the two color seats. `user_id` mirrors `white_user_id`
    # so existing owner-scoped queries keep working for White (online-plan §3.1).
    white_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    black_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    mode: Mapped[str] = mapped_column(String(50), nullable=False)  # 'local', 'computer', 'online'
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # 'active', 'checkmate', etc.
    fen: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False
    )  # For optimistic concurrency
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
