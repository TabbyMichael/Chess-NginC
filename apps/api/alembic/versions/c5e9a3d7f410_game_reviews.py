"""Game reviews: stored post-game engine analysis (REVIEW-005).

Revision ID: c5e9a3d7f410
Revises: a1c7e4f9b2d6
Create Date: 2026-10-23

One review row per (game, reviewing user): status/provider/depth metadata
plus the full classification + coaching payload, so GET can serve a review
without re-running the engine.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5e9a3d7f410"
down_revision: str | Sequence[str] | None = "a1c7e4f9b2d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "game_reviews",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("depth", sa.Integer(), nullable=False),
        sa.Column("hero_color", sa.String(length=1), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        # Unnamed constraints: Postgres applies its <table>_<column>_fkey /
        # <table>_pkey convention, matching the plain ORM declarations.
        sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("game_id", "user_id", name="uq_game_review_per_user"),
    )
    op.create_index(op.f("ix_game_reviews_game_id"), "game_reviews", ["game_id"], unique=False)
    op.create_index(op.f("ix_game_reviews_user_id"), "game_reviews", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_game_reviews_user_id"), table_name="game_reviews", if_exists=True)
    op.drop_index(op.f("ix_game_reviews_game_id"), table_name="game_reviews", if_exists=True)
    op.drop_table("game_reviews")
