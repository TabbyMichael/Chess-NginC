"""Game repository with ownership constraints and version checking."""

from sqlalchemy import or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.models.game import Game
from app.models.game_move import GameMove


class GameRepository:
    """Repository for game data access with ownership enforcement."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, user_id: int, mode: str, fen: str) -> Game:
        """Create a new game for the user."""
        game = Game(user_id=user_id, mode=mode, status="active", fen=fen)
        self.db.add(game)
        self.db.commit()
        self.db.refresh(game)
        return game

    def get_by_id(self, game_id: int, user_id: int) -> Game | None:
        """Get a game by ID, enforcing ownership."""
        stmt = select(Game).where(Game.id == game_id, Game.user_id == user_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_participant(self, game_id: int, user_id: int) -> Game | None:
        """Get a game where the user holds any seat: owner or color seat.

        Online games are owned by White (`user_id` mirrors `white_user_id`),
        so Black needs the participant view. Foreign games stay invisible
        (caller maps None to 404, never 403 — SEC-016).
        """
        stmt = select(Game).where(
            Game.id == game_id,
            or_(
                Game.user_id == user_id,
                Game.white_user_id == user_id,
                Game.black_user_id == user_id,
            ),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def update_fen(
        self, game_id: int, user_id: int, fen: str, expected_version: int
    ) -> Game | None:
        """Update game FEN with optimistic concurrency version checking.

        Compare-and-set on ``version``: returns ``None`` when the row moved
        under us (stale data) instead of read-modify-write racing.
        """
        stmt = (
            update(Game)
            .where(Game.id == game_id, Game.user_id == user_id, Game.version == expected_version)
            .values(fen=fen, version=Game.version + 1)
        )
        result = self.db.execute(stmt)
        self.db.commit()
        assert isinstance(result, CursorResult)  # DML always yields a CursorResult
        if result.rowcount == 0:
            return None  # stale version (or missing/foreign row)
        return self.get_by_id(game_id, user_id)

    def update_status(self, game_id: int, user_id: int, status: str) -> Game | None:
        """Atomically transition an *active* game to a terminal status.

        The ``status = 'active'`` predicate makes the active→terminal flip a
        compare-and-set: with two humans writing the same row, only the first
        concurrent finisher gets the row back; everyone else gets ``None``
        and must not award points (review §P1: double-award guard).
        """
        stmt = (
            update(Game)
            .where(Game.id == game_id, Game.user_id == user_id, Game.status == "active")
            .values(status=status)
        )
        result = self.db.execute(stmt)
        self.db.commit()
        assert isinstance(result, CursorResult)  # DML always yields a CursorResult
        if result.rowcount == 0:
            return None
        return self.get_by_id(game_id, user_id)

    def add_move(
        self, game_id: int, user_id: int, uci: str, san: str, move_number: int
    ) -> GameMove | None:
        """Add a move to the game, enforcing ownership."""
        game = self.get_by_id(game_id, user_id)
        if game is None:
            return None

        move = GameMove(
            game_id=game_id,
            uci=uci,
            san=san,
            move_number=move_number,
        )
        self.db.add(move)
        self.db.commit()
        self.db.refresh(move)
        return move

    def get_moves(self, game_id: int, user_id: int) -> list[GameMove]:
        """Get all moves for a game, enforcing ownership."""
        game = self.get_by_id(game_id, user_id)
        if game is None:
            return []

        stmt = select(GameMove).where(GameMove.game_id == game_id).order_by(GameMove.move_number)
        return list(self.db.execute(stmt).scalars().all())

    def recover_game(self, game_id: int, user_id: int) -> tuple[Game, list[GameMove]] | None:
        """Recover a game with all its moves, enforcing ownership.

        Returns (game, moves) tuple or None if not found or ownership violation.
        """
        game = self.get_by_id(game_id, user_id)
        if game is None:
            return None

        moves = self.get_moves(game_id, user_id)
        return game, moves
