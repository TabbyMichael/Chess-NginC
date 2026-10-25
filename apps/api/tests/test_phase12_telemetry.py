"""Phase 12A tests (D14/D15): /metrics surface, request ids, JSON logs, limiters.

Everything here is hermetic: no binary, no key, no network — the conftest world
already disarms both engines, and the limiter tests use tiny budgets.
"""

import json
import logging

import pytest
from fastapi.testclient import TestClient

from app.core import telemetry
from app.core.database import settings
from app.core.telemetry import ENGINE_ANALYSE_SECONDS, JsonFormatter, request_id_var

CUSTOM_METRICS = [
    "engine_analyse_seconds",
    "engine_unavailable_total",
    "rate_limit_rejections_total",
    "cloud_units_used_today",
    "cloud_upstream_errors_total",
    "ws_connections_active",
]


def metrics_body(client: TestClient) -> str:
    resp = client.get("/metrics")
    assert resp.status_code == 200
    return resp.text


# --- MON-002: the scrape surface --------------------------------------------------


class TestMetricsEndpoint:
    def test_serves_every_custom_instrument(self, client: TestClient) -> None:
        body = metrics_body(client)
        for name in CUSTOM_METRICS:
            assert name in body, f"{name} missing from /metrics"

    def test_instrumentator_adds_route_red(self, client: TestClient) -> None:
        body = metrics_body(client)
        # The free per-route family (name depends on instrumentator version;
        # either flavour proves the wiring landed).
        assert "http_requests_total" in body or "http_request_duration_seconds" in body

    def test_scrape_endpoint_stays_out_of_the_openapi_contract(self, client: TestClient) -> None:
        spec = client.get("/openapi.json").json()
        assert "/metrics" not in spec["paths"]


# --- MON-001: request ids + JSON lines --------------------------------------------


class TestRequestId:
    def test_response_carries_a_generated_id(self, client: TestClient) -> None:
        resp = client.get("/api/v1/health")
        assert resp.headers.get("X-Request-ID")

    def test_inbound_id_is_honored_not_replaced(self, client: TestClient) -> None:
        resp = client.get("/api/v1/health", headers={"X-Request-ID": "trace-me-1"})
        assert resp.headers["X-Request-ID"] == "trace-me-1"


def _record(msg: str = "hello") -> logging.LogRecord:
    return logging.LogRecord("t", logging.INFO, "f.py", 1, msg, None, None)


class TestJsonFormatter:
    def test_line_is_json_with_correlation_fields(self) -> None:
        token = request_id_var.set("abc123")
        try:
            entry = json.loads(JsonFormatter().format(_record()))
        finally:
            request_id_var.reset(token)
        assert entry["msg"] == "hello"
        assert entry["level"] == "INFO"
        assert entry["request_id"] == "abc123"
        assert entry["ts"].endswith("Z")

    def test_access_extras_are_whitelisted_never_secrets(self) -> None:
        # QA-019 in formatter form: only method/path/status/duration ride the
        # access line — anything else smuggled into http_access is dropped.
        rec = _record("request")
        rec.http_access = {
            "method": "POST",
            "path": "/x",
            "status": 429,
            "duration_ms": 1.0,
            "cookie": "session=SECRET",
        }
        entry = json.loads(JsonFormatter().format(rec))
        assert entry["http"]["status"] == 429
        assert "cookie" not in entry["http"]

    def test_configure_logging_swaps_formats(self) -> None:
        root = logging.getLogger()
        saved, saved_level = list(root.handlers), root.level
        try:
            telemetry.configure_logging("INFO", True)
            assert any(isinstance(h.formatter, JsonFormatter) for h in root.handlers)
            telemetry.configure_logging("INFO", False)
            assert not any(isinstance(h.formatter, JsonFormatter) for h in root.handlers)
        finally:
            root.handlers[:] = saved
            root.setLevel(saved_level)


# --- MON-003: the engine histogram records under the provider label ----------------


def test_engine_timer_observes_under_provider_label() -> None:
    with telemetry.engine_timer("unit-test-provider"):
        pass
    labeled = {
        s.labels.get("provider")
        for sample in ENGINE_ANALYSE_SECONDS.collect()
        for s in sample.samples
        if s.name.endswith("_count")
    }
    assert "unit-test-provider" in labeled


# --- RL-001/004: the cost-tiered limiter surface ------------------------------------


def _finished_local_game(client: TestClient) -> int:
    gid = client.post("/api/v1/games", json={"mode": "local"}).json()["id"]
    client.post(f"/api/v1/games/{gid}/moves", json={"uci": "e2e4", "expected_version": 1})
    client.post(f"/api/v1/games/{gid}/moves", json={"uci": "e7e5", "expected_version": 2})
    assert client.post(f"/api/v1/games/{gid}/resign").status_code == 200
    return gid


class TestRetryAfter:
    def test_auth_429_advertises_the_wait_and_counts(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "auth_rate_limit_per_minute", 1)
        body = {"email": "nobody@example.com", "password": "wrong-password"}
        assert client.post("/api/v1/auth/login", json=body).status_code == 401
        blocked = client.post("/api/v1/auth/login", json=body)
        assert blocked.status_code == 429
        assert blocked.headers["Retry-After"].isdigit()
        assert 1 <= int(blocked.headers["Retry-After"]) <= 60
        assert 'rate_limit_rejections_total{bucket="auth"}' in metrics_body(client)


class TestReviewBudget:
    """A review generation holds a warm engine (TD-013) — it is costed per hour."""

    def test_hourly_budget_blocks_further_generations(
        self, authed_client: tuple[TestClient, dict], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client, _ = authed_client
        monkeypatch.setattr(settings, "review_rate_limit_per_hour", 3)
        gid = _finished_local_game(client)
        for _ in range(3):
            assert client.post(f"/api/v1/games/{gid}/review", json={}).status_code == 200
        blocked = client.post(f"/api/v1/games/{gid}/review", json={})
        assert blocked.status_code == 429
        assert blocked.headers["Retry-After"].isdigit()
        assert 'rate_limit_rejections_total{bucket="review"}' in metrics_body(client)

    def test_force_pays_double(
        self, authed_client: tuple[TestClient, dict], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client, _ = authed_client
        monkeypatch.setattr(settings, "review_rate_limit_per_hour", 3)
        gid = _finished_local_game(client)
        first = client.post(f"/api/v1/games/{gid}/review", json={"force": True})
        assert first.status_code == 200  # weight 2 of 3
        # 2 + 2 > 3: the second forced re-run cannot fit the hour.
        assert client.post(f"/api/v1/games/{gid}/review", json={"force": True}).status_code == 429

    def test_cached_get_is_free(
        self, authed_client: tuple[TestClient, dict], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client, _ = authed_client
        monkeypatch.setattr(settings, "review_rate_limit_per_hour", 1)
        gid = _finished_local_game(client)
        assert client.post(f"/api/v1/games/{gid}/review", json={}).status_code == 200
        assert client.post(f"/api/v1/games/{gid}/review", json={}).status_code == 429
        # Re-reading the stored review never draws on the generation budget.
        assert client.get(f"/api/v1/games/{gid}/review").status_code == 200


class TestTrainingBudget:
    def test_attempt_budget(
        self, authed_client: tuple[TestClient, dict], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client, _ = authed_client
        monkeypatch.setattr(settings, "training_rate_limit_per_minute", 2)
        payload = {"key": "does-not-exist", "uci": "e2e4"}
        # The limiter runs before the handler: 404s still draw the budget —
        # spamming unknown keys is exactly the noise being capped.
        for _ in range(2):
            assert client.post("/api/v1/training/attempts", json=payload).status_code == 404
        blocked = client.post("/api/v1/training/attempts", json=payload)
        assert blocked.status_code == 429
        assert blocked.headers["Retry-After"].isdigit()
        assert 'rate_limit_rejections_total{bucket="training"}' in metrics_body(client)
