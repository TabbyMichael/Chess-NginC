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
from app.models.point_award import PointAward
from app.models.user import User
from app.repositories.game_repository import GameRepository

# Chess.com-style scoring for computer games: every recorded move earns a
# point and the finished game earns a result bonus. Local hot-seat games
# award nothing. In computer games the account owner plays White. Training
# awards are a deliberate side income: below a single game move so grinding
# drills can never out-earn playing.
POINT_RULES = {"move": 1, "win": 10, "draw": 5, "loss": 3, "drill": 2, "theme_clear": 5}


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


def require_version(game: GameRow, expected_version: int) -> None:
    """Reject writes based on a stale client snapshot (optimistic concurrency)."""
    if game.version != expected_version:
        raise StaleVersionError(
            f"Game changed elsewhere: you sent version {expected_version} "
            f"but the game is now at version {game.version}"
        )


class GameFinishedError(Exception):
    """State change requested on a finished game (mapped to 409)."""


def _require_game(repo: GameRepository, game_id: int, user_id: int) -> GameRow:
    game = repo.get_by_id(game_id, user_id)
    if game is None:
        raise GameNotFoundError(f"Game {game_id} not found")
    return game


def require_active(game: GameRow) -> None:
    if game.status != GameStatus.ACTIVE.value:
        raise GameFinishedError(f"Game is {game.status}")


def require_not_online(game: GameRow) -> None:
    """Online games mutate only through the /online endpoints (two-sided
    turn/award semantics do not fit the single-owner game routes)."""
    if game.mode == GameMode.ONLINE.value:
        raise IllegalMoveRequestError("Use the online endpoints for online games")


def _record(
    db: Session,
    user_id: int,
    delta: int,
    reason: str,
    *,
    game_id: int | None = None,
    move_number: int | None = None,
    slot_key: str | None = None,
) -> bool:
    """Insert one award, bump the running total, commit. Returns whether written.

    Deduped on whichever identity applies: game move slots by
    ``(game_id, 'move', move_number)``, gameless awards by ``(user_id, reason,
    slot_key)``. Re-awarding a filled slot is a silent no-op (returns False), so
    undo/replay and repeat solves cannot farm points.
    """
    if slot_key is not None:
        existing = db.execute(
            select(PointAward).where(
                PointAward.user_id == user_id,
                PointAward.reason == reason,
                PointAward.slot_key == slot_key,
            )
        ).scalar_one_or_none()
    elif game_id is not None and move_number is not None:
        existing = db.execute(
            select(PointAward).where(
                PointAward.game_id == game_id,
                PointAward.reason == "move",
                PointAward.move_number == move_number,
            )
        ).scalar_one_or_none()
    else:
        existing = None
    if existing is not None:
        return False
    db.add(
        PointAward(
            user_id=user_id,
            game_id=game_id,
            delta=delta,
            reason=reason,
            move_number=move_number,
            slot_key=slot_key,
        )
    )
    user = db.get(User, user_id)
    if user is not None:
        user.points += delta
    db.commit()
    return True


def award_points(
    db: Session, user_id: int, game: GameRow, reason: str, move_number: int | None = None
) -> None:
    """Record a point award for one user and bump their running total.

    Move awards are idempotent per (game, move slot), so undo-then-replay
    cannot farm extra points. Callers decide which games/modes earn points
    (shared by the computer and online services, online-plan §4).
    """
    _record(db, user_id, POINT_RULES[reason], reason, game_id=game.id, move_number=move_number)


def award_ledger(db: Session, user_id: int, reason: str, slot_key: str) -> int:
    """Award gameless points (a solved drill, a cleared theme), deduped on slot.

    Returns the delta actually granted (0 when the slot had already been paid),
    which the training service reports back so the reveal shows an honest number.
    """
    delta = POINT_RULES[reason]
    return delta if _record(db, user_id, delta, reason, slot_key=slot_key) else 0


def apply_and_store_move(
    db: Session, repo: GameRepository, game: GameRow, uci: str, expected_version: int
) -> tuple[ChessRules, GameRow, int]:
    """The shared move kernel: validate UCI, store the move, bump FEN/version.

    Callers must have loaded ``game`` and enforced active + version guards.
    Persistence goes through the row's owner (``game.user_id`` mirrors White
    for online games, so the repository's ownership filter always matches).
    Returns the applied rules, the updated row, and the move number (§12).
    """
    rules = ChessRules(game.fen)
    try:
        move = rules.apply_move(uci)
    except (InvalidMoveError, IllegalMoveError) as exc:
        raise IllegalMoveRequestError(str(exc)) from exc
    # Version-guarded update FIRST: a lost race raises 409 without leaving an
    # orphan GameMove row behind (two humans can now write the same row).
    updated = repo.update_fen(game.id, game.user_id, rules.fen, expected_version)
    if updated is None:
        raise StaleVersionError(f"Game {game.id} changed; expected version {expected_version}")
    move_number = len(repo.get_moves(game.id, game.user_id)) + 1
    repo.add_move(game.id, game.user_id, uci=move.uci, san=move.san, move_number=move_number)
    return rules, updated, move_number


def sync_status(db: Session, repo: GameRepository, game: GameRow, rules: ChessRules) -> GameRow:
    """Persist rules-derived terminal status and award result points once.

    The active→terminal transition is the single awards path for both computer
    and online games (undo/replay cannot re-trigger it, online-plan §12).
    """
    derived = rules.status()
    if derived == GameStatus.ACTIVE or game.status != GameStatus.ACTIVE.value:
        return game
    updated = repo.update_status(game.id, game.user_id, derived.value)
    if updated is None:
        # Lost the active→terminal race (opponent resigned/drew concurrently,
        # or a parallel finisher got here first): awards belong to the
        # transition that actually happened — record nothing twice.
        refreshed = repo.get_by_id(game.id, game.user_id)
        return refreshed if refreshed is not None else game
    mated_is_white = rules.fen.split(" ")[1] == "w"  # side to move is the mated side
    if updated.mode == GameMode.COMPUTER.value:
        # In checkmate the side TO MOVE is the loser; our user plays White.
        if derived == GameStatus.CHECKMATE:
            award_points(db, updated.user_id, updated, "loss" if mated_is_white else "win")
        elif derived in (GameStatus.STALEMATE, GameStatus.DRAW):
            award_points(db, updated.user_id, updated, "draw")
    elif updated.mode == GameMode.ONLINE.value:
        white, black = updated.white_user_id, updated.black_user_id
        if derived == GameStatus.CHECKMATE and white is not None and black is not None:
            winner, loser = (black, white) if mated_is_white else (white, black)
            award_points(db, winner, updated, "win")
            award_points(db, loser, updated, "loss")
        elif derived in (GameStatus.STALEMATE, GameStatus.DRAW):
            for seat in (white, black):
                if seat is not None:
                    award_points(db, seat, updated, "draw")
    return updated


def create_game(db: Session, user_id: int, mode: str) -> GameRow:
    """Create a game in the starting position (API-005)."""
    try:
        game_mode = GameMode(mode)
    except ValueError as exc:
        raise IllegalMoveRequestError(f"Invalid mode: {mode!r}") from exc
    if game_mode is GameMode.ONLINE:
        # Online games need two paired seats; only the lobby may create them.
        raise IllegalMoveRequestError("Online games are created through the lobby queue")
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
    require_active(game)
    require_version(game, expected_version)
    require_not_online(game)
    rules, updated, move_number = apply_and_store_move(db, repo, game, uci, expected_version)
    if updated.mode == GameMode.COMPUTER.value:
        award_points(db, updated.user_id, updated, "move", move_number)
    updated = sync_status(db, repo, updated, rules)
    return GameDetail(game=updated, moves=repo.get_moves(game_id, user_id))


def undo_move(db: Session, game_id: int, user_id: int, expected_version: int) -> GameDetail:
    """Undo the last move, restoring FEN (API-009)."""
    repo = GameRepository(db)
    game = _require_game(repo, game_id, user_id)
    require_active(game)
    require_version(game, expected_version)
    require_not_online(game)
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
    require_active(game)
    require_not_online(game)
    updated = repo.update_status(game.id, user_id, GameStatus.RESIGNED.value)
    if updated is None:
        raise GameFinishedError(f"Game {game_id} already finished")
    if updated.mode == GameMode.COMPUTER.value:
        award_points(db, updated.user_id, updated, "loss")
    return GameDetail(game=updated, moves=repo.get_moves(game_id, user_id))


def claim_draw(db: Session, game_id: int, user_id: int) -> GameDetail:
    """Claim a draw when the position supports it (API-011)."""
    import chess  # local: only service fn needing raw board predicates

    repo = GameRepository(db)
    game = _require_game(repo, game_id, user_id)
    require_active(game)
    require_not_online(game)
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
    if updated is None:
        raise GameFinishedError(f"Game {game_id} already finished")
    if updated.mode == GameMode.COMPUTER.value:
        award_points(db, updated.user_id, updated, "draw")
    return GameDetail(game=updated, moves=repo.get_moves(game_id, user_id))


def request_engine_move(
    db: Session,
    game_id: int,
    user_id: int,
    expected_version: int,
    max_depth: int | None = None,
    max_time_ms: int | None = None,
) -> GameDetail:
    """Ask real Stockfish for a move and persist it (API-012, PLAY-001)."""
    import chess

    from app.engine.opponent import stockfish_move
    from app.games.domain import Color
    from app.models.engine_run import EngineRun

    repo = GameRepository(db)
    game = _require_game(repo, game_id, user_id)
    require_active(game)
    if game.mode != GameMode.COMPUTER.value:
        raise IllegalMoveRequestError("Engine moves require a computer game")
    require_version(game, expected_version)
    board = chess.Board(game.fen)
    if board.is_game_over():
        raise GameFinishedError("Game is over")
    for_color = Color.WHITE if board.turn == chess.WHITE else Color.BLACK
    move = stockfish_move(board, for_color, max_depth, max_time_ms)
    pre_fen = game.fen  # the kernel mutates the row's FEN in place
    rules, updated, _ = apply_and_store_move(db, repo, game, move.uci, expected_version)
    db.add(
        EngineRun(
            game_id=game.id,
            fen=pre_fen,
            best_move=move.uci,
            score=move.score_cp,
            depth=move.depth,
            nodes_searched=move.nodes,
            time_ms=move.time_ms,
        )
    )
    db.commit()
    updated = sync_status(db, repo, updated, rules)
    return GameDetail(game=updated, moves=repo.get_moves(game_id, user_id))
