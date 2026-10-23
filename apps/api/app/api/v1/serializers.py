"""Shared HTTP serialization for game payloads (games + online routers).

Keeps the two routers on one response shape and one error-code mapping so
the OpenAPI contract stays a single source (API-017/021).
"""

from fastapi import HTTPException, status

from app.api.v1.schemas import (
    AchievementResponse,
    GameResponse,
    MoveResponse,
    ReviewResponse,
)
from app.games.errors import EngineUnavailableError
from app.games.service import (
    GameDetail,
    GameFinishedError,
    GameNotFoundError,
    IllegalMoveRequestError,
    StaleVersionError,
)
from app.models.game_review import GameReview
from app.reviews.service import ReviewTargetError


def to_game_response(
    detail: GameDetail,
    unlocked: list[AchievementResponse] | None = None,
) -> GameResponse:
    """Serialize a game + moves, including the online color seats.

    `unlocked` carries achievements earned by this very action (ACH-006) so
    the client can celebrate them without an extra round trip.
    """
    return GameResponse(
        id=detail.game.id,
        mode=detail.game.mode,
        status=detail.game.status,
        fen=detail.game.fen,
        version=detail.game.version,
        moves=[MoveResponse(uci=m.uci, san=m.san, move_number=m.move_number) for m in detail.moves],
        white_user_id=detail.game.white_user_id,
        black_user_id=detail.game.black_user_id,
        unlocked_achievements=list(unlocked or []),
    )


def to_review_response(
    review: GameReview,
    unlocked: list[AchievementResponse] | None = None,
) -> ReviewResponse:
    """Serialize a stored review row; the payload is unpacked defensively."""
    payload = review.payload or {}
    return ReviewResponse(
        id=review.id,
        game_id=review.game_id,
        status=review.status,
        provider=review.provider,
        depth=review.depth,
        hero_color=review.hero_color,
        error=review.error,
        summary=payload.get("summary", {}),
        counts=payload.get("counts", {}),
        moves=payload.get("moves", []),
        eval_graph=payload.get("eval_graph", []),
        improvements=payload.get("improvements", []),
        unlocked_achievements=list(unlocked or []),
    )


def as_http_exception(exc: Exception) -> HTTPException:
    """Domain error → HTTP status (404 invisible, 409 conflict, 422 invalid, 503 engine down)."""
    if isinstance(exc, GameNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, (StaleVersionError, GameFinishedError)):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, (IllegalMoveRequestError, ReviewTargetError)):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    if isinstance(exc, EngineUnavailableError):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    raise exc  # pragma: no cover - unexpected
