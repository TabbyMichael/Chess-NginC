"""Player statistics for achievement evaluation (ACH-003).

Aggregates the ledger tables into one flat ``metric -> value`` mapping the
catalog can be compared against. Everything is a SQL aggregate: evaluating
achievements never pulls move rows into Python, so it stays cheap enough to
run on every game transition.

Ownership model: a player's statistics cover every game they appear in —
as owner (local/computer games) or in either color seat (online games).
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.games.domain import GameMode, GameStatus
from app.models.engine_run import EngineRun
from app.models.game import Game as GameRow
from app.models.game_move import GameMove as GameMoveRow
from app.models.game_review import GameReview
from app.models.point_award import PointAward
from app.models.user import User

# Point-award reasons that describe a personal result (see games.service).
WIN = "win"
DRAW = "draw"
LOSS = "loss"

_PIECE_PREFIXES = {
    "pawn_moves": None,  # derived: anything that is not a piece or castling
    "knight_moves": "N",
    "bishop_moves": "B",
    "rook_moves": "R",
    "queen_moves": "Q",
    "king_moves": "K",
}


def _player_games(user_id: int) -> Select:
    """Base select for every game this player appears in."""
    return select(GameRow.id).where(
        or_(
            GameRow.user_id == user_id,
            GameRow.white_user_id == user_id,
            GameRow.black_user_id == user_id,
        )
    )


def _game_counts(db: Session, user_id: int) -> dict[str, int]:
    """Games started/completed and per-mode totals in one aggregate pass."""
    row = db.execute(
        select(
            func.count(),
            func.count().filter(GameRow.status != GameStatus.ACTIVE.value),
            func.count().filter(GameRow.mode == GameMode.COMPUTER.value),
            func.count().filter(GameRow.mode == GameMode.ONLINE.value),
            func.count().filter(GameRow.mode == GameMode.LOCAL.value),
        ).where(
            or_(
                GameRow.user_id == user_id,
                GameRow.white_user_id == user_id,
                GameRow.black_user_id == user_id,
            )
        )
    ).one()
    return {
        "games_total": int(row[0] or 0),
        "games_completed": int(row[1] or 0),
        "computer_games": int(row[2] or 0),
        "online_games": int(row[3] or 0),
        "local_games": int(row[4] or 0),
    }


def _move_counts(db: Session, game_ids: Select) -> dict[str, int]:
    """SAN-derived move statistics, aggregated entirely in SQL.

    SAN classification: a leading K/Q/R/B/N names the piece, 'O-O' is a
    castling, anything else is a pawn move. 'x' marks a capture, '+'/'#' a
    check/mate, '=' a promotion.
    """
    not_piece = and_(
        GameMoveRow.san.not_like("K%"),
        GameMoveRow.san.not_like("Q%"),
        GameMoveRow.san.not_like("R%"),
        GameMoveRow.san.not_like("B%"),
        GameMoveRow.san.not_like("N%"),
        GameMoveRow.san.not_like("O-O%"),
    )
    in_scope = GameMoveRow.game_id.in_(game_ids)
    row = db.execute(
        select(
            func.count(),
            func.count().filter(in_scope & GameMoveRow.san.like("%x%")),
            func.count().filter(
                in_scope & or_(GameMoveRow.san.like("%+%"), GameMoveRow.san.like("%#"))
            ),
            func.count().filter(in_scope & GameMoveRow.san.like("%#")),
            func.count().filter(in_scope & GameMoveRow.san.like("O-O%")),
            func.count().filter(in_scope & GameMoveRow.san.like("%=%")),
            func.count().filter(in_scope & not_piece),
            func.count().filter(in_scope & GameMoveRow.san.like("N%")),
            func.count().filter(in_scope & GameMoveRow.san.like("B%")),
            func.count().filter(in_scope & GameMoveRow.san.like("R%")),
            func.count().filter(in_scope & GameMoveRow.san.like("Q%")),
            func.count().filter(in_scope & GameMoveRow.san.like("K%")),
        ).where(in_scope)
    ).one()
    keys = (
        "moves_total",
        "captures",
        "checks",
        "checkmates",
        "castles",
        "promotions",
        "pawn_moves",
        "knight_moves",
        "bishop_moves",
        "rook_moves",
        "queen_moves",
        "king_moves",
    )
    stats = {key: int(value or 0) for key, value in zip(keys, row, strict=True)}
    stats["piece_variety"] = sum(1 for key in _PIECE_PREFIXES if stats[key] > 0)
    return stats


def _longest_game(db: Session, game_ids: Select) -> int:
    """Plies in the player's longest game (0 when no moves were recorded)."""
    per_game = (
        select(GameMoveRow.game_id, func.count().label("plies"))
        .where(GameMoveRow.game_id.in_(game_ids))
        .group_by(GameMoveRow.game_id)
        .subquery()
    )
    return int(db.execute(select(func.max(per_game.c.plies))).scalar() or 0)


def _results(db: Session, user_id: int) -> dict[str, int]:
    """Personal wins/draws/losses, overall and split by game mode.

    The point ledger is the authoritative result record: `sync_status` awards
    exactly one 'win'/'draw'/'loss' per finished game per player.
    """
    row = db.execute(
        select(
            func.count().filter(PointAward.reason == WIN),
            func.count().filter(PointAward.reason == DRAW),
            func.count().filter(PointAward.reason == LOSS),
            func.count().filter(PointAward.reason == WIN, GameRow.mode == GameMode.ONLINE.value),
            func.count().filter(PointAward.reason == WIN, GameRow.mode == GameMode.COMPUTER.value),
        )
        .join(GameRow, GameRow.id == PointAward.game_id, isouter=True)
        .where(PointAward.user_id == user_id)
    ).one()
    return {
        "wins": int(row[0] or 0),
        "draws": int(row[1] or 0),
        "losses": int(row[2] or 0),
        "online_wins": int(row[3] or 0),
        "computer_wins": int(row[4] or 0),
    }


def _habit(db: Session, user_id: int) -> dict[str, int]:
    """Days with recorded play and the best consecutive-day streak."""
    raw = db.execute(
        select(func.distinct(func.date(PointAward.created_at))).where(PointAward.user_id == user_id)
    ).scalars()
    seen: set[date] = set()
    for value in raw:
        seen.add(value if isinstance(value, date) else value.date())
    streak = best = 0
    previous: date | None = None
    for day in sorted(seen):
        streak = streak + 1 if previous is not None and (day - previous).days == 1 else 1
        best = max(best, streak)
        previous = day
    return {"active_days": len(seen), "best_streak_days": best}


def _engine_moves(db: Session, game_ids: Select) -> int:
    """Engine searches recorded for this player's games."""
    return int(
        db.execute(select(func.count()).where(EngineRun.game_id.in_(game_ids))).scalar() or 0
    )


def _review_stats(db: Session, user_id: int) -> dict[str, int]:
    """Review-derived metrics: how much the player has been analysing games.

    The per-grade counts only exist inside the stored review payload, so this
    reads those rows (one small JSON row per reviewed game).
    """
    rows = db.execute(
        select(GameReview.hero_color, GameReview.payload).where(
            GameReview.user_id == user_id, GameReview.status == "completed"
        )
    ).all()
    best_accuracy = 0
    brilliant = 0
    clean_games = 0
    for hero_color, payload in rows:
        data: dict = payload or {}
        counts: dict[str, int] = data.get("counts", {})
        brilliant += int(counts.get("brilliant", 0))
        if not int(counts.get("blunder", 0)) and not int(counts.get("mistake", 0)):
            clean_games += 1
        accuracy: dict[str, int] = data.get("summary", {}).get("accuracy", {})
        value = accuracy.get(hero_color)
        if isinstance(value, int | float):
            best_accuracy = max(best_accuracy, int(value))
    return {
        "reviews_completed": len(rows),
        "best_accuracy": best_accuracy,
        "brilliant_found": brilliant,
        "blunder_free_games": clean_games,
    }


def compute_stats(db: Session, user_id: int) -> dict[str, int]:
    """Every metric the catalog references, for one player."""
    user = db.get(User, user_id)
    game_ids = _player_games(user_id)
    return {
        "points": int(user.points) if user is not None else 0,
        **_game_counts(db, user_id),
        **_move_counts(db, game_ids),
        "longest_game": _longest_game(db, game_ids),
        **_results(db, user_id),
        **_habit(db, user_id),
        "engine_moves": _engine_moves(db, game_ids),
        **_review_stats(db, user_id),
    }
