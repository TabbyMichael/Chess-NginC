"""Shared HTTP serialization for game payloads (games + online routers).

Keeps the two routers on one response shape and one error-code mapping so
the OpenAPI contract stays a single source (API-017/021).
"""

from fastapi import HTTPException, status

from app.api.v1.schemas import GameResponse, MoveResponse
from app.games.service import (
    GameDetail,
    GameFinishedError,
    GameNotFoundError,
    IllegalMoveRequestError,
    StaleVersionError,
)


def to_game_response(detail: GameDetail) -> GameResponse:
    """Serialize a game + moves, including the online color seats."""
    return GameResponse(
        id=detail.game.id,
        mode=detail.game.mode,
        status=detail.game.status,
        fen=detail.game.fen,
        version=detail.game.version,
        moves=[MoveResponse(uci=m.uci, san=m.san, move_number=m.move_number) for m in detail.moves],
        white_user_id=detail.game.white_user_id,
        black_user_id=detail.game.black_user_id,
    )


def as_http_exception(exc: Exception) -> HTTPException:
    """Domain error → HTTP status (404 invisible, 409 conflict, 422 invalid)."""
    if isinstance(exc, GameNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, (StaleVersionError, GameFinishedError)):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, IllegalMoveRequestError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    raise exc  # pragma: no cover - unexpected
