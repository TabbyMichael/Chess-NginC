"""Points ledger: users.points total + point_awards history.

Revision ID: 9d4b7a2e61c8
Revises: 7c21f0e58d94
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9d4b7a2e61c8"
down_revision: str | Sequence[str] | None = "7c21f0e58d94"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("points", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "point_awards",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=20), nullable=False),
        sa.Column("move_number", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("game_id", "reason", "move_number", name="uq_point_award_slot"),
    )
    op.create_index(
        op.f("ix_point_awards_user_id"), "point_awards", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_point_awards_game_id"), "point_awards", ["game_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_point_awards_game_id"), table_name="point_awards")
    op.drop_index(op.f("ix_point_awards_user_id"), table_name="point_awards")
    op.drop_table("point_awards")
    op.drop_column("users", "points")
