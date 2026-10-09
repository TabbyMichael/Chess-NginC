"""Password hashing (bcrypt) and session-token generation."""

import secrets
from datetime import UTC, datetime, timedelta

import bcrypt

from app.core.database import settings

# bcrypt truncates passwords at 72 bytes; reject longer inputs explicitly
# rather than silently truncating.
MAX_PASSWORD_BYTES = 72

# Session tokens: 256-bit entropy, URL-safe for cookie transport.
TOKEN_BYTES = 32


def hash_password(password: str) -> str:
    """Hash a password with bcrypt. Raises ValueError on empty/too-long input."""
    if not password:
        raise ValueError("Password must not be empty")
    raw = password.encode("utf-8")
    if len(raw) > MAX_PASSWORD_BYTES:
        raise ValueError("Password must be at most 72 bytes")
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a bcrypt hash. Never raises on mismatch."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def generate_session_token() -> str:
    """Generate a cryptographically random session token."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def session_expiry(now: datetime | None = None) -> datetime:
    """Compute session expiry from the configured TTL."""
    base = now or datetime.now(UTC).replace(tzinfo=None)
    return base + timedelta(hours=settings.session_ttl_hours)
