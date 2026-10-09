"""Game service: rules validation + persistence (API-005..012).

Layering (per code-standards): routes validate HTTP input and call this
service; the service uses `ChessRules` for chess logic and `GameRepository`
for persistence.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.games.domain import STARTING_FEN, GameMode, GameStatus
from app.games.errors import IllegalMoveError, InvalidMoveError
from app.games.rules import ChessRules
from app.models.game import Game as GameRow
from app.models.game_move import GameMove as GameMoveRow
from app.repositories.game_repository import GameRepository


@dataclass(frozen=True)
class GameDetail:
    """A game row plus its ordered move history."""

    game: GameRow
    moves: list[GameMoveRow]


class GameNotFoundError(Exception):
    """Game id unknown or owned by another user (mapped to 404)."""


class StaleVersionError(Exception):
    """Optimistic-concurrency version mismatch (mapped to 409)."""


class IllegalMoveRequestError(Exception):
    """UCI unparsable, illegal, or bad mode/claim (mapped to 422)."""


class GameFinishedError(Exception):
    """State change requested on a finished game (mapped to 409)."""


def _require_game(repo: GameRepository, game_id: int, user_id: int) -> GameRow:
    game = repo.get_by_id(game_id, user_id)
    if game is None:
        raise GameNotFoundError(f"Game {game_id} not found")
    return game


def _require_active(game: GameRow) -> None:
    if game.status != GameStatus.ACTIVE.value:
        raise GameFinishedError(f"Game is {game.status}")


def _sync_status(repo: GameRepository, game: GameRow, rules: ChessRules) -> GameRow:
    """Persist rules-derived terminal status if the position ended the game."""
    derived = rules.status()
    if derived != GameStatus.ACTIVE and game.status == GameStatus.ACTIVE.value:
        updated = repo.update_status(game.id, game.user_id, derived.value)
        assert updated is not None
        return updated
    return game


def create_game(db: Session, user_id: int, mode: str) -> GameRow:
    """Create a game in the starting position (API-005)."""
    try:
        game_mode = GameMode(mode)
    except ValueError as exc:
        raise IllegalMoveRequestError(f"Invalid mode: {mode!r}") from exc
    return GameRepository(db).create(user_id=user_id, mode=game_mode.value, fen=STARTING_FEN)


def list_games(db: Session, user_id: int) -> list[GameRow]:
    """List the caller's games, newest first (API-006)."""
    stmt = select(GameRow).where(GameRow.user_id == user_id).order_by(GameRow.id.desc())
    return list(db.execute(stmt).scalars().all())


def get_game(db: Session, game_id: int, user_id: int) -> GameDetail:
    """Fetch a game with its move history (API-007)."""
    repo = GameRepository(db)
    game = _require_game(repo, game_id, user_id)
    return GameDetail(game=game, moves=repo.get_moves(game_id, user_id))


def submit_move(
    db: Session, game_id: int, user_id: int, uci: str, expected_version: int
) -> GameDetail:
    """Validate a UCI move, persist it, bump version (API-008/018/019)."""
    repo = GameRepository(db)
    game = _require_game(repo, game_id, user_id)
    _require_active(game)
    if game.version != expected_version:
        raise StaleVersionError(f"Expected version {game.version}, have {expected_version}")
    rules = ChessRules(game.fen)
    try:
        move = rules.apply_move(uci)
    except (InvalidMoveError, IllegalMoveError) as exc:
        raise IllegalMoveRequestError(str(exc)) from exc
    move_number = len(repo.get_moves(game_id, user_id)) + 1
    repo.add_move(game_id, user_id, uci=move.uci, san=move.san, move_number=move_number)
    updated = repo.update_fen(game_id, user_id, rules.fen, expected_version)
    assert updated is not None  # version checked above
    updated = _sync_status(repo, updated, rules)
    return GameDetail(game=updated, moves=repo.get_moves(game_id, user_id))


def undo_move(db: Session, game_id: int, user_id: int, expected_version: int) -> GameDetail:
    """Undo the last move, restoring FEN (API-009)."""
    repo = GameRepository(db)
    game = _require_game(repo, game_id, user_id)
    _require_active(game)
    if game.version != expected_version:
        raise StaleVersionError(f"Expected version {game.version}, have {expected_version}")
    moves = repo.get_moves(game_id, user_id)
    if not moves:
        raise IllegalMoveRequestError("No moves to undo")
    remaining = [m.uci for m in moves[:-1]]
    rules = ChessRules()
    rules.replay_moves(remaining)
    db.delete(moves[-1])
    db.commit()
    updated = repo.update_fen(game_id, user_id, rules.fen, expected_version)
    assert updated is not None
    return GameDetail(game=updated, moves=repo.get_moves(game_id, user_id))


def resign_game(db: Session, game_id: int, user_id: int) -> GameDetail:
    """Mark an active game resigned (API-010)."""
    repo = GameRepository(db)
    game = _require_game(repo, game_id, user_id)
    _require_active(game)
    updated = repo.update_status(game.id, user_id, GameStatus.RESIGNED.value)
    assert updated is not None
    return GameDetail(game=updated, moves=repo.get_moves(game_id, user_id))


def claim_draw(db: Session, game_id: int, user_id: int) -> GameDetail:
    """Claim a draw when the position supports it (API-011)."""
    import chess  # local: only service fn needing raw board predicates

    repo = GameRepository(db)
    game = _require_game(repo, game_id, user_id)
    _require_active(game)
    rules = ChessRules(game.fen)
    board = chess.Board(game.fen)
    if not (
        rules.status() == GameStatus.DRAW
        or board.is_fifty_moves()
        or board.is_repetition(3)
        or board.is_stalemate()
        or board.is_insufficient_material()
    ):
        raise IllegalMoveRequestError("Position does not support a draw claim")
    updated = repo.update_status(game.id, user_id, GameStatus.DRAW.value)
    assert updated is not None
    return GameDetail(game=updated, moves=repo.get_moves(game_id, user_id))


def request_engine_move(
    db: Session,
    game_id: int,
    user_id: int,
    expected_version: int,
    max_depth: int | None = None,
    max_time_ms: int | None = None,
) -> GameDetail:
    """Ask the custom engine for a move and persist it (API-012)."""
    import chess

    from app.engine.domain import EngineConfig
    from app.engine.engine import ChessEngine
    from app.games.domain import Color
    from app.models.engine_run import EngineRun

    repo = GameRepository(db)
    game = _require_game(repo, game_id, user_id)
    _require_active(game)
    if game.mode != GameMode.COMPUTER.value:
        raise IllegalMoveRequestError("Engine moves require a computer game")
    if game.version != expected_version:
        raise StaleVersionError(f"Expected version {game.version}, have {expected_version}")
    board = chess.Board(game.fen)
    if board.is_game_over():
        raise GameFinishedError("Game is over")
    for_color = Color.WHITE if board.turn == chess.WHITE else Color.BLACK
    config = EngineConfig()
    if max_depth is not None:
        config = EngineConfig(
            difficulty=config.difficulty, max_depth=max_depth, max_time_ms=config.max_time_ms
        )
    if max_time_ms is not None:
        config = EngineConfig(
            difficulty=config.difficulty, max_depth=config.max_depth, max_time_ms=max_time_ms
        )
    result = ChessEngine(config).search(board, for_color)
    rules = ChessRules(game.fen)
    try:
        move = rules.apply_move(result.best_move)
    except (InvalidMoveError, IllegalMoveError) as exc:
        raise IllegalMoveRequestError(f"Engine returned bad move: {exc}") from exc
    move_number = len(repo.get_moves(game_id, user_id)) + 1
    repo.add_move(game_id, user_id, uci=move.uci, san=move.san, move_number=move_number)
    db.add(
        EngineRun(
            game_id=game.id,
            fen=game.fen,
            best_move=move.uci,
            score=result.score,
            depth=result.depth,
            nodes_searched=result.nodes_searched,
            time_ms=result.time_ms,
        )
    )
    db.commit()
    updated = repo.update_fen(game_id, user_id, rules.fen, expected_version)
    assert updated is not None
    updated = _sync_status(repo, updated, rules)
    return GameDetail(game=updated, moves=repo.get_moves(game_id, user_id))
