"""Points ledger tests: chess.com-style scoring for computer games.

Rules under test: +1 per recorded move, win +10 / draw +5 / loss +3,
idempotent per move slot (undo-then-replay cannot farm points), and
local hot-seat games award nothing.
"""

import chess
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.engine.domain import EngineResult
from app.engine.engine import ChessEngine
from app.games.domain import Color
from app.models.game import Game as GameRow
from app.models.point_award import PointAward

MATE_IN_ONE_WHITE = "6k1/5ppp/8/8/8/8/8/R6K w - - 0 1"
MATE_IN_ONE_BLACK = "6k1/8/8/8/5b2/r7/2P1P3/3K4 b - - 0 1"


def _points(client: TestClient) -> int:
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    return int(resp.json()["points"])


def _create(authed_client: tuple[TestClient, dict], mode: str = "computer") -> dict:
    client, _ = authed_client
    resp = client.post("/api/v1/games", json={"mode": mode})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_new_user_starts_at_zero(authed_client: tuple[TestClient, dict]) -> None:
    client, body = authed_client
    assert body["points"] == 0
    assert _points(client) == 0


def test_computer_move_earns_one_point(authed_client: tuple[TestClient, dict]) -> None:
    client, _ = authed_client
    game = _create(authed_client)
    resp = client.post(
        f"/api/v1/games/{game['id']}/moves",
        json={"uci": "e2e4", "expected_version": game["version"]},
    )
    assert resp.status_code == 200, resp.text
    assert _points(client) == 1


def test_undo_replay_does_not_double_award(authed_client: tuple[TestClient, dict]) -> None:
    client, _ = authed_client
    game = _create(authed_client)
    resp = client.post(
        f"/api/v1/games/{game['id']}/moves",
        json={"uci": "e2e4", "expected_version": game["version"]},
    )
    body = resp.json()
    resp = client.post(
        f"/api/v1/games/{game['id']}/undo", json={"expected_version": body["version"]}
    )
    assert resp.status_code == 200, resp.text
    resp = client.post(
        f"/api/v1/games/{game['id']}/moves",
        json={"uci": "e2e4", "expected_version": resp.json()["version"]},
    )
    assert resp.status_code == 200, resp.text
    assert _points(client) == 1


def test_resign_adds_loss_bonus(authed_client: tuple[TestClient, dict]) -> None:
    client, _ = authed_client
    game = _create(authed_client)
    resp = client.post(
        f"/api/v1/games/{game['id']}/moves",
        json={"uci": "e2e4", "expected_version": game["version"]},
    )
    assert resp.status_code == 200, resp.text
    resp = client.post(f"/api/v1/games/{game['id']}/resign")
    assert resp.status_code == 200, resp.text
    # 1 (move) + 3 (loss bonus)
    assert _points(client) == 4


def test_local_games_award_nothing(authed_client: tuple[TestClient, dict]) -> None:
    client, _ = authed_client
    game = _create(authed_client, mode="local")
    resp = client.post(
        f"/api/v1/games/{game['id']}/moves",
        json={"uci": "e2e4", "expected_version": game["version"]},
    )
    assert resp.status_code == 200, resp.text
    resp = client.post(f"/api/v1/games/{game['id']}/resign")
    assert resp.status_code == 200, resp.text
    assert _points(client) == 0


def test_checkmate_win_bonus(
    authed_client: tuple[TestClient, dict], db: Session
) -> None:
    """User (White) delivers checkmate: +1 move and +10 win, exactly once."""
    client, _ = authed_client
    game = _create(authed_client)
    # Seed a mate-in-one position for White into the owned game.
    row = db.get(GameRow, game["id"])
    assert row is not None
    row.fen = MATE_IN_ONE_WHITE
    db.commit()
    resp = client.post(
        f"/api/v1/games/{game['id']}/moves",
        json={"uci": "a1a8", "expected_version": game["version"]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "checkmate"
    assert _points(client) == 11
    awards = db.execute(select(PointAward)).scalars().all()
    assert sorted((a.reason, a.delta) for a in awards) == [("move", 1), ("win", 10)]


def test_engine_checkmate_loss_bonus(
    authed_client: tuple[TestClient, dict], db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Engine (Black) mates the user: +loss only, and engine moves earn no point."""

    def fake_search(self: object, board: chess.Board, for_color: Color) -> EngineResult:
        return EngineResult(
            best_move="a3a1",
            score=-100,
            depth=1,
            nodes_searched=1,
            time_ms=1,
            termination="completed",
        )

    monkeypatch.setattr(ChessEngine, "search", fake_search)
    client, _ = authed_client
    game = _create(authed_client)
    row = db.get(GameRow, game["id"])
    assert row is not None
    row.fen = MATE_IN_ONE_BLACK
    db.commit()
    resp = client.post(
        f"/api/v1/games/{game['id']}/engine-move",
        json={"expected_version": game["version"]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "checkmate"
    # Engine moves earn no move point; the user gets only the loss bonus.
    assert _points(client) == 3
