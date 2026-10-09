"""Game repository with ownership constraints and version checking."""

from sqlalchemy import select
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

    def update_fen(
        self, game_id: int, user_id: int, fen: str, expected_version: int
    ) -> Game | None:
        """Update game FEN with optimistic concurrency version checking.

        Returns None if version mismatch (stale data).
        """
        game = self.get_by_id(game_id, user_id)
        if game is None:
            return None

        if game.version != expected_version:
            return None  # Stale version

        game.fen = fen
        game.version += 1
        self.db.commit()
        self.db.refresh(game)
        return game

    def update_status(self, game_id: int, user_id: int, status: str) -> Game | None:
        """Update game status, enforcing ownership."""
        game = self.get_by_id(game_id, user_id)
        if game is None:
            return None

        game.status = status
        self.db.commit()
        self.db.refresh(game)
        return game

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
