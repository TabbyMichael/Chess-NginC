"""Online (human vs. human) game service (online-plan §4).

Server-authoritative: legality, turns, and results are decided here — the
socket/REST layers are transports, never authorities. Everything reuses the
shared move kernel, per-user points path, and terminal-status helper from
:mod:`app.games.service` so computer and online games cannot drift apart.
"""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.games.domain import STARTING_FEN, Color, GameMode, GameStatus
from app.games.rules import ChessRules
from app.games.service import (
    GameDetail,
    GameFinishedError,
    GameNotFoundError,
    IllegalMoveRequestError,
    apply_and_store_move,
    award_points,
    require_active,
    require_version,
    sync_status,
)
from app.models.game import Game as GameRow
from app.repositories.game_repository import GameRepository


def create_online_game(db: Session, white_id: int, black_id: int) -> GameRow:
    """Pair two accounts in one game; `user_id` mirrors White (§12 pitfall)."""
    game = GameRow(
        user_id=white_id,
        white_user_id=white_id,
        black_user_id=black_id,
        mode=GameMode.ONLINE.value,
        status=GameStatus.ACTIVE.value,
        fen=STARTING_FEN,
        version=1,
    )
    db.add(game)
    db.commit()
    db.refresh(game)
    return game


def _require_online_game(repo: GameRepository, game_id: int, player_id: int) -> GameRow:
    """Participant OR invisible (SEC-016); non-online games are not actionable."""
    game = repo.get_by_participant(game_id, player_id)
    if game is None:
        raise GameNotFoundError(f"Game {game_id} not found")
    if game.mode != GameMode.ONLINE.value:
        raise IllegalMoveRequestError("Not an online game")
    return game


def _color_for(game: GameRow, player_id: int) -> Color:
    if game.white_user_id == player_id:
        return Color.WHITE
    if game.black_user_id == player_id:
        return Color.BLACK
    # Owner-but-not-seat (legacy/computer game) — unreachable via the router.
    raise GameNotFoundError(f"Game {game.id} not found")


def _side_to_move(fen: str) -> Color:
    return Color.WHITE if fen.split(" ")[1] == "w" else Color.BLACK


def _opponent_id(game: GameRow, player_id: int) -> int | None:
    if game.white_user_id == player_id:
        return game.black_user_id
    if game.black_user_id == player_id:
        return game.white_user_id
    return None


def submit_online_move(
    db: Session, game_id: int, player_id: int, uci: str, expected_version: int
) -> GameDetail:
    """Turn-checked move for one color seat; both humans earn move points."""
    repo = GameRepository(db)
    game = _require_online_game(repo, game_id, player_id)
    require_active(game)
    require_version(game, expected_version)
    if _color_for(game, player_id) != _side_to_move(game.fen):
        raise IllegalMoveRequestError("It is not your turn")
    rules, updated, move_number = apply_and_store_move(db, repo, game, uci, expected_version)
    award_points(db, player_id, updated, "move", move_number)
    updated = sync_status(db, repo, updated, rules)
    return GameDetail(game=updated, moves=repo.get_moves(game_id, game.user_id))


def resign_online_game(db: Session, game_id: int, player_id: int) -> GameDetail:
    """Resigning player takes the loss; the opponent takes the win."""
    repo = GameRepository(db)
    game = _require_online_game(repo, game_id, player_id)
    require_active(game)
    updated = repo.update_status(game.id, game.user_id, GameStatus.RESIGNED.value)
    if updated is None:
        raise GameFinishedError(f"Game {game_id} already finished")
    award_points(db, player_id, updated, "loss")
    opponent = _opponent_id(game, player_id)
    if opponent is not None:
        award_points(db, opponent, updated, "win")
    return GameDetail(game=updated, moves=repo.get_moves(game_id, game.user_id))


def claim_online_draw(db: Session, game_id: int, player_id: int) -> GameDetail:
    """Position-based draw claim (same predicates as claim_draw); both earn +5."""
    import chess  # local: only this fn needs raw board predicates

    repo = GameRepository(db)
    game = _require_online_game(repo, game_id, player_id)
    require_active(game)
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
    updated = repo.update_status(game.id, game.user_id, GameStatus.DRAW.value)
    if updated is None:
        raise GameFinishedError(f"Game {game_id} already finished")
    for seat in (game.white_user_id, game.black_user_id):
        if seat is not None:
            award_points(db, seat, updated, "draw")
    return GameDetail(game=updated, moves=repo.get_moves(game_id, game.user_id))


def get_online_game(db: Session, game_id: int, player_id: int) -> GameDetail:
    """Participant-scoped fetch for Black (GET /games/{id} stays owner-only)."""
    repo = GameRepository(db)
    game = _require_online_game(repo, game_id, player_id)
    return GameDetail(game=game, moves=repo.get_moves(game_id, game.user_id))


def list_online_games(db: Session, user_id: int) -> list[GameRow]:
    """The caller's online games (either seat), newest first."""
    stmt = (
        select(GameRow)
        .where(
            GameRow.mode == GameMode.ONLINE.value,
            or_(GameRow.white_user_id == user_id, GameRow.black_user_id == user_id),
        )
        .order_by(GameRow.id.desc())
    )
    return list(db.execute(stmt).scalars().all())


def list_online_game_details(db: Session, user_id: int) -> list[GameDetail]:
    """Participant-scoped online game list with histories (Black's view)."""
    repo = GameRepository(db)
    return [
        GameDetail(game=row, moves=repo.get_moves(row.id, row.user_id))
        for row in list_online_games(db, user_id)
    ]
