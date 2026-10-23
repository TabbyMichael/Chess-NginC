"""Achievement endpoints (ACH-005/006/007).

Reads are cheap views over the catalog plus the player's unlock rows. Mutating
game actions carry fresh unlocks in `GameResponse.unlocked_achievements`; the
client acknowledges them here so a celebration is shown exactly once.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.achievements import service as achievement_service
from app.achievements.catalog import Achievement
from app.api.v1.deps import enforce_same_origin, get_current_user, get_db_session
from app.api.v1.schemas import (
    AchievementListResponse,
    AchievementProgressResponse,
    AchievementResponse,
    AchievementSeenRequest,
    ErrorResponse,
    MessageResponse,
)
from app.games.domain import GameStatus
from app.games.service import GameDetail
from app.models.user import User

router = APIRouter(tags=["achievements"])

_DbSession = Depends(get_db_session)  # noqa: E402
_CurrentUser = Depends(get_current_user)  # noqa: E402
_SameOrigin = Depends(enforce_same_origin)  # noqa: E402


def to_response(achievement: Achievement) -> AchievementResponse:
    """Catalog entry → API shape."""
    return AchievementResponse(
        key=achievement.key,
        title=achievement.title,
        description=achievement.description,
        metric=achievement.metric,
        threshold=achievement.threshold,
        tier=achievement.tier.value,
        group=achievement.group,
    )


def celebrate(db: Session, user_id: int) -> list[AchievementResponse]:
    """Persist and return everything this player just earned (ACH-006)."""
    return [to_response(a) for a in achievement_service.flush(db, user_id)]


def celebrate_at_end(db: Session, detail: GameDetail, user_id: int) -> list[AchievementResponse]:
    """Evaluate only on terminal transitions.

    Most achievements flip when a game finishes, and the stat aggregation is
    heavy enough that running it on every single ply is not worth it. Mid-game
    milestones still surface: `GET /me/achievements/new` re-evaluates lazily.
    """
    if detail.game.status == GameStatus.ACTIVE.value:
        return []
    return celebrate(db, user_id)


@router.get(
    "/me/achievements",
    response_model=AchievementListResponse,
    responses={401: {"model": ErrorResponse}},
)
def list_achievements(
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> AchievementListResponse:
    """The full catalog with this player's progress (ACH-005)."""
    entries = achievement_service.gallery(db, current_user.id)
    return AchievementListResponse(
        total=len(entries),
        unlocked=sum(1 for entry in entries if entry.unlocked),
        items=[
            AchievementProgressResponse(
                **to_response(entry.achievement).model_dump(),
                value=entry.value,
                unlocked=entry.unlocked,
                progress=round(entry.ratio, 4),
                unlocked_at=entry.unlocked_at.isoformat() if entry.unlocked_at else None,
            )
            for entry in entries
        ],
    )


@router.get(
    "/me/achievements/new",
    response_model=list[AchievementResponse],
    responses={401: {"model": ErrorResponse}},
)
def new_achievements(
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> list[AchievementResponse]:
    """Unlocks not yet celebrated — evaluated lazily on read (ACH-006)."""
    return [to_response(a) for a in achievement_service.pending(db, current_user.id)]


@router.post(
    "/me/achievements/seen",
    response_model=MessageResponse,
    responses={401: {"model": ErrorResponse}},
    dependencies=[_SameOrigin],
    status_code=status.HTTP_200_OK,
)
def mark_seen(
    payload: AchievementSeenRequest,
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> MessageResponse:
    """Acknowledge celebrated achievements so they are not replayed (ACH-007)."""
    count = achievement_service.mark_seen(db, current_user.id, payload.keys)
    return MessageResponse(message=f"Acknowledged {count} achievement(s)")
