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

from app.engine.opponent import OpponentMove
from app.games.domain import Color
from app.games.service import award_ledger
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


def test_checkmate_win_bonus(authed_client: tuple[TestClient, dict], db: Session) -> None:
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

    def fake_move(
        board: chess.Board,
        for_color: Color,
        max_depth: int | None = None,
        max_time_ms: int | None = None,
    ) -> OpponentMove:
        # The opponent seam is patched wholesale: the fake binary would not
        # find mate here, and the ledger only records what it is told.
        return OpponentMove(uci="a3a1", score_cp=-100, depth=1, nodes=1, time_ms=1)

    monkeypatch.setattr("app.engine.opponent.stockfish_move", fake_move)
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


# --- Gameless ledger awards (drill/theme slots) ---------------------------


def test_gameless_award_writes_slot_key_row(
    authed_client: tuple[TestClient, dict], db: Session
) -> None:
    """A drill award carries no game, is stored with its slot_key, and bumps the total."""
    client, body = authed_client
    user_id = int(body["id"])
    granted = award_ledger(db, user_id, "drill", "drill:mate-1")
    assert granted == 2
    assert _points(client) == 2
    rows = (
        db.execute(
            select(PointAward).where(PointAward.user_id == user_id, PointAward.reason == "drill")
        )
        .scalars()
        .all()
    )
    assert [(r.game_id, r.slot_key, r.delta) for r in rows] == [(None, "drill:mate-1", 2)]


def test_gameless_award_dedupes_on_slot_key(
    authed_client: tuple[TestClient, dict], db: Session
) -> None:
    """The partial unique index blocks a second award for the same (user, reason, slot)."""
    client, body = authed_client
    user_id = int(body["id"])
    assert award_ledger(db, user_id, "drill", "drill:mate-1") == 2
    # Re-solving the same drill pays nothing and writes no extra row.
    assert award_ledger(db, user_id, "drill", "drill:mate-1") == 0
    assert _points(client) == 2
    rows = (
        db.execute(
            select(PointAward).where(PointAward.user_id == user_id, PointAward.reason == "drill")
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1


def test_gameless_slots_are_independent(
    authed_client: tuple[TestClient, dict], db: Session
) -> None:
    """A different reason or slot_key is its own award — dedupe is per (user, reason, slot)."""
    client, body = authed_client
    user_id = int(body["id"])
    assert award_ledger(db, user_id, "drill", "drill:mate-1") == 2
    assert award_ledger(db, user_id, "theme_clear", "theme:mate") == 5
    assert _points(client) == 7


def test_game_slot_still_dedupes_alongside_slot_key(
    authed_client: tuple[TestClient, dict], db: Session
) -> None:
    """The existing (game_id, reason, move_number) dedupe is untouched by the new column."""
    client, _ = authed_client
    game = _create(authed_client)
    resp = client.post(
        f"/api/v1/games/{game['id']}/moves",
        json={"uci": "e2e4", "expected_version": game["version"]},
    )
    assert resp.status_code == 200, resp.text
    awards = db.execute(select(PointAward).where(PointAward.reason == "move")).scalars().all()
    # Game move rows keep a NULL slot_key and are keyed on the game/move slot.
    assert [(a.game_id, a.slot_key, a.move_number) for a in awards] == [(game["id"], None, 1)]
