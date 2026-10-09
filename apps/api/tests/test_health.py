"""Tests for the health endpoint."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_returns_service_name() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "chess-engine-api"
