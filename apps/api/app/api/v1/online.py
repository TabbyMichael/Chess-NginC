"""Online play endpoints: lobby queue, moves, resign/draw, WebSocket (§6).

REST stays authoritative; the socket is a transport that accelerates the same
state updates (the frontend must work polling-only if the socket dies, §6.2).
All ownership failures map to 404 — never 403 — so strangers cannot discover
that a game exists (SEC-016).
"""

import json
import time
from collections import deque
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from starlette.websockets import WebSocketDisconnect

from app.api.v1.achievements import celebrate_at_end
from app.api.v1.deps import (
    SESSION_COOKIE,
    check_move_rate,
    enforce_same_origin,
    get_current_user,
    get_db_session,
    rate_limit_moves,
    same_origin_ok,
)
from app.api.v1.schemas import (
    ErrorResponse,
    GameResponse,
    MoveRequest,
    QueueResponse,
)
from app.api.v1.serializers import as_http_exception, to_game_response
from app.auth import service as auth_service
from app.core.database import SessionLocal
from app.games import hub, lobby, online_service
from app.games.service import (
    GameDetail,
    GameFinishedError,
    GameNotFoundError,
    IllegalMoveRequestError,
    StaleVersionError,
)
from app.models.user import User

router = APIRouter(prefix="/online", tags=["online"])

# Module-level dependency singletons (E402 exempted; see games.py).
_DbSession = Depends(get_db_session)  # noqa: E402
_CurrentUser = Depends(get_current_user)  # noqa: E402
_SameOrigin = Depends(enforce_same_origin)  # noqa: E402
_MoveLimit = Depends(rate_limit_moves)  # noqa: E402

_ONLINE_ERRORS = (GameNotFoundError, StaleVersionError, GameFinishedError, IllegalMoveRequestError)

# WS guards (plan §9): message size cap and per-socket message rate.
_MAX_MESSAGE_BYTES = 4096
_MAX_MESSAGES_PER_SECOND = 10


def _detail(db: Session, game_id: int, player_id: int) -> GameDetail:
    return online_service.get_online_game(db, game_id, player_id)


@router.post(
    "/queue",
    response_model=QueueResponse,
    responses={401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
    dependencies=[_SameOrigin],
)
def join_queue(
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> QueueResponse:
    """Queue the caller for a match, or return the game they were paired into."""
    return QueueResponse(**lobby.join(db, current_user.id))


@router.delete(
    "/queue",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={401: {"model": ErrorResponse}},
    dependencies=[_SameOrigin],
)
def leave_queue(
    current_user: Annotated[User, _CurrentUser],
) -> None:
    """Cancel a pending queue slot."""
    lobby.leave(current_user.id)


@router.get(
    "/queue",
    response_model=QueueResponse,
    responses={401: {"model": ErrorResponse}},
)
def queue_status(
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> QueueResponse:
    """Poll-free state read (used by the client after page reloads, §5)."""
    return QueueResponse(**lobby.queue_status(db, current_user.id))


@router.get(
    "/games",
    response_model=list[GameResponse],
    responses={401: {"model": ErrorResponse}},
)
def list_online_games(
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> list[GameResponse]:
    """Caller's online games from either color seat (Black's list view)."""
    details = online_service.list_online_game_details(db, current_user.id)
    return [to_game_response(d) for d in details]


@router.get(
    "/games/{game_id}",
    response_model=GameResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def get_online_game(
    game_id: int,
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> GameResponse:
    """Participant-scoped fetch — works for Black, 404 for strangers (§12)."""
    try:
        return to_game_response(_detail(db, game_id, current_user.id))
    except _ONLINE_ERRORS as exc:
        raise as_http_exception(exc) from None


_MOVE_RESPONSES: dict[int | str, dict[str, object]] = {
    401: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
}


@router.post(
    "/games/{game_id}/moves",
    response_model=GameResponse,
    responses=_MOVE_RESPONSES,
    dependencies=[_SameOrigin, _MoveLimit],
)
def submit_online_move(
    game_id: int,
    payload: MoveRequest,
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> GameResponse:
    """Turn-checked move via REST (same service path as the socket)."""
    try:
        detail = online_service.submit_online_move(
            db, game_id, current_user.id, payload.uci, payload.expected_version
        )
    except _ONLINE_ERRORS as exc:
        raise as_http_exception(exc) from None
    return to_game_response(detail, celebrate_at_end(db, detail, current_user.id))


@router.post(
    "/games/{game_id}/resign",
    response_model=GameResponse,
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
    dependencies=[_SameOrigin],
)
def resign_online_game(
    game_id: int,
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> GameResponse:
    """Resign: the resigning seat gets 'loss', the opponent 'win'."""
    try:
        detail = online_service.resign_online_game(db, game_id, current_user.id)
    except _ONLINE_ERRORS as exc:
        raise as_http_exception(exc) from None
    return to_game_response(detail, celebrate_at_end(db, detail, current_user.id))


@router.post(
    "/games/{game_id}/draw-claim",
    response_model=GameResponse,
    responses=_MOVE_RESPONSES,
    dependencies=[_SameOrigin],
)
def claim_online_draw(
    game_id: int,
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> GameResponse:
    """Position-based draw claim; both seats earn the draw bonus."""
    try:
        detail = online_service.claim_online_draw(db, game_id, current_user.id)
    except _ONLINE_ERRORS as exc:
        raise as_http_exception(exc) from None
    return to_game_response(detail, celebrate_at_end(db, detail, current_user.id))


# --- WebSocket ---------------------------------------------------------


def _ws_call(fn_name: str, game_id: int, user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Sync DB work for one socket message, in its own session (thread run).

    Never share a session across sockets/messages: each unit of work opens,
    commits, and closes one session (§12 pitfall).

    Returns the actor's game state; any unlocks it carries belong to the actor
    alone, so the caller must not broadcast them to the opponent.
    """
    db = SessionLocal()
    try:
        fn = getattr(online_service, fn_name)
        if fn_name == "submit_online_move":
            detail = fn(
                db,
                game_id,
                user_id,
                str(payload.get("uci", "")),
                int(payload.get("expected_version", 0)),
            )
        elif fn_name in ("resign_online_game", "claim_online_draw"):
            detail = fn(db, game_id, user_id)
        else:  # pragma: no cover - dispatch table above is exhaustive
            raise RuntimeError(fn_name)
        return dict(to_game_response(detail, celebrate_at_end(db, detail, user_id)).model_dump())
    finally:
        db.close()


def _ws_lookup(game_id: int, user_id: int) -> dict[str, Any] | None:
    """Handshake participant check: returns the game state or None.

    Any online-service rejection (stranger, non-online game, missing row)
    closes the handshake with 4403 — nothing here may escape as a traceback.
    """
    db = SessionLocal()
    try:
        detail = online_service.get_online_game(db, game_id, user_id)
        return dict(to_game_response(detail).model_dump())
    except _ONLINE_ERRORS:
        return None
    finally:
        db.close()


def _ws_user(token: str) -> dict[str, Any] | None:
    db = SessionLocal()
    try:
        user = auth_service.authenticate(db, token)
        return {"id": user.id} if user is not None else None
    finally:
        db.close()


@router.websocket("/ws")
async def online_ws(websocket: WebSocket, game_id: int = Query(default=0)) -> None:
    """One socket per player; carries events, never decides outcomes (§2)."""
    # Origin check on the upgrade request (CSWSRF, §9).
    if not same_origin_ok(websocket.headers):
        await websocket.close(code=4403)
        return
    if game_id <= 0:
        await websocket.close(code=4400)
        return
    token = websocket.cookies.get(SESSION_COOKIE, "")
    user = await run_in_threadpool(_ws_user, token)
    if user is None:
        await websocket.close(code=4401)
        return
    user_id = int(user["id"])
    state = await run_in_threadpool(_ws_lookup, game_id, user_id)
    if state is None:
        await websocket.close(code=4403)
        return
    await websocket.accept()
    await hub.register(game_id, user_id, websocket)
    my_color = "w" if state.get("white_user_id") == user_id else "b"
    await hub.send_to(game_id, user_id, {"type": "game_state", "payload": state})
    for peer in hub.peers(game_id, user_id):
        await hub.send_to(
            game_id, peer, {"type": "opponent_joined", "payload": {"color": my_color}}
        )

    stamps: deque[float] = deque()
    try:
        while True:
            raw = await websocket.receive_text()
            if len(raw.encode("utf-8")) > _MAX_MESSAGE_BYTES:
                await hub.send_to(
                    game_id, user_id, {"type": "error", "payload": {"detail": "Message too large"}}
                )
                continue
            now = time.monotonic()
            while stamps and now - stamps[0] > 1.0:
                stamps.popleft()
            if len(stamps) >= _MAX_MESSAGES_PER_SECOND:
                await websocket.close(code=1008)
                return
            stamps.append(now)

            try:
                message = json.loads(raw)
                mtype = message["type"]
                payload = message.get("payload") or {}
                if not isinstance(mtype, str) or not isinstance(payload, dict):
                    raise ValueError("frame shape rejected")
            except (ValueError, KeyError, TypeError):
                await hub.send_to(
                    game_id, user_id, {"type": "error", "payload": {"detail": "Bad message"}}
                )
                continue

            if mtype == "ping":
                await hub.send_to(game_id, user_id, {"type": "pong", "payload": {}})
                continue

            fn_name = {
                "move": "submit_online_move",
                "resign": "resign_online_game",
                "draw_claim": "claim_online_draw",
            }.get(mtype)
            if fn_name is None:
                await hub.send_to(
                    game_id, user_id, {"type": "error", "payload": {"detail": "Unknown type"}}
                )
                continue
            if fn_name == "submit_online_move":
                # Same per-user budget as the REST route: a socket must not be
                # a cheaper transport for the same mutation (review §P1).
                try:
                    check_move_rate(user_id)
                except HTTPException as exc:
                    await hub.send_to(
                        game_id, user_id, {"type": "error", "payload": {"detail": exc.detail}}
                    )
                    continue
                try:
                    expected_version = int(payload.get("expected_version", 0))
                except (TypeError, ValueError):
                    await hub.send_to(
                        game_id, user_id, {"type": "error", "payload": {"detail": "Bad message"}}
                    )
                    continue
                call_payload = {
                    "uci": str(payload.get("uci", "")),
                    "expected_version": expected_version,
                }
            else:
                call_payload = payload
            try:
                new_state = await run_in_threadpool(
                    _ws_call, fn_name, game_id, user_id, call_payload
                )
            except _ONLINE_ERRORS as exc:
                # Failed action changes nothing; error goes to the sender only.
                await hub.send_to(
                    game_id, user_id, {"type": "error", "payload": {"detail": str(exc)}}
                )
                continue
            # Achievements are personal: the shared broadcast keeps the exact
            # response shape but carries none, and the actor gets its own list.
            unlocks = new_state.get("unlocked_achievements") or []
            shared = {**new_state, "unlocked_achievements": []}
            await hub.broadcast(game_id, {"type": "game_state", "payload": shared})
            if unlocks:
                await hub.send_to(
                    game_id, user_id, {"type": "achievement", "payload": {"items": unlocks}}
                )
    except WebSocketDisconnect:
        pass
    finally:
        if await hub.unregister(game_id, user_id, websocket):
            for peer in hub.peers(game_id, user_id):
                await hub.send_to(game_id, peer, {"type": "opponent_left", "payload": {}})
