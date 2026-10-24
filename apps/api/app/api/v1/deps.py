"""Shared API dependencies: current-user resolution and auth rate limiting."""

import time
from collections import defaultdict
from collections.abc import Generator, Mapping
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
# Separate bucket for online move submissions (online-plan §6.1), keyed by
# user id — mirrors the auth limiter; same single-process caveat.
_move_buckets: defaultdict[int, list[float]] = defaultdict(list)
# Coach assistant asks (Phase 11), keyed by user id — an LLM/what-if question is
# more expensive than a page read, so it gets its own budget. Same caveat.
_assistant_buckets: defaultdict[int, list[float]] = defaultdict(list)


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
    _move_buckets.clear()
    _assistant_buckets.clear()


def same_origin_ok(headers: Mapping[str, str]) -> bool:
    """Return whether an Origin/Referer header value passes the allowlist.

    Shared by the HTTP dependency and the WebSocket handshake (CSWSRF).
    Requests without either header (curl, tests) pass, like `enforce_same_origin`.
    """
    origin = headers.get("origin")
    referer = headers.get("referer")
    if not origin and not referer:
        return True
    allowed = {o.strip().rstrip("/") for o in settings.cors_origins.split(",") if o.strip()}
    candidate = (origin or referer or "").rstrip("/")
    return candidate in allowed


def enforce_same_origin(request: Request) -> None:
    """Reject cross-origin state-changing requests (SEC-008, CSRF defense).

    Browsers attach `Origin` (or `Referer`) to cross-site POSTs; same-origin
    fetch/XHR from our frontend carries our own origin. Requests without
    either header (curl, tests, non-browser clients) are allowed through —
    they cannot be forged cross-site form/fetch submissions.
    """
    if not same_origin_ok(request.headers):
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


def check_move_rate(user_id: int) -> None:
    """Allow N move submissions per minute per user (online-plan §6.1).

    Shared by the REST dependency and the WebSocket dispatch so choosing a
    transport cannot bypass the limit.
    """
    now = time.monotonic()
    window_start = now - 60.0
    hits = [t for t in _move_buckets[user_id] if t > window_start]
    _move_buckets[user_id] = hits
    if len(hits) >= settings.move_rate_limit_per_minute:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many moves. Please slow down.",
        )
    hits.append(now)


def rate_limit_moves(current_user: Annotated[User, Depends(get_current_user)]) -> None:
    """REST dependency wrapper around :func:`check_move_rate`."""
    check_move_rate(current_user.id)


def check_assistant_rate(user_id: int) -> None:
    """Allow N coach-assistant asks per minute per user (Phase 11).

    A question can trigger a live engine pass and (when configured) an LLM call,
    so it is capped more tightly than ordinary reads. Mirrors :func:`check_move_rate`.
    """
    now = time.monotonic()
    window_start = now - 60.0
    hits = [t for t in _assistant_buckets[user_id] if t > window_start]
    _assistant_buckets[user_id] = hits
    if len(hits) >= settings.assistant_rate_limit_per_minute:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many questions. Please slow down.",
        )
    hits.append(now)


def rate_limit_assistant(current_user: Annotated[User, Depends(get_current_user)]) -> None:
    """REST dependency wrapper around :func:`check_assistant_rate`."""
    check_assistant_rate(current_user.id)
