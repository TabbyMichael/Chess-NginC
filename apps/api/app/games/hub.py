"""In-memory socket hub for online games (online-plan §6.2).

Transport only: the hub holds sockets, never game state or business logic.
Postgres (via ``online_service``) is the source of truth; a client that
misses a broadcast re-fetches over REST. Single-replica assumption (D6 in
docs/architecture.md): all pairings live in one process.
"""

import asyncio
from collections import defaultdict
from contextlib import suppress
from typing import Any

from fastapi import WebSocket

_lock = asyncio.Lock()
# game_id -> user_id -> live socket (one socket per player in v1).
_sockets: dict[int, dict[int, WebSocket]] = defaultdict(dict)

# Outbound message types (plan §6.2): game_state, opponent_joined,
# opponent_left, error, pong.


async def register(game_id: int, user_id: int, websocket: WebSocket) -> None:
    async with _lock:
        _sockets[game_id][user_id] = websocket


async def unregister(game_id: int, user_id: int, websocket: WebSocket) -> bool:
    """Drop ``websocket`` only while it is still the seat's live socket.

    A stale second tab closing must not evict the seat's current connection.
    Returns True when this socket was the registered one — the caller then
    tells peers about the departure.
    """
    async with _lock:
        players = _sockets.get(game_id)
        if players is None:
            return False
        left = players.get(user_id) is websocket
        if left:
            players.pop(user_id, None)
        if not players:
            _sockets.pop(game_id, None)
        return left


def peers(game_id: int, exclude_user_id: int) -> list[int]:
    """Ids of the other connected participants (call outside the lock)."""
    return [uid for uid in _sockets.get(game_id, {}) if uid != exclude_user_id]


async def send_to(game_id: int, user_id: int, message: dict[str, Any]) -> None:
    """Send to one socket, best-effort: a dead socket must not block the game."""
    websocket = _sockets.get(game_id, {}).get(user_id)
    if websocket is None:
        return
    with suppress(Exception):  # pragma: no cover - client vanished mid-send
        await websocket.send_json(message)


async def broadcast(game_id: int, message: dict[str, Any]) -> None:
    for user_id in list(_sockets.get(game_id, {})):
        await send_to(game_id, user_id, message)


def reset_hub() -> None:
    """Drop socket state (between tests; sockets themselves stay closed by
    the endpoint teardown)."""
    _sockets.clear()
