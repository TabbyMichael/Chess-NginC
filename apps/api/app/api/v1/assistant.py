"""Coach assistant endpoints (Phase 11).

Reached from the review page's ⭐: a conversational question about the reviewed
game, answered strictly from engine + book facts (long context over the stored
review, a bounded live engine pass for what-ifs, and RAG recall across the
player's own games for "what do I keep doing wrong").

Routes stay thin like `games.py`: check access, call the assistant service, map
domain errors to HTTP. A question is a read-only, rate-limited mutation of the
conversation only, so it is same-origin-guarded like the other POSTs.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai import service as assistant_service
from app.ai.service import NoReviewError
from app.api.v1.deps import (
    enforce_same_origin,
    get_current_user,
    get_db_session,
    rate_limit_assistant,
)
from app.api.v1.schemas import (
    AssistantAnswerResponse,
    AssistantAskRequest,
    AssistantReference,
    CoachPattern,
    CoachPatternsResponse,
    ErrorResponse,
)
from app.api.v1.serializers import as_http_exception
from app.models.game_review import GameReview
from app.models.user import User
from app.reviews import service as review_service
from app.reviews.service import GameNotFoundError

router = APIRouter(tags=["assistant"])

_DbSession = Depends(get_db_session)  # noqa: E402
_CurrentUser = Depends(get_current_user)  # noqa: E402
_SameOrigin = Depends(enforce_same_origin)  # noqa: E402
_LimitAssistant = Depends(rate_limit_assistant)  # noqa: E402

_ASSISTANT_RESPONSES: dict[int | str, dict[str, object]] = {
    401: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
}


def _load_completed_review(db: Session, game_id: int, user_id: int) -> GameReview:
    """Access-check the game, then require its completed review (or 404/409)."""
    try:
        # Unknown/foreign game → 404, exactly like the review endpoints.
        review_service.load_game(db, game_id, user_id)
    except GameNotFoundError as exc:
        raise as_http_exception(exc) from None
    try:
        return assistant_service.ensure_completed_review(db, game_id, user_id)
    except NoReviewError as exc:
        # Not analysed yet (or the analysis failed): a conflict, not a secret.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None


def _to_answer_response(answer: assistant_service.CoachAnswer) -> AssistantAnswerResponse:
    return AssistantAnswerResponse(
        answer=answer.answer,
        intent=answer.intent,
        mode=answer.mode,
        provider=answer.provider,
        references=[AssistantReference(**vars(ref)) for ref in answer.references],
        position_fen=answer.position_fen,
    )


@router.post(
    "/games/{game_id}/assistant",
    response_model=AssistantAnswerResponse,
    responses=_ASSISTANT_RESPONSES,
    dependencies=[_SameOrigin, _LimitAssistant],
)
def ask_coach(
    game_id: int,
    payload: AssistantAskRequest,
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> AssistantAnswerResponse:
    """Answer a coaching question grounded in the caller's own reviewed game."""
    review = _load_completed_review(db, game_id, current_user.id)
    answer = assistant_service.answer(
        db, review, payload.question, payload.focus_ply, user_id=current_user.id
    )
    return _to_answer_response(answer)


@router.get(
    "/games/{game_id}/assistant/patterns",
    response_model=CoachPatternsResponse,
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def coach_patterns(
    game_id: int,
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> CoachPatternsResponse:
    """Cross-game recall: the openings where this player errs most (RAG)."""
    review = _load_completed_review(db, game_id, current_user.id)
    summary, rows = assistant_service.cross_game_advice(db, review, current_user.id)
    return CoachPatternsResponse(
        summary=summary,
        items=[
            CoachPattern(
                opening_family=row.opening_family,
                mistakes=row.mistakes,
                blunders=row.blunders,
                total_errors=row.total_errors,
                avg_loss_cp=row.avg_loss_cp,
            )
            for row in rows
        ],
    )
