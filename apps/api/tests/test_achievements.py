"""Achievement tests: catalog (ACH-001/002), stats (ACH-003), unlocks (ACH-004..007).

Three layers are covered deliberately:

* the catalog is pure data, so its invariants (size, unique keys, rarity shape)
  are checked without a database;
* the stats layer is checked against hand-counted rows, because the SQL FILTER
  aggregates are the only place SAN patterns are interpreted;
* unlocks are checked end to end through the API, since the celebration rides on
  game responses.
"""

from datetime import datetime

import chess
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.achievements.catalog import (
    CATALOG,
    LADDERS,
    MIN_CATALOG_SIZE,
    Achievement,
    Tier,
    achievement_by_key,
    metric_names,
)
from app.achievements.service import earned_keys, flush, gallery
from app.achievements.stats import compute_stats
from app.models.game import Game as GameRow
from app.models.game_move import GameMove as GameMoveRow
from app.models.game_review import GameReview
from app.models.point_award import PointAward
from app.models.user_achievement import UserAchievement

MATE_IN_ONE_WHITE = "6k1/5ppp/8/8/8/8/8/R6K w - - 0 1"

# One ply of each interesting kind: pawn, piece, capture, check, mate, castle,
# promotion. Expected aggregates are written out by hand below.
SCRIPTED_SANS = [
    "e4",  # pawn
    "e5",  # pawn
    "Nf3",  # knight
    "Nc6",  # knight
    "Bc4",  # bishop
    "d5",  # pawn
    "exd5",  # pawn capture
    "Bb4+",  # bishop check
    "O-O",  # castling
    "a8=Q",  # promotion
    "Qb5+",  # queen check
    "Qd8#",  # queen checkmate
]


def _seed_game(db: Session, user_id: int, mode: str = "computer") -> int:
    """Insert a game row directly.

    The lobby owns online pairing, so the service refuses `mode='online'`;
    the stats layer only reads the stored mode/status anyway.
    """
    game = GameRow(user_id=user_id, mode=mode, status="active", fen=chess.STARTING_FEN)
    db.add(game)
    db.commit()
    return int(game.id)


def _seed_moves(db: Session, game_id: int, sans: list[str]) -> None:
    for index, san in enumerate(sans, start=1):
        db.add(GameMoveRow(game_id=game_id, uci=f"m{index}", san=san, move_number=index))
    db.commit()


def _seed_award(
    db: Session,
    user_id: int,
    game_id: int,
    reason: str,
    delta: int,
    day: datetime,
    move_number: int | None = None,
) -> None:
    db.add(
        PointAward(
            user_id=user_id,
            game_id=game_id,
            reason=reason,
            delta=delta,
            move_number=move_number,
            created_at=day,
        )
    )
    db.commit()


def _seed_review(
    db: Session,
    user_id: int,
    game_id: int,
    *,
    hero_color: str = "w",
    counts: dict[str, int] | None = None,
    accuracy: dict[str, int] | None = None,
    status: str = "completed",
) -> None:
    db.add(
        GameReview(
            game_id=game_id,
            user_id=user_id,
            status=status,
            hero_color=hero_color,
            payload={"counts": counts or {}, "summary": {"accuracy": accuracy or {}}},
        )
    )
    db.commit()


def _keys(items: list[dict]) -> set[str]:
    return {str(item["key"]) for item in items}


class TestCatalog:
    """ACH-001/002: the catalog is a product requirement, not an implementation note."""

    def test_holds_more_than_two_hundred_achievements(self) -> None:
        assert len(CATALOG) >= MIN_CATALOG_SIZE == 200

    def test_keys_are_unique_and_derive_from_metric_and_threshold(self) -> None:
        keys = [achievement.key for achievement in CATALOG]
        assert len(set(keys)) == len(keys)
        assert all(a.key == f"{a.metric}-{a.threshold}" for a in CATALOG)

    def test_every_threshold_is_positive_and_tiers_are_known(self) -> None:
        assert all(a.threshold >= 1 for a in CATALOG)
        assert {a.tier for a in CATALOG} <= set(Tier)

    def test_ladders_get_rarer_as_they_deepen(self) -> None:
        order = [t.value for t in Tier]
        by_metric: dict[str, list[Achievement]] = {}
        for achievement in CATALOG:
            by_metric.setdefault(achievement.metric, []).append(achievement)
        assert set(by_metric) == {ladder.metric for ladder in LADDERS}
        for entries in by_metric.values():
            ranks = [order.index(a.tier.value) for a in sorted(entries, key=lambda e: e.threshold)]
            assert ranks == sorted(ranks), "rarity must never decrease up a ladder"
            assert ranks[0] == 0, "every ladder starts at bronze"
            assert ranks[-1] >= 3, "every ladder ends at diamond or legendary"

    def test_lookup_by_key(self) -> None:
        first = CATALOG[0]
        assert achievement_by_key(first.key) == first
        assert achievement_by_key("no-such-achievement") is None


class TestStats:
    """ACH-003: the aggregation layer must feed every metric the catalog names."""

    def test_every_catalog_metric_is_computed(
        self, db: Session, authed_client: tuple[TestClient, dict]
    ) -> None:
        _, body = authed_client
        stats = compute_stats(db, int(body["id"]))
        assert metric_names() <= set(stats)

    def test_empty_player_reads_zero_everywhere(
        self, db: Session, authed_client: tuple[TestClient, dict]
    ) -> None:
        _, body = authed_client
        stats = compute_stats(db, int(body["id"]))
        assert all(value == 0 for value in stats.values()), stats

    def test_move_patterns_are_classified(
        self, db: Session, authed_client: tuple[TestClient, dict]
    ) -> None:
        _, body = authed_client
        user_id = int(body["id"])
        game_id = _seed_game(db, user_id, mode="local")
        _seed_moves(db, game_id, SCRIPTED_SANS)

        stats = compute_stats(db, user_id)
        assert stats["moves_total"] == 12
        assert stats["captures"] == 1
        assert stats["checks"] == 3
        assert stats["checkmates"] == 1
        assert stats["castles"] == 1
        assert stats["promotions"] == 1
        assert stats["pawn_moves"] == 5
        assert stats["knight_moves"] == 2
        assert stats["bishop_moves"] == 2
        assert stats["rook_moves"] == 0
        assert stats["queen_moves"] == 2
        assert stats["king_moves"] == 0
        assert stats["piece_variety"] == 4
        assert stats["longest_game"] == 12

    def test_longest_game_is_the_max_not_the_sum(
        self, db: Session, authed_client: tuple[TestClient, dict]
    ) -> None:
        _, body = authed_client
        user_id = int(body["id"])
        _seed_moves(db, _seed_game(db, user_id, mode="local"), SCRIPTED_SANS[:4])
        _seed_moves(db, _seed_game(db, user_id, mode="local"), SCRIPTED_SANS[:8])
        assert compute_stats(db, user_id)["longest_game"] == 8

    def test_results_come_from_the_point_ledger(
        self, db: Session, authed_client: tuple[TestClient, dict]
    ) -> None:
        _, body = authed_client
        user_id = int(body["id"])
        computer = _seed_game(db, user_id, mode="computer")
        online = _seed_game(db, user_id, mode="online")
        today = datetime(2026, 1, 4, 9, 0)
        _seed_award(db, user_id, computer, "win", 10, today)
        _seed_award(db, user_id, online, "win", 10, today)
        _seed_award(db, user_id, computer, "draw", 5, today)
        _seed_award(db, user_id, computer, "loss", 3, today)
        # Move awards are play records too: they count toward the habit stats.
        _seed_award(db, user_id, computer, "move", 1, datetime(2026, 1, 2, 8, 0), move_number=1)
        _seed_award(db, user_id, computer, "move", 1, datetime(2026, 1, 3, 8, 0), move_number=2)

        stats = compute_stats(db, user_id)
        assert stats["wins"] == 2
        assert stats["computer_wins"] == 1
        assert stats["online_wins"] == 1
        assert stats["draws"] == 1
        assert stats["losses"] == 1
        assert stats["active_days"] == 3
        # 2nd, 3rd and 4th of January are consecutive; 1st is missing.
        assert stats["best_streak_days"] == 3

    def test_local_games_do_not_produce_results(
        self, db: Session, authed_client: tuple[TestClient, dict]
    ) -> None:
        """The ledger is the result source and hot-seat play awards nothing."""
        _, body = authed_client
        user_id = int(body["id"])
        game_id = _seed_game(db, user_id, mode="local")
        row = db.get(GameRow, game_id)
        assert row is not None
        row.status = "resigned"
        db.commit()
        stats = compute_stats(db, user_id)
        assert stats["local_games"] == 1
        assert stats["games_completed"] == 1
        assert stats["wins"] == stats["draws"] == stats["losses"] == 0
        assert stats["active_days"] == 0

    def test_review_metrics(self, db: Session, authed_client: tuple[TestClient, dict]) -> None:
        _, body = authed_client
        user_id = int(body["id"])
        _seed_review(
            db,
            user_id,
            _seed_game(db, user_id),
            counts={"brilliant": 2, "blunder": 0, "mistake": 0},
            accuracy={"w": 91, "b": 64},
        )
        _seed_review(
            db,
            user_id,
            _seed_game(db, user_id),
            hero_color="b",
            counts={"brilliant": 1, "blunder": 3},
            accuracy={"w": 40, "b": 78},
        )
        _seed_review(db, user_id, _seed_game(db, user_id), status="failed")

        stats = compute_stats(db, user_id)
        assert stats["reviews_completed"] == 2
        assert stats["brilliant_found"] == 3
        assert stats["blunder_free_games"] == 1
        # best_accuracy always reads the reviewer's own color.
        assert stats["best_accuracy"] == 91

    def test_other_players_do_not_leak_into_stats(
        self,
        db: Session,
        authed_client: tuple[TestClient, dict],
        other_client: TestClient,
    ) -> None:
        _, body = authed_client
        stranger_id = int(other_client.get("/api/v1/auth/me").json()["id"])
        _seed_moves(db, _seed_game(db, stranger_id), SCRIPTED_SANS)
        stats = compute_stats(db, int(body["id"]))
        assert stats["moves_total"] == 0
        assert stats["games_total"] == 0


class TestEarnedKeys:
    """ACH-004: unlocking is a pure comparison against the stats."""

    def test_no_stats_unlock_nothing(self) -> None:
        assert earned_keys({}) == set()

    def test_thresholds_are_inclusive_and_ladder_scoped(self) -> None:
        earned = earned_keys({"wins": 5, "captures": 1})
        assert {"wins-1", "wins-2", "wins-3", "wins-5", "captures-1"} <= earned
        assert "wins-8" not in earned
        assert "captures-3" not in earned

    def test_earning_one_ladder_does_not_light_others(self) -> None:
        earned = earned_keys({"moves_total": 100})
        assert "moves_total-100" in earned
        assert not any(key.startswith("games_total-") for key in earned)


class TestFlush:
    """Persistence and idempotency of the unlock pass."""

    def test_flush_records_and_is_idempotent(
        self, db: Session, authed_client: tuple[TestClient, dict]
    ) -> None:
        _, body = authed_client
        user_id = int(body["id"])
        _seed_moves(db, _seed_game(db, user_id, mode="local"), SCRIPTED_SANS[:3])

        unlocked = flush(db, user_id)
        keys = [a.key for a in unlocked]
        catalog_order = [a.key for a in CATALOG]
        assert keys == [key for key in catalog_order if key in set(keys)]
        assert "games_total-1" in keys and "moves_total-1" in keys and "pawn_moves-1" in keys
        stored = db.execute(select(UserAchievement)).scalars().all()
        assert {row.key for row in stored} == set(keys)
        assert all(row.seen_at is None for row in stored)
        assert flush(db, user_id) == []

    def test_later_stats_only_report_the_difference(
        self, db: Session, authed_client: tuple[TestClient, dict]
    ) -> None:
        _, body = authed_client
        user_id = int(body["id"])
        game_id = _seed_game(db, user_id, mode="local")
        _seed_moves(db, game_id, SCRIPTED_SANS[:3])
        assert "moves_total-5" not in [a.key for a in flush(db, user_id)]
        _seed_moves(db, game_id, SCRIPTED_SANS[3:10])
        assert "moves_total-5" in [a.key for a in flush(db, user_id)]

    def test_gallery_carries_progress_for_locked_entries(
        self, db: Session, authed_client: tuple[TestClient, dict]
    ) -> None:
        _, body = authed_client
        user_id = int(body["id"])
        _seed_moves(db, _seed_game(db, user_id, mode="local"), SCRIPTED_SANS[:3])
        flush(db, user_id)

        entries = gallery(db, user_id)
        assert len(entries) == len(CATALOG)
        assert entries[0].unlocked, "unlocked entries sort first"
        for entry in entries:
            threshold = entry.achievement.threshold
            expected = 1.0 if entry.unlocked else min(1.0, entry.value / threshold)
            assert entry.ratio == pytest.approx(expected)
        by_key = {entry.achievement.key: entry for entry in entries}
        assert by_key["moves_total-1"].unlocked_at is not None
        assert by_key["moves_total-10000"].value == 3
        assert by_key["moves_total-10000"].unlocked_at is None


class TestSocketDelivery:
    """ACH-006 over the transport: unlocks are personal, state is shared."""

    def test_unlocks_go_to_the_actor_and_never_the_opponent(
        self, authed_client: tuple[TestClient, dict], other_client: TestClient
    ) -> None:
        client, _ = authed_client
        assert client.post("/api/v1/online/queue").json()["status"] == "queued"
        second = other_client.post("/api/v1/online/queue").json()
        game_id = int(second["game_id"])

        with (
            client.websocket_connect(f"/api/v1/online/ws?game_id={game_id}") as winner,
            other_client.websocket_connect(f"/api/v1/online/ws?game_id={game_id}") as loser,
        ):
            assert winner.receive_json()["type"] == "game_state"
            loser.receive_json()  # game_state
            winner.receive_json()  # opponent_joined for the first socket

            loser.send_json({"type": "resign"})
            shared = loser.receive_json()
            assert shared["type"] == "game_state"
            assert shared["payload"]["status"] == "resigned"
            assert shared["payload"]["unlocked_achievements"] == []
            # The acting socket gets the same state without its private payload...
            assert winner.receive_json()["payload"]["version"] == shared["payload"]["version"]
            # ...followed by its own celebration event.
            celebrated = loser.receive_json()
            assert celebrated["type"] == "achievement"
            assert "losses-1" in _keys(celebrated["payload"]["items"])


class TestEndpoints:
    """ACH-005..007: the gallery, the celebration ride, and the acknowledgement."""

    def test_gallery_requires_a_session(self, client: TestClient) -> None:
        assert client.get("/api/v1/me/achievements").status_code == 401
        assert client.get("/api/v1/me/achievements/new").status_code == 401
        assert client.post("/api/v1/me/achievements/seen", json={"keys": []}).status_code == 401

    def test_empty_gallery_for_a_brand_new_player(
        self, authed_client: tuple[TestClient, dict]
    ) -> None:
        client, _ = authed_client
        body = client.get("/api/v1/me/achievements")
        assert body.status_code == 200, body.text
        data = body.json()
        assert data["total"] == len(CATALOG)
        assert data["unlocked"] == 0
        assert all(item["unlocked"] is False for item in data["items"])

    def test_creating_a_game_celebrates_immediately(
        self, authed_client: tuple[TestClient, dict]
    ) -> None:
        client, _ = authed_client
        resp = client.post("/api/v1/games", json={"mode": "computer"})
        assert resp.status_code == 201, resp.text
        unlocked = resp.json()["unlocked_achievements"]
        assert _keys(unlocked) == {"games_total-1", "computer_games-1"}
        titles = {item["title"] for item in unlocked}
        assert "First Game" in titles
        assert all(item["tier"] == "bronze" for item in unlocked)

    def test_mid_game_moves_do_not_interrupt(self, authed_client: tuple[TestClient, dict]) -> None:
        client, _ = authed_client
        game = client.post("/api/v1/games", json={"mode": "computer"}).json()
        resp = client.post(
            f"/api/v1/games/{game['id']}/moves",
            json={"uci": "e2e4", "expected_version": game["version"]},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "active"
        assert resp.json()["unlocked_achievements"] == []

    def test_a_finished_game_carries_every_milestone_it_earned(
        self, authed_client: tuple[TestClient, dict], db: Session
    ) -> None:
        client, body = authed_client
        game = client.post("/api/v1/games", json={"mode": "computer"}).json()
        row = db.get(GameRow, int(game["id"]))
        assert row is not None
        row.fen = MATE_IN_ONE_WHITE
        db.commit()

        resp = client.post(
            f"/api/v1/games/{game['id']}/moves",
            json={"uci": "a1a8", "expected_version": game["version"]},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "checkmate"
        keys = _keys(resp.json()["unlocked_achievements"])
        assert {"games_completed-1", "moves_total-1", "checkmates-1", "rook_moves-1"} <= keys
        assert {"wins-1", "computer_wins-1", "points-1", "active_days-1"} <= keys
        # The next rung of each ladder is still out of reach.
        assert {"wins-2", "games_total-2", "captures-1"}.isdisjoint(keys)
        # The ride is exactly "earned now" minus "already recorded at creation".
        recorded = {row.key for row in db.execute(select(UserAchievement)).scalars().all()}
        assert recorded == earned_keys(compute_stats(db, int(body["id"])))
        assert recorded - keys == {"games_total-1", "computer_games-1"}

    def test_a_second_game_replays_nothing(self, authed_client: tuple[TestClient, dict]) -> None:
        client, _ = authed_client
        first = client.post("/api/v1/games", json={"mode": "computer"}).json()
        earned = _keys(first["unlocked_achievements"])
        client.post(f"/api/v1/games/{first['id']}/resign")

        second = client.post("/api/v1/games", json={"mode": "computer"})
        assert second.status_code == 201, second.text
        fresh = _keys(second.json()["unlocked_achievements"])
        assert fresh == {"games_total-2"}
        assert earned.isdisjoint(fresh)

    def test_online_results_unlock_for_both_seats(
        self, authed_client: tuple[TestClient, dict], other_client: TestClient
    ) -> None:
        """Black and White are each evaluated from their own ledger rows."""
        client, _ = authed_client
        assert client.post("/api/v1/online/queue").json()["status"] == "queued"
        second = other_client.post("/api/v1/online/queue").json()
        assert second["status"] == "matched"
        game_id = int(second["game_id"])

        # The resigning seat is celebrated by its own mutation.
        lost_resp = other_client.post(f"/api/v1/online/games/{game_id}/resign")
        assert lost_resp.status_code == 200, lost_resp.text
        lost = _keys(lost_resp.json()["unlocked_achievements"])
        assert {"games_total-1", "online_games-1", "games_completed-1", "losses-1"} <= lost

        # The winner performed no mutation, so reads stay silent and the
        # catch-up endpoint evaluates lazily on demand (ACH-006).
        state = client.get(f"/api/v1/online/games/{game_id}")
        assert state.status_code == 200, state.text
        assert state.json()["unlocked_achievements"] == []
        fresh = _keys(client.get("/api/v1/me/achievements/new").json())
        assert {"games_total-1", "online_games-1", "games_completed-1", "wins-1"} <= fresh
        assert "losses-1" not in fresh

    def test_new_lists_celebrations_once_and_seen_acks_them(
        self, authed_client: tuple[TestClient, dict]
    ) -> None:
        client, _ = authed_client
        game = client.post("/api/v1/games", json={"mode": "computer"}).json()
        keys = _keys(game["unlocked_achievements"])

        pending_resp = client.get("/api/v1/me/achievements/new")
        assert pending_resp.status_code == 200
        assert _keys(pending_resp.json()) == keys

        ack = client.post("/api/v1/me/achievements/seen", json={"keys": sorted(keys)})
        assert ack.status_code == 200, ack.text
        assert ack.json()["message"] == f"Acknowledged {len(keys)} achievement(s)"
        assert client.get("/api/v1/me/achievements/new").json() == []

    def test_seen_is_scoped_to_the_caller(self, authed_client: tuple[TestClient, dict]) -> None:
        client, _ = authed_client
        client.post("/api/v1/games", json={"mode": "computer"})
        resp = client.post("/api/v1/me/achievements/seen", json={"keys": ["wins-300"]})
        assert resp.status_code == 200, resp.text
        assert resp.json()["message"] == "Acknowledged 0 achievement(s)"

    def test_review_completion_celebrates_the_review_track(
        self,
        authed_client: tuple[TestClient, dict],
        fake_binary: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        assert fake_binary  # PATH-resolved fake UCI engine stands in for Stockfish
        monkeypatch.setattr("app.reviews.service.REVIEW_TIME_MS", 100)
        client, _ = authed_client
        game = client.post("/api/v1/games", json={"mode": "local"}).json()
        game_id = int(game["id"])
        version = int(game["version"])
        for uci in ("e2e4", "e7e5"):
            moved = client.post(
                f"/api/v1/games/{game_id}/moves", json={"uci": uci, "expected_version": version}
            )
            assert moved.status_code == 200, moved.text
            version = int(moved.json()["version"])
        assert client.post(f"/api/v1/games/{game_id}/resign").status_code == 200

        resp = client.post(f"/api/v1/games/{game_id}/review", json={})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "completed"
        # Analysing a game is the first step of its own ladder (ACH-006).
        assert "reviews_completed-1" in _keys(body["unlocked_achievements"])

        cached = client.get(f"/api/v1/games/{game_id}/review")
        assert cached.status_code == 200, cached.text
        # Reads never re-award: the metric has not moved since.
        assert cached.json()["unlocked_achievements"] == []

    def test_gallery_reports_unlocked_state(self, authed_client: tuple[TestClient, dict]) -> None:
        client, _ = authed_client
        client.post("/api/v1/games", json={"mode": "computer"})
        data = client.get("/api/v1/me/achievements").json()
        assert data["unlocked"] == 2
        by_key = {item["key"]: item for item in data["items"]}
        first = by_key["games_total-1"]
        assert first["unlocked"] is True and first["progress"] == 1.0
        assert first["unlocked_at"] is not None
        assert first["title"] == "First Game"
        deep = by_key["wins-300"]
        assert deep["unlocked"] is False and deep["progress"] == 0.0
        assert deep["tier"] == "legendary"
        partial = by_key["games_total-2"]
        assert partial["value"] == 1 and partial["progress"] == pytest.approx(0.5)
