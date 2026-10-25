"""Online REST + lobby tests (Phase 2, online-plan §11).

Queue/match flow with two TestClients, moves via REST, cross-account 404,
undo rejection on the legacy route, and the duplicate-queue guard.
"""

from fastapi.testclient import TestClient


def _queue(client: TestClient) -> dict:
    resp = client.post("/api/v1/online/queue")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _match_pair(a: TestClient, b: TestClient) -> tuple[int, str, str]:
    """Queue both, return (game_id, color_a, color_b)."""
    first = _queue(a)
    assert first["status"] == "queued", first
    second = _queue(b)
    assert second["status"] == "matched", second
    game_id = int(second["game_id"])
    # The waiting side learns the pairing through the no-side-effect GET.
    seen = a.get("/api/v1/online/queue")
    assert seen.status_code == 200
    body = seen.json()
    assert body["status"] == "matched"
    assert int(body["game_id"]) == game_id
    return game_id, str(body["color"]), str(second["color"])


def test_queue_then_match_assigns_opposite_colors(
    authed_client: tuple[TestClient, dict], other_client: TestClient
) -> None:
    a, _ = authed_client
    game_id, color_a, color_b = _match_pair(a, other_client)
    assert color_a != color_b
    game = a.get(f"/api/v1/online/games/{game_id}")
    assert game.status_code == 200, game.text


def test_duplicate_queue_guard(
    authed_client: tuple[TestClient, dict], other_client: TestClient
) -> None:
    a, _ = authed_client
    assert _queue(a)["status"] == "queued"
    again = _queue(a)
    assert again == {"status": "queued", "game_id": None, "color": None}
    _match_pair(a, other_client)
    # Matched users cannot take a second slot; they get the game back.
    third = _queue(a)
    assert third["status"] == "matched"


def test_leave_queue(authed_client: tuple[TestClient, dict]) -> None:
    a, _ = authed_client
    assert _queue(a)["status"] == "queued"
    resp = a.delete("/api/v1/online/queue")
    assert resp.status_code == 204
    assert a.get("/api/v1/online/queue").json()["status"] == "idle"


def test_move_via_rest_both_sides_and_points(
    authed_client: tuple[TestClient, dict], other_client: TestClient
) -> None:
    a, user_a = authed_client
    game_id, color_a, _ = _match_pair(a, other_client)
    white, black = (a, other_client) if color_a == "w" else (other_client, a)

    resp = white.post(
        f"/api/v1/online/games/{game_id}/moves",
        json={"uci": "e2e4", "expected_version": 1},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["version"] == 2
    assert len(body["moves"]) == 1

    resp = black.post(
        f"/api/v1/online/games/{game_id}/moves",
        json={"uci": "e7e5", "expected_version": body["version"]},
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["moves"]) == 2

    me_a = a.get("/api/v1/auth/me").json()["points"]
    me_b = other_client.get("/api/v1/auth/me").json()["points"]
    assert me_a == 1 and me_b == 1  # one move point each, both seats earn


def test_not_your_turn_over_rest(
    authed_client: tuple[TestClient, dict], other_client: TestClient
) -> None:
    a, _ = authed_client
    game_id, color_a, _ = _match_pair(a, other_client)
    white = a if color_a == "w" else other_client
    resp = white.post(
        f"/api/v1/online/games/{game_id}/moves", json={"uci": "e2e4", "expected_version": 1}
    )
    assert resp.status_code == 200
    # Same side again: version 2 now belongs to Black.
    resp = white.post(
        f"/api/v1/online/games/{game_id}/moves", json={"uci": "d2d4", "expected_version": 2}
    )
    assert resp.status_code == 422
    assert "not your turn" in resp.json()["detail"]


def test_stranger_gets_404_not_403(
    authed_client: tuple[TestClient, dict],
    other_client: TestClient,
    third_client: TestClient,
) -> None:
    a, _ = authed_client
    game_id, _, _ = _match_pair(a, other_client)
    resp = third_client.get(f"/api/v1/online/games/{game_id}")
    assert resp.status_code == 404
    resp = third_client.post(
        f"/api/v1/online/games/{game_id}/moves",
        json={"uci": "e2e4", "expected_version": 1},
    )
    assert resp.status_code == 404


def test_undo_rejected_for_online_games(
    authed_client: tuple[TestClient, dict], other_client: TestClient
) -> None:
    a, _ = authed_client
    game_id, color_a, _ = _match_pair(a, other_client)
    white = a if color_a == "w" else other_client
    resp = white.post(
        f"/api/v1/online/games/{game_id}/moves",
        json={"uci": "e2e4", "expected_version": 1},
    )
    assert resp.status_code == 200
    # Legacy undo route sees the row (White owns it) but refuses online games.
    resp = white.post(f"/api/v1/games/{game_id}/undo", json={"expected_version": 2})
    assert resp.status_code == 422
    assert "online endpoints" in resp.json()["detail"]


def test_resign_over_rest_scores_opponent(
    authed_client: tuple[TestClient, dict], other_client: TestClient
) -> None:
    a, _ = authed_client
    game_id, color_a, _ = _match_pair(a, other_client)
    black = other_client if color_a == "w" else a
    resp = black.post(f"/api/v1/online/games/{game_id}/resign")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "resigned"
    white = a if color_a == "w" else other_client
    assert white.get("/api/v1/auth/me").json()["points"] == 10
    assert black.get("/api/v1/auth/me").json()["points"] == 3


def test_legacy_create_game_rejects_online_mode(
    authed_client: tuple[TestClient, dict],
) -> None:
    """Only the lobby may create online games (no seat-less orphan rows)."""
    a, _ = authed_client
    resp = a.post("/api/v1/games", json={"mode": "online"})
    assert resp.status_code == 422
    assert "lobby queue" in resp.json()["detail"]


def test_legacy_games_list_unaffected_and_black_can_list(
    authed_client: tuple[TestClient, dict], other_client: TestClient
) -> None:
    a, _ = authed_client
    game_id, color_a, _ = _match_pair(a, other_client)
    white, black = (a, other_client) if color_a == "w" else (other_client, a)
    # White's legacy list (owner column) sees it...
    legacy = white.get("/api/v1/games").json()
    assert any(g["id"] == game_id for g in legacy)
    # ...Black only sees it through the online list.
    black_list = black.get("/api/v1/online/games").json()
    assert [g["id"] for g in black_list] == [game_id]
    assert black.get("/api/v1/games").json() == []
