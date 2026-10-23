"""Online WebSocket tests (Phase 3, online-plan §6/§9, §11).

Handshake rejection codes, initial state sync, move broadcast to both
players, ping/pong, and opponent_left on disconnect. The socket is a pure
transport: every action still runs through online_service.
"""

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


def _match(client_a: TestClient, client_b: TestClient) -> tuple[int, str]:
    """Queue both over REST, return (game_id, color_a)."""
    assert client_a.post("/api/v1/online/queue").json()["status"] == "queued"
    second = client_b.post("/api/v1/online/queue").json()
    assert second["status"] == "matched"
    game_id = int(second["game_id"])
    seen = client_a.get("/api/v1/online/queue").json()
    assert seen["status"] == "matched" and int(seen["game_id"]) == game_id
    return game_id, str(seen["color"])


def _ws_url(game_id: int) -> str:
    return f"/api/v1/online/ws?game_id={game_id}"


def _close_code(client: TestClient, url: str) -> int:
    """Connect expecting a pre-accept close; return the close code."""
    try:
        with client.websocket_connect(url):
            raise AssertionError("server accepted a rejected handshake")
    except WebSocketDisconnect as exc:
        return int(exc.code)


def test_ws_requires_game_id(authed_client: tuple[TestClient, dict]) -> None:
    a, _ = authed_client
    assert _close_code(a, "/api/v1/online/ws") == 4400


def test_ws_rejects_anonymous(client: TestClient) -> None:
    assert _close_code(client, _ws_url(1)) == 4401


def test_ws_rejects_stranger(
    authed_client: tuple[TestClient, dict],
    other_client: TestClient,
    third_client: TestClient,
) -> None:
    a, _ = authed_client
    game_id, _ = _match(a, other_client)
    assert _close_code(third_client, _ws_url(game_id)) == 4403


def test_ws_rejects_non_online_game(authed_client: tuple[TestClient, dict]) -> None:
    """A participant's own computer/local game closes 4403 — never a traceback."""
    a, _ = authed_client
    local_id = int(a.post("/api/v1/games", json={"mode": "local"}).json()["id"])
    assert _close_code(a, _ws_url(local_id)) == 4403


def test_ws_malformed_payload_gets_error_and_survives(
    authed_client: tuple[TestClient, dict], other_client: TestClient
) -> None:
    a, _ = authed_client
    game_id, color_a = _match(a, other_client)
    mover = a if color_a == "w" else other_client

    with mover.websocket_connect(_ws_url(game_id)) as ws:
        ws.receive_json()  # game_state
        ws.send_json({"type": "move", "payload": 5})
        assert ws.receive_json()["payload"]["detail"] == "Bad message"
        ws.send_json({"type": "ping"})
        assert ws.receive_json()["type"] == "pong"


def test_ws_move_rate_limit_shared_with_rest(
    authed_client: tuple[TestClient, dict], other_client: TestClient
) -> None:
    """The socket enforces the same per-user budget as REST (review §P1-3)."""
    from app.api.v1 import deps

    a, _ = authed_client
    game_id, color_a = _match(a, other_client)
    mover = a if color_a == "w" else other_client

    original = deps.settings.move_rate_limit_per_minute
    deps.settings.move_rate_limit_per_minute = 1
    try:
        with mover.websocket_connect(_ws_url(game_id)) as ws:
            ws.receive_json()  # game_state
            ws.send_json({"type": "move", "payload": {"uci": "e2e4", "expected_version": 1}})
            assert ws.receive_json()["type"] == "game_state"  # first move allowed
            ws.send_json({"type": "move", "payload": {"uci": "d2d4", "expected_version": 2}})
            err = ws.receive_json()
            assert err["type"] == "error"
            assert "Too many moves" in err["payload"]["detail"]
    finally:
        deps.settings.move_rate_limit_per_minute = original
        deps.reset_rate_limits()


def test_ws_state_sync_and_move_broadcast(
    authed_client: tuple[TestClient, dict], other_client: TestClient
) -> None:
    a, _ = authed_client
    game_id, color_a = _match(a, other_client)
    mover = a if color_a == "w" else other_client
    waiter = other_client if color_a == "w" else a

    with (
        mover.websocket_connect(_ws_url(game_id)) as wm,
        waiter.websocket_connect(_ws_url(game_id)) as ww,
    ):
        first = wm.receive_json()
        assert first["type"] == "game_state"
        assert first["payload"]["version"] == 1
        # The second socket's arrival notifies the peer (§6.1 event list).
        joined = wm.receive_json()
        assert joined["type"] == "opponent_joined"
        assert ww.receive_json()["type"] == "game_state"

        wm.send_json({"type": "move", "payload": {"uci": "e2e4", "expected_version": 1}})
        after = wm.receive_json()
        assert after["type"] == "game_state"
        assert after["payload"]["version"] == 2
        assert after["payload"]["moves"][-1]["uci"] == "e2e4"
        # The opponent's socket sees the same authoritative state.
        peer_after = ww.receive_json()
        assert peer_after["type"] == "game_state"
        assert peer_after["payload"]["version"] == 2


def test_ws_wrong_turn_errors_only_the_sender(
    authed_client: tuple[TestClient, dict], other_client: TestClient
) -> None:
    a, _ = authed_client
    game_id, color_a = _match(a, other_client)
    black = other_client if color_a == "w" else a
    white = a if color_a == "w" else other_client

    with (
        white.websocket_connect(_ws_url(game_id)) as ws_w,
        black.websocket_connect(_ws_url(game_id)) as ws_b,
    ):
        ws_w.receive_json()
        ws_w.receive_json()  # opponent_joined
        ws_b.receive_json()
        ws_b.send_json({"type": "move", "payload": {"uci": "e7e5", "expected_version": 1}})
        err = ws_b.receive_json()
        assert err["type"] == "error"
        assert "not your turn" in err["payload"]["detail"]
        # Failed action changes nothing: White's next event is still a pong.
        ws_b.send_json({"type": "ping"})
        assert ws_b.receive_json()["type"] == "pong"
        assert white.get(f"/api/v1/online/games/{game_id}").json()["version"] == 1


def test_ws_ping_unknown_type_and_opponent_left(
    authed_client: tuple[TestClient, dict], other_client: TestClient
) -> None:
    a, _ = authed_client
    game_id, _ = _match(a, other_client)

    with a.websocket_connect(_ws_url(game_id)) as wa:
        assert wa.receive_json()["type"] == "game_state"
        with other_client.websocket_connect(_ws_url(game_id)) as wb:
            assert wb.receive_json()["type"] == "game_state"
            assert wa.receive_json()["type"] == "opponent_joined"

            wa.send_json({"type": "ping"})
            assert wa.receive_json()["type"] == "pong"

            wa.send_json({"type": "nonsense"})
            assert wa.receive_json()["payload"]["detail"] == "Unknown type"
        # Black's socket tore down; the server's finally path announces it.
        assert wa.receive_json()["type"] == "opponent_left"
