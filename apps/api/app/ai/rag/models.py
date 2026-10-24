"""Coach index model: one row per graded ply, full-text searchable (COACH RAG).

This is the corpus the assistant retrieves *across games* from — "what do I keep
doing wrong" and "which opening am I always blundering in". It is a projection of
the stored review payloads, not a second source of truth: it only ever holds
engine/book facts already computed by the review pass.

Deliberately embedding-free: the retrieval column is a Postgres `tsvector` behind
a GIN index, so the offline test/CI image needs no extension and no new
dependency (see docs/architecture.md, "why not pgvector").
"""

from __future__ import annotations

from sqlalchemy import Computed, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CoachIndex(Base):
    """One searchable row per reviewed ply."""

    __tablename__ = "coach_index"
    __table_args__ = (
        # A ply belongs to exactly one (game, user) review; re-indexing upserts.
        UniqueConstraint("game_id", "user_id", "ply", name="uq_coach_index_ply"),
        # Full-text recall over the note + opening name (the GIN index).
        Index("ix_coach_index_search", "search", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    ply: Mapped[int] = mapped_column(Integer, nullable=False)
    move_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    san: Mapped[str] = mapped_column(String(16), nullable=False, default="")
    color: Mapped[str] = mapped_column(String(8), nullable=False, default="white")
    quality: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    centipawn_loss: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    opening_eco: Mapped[str] = mapped_column(String(3), nullable=False, default="")
    opening_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    opening_family: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    # The coaching line + opening name, concatenated; the text free-text search runs.
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Stored generated column: Postgres maintains `to_tsvector('english', note)`,
    # so the writer never sets it and it can never drift from `note`. A plain
    # column default cannot reference another column; a generated column can.
    # (Computed goes positionally: mapped_column has no `computed=` keyword.)
    search: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', note)", persisted=True),
        nullable=False,
    )
