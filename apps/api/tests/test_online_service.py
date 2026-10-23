"""Online service tests (Phase 1, online-plan §11).

Covers: pairing, turn enforcement, participant-OR-404 ownership, points for
BOTH players, version conflicts, and resign/checkmate/draw award symmetry.
Runs on the live-Postgres `db` fixture like the rest of the suite.
"""

import pytest
from sqlalchemy.orm import Session

from app.games import online_service
from app.games.domain import GameMode, GameStatus
from app.games.service import (
    GameFinishedError,
    GameNotFoundError,
    IllegalMoveRequestError,
    StaleVersionError,
)
from app.models.point_award import PointAward
from app.models.user import User

# Mate-in-one for White (Ra8#) and a bare-king draw position.
MATE_IN_ONE_WHITE = "6k1/5ppp/8/8/8/8/8/R6K w - - 0 1"
INSUFFICIENT_MATERIAL = "4k3/8/8/8/8/8/8/4K3 w - - 0 1"


def _mk_user(db: Session, email: str) -> User:
    user = User(email=email, password_hash="not-a-real-hash")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _pair(db: Session) -> tuple[User, User, object]:
    white = _mk_user(db, "white@example.com")
    black = _mk_user(db, "black@example.com")
    game = online_service.create_online_game(db, white.id, black.id)
    return white, black, game


def test_create_online_game_mirrors_white(db: Session) -> None:
    white, black, game = _pair(db)
    assert game.mode == GameMode.ONLINE.value
    assert game.user_id == white.id  # §12: legacy queries filter by user_id
    assert game.white_user_id == white.id
    assert game.black_user_id == black.id
    assert game.status == GameStatus.ACTIVE.value
    assert game.version == 1


def test_both_players_move_and_earn_points(db: Session) -> None:
    white, black, game = _pair(db)
    online_service.submit_online_move(db, game.id, white.id, "e2e4", game.version)
    after = online_service.get_online_game(db, game.id, black.id)
    detail = online_service.submit_online_move(db, game.id, black.id, "e7e5", after.game.version)

    assert [m.uci for m in detail.moves] == ["e2e4", "e7e5"]
    awards = {a.user_id: (a.reason, a.delta) for a in db.query(PointAward)}
    assert awards[white.id] == ("move", 1)
    assert awards[black.id] == ("move", 1)
    assert db.get(User, white.id).points == 1
    assert db.get(User, black.id).points == 1


def test_not_your_turn_is_rejected(db: Session) -> None:
    white, black, game = _pair(db)
    with pytest.raises(IllegalMoveRequestError, match="not your turn"):
        online_service.submit_online_move(db, game.id, black.id, "e7e5", game.version)


def test_stranger_cannot_see_the_game(db: Session) -> None:
    white, black, game = _pair(db)
    stranger = _mk_user(db, "stranger@example.com")
    with pytest.raises(GameNotFoundError):
        online_service.get_online_game(db, game.id, stranger.id)
    with pytest.raises(GameNotFoundError):
        online_service.submit_online_move(db, game.id, stranger.id, "e2e4", game.version)


def test_version_conflict(db: Session) -> None:
    white, black, game = _pair(db)
    with pytest.raises(StaleVersionError):
        online_service.submit_online_move(db, game.id, white.id, "e2e4", game.version + 5)


def test_resign_awards_win_and_loss(db: Session) -> None:
    white, black, game = _pair(db)
    detail = online_service.resign_online_game(db, game.id, black.id)
    assert detail.game.status == GameStatus.RESIGNED.value
    assert db.get(User, black.id).points == 3  # loss
    assert db.get(User, white.id).points == 10  # win
    with pytest.raises(GameFinishedError):
        online_service.resign_online_game(db, game.id, white.id)


def test_status_transition_is_compare_and_set(db: Session) -> None:
    """Only the first active→terminal write wins; losers get None (no awards)."""
    from app.repositories.game_repository import GameRepository

    white, _black, game = _pair(db)
    repo = GameRepository(db)
    assert repo.update_status(game.id, game.user_id, GameStatus.RESIGNED.value) is not None
    # Second finisher (any route) finds the row no longer active → None.
    assert repo.update_status(game.id, game.user_id, GameStatus.DRAW.value) is None
    db.refresh(game)
    assert game.status == GameStatus.RESIGNED.value
    assert db.get(User, white.id).points == 0  # raw CAS awards nothing by itself


def test_checkmate_awards_both_seats(db: Session) -> None:
    white, black, game = _pair(db)
    game.fen = MATE_IN_ONE_WHITE
    db.commit()
    detail = online_service.submit_online_move(db, game.id, white.id, "a1a8", game.version)
    assert detail.game.status == GameStatus.CHECKMATE.value
    assert db.get(User, white.id).points == 1 + 10  # move + win
    assert db.get(User, black.id).points == 3  # loss only, no move point


def test_draw_claim_awards_both(db: Session) -> None:
    white, black, game = _pair(db)
    game.fen = INSUFFICIENT_MATERIAL
    db.commit()
    detail = online_service.claim_online_draw(db, game.id, white.id)
    assert detail.game.status == GameStatus.DRAW.value
    assert db.get(User, white.id).points == 5
    assert db.get(User, black.id).points == 5


def test_draw_claim_rejected_without_position(db: Session) -> None:
    white, black, game = _pair(db)
    with pytest.raises(IllegalMoveRequestError, match="does not support"):
        online_service.claim_online_draw(db, game.id, white.id)


def test_online_games_rejected_by_legacy_endpoints(db: Session) -> None:
    """The single-owner /games routes refuse online rows (two-sided guard)."""
    from app.games import service as game_service

    white, black, game = _pair(db)
    with pytest.raises(IllegalMoveRequestError, match="online endpoints"):
        game_service.submit_move(db, game.id, white.id, "e2e4", game.version)
    with pytest.raises(IllegalMoveRequestError, match="online endpoints"):
        game_service.resign_game(db, game.id, white.id)
