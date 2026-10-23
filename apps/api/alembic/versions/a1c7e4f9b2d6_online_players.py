"""Online play: games.white_user_id / black_user_id color seats.

Revision ID: a1c7e4f9b2d6
Revises: 9d4b7a2e61c8
Create Date: 2026-10-23

Adds the two participant columns for human-vs-human online games
(online-plan §3.1). ``games.mode`` already stores a free string, so
GameMode.ONLINE needs no schema change. ``user_id`` keeps mirroring
White for legacy owner-scoped queries (see pitfalls §12).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1c7e4f9b2d6"
down_revision: str | Sequence[str] | None = "9d4b7a2e61c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("games", sa.Column("white_user_id", sa.Integer(), nullable=True))
    op.add_column("games", sa.Column("black_user_id", sa.Integer(), nullable=True))
    # Unnamed constraints: Postgres applies its <table>_<column>_fkey convention,
    # matching the plain ForeignKey("users.id") in the ORM model (alembic check).
    op.create_foreign_key(None, "games", "users", ["white_user_id"], ["id"])
    op.create_foreign_key(None, "games", "users", ["black_user_id"], ["id"])
    op.create_index(op.f("ix_games_white_user_id"), "games", ["white_user_id"], unique=False)
    op.create_index(op.f("ix_games_black_user_id"), "games", ["black_user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_games_black_user_id"), table_name="games", if_exists=True)
    op.drop_index(op.f("ix_games_white_user_id"), table_name="games", if_exists=True)
    op.drop_constraint("games_black_user_id_fkey", "games", type_="foreignkey", exists=True)
    op.drop_constraint("games_white_user_id_fkey", "games", type_="foreignkey", exists=True)
    op.drop_column("games", "black_user_id")
    op.drop_column("games", "white_user_id")
