"""Coach assistant index: cross-game full-text recall (Phase 11 RAG).

Revision ID: f6b1c8d2a9e4
Revises: e2a9c4f1b830
Create Date: 2026-10-24

A projection of stored review payloads into one searchable row per graded ply, so
the assistant can answer "what do I keep doing wrong across games" and name the
openings a player reaches. Retrieval is Postgres full-text (`tsvector` + GIN) —
no embedding column, no extension, so the offline test/CI image is unchanged.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6b1c8d2a9e4"
down_revision: str | Sequence[str] | None = "e2a9c4f1b830"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "coach_index",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("ply", sa.Integer(), nullable=False),
        sa.Column("move_number", sa.Integer(), nullable=False),
        sa.Column("san", sa.String(length=16), nullable=False),
        sa.Column("color", sa.String(length=8), nullable=False),
        sa.Column("quality", sa.String(length=20), nullable=False),
        sa.Column("centipawn_loss", sa.Integer(), nullable=False),
        sa.Column("opening_eco", sa.String(length=3), nullable=False),
        sa.Column("opening_name", sa.String(length=120), nullable=False),
        sa.Column("opening_family", sa.String(length=120), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        # Stored generated column: Postgres maintains the tsvector from `note`,
        # exactly as the ORM's Computed() declares it (one source of truth).
        # Computed is positional: `sa.Column(..., computed=...)` is not a kwarg.
        sa.Column(
            "search",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', note)", persisted=True),
            nullable=False,
        ),
        # Unnamed FK/PK: Postgres applies the <table>_<column>_fkey / _pkey
        # convention, matching the plain ORM declarations.
        sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("game_id", "user_id", "ply", name="uq_coach_index_ply"),
    )
    op.create_index(op.f("ix_coach_index_game_id"), "coach_index", ["game_id"], unique=False)
    op.create_index(op.f("ix_coach_index_user_id"), "coach_index", ["user_id"], unique=False)
    # GIN index backing the `@@ websearch_to_tsquery` recall path.
    op.create_index(
        "ix_coach_index_search", "coach_index", ["search"], unique=False, postgresql_using="gin"
    )


def downgrade() -> None:
    op.drop_index("ix_coach_index_search", table_name="coach_index", if_exists=True)
    op.drop_index(op.f("ix_coach_index_user_id"), table_name="coach_index", if_exists=True)
    op.drop_index(op.f("ix_coach_index_game_id"), table_name="coach_index", if_exists=True)
    op.drop_table("coach_index")
