"""Tests for GameRepository with ownership and version checking."""

import pytest
from sqlalchemy.orm import Session

from app.core.database import Base, SessionLocal, engine
from app.models.user import User
from app.repositories.game_repository import GameRepository


@pytest.fixture
def db_session() -> Session:
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        # Create test users
        user1 = User(email="test1@example.com", password_hash="hashed1")
        user2 = User(email="test2@example.com", password_hash="hashed2")
        session.add(user1)
        session.add(user2)
        session.commit()
        session.refresh(user1)
        session.refresh(user2)
        yield session, user1.id, user2.id
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_create_game(db_session: Session) -> None:
    session, user1_id, _ = db_session
    repo = GameRepository(session)
    game = repo.create(
        user_id=user1_id,
        mode="local",
        fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    )
    assert game.id is not None
    assert game.user_id == user1_id
    assert game.mode == "local"
    assert game.status == "active"
    assert game.version == 1


def test_get_by_id_ownership_enforced(db_session: Session) -> None:
    session, user1_id, user2_id = db_session
    repo = GameRepository(session)
    game = repo.create(
        user_id=user1_id,
        mode="local",
        fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    )

    # Owner can access
    assert repo.get_by_id(game.id, user_id=user1_id) is not None

    # Different user cannot access
    assert repo.get_by_id(game.id, user_id=user2_id) is None


def test_update_fen_version_check(db_session: Session) -> None:
    session, user1_id, _ = db_session
    repo = GameRepository(session)
    game = repo.create(
        user_id=user1_id,
        mode="local",
        fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    )

    # Correct version
    updated = repo.update_fen(
        game.id,
        user_id=user1_id,
        fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
        expected_version=1,
    )
    assert updated is not None
    assert updated.version == 2

    # Stale version
    stale = repo.update_fen(
        game.id,
        user_id=user1_id,
        fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        expected_version=1,
    )
    assert stale is None


def test_update_fen_ownership_enforced(db_session: Session) -> None:
    session, user1_id, user2_id = db_session
    repo = GameRepository(session)
    game = repo.create(
        user_id=user1_id,
        mode="local",
        fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    )

    # Different user cannot update
    updated = repo.update_fen(
        game.id,
        user_id=user2_id,
        fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
        expected_version=1,
    )
    assert updated is None


def test_add_move_ownership_enforced(db_session: Session) -> None:
    session, user1_id, user2_id = db_session
    repo = GameRepository(session)
    game = repo.create(
        user_id=user1_id,
        mode="local",
        fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    )

    # Owner can add move
    move = repo.add_move(game.id, user_id=user1_id, uci="e2e4", san="e4", move_number=1)
    assert move is not None
    assert move.uci == "e2e4"

    # Different user cannot add move
    move = repo.add_move(game.id, user_id=user2_id, uci="e7e5", san="e5", move_number=2)
    assert move is None


def test_get_moves_ownership_enforced(db_session: Session) -> None:
    session, user1_id, user2_id = db_session
    repo = GameRepository(session)
    game = repo.create(
        user_id=user1_id,
        mode="local",
        fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    )

    repo.add_move(game.id, user_id=user1_id, uci="e2e4", san="e4", move_number=1)

    # Owner can get moves
    moves = repo.get_moves(game.id, user_id=user1_id)
    assert len(moves) == 1

    # Different user cannot get moves
    moves = repo.get_moves(game.id, user_id=user2_id)
    assert len(moves) == 0


def test_rollback_after_failed_write(db_session: Session) -> None:
    """Test that failed writes are rolled back."""
    session, user1_id, user2_id = db_session
    repo = GameRepository(session)
    game = repo.create(
        user_id=user1_id,
        mode="local",
        fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    )

    # Attempt update with wrong user (should fail)
    updated = repo.update_fen(
        game.id,
        user_id=user2_id,
        fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
        expected_version=1,
    )
    assert updated is None

    # Verify game was not modified
    original = repo.get_by_id(game.id, user_id=user1_id)
    assert original.fen == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    assert original.version == 1


def test_recover_game_with_moves(db_session: Session) -> None:
    """Test game recovery with full move history."""
    session, user1_id, _ = db_session
    repo = GameRepository(session)
    game = repo.create(
        user_id=user1_id,
        mode="local",
        fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    )

    repo.add_move(game.id, user_id=user1_id, uci="e2e4", san="e4", move_number=1)
    repo.add_move(game.id, user_id=user1_id, uci="e7e5", san="e5", move_number=2)

    recovered = repo.recover_game(game.id, user_id=user1_id)
    assert recovered is not None
    recovered_game, moves = recovered
    assert recovered_game.id == game.id
    assert len(moves) == 2
    assert moves[0].uci == "e2e4"
    assert moves[1].uci == "e7e5"


def test_recover_game_ownership_enforced(db_session: Session) -> None:
    """Test that game recovery enforces ownership."""
    session, user1_id, user2_id = db_session
    repo = GameRepository(session)
    game = repo.create(
        user_id=user1_id,
        mode="local",
        fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    )

    repo.add_move(game.id, user_id=user1_id, uci="e2e4", san="e4", move_number=1)

    # Different user cannot recover
    recovered = repo.recover_game(game.id, user_id=user2_id)
    assert recovered is None
