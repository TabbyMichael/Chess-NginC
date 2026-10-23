"""Achievements: per-player unlock records (ACH-004).

Revision ID: d7f3b0c9e512
Revises: c5e9a3d7f410
Create Date: 2026-10-23

The catalog itself is code (app/achievements/catalog.py), so only the fact
that a player earned an achievement is stored: (user, key) with the unlock
time and an optional 'seen' time used for one-shot celebrations.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7f3b0c9e512"
down_revision: str | Sequence[str] | None = "c5e9a3d7f410"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_achievements",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("unlocked_at", sa.DateTime(), nullable=False),
        sa.Column("seen_at", sa.DateTime(), nullable=True),
        # Unnamed constraints: Postgres applies its <table>_<column>_fkey /
        # <table>_pkey convention, matching the plain ORM declarations.
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "key", name="uq_user_achievement_key"),
    )
    op.create_index(
        op.f("ix_user_achievements_user_id"), "user_achievements", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_user_achievements_user_id"), table_name="user_achievements", if_exists=True)
    op.drop_table("user_achievements")
