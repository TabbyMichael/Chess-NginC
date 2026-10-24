"""Personalised puzzles mined from the player's own reviews (REV-005).

The guarantee under test is that mining never invents or breaks content: a
puzzle appears only when the stored review carries a hero mistake/blunder with
a big centipawn loss and a legal `best_uci` that replays on a real board. An
odd, stale, opponent-side or illegal payload yields nothing rather than a
broken puzzle, and a solved one is paid for exactly once.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.game_review import GameReview

START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
LEGAL_BEST = "e2e4"  # legal for White in START
ILLEGAL_BEST = "e2e5"  # same pawn, illegal destination


def _game(client: TestClient) -> int:
    resp = client.post("/api/v1/games", json={"mode": "computer"})
    assert resp.status_code == 201, resp.text
    return int(resp.json()["id"])


def _hero_move(**overrides: Any) -> dict[str, Any]:
    move: dict[str, Any] = {
        "ply": 1,
        "color": "w",
        "quality": "blunder",
        "centipawn_loss": 200,
        "best_uci": LEGAL_BEST,
        "pre_fen": START,
        "explanation": "A stronger move was available.",
    }
    move.update(overrides)
    return move


def _seed_review(
    db: Session, game_id: int, user_id: int, moves: list[dict[str, Any]], hero_color: str = "w"
) -> None:
    db.add(
        GameReview(
            game_id=game_id,
            user_id=user_id,
            status="completed",
            provider="stockfish",
            depth=15,
            hero_color=hero_color,
            payload={"moves": moves},
        )
    )
    db.commit()


def _mine(client: TestClient) -> list[dict]:
    resp = client.get("/api/v1/training/mine")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _summary(client: TestClient) -> dict:
    return client.get("/api/v1/training/summary").json()


def _attempt(client: TestClient, key: str, uci: str) -> dict:
    resp = client.post("/api/v1/training/attempts", json={"key": key, "uci": uci})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_hero_blunder_is_mined_and_counted(
    authed_client: tuple[TestClient, dict], db: Session
) -> None:
    client, body = authed_client
    game_id = _game(client)
    _seed_review(db, game_id, int(body["id"]), [_hero_move()])
    puzzles = _mine(client)
    assert [p["key"] for p in puzzles] == [f"mine:{game_id}:1"]
    assert puzzles[0]["fen"] == START
    assert _summary(client)["mine_available"] == 1


def test_solving_a_mined_puzzle_awards_and_clears_it(
    authed_client: tuple[TestClient, dict], db: Session
) -> None:
    client, body = authed_client
    game_id = _game(client)
    _seed_review(db, game_id, int(body["id"]), [_hero_move()])
    key = f"mine:{game_id}:1"
    result = _attempt(client, key, LEGAL_BEST)
    assert result["solved"] is True
    # 'missed' theme earns the drill point but never a theme-clear bonus.
    assert result["points_awarded"] == 2
    assert _summary(client)["mine_available"] == 0


def test_puzzle_source_game_serves_a_mined_position(
    authed_client: tuple[TestClient, dict], db: Session
) -> None:
    client, body = authed_client
    game_id = _game(client)
    _seed_review(db, game_id, int(body["id"]), [_hero_move(ply=3)])
    resp = client.get("/api/v1/training/puzzle", params={"source": "game"})
    assert resp.status_code == 200, resp.text
    puzzle = resp.json()
    assert puzzle["key"] == f"mine:{game_id}:3"
    assert puzzle["source"] == "game"
    for banned in ("solution", "alternatives", "line"):
        assert banned not in puzzle


def test_illegal_best_uci_is_not_mined(authed_client: tuple[TestClient, dict], db: Session) -> None:
    client, body = authed_client
    game_id = _game(client)
    _seed_review(db, game_id, int(body["id"]), [_hero_move(best_uci=ILLEGAL_BEST)])
    assert _mine(client) == []
    assert _summary(client)["mine_available"] == 0


def test_invalid_fen_is_not_mined(authed_client: tuple[TestClient, dict], db: Session) -> None:
    client, body = authed_client
    game_id = _game(client)
    _seed_review(db, game_id, int(body["id"]), [_hero_move(pre_fen="not a position")])
    assert _mine(client) == []


def test_small_loss_and_non_hero_qualities_are_not_mined(
    authed_client: tuple[TestClient, dict], db: Session
) -> None:
    client, body = authed_client
    game_id = _game(client)
    _seed_review(
        db,
        game_id,
        int(body["id"]),
        [
            _hero_move(ply=1, centipawn_loss=50),  # below the 120 floor
            _hero_move(ply=3, quality="inaccuracy"),  # too close to call
            _hero_move(ply=5, quality="mistake"),  # a genuine mistake, mined
        ],
    )
    # Only the mistake clears every gate.
    assert [p["key"] for p in _mine(client)] == [f"mine:{game_id}:5"]


def test_opponent_mistakes_are_never_mined(
    authed_client: tuple[TestClient, dict], db: Session
) -> None:
    client, body = authed_client
    game_id = _game(client)
    # The hero was White; a Black blunder is the opponent's, not ours to drill.
    _seed_review(db, game_id, int(body["id"]), [_hero_move(color="b")], hero_color="w")
    assert _mine(client) == []


def test_duplicate_positions_are_deduped(
    authed_client: tuple[TestClient, dict], db: Session
) -> None:
    client, body = authed_client
    game_id = _game(client)
    # Same position + same answer at two plies is one drill, not two.
    _seed_review(db, game_id, int(body["id"]), [_hero_move(ply=1), _hero_move(ply=7)])
    assert len(_mine(client)) == 1


def test_only_completed_reviews_are_mined(
    authed_client: tuple[TestClient, dict], db: Session
) -> None:
    client, body = authed_client
    game_id = _game(client)
    db.add(
        GameReview(
            game_id=game_id,
            user_id=int(body["id"]),
            status="failed",
            provider="stockfish",
            depth=0,
            hero_color="w",
            payload={"moves": [_hero_move()]},
            error="engine timeout",
        )
    )
    db.commit()
    assert _mine(client) == []
