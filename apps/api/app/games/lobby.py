"""In-process match queue (online-plan §5).

Ephemeral by design: the queue holds user ids only (no PII to strangers) and
lives for the process lifetime — a restart just means users re-queue. Games
themselves live in Postgres, so a matched game always survives the queue.
Single-replica assumption (plan §2): one process owns all pairings.
"""

import random
import threading
from collections import deque
from contextlib import suppress
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.games import online_service
from app.games.domain import GameMode, GameStatus
from app.models.game import Game as GameRow

_waiting: deque[int] = deque()
_lock = threading.Lock()


def reset_lobby() -> None:
    """Drop all queued state (process restart in prod; between tests)."""
    with _lock:
        _waiting.clear()


def _active_online_game(db: Session, user_id: int) -> GameRow | None:
    stmt = (
        select(GameRow)
        .where(
            GameRow.mode == GameMode.ONLINE.value,
            GameRow.status == GameStatus.ACTIVE.value,
            or_(GameRow.white_user_id == user_id, GameRow.black_user_id == user_id),
        )
        .order_by(GameRow.id.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def _matched(game: GameRow, user_id: int) -> dict[str, Any]:
    return {
        "status": "matched",
        "game_id": game.id,
        "color": "w" if game.white_user_id == user_id else "b",
    }


def queue_status(db: Session, user_id: int) -> dict[str, Any]:
    """{idle|queued|matched(+game_id,color)} — the poll/refresh view (§5)."""
    game = _active_online_game(db, user_id)
    if game is not None:
        return _matched(game, user_id)
    with _lock:
        queued = user_id in _waiting
    return {"status": "queued" if queued else "idle"}


def join(db: Session, user_id: int) -> dict[str, Any]:
    """Queue the caller, or pair them with the first waiting opponent.

    Duplicate guard: an already-queued user or one with an unfinished online
    game gets their existing state instead of a second slot (§5). All state
    checks run under the lock — two overlapping requests from the same user
    must never pair that user with themself.
    """
    existing = queue_status(db, user_id)
    if existing["status"] != "idle":
        return existing
    with _lock:
        # Re-check under the lock (the pre-check above raced with a parallel
        # request from the same account).
        game = _active_online_game(db, user_id)
        if game is not None:
            return _matched(game, user_id)
        if user_id in _waiting:
            return {"status": "queued"}
        while _waiting:
            opponent = _waiting.popleft()
            # Skip a stale id whose game appeared between queueing and here,
            # and never pair a user with their own second request.
            if opponent == user_id or _active_online_game(db, opponent) is not None:
                continue
            white_id, black_id = (
                (user_id, opponent) if random.random() < 0.5 else (opponent, user_id)
            )
            game = online_service.create_online_game(db, white_id, black_id)
            return _matched(game, user_id)
        _waiting.append(user_id)
    return {"status": "queued"}


def leave(user_id: int) -> dict[str, Any]:
    """Cancel a pending queue slot (no-op if not queued)."""
    with _lock, suppress(ValueError):
        _waiting.remove(user_id)
    return {"status": "idle"}
