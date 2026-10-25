"""Training: attempt log + gameless point slots (LEARN-001/005).

Revision ID: e2a9c4f1b830
Revises: d7f3b0c9e512
Create Date: 2026-10-24

Adds the append-only ``training_attempts`` log, and teaches the point ledger
to hold gameless awards: a solved drill or cleared theme has no game, so
``game_id`` becomes nullable and a ``slot_key`` carries the dedupe identity.
The existing ``uq_point_award_slot`` still guards game awards; a NULL slot_key
would never dedupe under Postgres, hence the *partial* unique index.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e2a9c4f1b830"
down_revision: str | Sequence[str] | None = "d7f3b0c9e512"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "training_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("puzzle_key", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=8), nullable=False),
        sa.Column("theme", sa.String(length=32), nullable=False),
        sa.Column("level", sa.SmallInteger(), nullable=False),
        sa.Column("solved", sa.Boolean(), nullable=False),
        sa.Column("uci", sa.String(length=5), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=True),
        sa.Column("ply", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_training_attempts_user_id"), "training_attempts", ["user_id"], unique=False
    )

    op.alter_column("point_awards", "game_id", existing_type=sa.Integer(), nullable=True)
    op.add_column("point_awards", sa.Column("slot_key", sa.String(length=64), nullable=True))
    op.create_index(
        "uq_point_award_slot_key",
        "point_awards",
        ["user_id", "reason", "slot_key"],
        unique=True,
        postgresql_where=sa.text("slot_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_point_award_slot_key", table_name="point_awards")
    op.drop_column("point_awards", "slot_key")
    # Any gameless rows this revision allowed cannot go back to NOT NULL.
    op.execute("DELETE FROM point_awards WHERE game_id IS NULL")
    op.alter_column("point_awards", "game_id", existing_type=sa.Integer(), nullable=False)
    op.drop_index(op.f("ix_training_attempts_user_id"), table_name="training_attempts")
    op.drop_table("training_attempts")
