"""Training endpoints: skill progress, puzzles, and the answer verdict (LEARN-*).

Routes stay thin — validate HTTP input, call the training service, respond —
mirroring `games.py`. The load-bearing invariant lives here: a puzzle is served
without its `solution`/`alternatives`/`line`, and the answer only ever leaves the
server inside an attempt/reveal response (the frontend never determines outcomes).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.achievements.catalog import Achievement
from app.api.v1.achievements import to_response as to_achievement_response
from app.api.v1.deps import (
    enforce_same_origin,
    get_current_user,
    get_db_session,
    rate_limit_training,
)
from app.api.v1.schemas import (
    ErrorResponse,
    MinePuzzleResponse,
    PuzzleResponse,
    TrainingAttemptRequest,
    TrainingAttemptResponse,
    TrainingSummaryResponse,
    TrainingThemeProgress,
)
from app.models.user import User
from app.training import from_reviews
from app.training import service as training_service
from app.training.drills import Drill
from app.training.service import IllegalAttemptError, PuzzleNotFoundError

router = APIRouter(tags=["training"])

_DbSession = Depends(get_db_session)  # noqa: E402
_CurrentUser = Depends(get_current_user)  # noqa: E402
_SameOrigin = Depends(enforce_same_origin)  # noqa: E402
# Every attempt grades server-side and may write a ledger row, so the write
# route carries its own per-user budget (Phase 12A, RL-002).
_RateLimitTraining = Depends(rate_limit_training)  # noqa: E402

_READ_RESPONSES: dict[int | str, dict[str, object]] = {401: {"model": ErrorResponse}}
_PUZZLE_RESPONSES: dict[int | str, dict[str, object]] = {
    401: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
}
_ATTEMPT_RESPONSES: dict[int | str, dict[str, object]] = {
    401: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
}


def _puzzle_to_response(puzzle: Drill) -> PuzzleResponse:
    """Answer-free puzzle serialization: solution/alternatives/line are not read."""
    player_moves = (len(puzzle.moves) + 1) // 2 if puzzle.moves else 1
    return PuzzleResponse(
        key=puzzle.key,
        theme=puzzle.theme,
        name=puzzle.name,
        level=puzzle.level,
        fen=puzzle.fen,
        prompt=puzzle.prompt,
        source=puzzle.source,
        game_id=puzzle.game_id,
        ply=puzzle.ply,
        player_moves=player_moves,
    )


def _attempt_to_response(result: dict) -> TrainingAttemptResponse:
    unlocked: list[Achievement] = result["unlocked_achievements"]
    return TrainingAttemptResponse(
        solved=result["solved"],
        solution_san=result["solution_san"],
        solution_from=result["solution_from"],
        solution_to=result["solution_to"],
        why=result["why"],
        continuation=result["continuation"],
        points_awarded=result["points_awarded"],
        unlocked_achievements=[to_achievement_response(a) for a in unlocked],
        complete=result.get("complete", True),
        position_fen=result.get("position_fen", ""),
        played_san=result.get("played_san", []),
    )


@router.get("/training/summary", response_model=TrainingSummaryResponse, responses=_READ_RESPONSES)
def training_summary(
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> TrainingSummaryResponse:
    """Per-theme progress and headline totals (LEARN-003)."""
    data = training_service.summary(db, current_user.id)
    themes = {key: TrainingThemeProgress(**value) for key, value in data["themes"].items()}
    return TrainingSummaryResponse(
        themes=themes,
        puzzles_solved=data["puzzles_solved"],
        streak=data["streak"],
        mine_available=data["mine_available"],
    )


@router.get("/training/puzzle", response_model=PuzzleResponse, responses=_PUZZLE_RESPONSES)
def training_puzzle(
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
    theme: Annotated[str | None, Query(max_length=32)] = None,
    source: Annotated[str | None, Query(max_length=8)] = None,
) -> PuzzleResponse:
    """One puzzle, with no answer in the payload (LEARN-002)."""
    puzzle = training_service.next_puzzle(db, current_user.id, theme=theme, source=source)
    if puzzle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No puzzle available",
        )
    return _puzzle_to_response(puzzle)


def _mine_to_response(puzzle: Drill) -> MinePuzzleResponse:
    # A mined puzzle always carries its source coordinates (see from_reviews).
    assert puzzle.game_id is not None and puzzle.ply is not None
    return MinePuzzleResponse(
        key=puzzle.key,
        fen=puzzle.fen,
        prompt=puzzle.prompt,
        game_id=puzzle.game_id,
        ply=puzzle.ply,
    )


@router.get(
    "/training/mine",
    response_model=list[MinePuzzleResponse],
    responses=_READ_RESPONSES,
)
def training_mine(
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> list[MinePuzzleResponse]:
    """Missed-move puzzles from the caller's own analysed games (REV-005)."""
    return [_mine_to_response(p) for p in from_reviews.mine_puzzles(db, current_user.id)]


@router.post(
    "/training/attempts",
    response_model=TrainingAttemptResponse,
    responses=_ATTEMPT_RESPONSES,
    dependencies=[_SameOrigin, _RateLimitTraining],
)
def submit_attempt(
    payload: TrainingAttemptRequest,
    current_user: Annotated[User, _CurrentUser],
    db: Annotated[Session, _DbSession],
) -> TrainingAttemptResponse:
    """Grade a move (or reveal on request): verdict + answer + points + unlocks."""
    try:
        if payload.reveal:
            result = training_service.reveal(db, current_user.id, payload.key)
        elif payload.moves:
            # Multi-move stepper: replay the cumulative own-moves server-side.
            result = training_service.record_sequence_attempt(
                db, current_user.id, payload.key, payload.moves
            )
        else:
            result = training_service.record_attempt(db, current_user.id, payload.key, payload.uci)
    except PuzzleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from None
    except IllegalAttemptError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from None
    return _attempt_to_response(result)
