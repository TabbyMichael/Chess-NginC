"""Shared test fixtures: live-Postgres DB session and authed API clients."""

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401  (register tables on Base.metadata)
from app.api.v1.deps import get_db_session, reset_rate_limits
from app.core.database import Base
from app.main import app

# Env wins (CI injects `database_url` with credentials), dev URL fallback —
# same convention as alembic/env.py; the hardcoded default has no password
# and cannot authenticate against CI's password-scram Postgres service.
TEST_DB_URL = (
    os.environ.get("database_url")  # noqa: SIM112 — compose/CI inject lowercase (REL-001)
    or os.environ.get("DATABASE_URL")
    or "postgresql+psycopg://tabbymichael@localhost:5432/chess"
)

engine = create_engine(TEST_DB_URL)
TestingSession = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture()
def db() -> Session:
    """Yield a DB session with a fresh schema per test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db: Session) -> TestClient:
    """Yield a TestClient bound to the fixture DB session."""
    reset_rate_limits()

    def override_db() -> Session:
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db_session] = override_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _wipe(db: Session) -> None:
    """Wipe every registered table in FK-safe (reverse-dependency) order.

    Registry-driven so a new model cannot silently escape cleanup (Step 0.4).
    Tolerates missing tables: the db_session fixture in
    test_game_repository.py manages its own schema lifecycle.
    """
    from sqlalchemy.exc import ProgrammingError

    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
    except ProgrammingError:
        db.rollback()


@pytest.fixture(autouse=True)
def _clean_tables(db: Session) -> None:
    """Wipe tables before/after each test."""
    _wipe(db)
    yield
    _wipe(db)


@pytest.fixture(autouse=True)
def _clean_ephemeral_state() -> Generator[None, None, None]:
    """Reset in-process state islands between tests (lobby, hubs, limiters).

    The online feature keeps queue + socket state in the process by design
    (online-plan §2/§5); without this reset tests leak pairings into
    each other.
    """
    from app.games import hub, lobby

    lobby.reset_lobby()
    hub.reset_hub()
    reset_rate_limits()
    yield
    lobby.reset_lobby()
    hub.reset_hub()
    reset_rate_limits()


@pytest.fixture()
def authed_client(client: TestClient) -> tuple[TestClient, dict]:
    """Register a user and return (client, user body) with session cookie set."""
    resp = client.post(
        "/api/v1/auth/register",
        json={"email": "player@example.com", "password": "s3cret-pass"},
    )
    assert resp.status_code == 201, resp.text
    return client, resp.json()


def _register_other(email: str) -> object:
    """Build a client fixture factory registering `email` (shared body)."""

    def factory(db: Session) -> TestClient:
        reset_rate_limits()

        def override_db() -> Session:
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_db_session] = override_db
        other = TestClient(app)
        try:
            resp = other.post(
                "/api/v1/auth/register",
                json={"email": email, "password": "s3cret-pass"},
            )
            assert resp.status_code == 201, resp.text
            yield other
        finally:
            app.dependency_overrides.clear()

    return factory


@pytest.fixture()
def other_client(db: Session) -> TestClient:
    """A second independent client (separate user) for cross-account tests."""
    yield from _register_other("opponent@example.com")(db)


@pytest.fixture()
def third_client(db: Session) -> TestClient:
    """A third account — the stranger for online-game visibility tests."""
    yield from _register_other("stranger@example.com")(db)
