"""Shared test fixtures: live-Postgres DB session and authed API clients."""

import os
import stat
import sys
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401  (register tables on Base.metadata)
from app.api.v1.deps import get_db_session, reset_rate_limits
from app.core.database import Base, settings
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


# No shebang on purpose: `env -S` splits the interpreter path on spaces, so an
# install directory like "Chess NginC" would fail to exec (exit 127). The POSIX
# wrapper below launches this through a quoted `/bin/sh` script instead.
# Written verbatim (not a format template), so f-string braces stay single.
FAKE_UCI = """import sys
def main():
    multipv = 1
    fen = None
    for line in sys.stdin:
        line = line.strip()
        if line == "uci":
            print("id name FakeStockfish")
            print("id author test")
            print("option name Threads type spin default 1 min 1 max 1")
            print("option name Hash type spin default 16 min 1 max 64")
            print("option name MultiPV type spin default 1 min 1 max 5")
            print("uciok")
        elif line == "isready":
            print("readyok")
        elif line.startswith("setoption"):
            if "multipv" in line.lower():
                try:
                    multipv = int(line.split()[-1])
                except ValueError:
                    multipv = 1
        elif line.startswith("position"):
            if " fen " in line:
                fen = line.split(" fen ", 1)[1].split(" moves ")[0]
            else:
                fen = None
        elif line.startswith("go"):
            infos = [
                ("e2e4", 20, ["e2e4", "e7e5"]),
                ("d2d4", 10, ["d2d4", "d7d5"]),
                ("g1f3", 5, ["g1f3", "g8f6"]),
            ]
            best = infos[0][0]
            if fen is not None:
                # Reply with legal moves for the side to move, so opponent
                # flows (which validate legality) work against the fake too.
                import chess

                board = chess.Board(fen)
                legal = [m.uci() for m in board.legal_moves]
                infos = [(m, 20 - 5 * i, [m]) for i, m in enumerate(legal[:3])]
                best = legal[0] if legal else "(none)"
            for i, (move, cp, pv) in enumerate(infos[:max(1, multipv)]):
                joined = " ".join(pv)
                line = f"info depth 1 multipv {i + 1} score cp {cp} pv {joined}"
                print(line)
            print(f"bestmove {best}")
        elif line == "quit":
            return
        sys.stdout.flush()
main()
"""


@pytest.fixture(autouse=True)
def _no_configured_stockfish(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests never talk to a real Stockfish, local or hosted.

    A developer machine may have the engine installed (Homebrew on macOS, an apt
    package on Linux), and the adapter probes well-known package paths precisely so
    that image works — which would make "engine unavailable" tests pass in CI and
    quietly run a 19-strength real engine locally. So the default world for tests
    has no configured path and no packaged binary: resolution goes through PATH
    only, where a test puts either the fake below or nothing at all.

    The hosted fallback is disarmed the same way: a real key sitting in .env must
    not turn a test run into paid API calls and rate-limit flakes.
    """
    monkeypatch.setattr(settings, "stockfish_path", "", raising=False)
    monkeypatch.setattr(settings, "stockfish_api_key", "", raising=False)
    monkeypatch.setattr("app.engine.stockfish.STOCKFISH_PACKAGE_PATHS", ())


@pytest.fixture()
def fake_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """A PATH-visible fake UCI engine: real Stockfish is never required in CI.

    Named plain `stockfish` so PATH lookup (opponent flow) finds it, while
    tests that pass the returned path exercise the configured-path route.
    """
    script = tmp_path / "fake-stockfish.py"
    script.write_text(FAKE_UCI)
    if os.name == "nt":
        # Windows cannot exec extensionless shebang scripts (WinError 193);
        # wrap in a .cmd so CreateProcess can launch it.
        wrapper = tmp_path / "stockfish.cmd"
        wrapper.write_text(f'@"{sys.executable}" -u "{script}" %*\n')
        monkeypatch.setenv("PATH", str(tmp_path), prepend=os.pathsep)
        return str(wrapper)
    # Quote both paths: the interpreter or the checkout may contain spaces.
    wrapper = tmp_path / "stockfish"
    wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" -u "{script}" "$@"\n')
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", str(tmp_path))
    return str(wrapper)
