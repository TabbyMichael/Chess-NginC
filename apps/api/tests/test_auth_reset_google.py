"""Password-reset and Google sign-in tests (forgot/reset flow, OAuth upsert)."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1 import auth as auth_routes
from app.auth import google as google_auth
from app.core.database import settings
from app.models.password_reset_token import PasswordResetToken


def _register(client: TestClient, email: str = "ada@example.com", password: str = "s3cret-pass"):
    resp = client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _capture_emails(monkeypatch) -> list[tuple[str, str]]:
    """Swap the dispatcher for a recorder; returns the (email, token) list."""
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        auth_routes, "send_password_reset_email", lambda email, token: sent.append((email, token))
    )
    return sent


def _forgot(client: TestClient, email: str):
    return client.post("/api/v1/auth/forgot-password", json={"email": email})


# ---------- forgot-password ------------------------------------------------


def test_forgot_password_unknown_email_is_indistinguishable(
    client: TestClient, monkeypatch
) -> None:
    sent = _capture_emails(monkeypatch)
    resp = _forgot(client, "nobody@example.com")
    assert resp.status_code == 200
    assert resp.json()["message"]  # same shape as the known-email path
    assert sent == []


def test_forgot_password_known_email_issues_token(
    client: TestClient, monkeypatch, db: Session
) -> None:
    _register(client, email="ada@example.com")
    sent = _capture_emails(monkeypatch)
    resp = _forgot(client, "ada@example.com")
    assert resp.status_code == 200
    assert sent == [("ada@example.com", sent[0][1])]
    raw_token = sent[0][1]
    assert len(raw_token) >= 32
    # Only the SHA-256 hash is persisted, never the raw token.
    row = db.execute(select(PasswordResetToken)).scalar_one()
    assert row.token_hash != raw_token
    assert len(row.token_hash) == 64
    assert row.used_at is None


# ---------- reset-password --------------------------------------------------


def test_reset_password_flow(client: TestClient, monkeypatch) -> None:
    _register(client, email="ada@example.com", password="s3cret-pass")
    sent = _capture_emails(monkeypatch)
    assert _forgot(client, "ada@example.com").status_code == 200
    raw_token = sent[0][1]

    resp = client.post(
        "/api/v1/auth/reset-password", json={"token": raw_token, "password": "brand-new-pass"}
    )
    assert resp.status_code == 200, resp.text

    # Old session is revoked (the register-login cookie is in the jar).
    assert client.get("/api/v1/auth/me").status_code == 401
    # Old password no longer works; new one does.
    bad = client.post(
        "/api/v1/auth/login", json={"email": "ada@example.com", "password": "s3cret-pass"}
    )
    assert bad.status_code == 401
    good = client.post(
        "/api/v1/auth/login", json={"email": "ada@example.com", "password": "brand-new-pass"}
    )
    assert good.status_code == 200


def test_reset_token_is_single_use(client: TestClient, monkeypatch) -> None:
    _register(client)
    sent = _capture_emails(monkeypatch)
    _forgot(client, "ada@example.com")
    raw_token = sent[0][1]
    first = client.post(
        "/api/v1/auth/reset-password", json={"token": raw_token, "password": "brand-new-pass"}
    )
    assert first.status_code == 200
    second = client.post(
        "/api/v1/auth/reset-password", json={"token": raw_token, "password": "another-pass"}
    )
    assert second.status_code == 400
    assert "not valid" in second.json()["detail"]


def test_reset_rejects_unknown_and_expired_tokens(
    client: TestClient, monkeypatch, db: Session
) -> None:
    _register(client)
    sent = _capture_emails(monkeypatch)
    unknown = client.post(
        "/api/v1/auth/reset-password",
        json={"token": "a" * 43, "password": "brand-new-pass"},
    )
    assert unknown.status_code == 400

    _forgot(client, "ada@example.com")
    raw_token = sent[-1][1]
    row = db.execute(select(PasswordResetToken)).scalar_one()
    row.expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=1)
    db.commit()
    expired = client.post(
        "/api/v1/auth/reset-password", json={"token": raw_token, "password": "brand-new-pass"}
    )
    assert expired.status_code == 400
    assert "expired" in expired.json()["detail"]


def test_reset_enforces_password_policy(client: TestClient, monkeypatch) -> None:
    _register(client)
    sent = _capture_emails(monkeypatch)
    _forgot(client, "ada@example.com")
    resp = client.post(
        "/api/v1/auth/reset-password", json={"token": sent[0][1], "password": "short"}
    )
    assert resp.status_code == 400
    assert "at least 8" in resp.json()["detail"]


# ---------- Google sign-in ---------------------------------------------------


def test_google_login_disabled_by_default(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "google_client_id", "")
    resp = client.post("/api/v1/auth/google", json={"credential": "x" * 32})
    assert resp.status_code == 404


def test_google_login_creates_and_reuses_account(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "google_client_id", "test-client.apps.googleusercontent.com")
    monkeypatch.setattr(google_auth, "verify_credential", lambda _c: "Grace@Example.com")

    first = client.post("/api/v1/auth/google", json={"credential": "valid-google-id-token"})
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["email"] == "grace@example.com"
    assert client.get("/api/v1/auth/me").status_code == 200

    second = client.post("/api/v1/auth/google", json={"credential": "valid-google-id-token-2"})
    assert second.status_code == 200
    assert second.json()["id"] == body["id"]  # no duplicate account


def test_google_login_rejects_invalid_credential(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "google_client_id", "test-client.apps.googleusercontent.com")
    monkeypatch.setattr(google_auth, "verify_credential", lambda _c: None)
    resp = client.post("/api/v1/auth/google", json={"credential": "forged-google-id-token"})
    assert resp.status_code == 401


def test_google_only_user_cannot_use_password_login(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "google_client_id", "test-client.apps.googleusercontent.com")
    monkeypatch.setattr(google_auth, "verify_credential", lambda _c: "grace@example.com")
    client.post("/api/v1/auth/google", json={"credential": "valid-google-id-token"})
    resp = client.post(
        "/api/v1/auth/login", json={"email": "grace@example.com", "password": "anything123"}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid email or password"
