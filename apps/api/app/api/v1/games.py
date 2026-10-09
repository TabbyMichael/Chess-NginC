"""Games endpoints: CRUD + moves + resign/draw/engine (API-005..012)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import enforce_same_origin, get_current_user, get_db_session
from app.games import service as game_service
from app.games.service import (
    GameDetail,
    GameFinishedError,
    GameNotFoundError,
    IllegalMoveRequestError,
    StaleVersionError,
)
from app.models.user import User

from .schemas import (
    CreateGameRequest,
    EngineMoveRequest,
    ErrorResponse,
    GameResponse,
    MoveRequest,
    MoveResponse,
    VersionRequest,
)

router = APIRouter(tags=["games"])

# Module-level dependency singletons (E402 exempted; see auth.py).
_DbSession = Depends(get_db_session)  # noqa: E402
_CurrentUser = Depends(get_current_user)  # noqa: E402
_SameOrigin = Depends(enforce_same_origin)  # noqa: E402


def _to_response(detail: GameDetail) -> GameResponse:
    return GameResponse(
        id=detail.game.id,
        mode=detail.game.mode,
        status=detail.game.status,
        fen=detail.game.fen,
        version=detail.game.version,
        moves=[MoveResponse(uci=m.uci, san=m.san, move_number=m.move_number) for m in detail.moves],
    )


def _map_errors(exc: Exception) -> HTTPException:
    if isinstance(exc, GameNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, (StaleVersionError, GameFinishedError)):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, IllegalMoveRequestError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    raise exc  # pragma: no cover - unexpected


@router.post(
    "/games",
    response_model=GameResponse,
    status_code=status.HTTP_201_CREATED,
    responses={401: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
    dependencies=[_SameOrigin],
)
def create_game(
    payload: CreateGameRequest,
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> GameResponse:
    """Create a game in the starting position (API-005)."""
    try:
        game = game_service.create_game(db, current_user.id, payload.mode)
    except IllegalMoveRequestError as exc:
        raise _map_errors(exc) from None
    return _to_response(game_service.get_game(db, game.id, current_user.id))


@router.get("/games", response_model=list[GameResponse])
def list_games(
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> list[GameResponse]:
    """List the caller's games (API-006)."""
    games = game_service.list_games(db, current_user.id)
    return [_to_response(game_service.get_game(db, g.id, current_user.id)) for g in games]


@router.get(
    "/games/{game_id}",
    response_model=GameResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def get_game(
    game_id: int,
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> GameResponse:
    """Fetch one game; 404 for unknown or foreign games (API-007)."""
    try:
        return _to_response(game_service.get_game(db, game_id, current_user.id))
    except GameNotFoundError as exc:
        raise _map_errors(exc) from None


_MOVE_RESPONSES: dict[int | str, dict[str, object]] = {
    401: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
}


@router.post(
    "/games/{game_id}/moves",
    response_model=GameResponse,
    responses=_MOVE_RESPONSES,
    dependencies=[_SameOrigin],
)
def submit_move(
    game_id: int,
    payload: MoveRequest,
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> GameResponse:
    """Validate + persist a UCI move (API-008/018/019)."""
    try:
        detail = game_service.submit_move(
            db, game_id, current_user.id, payload.uci, payload.expected_version
        )
    except (
        GameNotFoundError,
        StaleVersionError,
        GameFinishedError,
        IllegalMoveRequestError,
    ) as exc:
        raise _map_errors(exc) from None
    return _to_response(detail)


@router.post(
    "/games/{game_id}/undo",
    response_model=GameResponse,
    responses=_MOVE_RESPONSES,
    dependencies=[_SameOrigin],
)
def undo_move(
    game_id: int,
    payload: VersionRequest,
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> GameResponse:
    """Undo the last move (API-009)."""
    try:
        detail = game_service.undo_move(db, game_id, current_user.id, payload.expected_version)
    except (
        GameNotFoundError,
        StaleVersionError,
        GameFinishedError,
        IllegalMoveRequestError,
    ) as exc:
        raise _map_errors(exc) from None
    return _to_response(detail)


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
def resign_game(
    game_id: int,
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> GameResponse:
    """Resign an active game (API-010)."""
    try:
        detail = game_service.resign_game(db, game_id, current_user.id)
    except (GameNotFoundError, GameFinishedError) as exc:
        raise _map_errors(exc) from None
    return _to_response(detail)


@router.post(
    "/games/{game_id}/draw-claim",
    response_model=GameResponse,
    responses=_MOVE_RESPONSES,
    dependencies=[_SameOrigin],
)
def claim_draw(
    game_id: int,
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> GameResponse:
    """Claim a draw when the position supports it (API-011)."""
    try:
        detail = game_service.claim_draw(db, game_id, current_user.id)
    except (
        GameNotFoundError,
        GameFinishedError,
        IllegalMoveRequestError,
    ) as exc:
        raise _map_errors(exc) from None
    return _to_response(detail)


@router.post(
    "/games/{game_id}/engine-move",
    response_model=GameResponse,
    responses=_MOVE_RESPONSES,
    dependencies=[_SameOrigin],
)
def engine_move(
    game_id: int,
    payload: EngineMoveRequest,
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> GameResponse:
    """Request a custom-engine move within budget (API-012, SEC-013)."""
    try:
        detail = game_service.request_engine_move(
            db,
            game_id,
            current_user.id,
            payload.expected_version,
            max_depth=payload.max_depth,
            max_time_ms=payload.max_time_ms,
        )
    except (
        GameNotFoundError,
        StaleVersionError,
        GameFinishedError,
        IllegalMoveRequestError,
    ) as exc:
        raise _map_errors(exc) from None
    return _to_response(detail)
