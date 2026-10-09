"""Authentication endpoints: register, login, logout, me (SEC-001..008)."""

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.v1.deps import (
    SESSION_COOKIE,
    enforce_same_origin,
    get_current_user,
    get_db_session,
    rate_limit_auth,
)
from app.auth import service as auth_service
from app.auth.security import MAX_PASSWORD_BYTES
from app.core.database import settings
from app.models.user import User

from .schemas import ErrorResponse, LoginRequest, RegisterRequest, UserResponse

router = APIRouter(tags=["auth"])

# Module-level dependency singletons (kept after imports; ruff E402 exempted
# since FastAPI requires these as Annotated metadata, not call-site Defaults).
_DbSession = Depends(get_db_session)  # noqa: E402
_SessionCookie = Cookie(alias=SESSION_COOKIE)  # noqa: E402
_CurrentUser = Depends(get_current_user)  # noqa: E402


def _set_auth_cookies(response: Response, token: str) -> None:
    """Set the session cookie (SEC-007: HttpOnly + SameSite=Lax).

    CSRF defense (SEC-008) is SameSite=Lax plus the Origin/Referer check in
    `enforce_same_origin`, not a separate synchronizer token.
    """
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
        max_age=settings.session_ttl_hours * 3600,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def _to_user_response(user: User) -> UserResponse:
    return UserResponse(id=user.id, email=user.email)


@router.post(
    "/auth/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
    dependencies=[Depends(rate_limit_auth), Depends(enforce_same_origin)],
)
def register(
    payload: RegisterRequest,
    response: Response,
    db: Annotated[Session, _DbSession],
) -> UserResponse:
    """Register a new account and start a session (SEC-001/002/003)."""
    if len(payload.password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password is too long")
    try:
        user = auth_service.register(db, payload.email, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
    result = auth_service.login(db, payload.email, payload.password)
    _set_auth_cookies(response, result.token)
    return _to_user_response(user)


@router.post(
    "/auth/login",
    response_model=UserResponse,
    responses={401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
    dependencies=[Depends(rate_limit_auth), Depends(enforce_same_origin)],
)
def login(
    payload: LoginRequest,
    response: Response,
    db: Annotated[Session, _DbSession],
) -> UserResponse:
    """Authenticate with email + password and start a session (SEC-004)."""
    try:
        result = auth_service.login(db, payload.email, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from None
    _set_auth_cookies(response, result.token)
    return _to_user_response(result.user)


@router.post(
    "/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(enforce_same_origin)],
)
def logout(
    response: Response,
    db: Annotated[Session, _DbSession],
    session_token: Annotated[str | None, _SessionCookie] = None,
) -> None:
    """Revoke the current session; always clears cookies (SEC-005, idempotent)."""
    auth_service.logout(db, session_token or "")
    _clear_auth_cookies(response)


@router.get("/auth/me", response_model=UserResponse, responses={401: {"model": ErrorResponse}})
def me(current_user: Annotated[User, _CurrentUser]) -> UserResponse:
    """Return the currently authenticated user (SEC-006)."""
    return _to_user_response(current_user)
