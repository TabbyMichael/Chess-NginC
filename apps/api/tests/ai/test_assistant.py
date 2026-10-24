"""Coach assistant service + HTTP endpoint tests (Phase 11).

The answer path must be fully exercisable offline: a completed review is written
straight into the DB, and the assistant answers from those stored facts. The
conftest world has no Stockfish and no LLM key, so these tests assert the
deterministic fallback *is* the answer — and that a hallucinating model is thrown
away — rather than depending on a real engine or network.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.ai import service as assistant_service
from app.ai.provider import ChatProvider
from app.ai.rag.index import upsert_review
from app.core.database import Settings, settings

STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"

_PAYLOAD = {
    "moves": [
        {
            "ply": 1,
            "move_number": 1,
            "uci": "e2e4",
            "san": "e4",
            "pre_fen": STARTING_FEN,
            "color": "w",
            "quality": "best",
            "centipawn_loss": 0,
            "best_uci": "e2e4",
            "eval_cp": 20,
            "eval_mate": None,
            "explanation": "e4 is exactly what the engine wants.",
        },
        {
            "ply": 2,
            "move_number": 1,
            "uci": "c7c5",
            "san": "c5",
            "pre_fen": AFTER_E4,
            "color": "b",
            "quality": "blunder",
            "centipawn_loss": 250,
            "best_uci": "e7e5",
            "eval_cp": -20,
            "eval_mate": None,
            "explanation": "c5 hangs a pawn in the Sicilian Defense.",
        },
    ]
}


class _StubProvider(ChatProvider):
    """A fake LLM that always replies with a fixed string, grounded or not."""

    def __init__(self, text: str) -> None:
        self._text = text

    @property
    def name(self) -> str:
        return "stub-llm"

    def complete(self, system: str, user: str) -> str:
        return self._text


def _seed_review(db: Session, user_id: int, game_id: int, hero: str = "b") -> None:
    from app.models.game_review import GameReview

    review = GameReview(
        game_id=game_id,
        user_id=user_id,
        status="completed",
        provider="stockfish",
        depth=15,
        hero_color=hero,
        payload=_PAYLOAD,
    )
    db.add(review)
    db.commit()


def _setup(authed_client: tuple[TestClient, dict], db: Session) -> tuple[TestClient, int, int]:
    client, body = authed_client
    game = client.post("/api/v1/games", json={"mode": "computer"}).json()
    _seed_review(db, body["id"], game["id"])
    return client, game["id"], body["id"]


# --- service-level (deterministic) --------------------------------------------


def test_service_answers_deterministically_without_an_llm(
    authed_client: tuple[TestClient, dict], db: Session
) -> None:
    client, gid, uid = _setup(authed_client, db)
    review = assistant_service.ensure_completed_review(db, gid, uid)
    answer = assistant_service.answer(db, review, "how did the game go overall?", None, user_id=uid)
    assert answer.intent == "summary"
    assert answer.mode == "deterministic"
    assert answer.provider == "stockfish+book"
    assert "c5" in answer.answer
    assert any(ref.san == "c5" for ref in answer.references)


def test_service_offline_path_uses_no_engine_no_network(
    authed_client: tuple[TestClient, dict], db: Session
) -> None:
    client, gid, uid = _setup(authed_client, db)
    review = assistant_service.ensure_completed_review(db, gid, uid)
    # PLAN is an engine intent: with no binary/key it degrades to stored facts,
    # which is the whole point of the offline guarantee.
    answer = assistant_service.answer(
        db, review, "what is the best way to proceed?", 1, user_id=uid
    )
    assert answer.mode == "deterministic"
    assert answer.answer


def test_llm_invention_is_discarded_for_the_fallback(
    authed_client: tuple[TestClient, dict], db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, gid, uid = _setup(authed_client, db)
    review = assistant_service.ensure_completed_review(db, gid, uid)
    monkeypatch.setattr(
        assistant_service, "open_chat_provider", lambda: _StubProvider("Qh7# wins.")
    )
    answer = assistant_service.answer(db, review, "how did it go?", None, user_id=uid)
    assert answer.mode == "deterministic"  # invented move -> grounded() rejects it
    assert "Qh7" not in answer.answer


def test_llm_grounded_output_is_accepted_as_llm_mode(
    authed_client: tuple[TestClient, dict], db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, gid, uid = _setup(authed_client, db)
    review = assistant_service.ensure_completed_review(db, gid, uid)
    monkeypatch.setattr(
        assistant_service,
        "open_chat_provider",
        lambda: _StubProvider("Your c5 blunder lost a pawn."),
    )
    answer = assistant_service.answer(db, review, "how did it go?", None, user_id=uid)
    assert answer.mode == "llm"
    assert answer.provider == "stub-llm"


def test_cross_game_advice_reads_the_index(
    authed_client: tuple[TestClient, dict], db: Session
) -> None:
    client, gid, uid = _setup(authed_client, db)
    review = assistant_service.ensure_completed_review(db, gid, uid)
    upsert_review(db, review)  # the endpoint hook normally does this
    summary, rows = assistant_service.cross_game_advice(db, review, uid)
    assert "Sicilian Defense" in summary
    assert rows and rows[0].opening_family == "Sicilian Defense"


def test_describe_position_names_material_and_turn(
    authed_client: tuple[TestClient, dict], db: Session
) -> None:
    client, gid, uid = _setup(authed_client, db)
    review = assistant_service.ensure_completed_review(db, gid, uid)
    text = assistant_service.describe_position(db, review, 1)
    assert "Position on move" in text


def test_ensure_completed_review_requires_analysis(
    authed_client: tuple[TestClient, dict], db: Session
) -> None:
    client, body = authed_client
    gid = client.post("/api/v1/games", json={"mode": "computer"}).json()["id"]
    with pytest.raises(assistant_service.NoReviewError):
        assistant_service.ensure_completed_review(db, gid, body["id"])


# --- HTTP surface -------------------------------------------------------------


def test_unauthenticated_ask_rejected(client: TestClient) -> None:
    client.cookies.clear()
    assert client.post("/api/v1/games/1/assistant", json={"question": "hi"}).status_code == 401
    assert client.get("/api/v1/games/1/assistant/patterns").status_code == 401


def test_ask_unknown_game_is_404(authed_client: tuple[TestClient, dict]) -> None:
    client, _ = authed_client
    resp = client.post("/api/v1/games/999999/assistant", json={"question": "how did it go?"})
    assert resp.status_code == 404


def test_ask_without_review_is_409(authed_client: tuple[TestClient, dict], db: Session) -> None:
    client, body = authed_client
    gid = client.post("/api/v1/games", json={"mode": "computer"}).json()["id"]
    resp = client.post(f"/api/v1/games/{gid}/assistant", json={"question": "how did it go?"})
    assert resp.status_code == 409


def test_ask_returns_grounded_summary(authed_client: tuple[TestClient, dict], db: Session) -> None:
    client, gid, _ = _setup(authed_client, db)
    resp = client.post(
        f"/api/v1/games/{gid}/assistant", json={"question": "how did it go overall?"}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["mode"] == "deterministic"
    assert body["intent"] == "summary"
    assert body["references"]
    assert body["position_fen"]  # a real board to show


def test_ask_rejects_empty_question_and_bad_focus(
    authed_client: tuple[TestClient, dict], db: Session
) -> None:
    client, gid, _ = _setup(authed_client, db)
    assert client.post(f"/api/v1/games/{gid}/assistant", json={"question": ""}).status_code == 422
    assert (
        client.post(
            f"/api/v1/games/{gid}/assistant", json={"question": "hi", "focus_ply": 0}
        ).status_code
        == 422
    )


def test_patterns_endpoint(authed_client: tuple[TestClient, dict], db: Session) -> None:
    client, gid, uid = _setup(authed_client, db)
    from app.ai.service import ensure_completed_review

    upsert_review(db, ensure_completed_review(db, gid, uid))
    resp = client.get(f"/api/v1/games/{gid}/assistant/patterns")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "Sicilian Defense" in body["summary"]
    assert body["items"][0]["opening_family"] == "Sicilian Defense"


def test_foreign_game_is_invisible(
    authed_client: tuple[TestClient, dict], db: Session, other_client: TestClient
) -> None:
    client, gid, _ = _setup(authed_client, db)
    assert (
        other_client.post(f"/api/v1/games/{gid}/assistant", json={"question": "hi"}).status_code
        == 404
    )
    assert other_client.get(f"/api/v1/games/{gid}/assistant/patterns").status_code == 404


def test_ask_is_rate_limited(
    authed_client: tuple[TestClient, dict],
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, gid, _ = _setup(authed_client, db)
    monkeypatch.setattr(Settings, "assistant_rate_limit_per_minute", 2, raising=False)
    monkeypatch.setattr(settings, "assistant_rate_limit_per_minute", 2, raising=False)
    assert client.post(f"/api/v1/games/{gid}/assistant", json={"question": "a"}).status_code == 200
    assert client.post(f"/api/v1/games/{gid}/assistant", json={"question": "b"}).status_code == 200
    limited = client.post(f"/api/v1/games/{gid}/assistant", json={"question": "c"})
    assert limited.status_code == 429
