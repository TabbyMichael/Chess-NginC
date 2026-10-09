"""Shared API dependencies: current-user resolution and auth rate limiting."""

import time
from collections import defaultdict
from collections.abc import Generator
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth import service as auth_service
from app.core.database import get_db, settings
from app.models.user import User

SESSION_COOKIE = "session_token"

# In-memory per-client rate limiter for auth endpoints (single-process dev
# default; replace with Redis for multi-worker production).
_rate_buckets: defaultdict[str, list[float]] = defaultdict(list)


def rate_limit_auth(request: Request) -> None:
    """Allow N auth attempts per minute per client IP (SEC-012)."""
    now = time.monotonic()
    window_start = now - 60.0
    key = request.client.host if request.client else "unknown"
    hits = [t for t in _rate_buckets[key] if t > window_start]
    _rate_buckets[key] = hits
    if len(hits) >= settings.auth_rate_limit_per_minute:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please try again later.",
        )
    hits.append(now)


def reset_rate_limits() -> None:
    """Clear rate-limit state (used by tests)."""
    _rate_buckets.clear()


def enforce_same_origin(request: Request) -> None:
    """Reject cross-origin state-changing requests (SEC-008, CSRF defense).

    Browsers attach `Origin` (or `Referer`) to cross-site POSTs; same-origin
    fetch/XHR from our frontend carries our own origin. Requests without
    either header (curl, tests, non-browser clients) are allowed through —
    they cannot be forged cross-site form/fetch submissions.
    """
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    if not origin and not referer:
        return
    allowed = {o.strip() for o in settings.cors_origins.split(",") if o.strip()}
    candidate = origin or referer
    assert candidate is not None
    if candidate.rstrip("/") not in {o.rstrip("/") for o in allowed}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-origin request forbidden",
        )


def get_db_session() -> Generator[Session, None, None]:
    """Yield a DB session (thin alias so routes depend on the api layer)."""
    yield from get_db()


# Module-level singletons for Annotated dependency metadata (E402 exempted).
# NOTE: FastAPI forbids defaults inside Annotated Cookie/Depends; the `= None`
# defaults live on the parameter declarations below.
_DbSession = Depends(get_db_session)  # noqa: E402
_SessionCookie = Cookie(alias=SESSION_COOKIE)  # noqa: E402


def get_current_user(
    session_token: Annotated[str | None, _SessionCookie] = None,
    db: Annotated[Session, _DbSession] = None,  # type: ignore[assignment]
) -> User:
    """Resolve the session cookie to a user or raise 401 (SEC-020)."""
    assert db is not None  # guaranteed by FastAPI dependency injection
    user = auth_service.authenticate(db, session_token or "")
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user
