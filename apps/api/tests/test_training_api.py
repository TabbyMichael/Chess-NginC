"""Training API + service behaviour (LEARN-002/003/005).

Covers the load-bearing invariants: the puzzle payload is answer-free, the
verdict is decided server-side, first-solve points are deduped on a ledger slot,
and the ramp raises after three correct / drops after two wrong.
"""

from __future__ import annotations

import chess
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.point_award import PointAward
from app.training import service
from app.training.drills import DRILLS
from app.training.models import TrainingAttempt
from app.training.verify import VALID_THEMES

MATE_1 = next(d for d in DRILLS if d.key == "mate-1")  # sol a1a8, fen back-rank mate
WRONG_LEGAL = "a1a2"  # legal rook move in mate-1's position, but not the mate

# A two-move sequence (three plies: own, forced reply, own mate) is the simplest
# multi-move puzzle to drive the stepper through in tests.
SEQ = next(d for d in DRILLS if d.theme == "sequence" and len(d.moves) == 3)
SEQ_PLAYER_MOVES = list(SEQ.moves[0::2])  # the own-moves the player must replay


def _points(client: TestClient) -> int:
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    return int(resp.json()["points"])


def _attempt(client: TestClient, key: str, uci: str, reveal: bool = False) -> dict:
    resp = client.post("/api/v1/training/attempts", json={"key": key, "uci": uci, "reveal": reveal})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _attempt_moves(client: TestClient, key: str, moves: list[str]) -> dict:
    resp = client.post("/api/v1/training/attempts", json={"key": key, "moves": moves})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _seq_rows(db: Session, user_id: int) -> list[TrainingAttempt]:
    return list(
        db.execute(
            select(TrainingAttempt).where(
                TrainingAttempt.user_id == user_id, TrainingAttempt.puzzle_key == SEQ.key
            )
        ).scalars()
    )


# --- Puzzle payload is answer-free -----------------------------------------


def test_puzzle_payload_has_no_answer(authed_client: tuple[TestClient, dict]) -> None:
    client, _ = authed_client
    resp = client.get("/api/v1/training/puzzle", params={"theme": "mate"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    for banned in ("solution", "alternatives", "line"):
        assert banned not in body, f"{banned} leaked to the client"
    assert body["fen"] and body["key"] == MATE_1.key


def test_puzzle_themes_are_valid(authed_client: tuple[TestClient, dict]) -> None:
    client, _ = authed_client
    for theme in VALID_THEMES - {"missed"}:
        resp = client.get("/api/v1/training/puzzle", params={"theme": theme})
        assert resp.status_code == 200, resp.text
        assert resp.json()["theme"] == theme


# --- Summary ---------------------------------------------------------------


def test_summary_empty_state(authed_client: tuple[TestClient, dict]) -> None:
    client, _ = authed_client
    body = client.get("/api/v1/training/summary").json()
    assert body["puzzles_solved"] == 0
    assert body["streak"] == 0
    assert body["mine_available"] == 0
    assert len(body["themes"]) == len(VALID_THEMES - {"missed"})
    for theme in body["themes"].values():
        assert theme["level"] == 1 and theme["solved"] == 0 and theme["attempts"] == 0


# --- Verdict, points, ledger ----------------------------------------------


def test_correct_answer_solves_awards_and_reveals(
    authed_client: tuple[TestClient, dict], db: Session
) -> None:
    client, body = authed_client
    result = _attempt(client, MATE_1.key, MATE_1.solution)
    assert result["solved"] is True
    assert result["solution_san"]  # reveal carries the answer
    # First solve of the first mate drill: 2 (drill) + 5 (theme cleared).
    assert result["points_awarded"] == 7
    assert _points(client) == 7
    rows = (
        db.execute(
            select(PointAward).where(PointAward.user_id == body["id"], PointAward.reason == "drill")
        )
        .scalars()
        .all()
    )
    assert [r.slot_key for r in rows] == [f"drill:{MATE_1.key}"]
    assert all(r.game_id is None for r in rows)


def test_re_solve_does_not_double_award(
    authed_client: tuple[TestClient, dict], db: Session
) -> None:
    client, body = authed_client
    _attempt(client, MATE_1.key, MATE_1.solution)
    again = _attempt(client, MATE_1.key, MATE_1.solution)
    assert again["points_awarded"] == 0
    assert _points(client) == 7  # unchanged
    slots = (
        db.execute(
            select(PointAward).where(PointAward.user_id == body["id"], PointAward.reason == "drill")
        )
        .scalars()
        .all()
    )
    assert len(slots) == 1  # one drill row despite two solves


def test_wrong_answer_reveals_without_points(authed_client: tuple[TestClient, dict]) -> None:
    client, _ = authed_client
    result = _attempt(client, MATE_1.key, WRONG_LEGAL)
    assert result["solved"] is False
    assert result["points_awarded"] == 0
    assert result["solution_san"]  # still shown the answer, honestly
    assert _points(client) == 0


def test_reveal_awards_nothing(authed_client: tuple[TestClient, dict]) -> None:
    client, _ = authed_client
    result = _attempt(client, MATE_1.key, "", reveal=True)
    assert result["solved"] is False
    assert result["points_awarded"] == 0
    assert _points(client) == 0


# --- Error mapping ---------------------------------------------------------


def test_illegal_uci_is_422(authed_client: tuple[TestClient, dict]) -> None:
    client, _ = authed_client
    resp = client.post("/api/v1/training/attempts", json={"key": MATE_1.key, "uci": "e2e4"})
    assert resp.status_code == 422, resp.text


def test_unknown_key_is_404(authed_client: tuple[TestClient, dict]) -> None:
    client, _ = authed_client
    resp = client.post("/api/v1/training/attempts", json={"key": "nope-1", "uci": "e2e4"})
    assert resp.status_code == 404, resp.text


def test_attempts_require_same_origin(authed_client: tuple[TestClient, dict]) -> None:
    client, _ = authed_client
    resp = client.post(
        "/api/v1/training/attempts",
        json={"key": MATE_1.key, "uci": MATE_1.solution},
        headers={"Origin": "https://evil.example"},
    )
    assert resp.status_code == 403, resp.text


def test_all_training_routes_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/training/summary").status_code == 401
    assert client.get("/api/v1/training/puzzle").status_code == 401
    assert client.get("/api/v1/training/mine").status_code == 401
    assert (
        client.post("/api/v1/training/attempts", json={"key": "x", "uci": "e2e4"}).status_code
        == 401
    )


# --- Achievements ride the response ---------------------------------------


def test_solving_unlocks_training_achievements(authed_client: tuple[TestClient, dict]) -> None:
    client, _ = authed_client
    result = _attempt(client, MATE_1.key, MATE_1.solution)
    groups = {a["group"] for a in result["unlocked_achievements"]}
    assert "training" in groups


# --- Ramp ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("recent", "expected"),
    [
        ([True, True, True], 1),
        ([False, False], -1),
        ([True, True, False, False], -1),
        ([True, False], 0),
        ([False, True, True], 0),
        ([], 0),
    ],
)
def test_next_level_rule(recent: list[bool], expected: int) -> None:
    assert service.next_level(recent) == expected


def test_three_correct_raises_level_two_wrong_lowers(
    authed_client: tuple[TestClient, dict], db: Session
) -> None:
    client, body = authed_client
    user_id = int(body["id"])
    # Re-solving one level-1 drill three times proves the ramp independent of the
    # catalog's own difficulty ordering (a fresh mate theme starts at level 1).
    assert service.summary(db, user_id)["themes"]["mate"]["level"] == 1
    for _ in range(3):
        _attempt(client, MATE_1.key, MATE_1.solution)
    assert service.summary(db, user_id)["themes"]["mate"]["level"] == 2
    # Two wrong in a row steps back down.
    _attempt(client, MATE_1.key, WRONG_LEGAL)
    _attempt(client, MATE_1.key, WRONG_LEGAL)
    assert service.summary(db, user_id)["themes"]["mate"]["level"] == 1


# --- Multi-move sequence stepper ------------------------------------------


def test_sequence_puzzle_exposes_move_count_but_no_answer(
    authed_client: tuple[TestClient, dict],
) -> None:
    client, _ = authed_client
    body = client.get("/api/v1/training/puzzle", params={"theme": "sequence"}).json()
    assert body["theme"] == "sequence"
    assert body["player_moves"] >= 2  # multi-move by construction
    for banned in ("solution", "alternatives", "line", "moves"):
        assert banned not in body, f"{banned} leaked to the client"


def test_sequence_first_ply_is_in_progress_and_logs_nothing(
    authed_client: tuple[TestClient, dict], db: Session
) -> None:
    client, body = authed_client
    result = _attempt_moves(client, SEQ.key, SEQ_PLAYER_MOVES[:1])
    assert result["complete"] is False
    assert result["solved"] is False
    assert result["position_fen"]  # board after the scripted forced reply
    assert result["played_san"] == [result["played_san"][0]]  # just the one ply
    assert result["solution_san"] == ""  # answer withheld mid-run
    assert result["points_awarded"] == 0
    assert _seq_rows(db, int(body["id"])) == []  # nothing logged until resolved


def test_sequence_full_line_solves_with_one_row(
    authed_client: tuple[TestClient, dict], db: Session
) -> None:
    client, body = authed_client
    result = _attempt_moves(client, SEQ.key, SEQ_PLAYER_MOVES)
    assert result["complete"] is True
    assert result["solved"] is True
    assert result["solution_san"]  # revealed on completion
    assert result["points_awarded"] == 7  # drill (2) + first sequence-theme clear (5)
    assert _points(client) == 7
    rows = _seq_rows(db, int(body["id"]))
    assert len(rows) == 1 and rows[0].solved is True


def test_sequence_wrong_ply_fails_reveals_and_logs_one(
    authed_client: tuple[TestClient, dict], db: Session
) -> None:
    client, body = authed_client
    board = chess.Board(SEQ.fen)
    wrong = next(m.uci() for m in board.legal_moves if m.uci() != SEQ.moves[0])
    result = _attempt_moves(client, SEQ.key, [wrong])
    assert result["complete"] is True
    assert result["solved"] is False
    assert result["solution_san"]  # the line is shown honestly
    assert result["points_awarded"] == 0
    assert _points(client) == 0
    rows = _seq_rows(db, int(body["id"]))
    assert len(rows) == 1 and rows[0].solved is False


def test_sequence_illegal_ply_is_422(authed_client: tuple[TestClient, dict]) -> None:
    client, _ = authed_client
    resp = client.post("/api/v1/training/attempts", json={"key": SEQ.key, "moves": ["e2e4"]})
    assert resp.status_code == 422, resp.text
