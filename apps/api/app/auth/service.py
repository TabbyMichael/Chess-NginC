"""Auth service: registration, login, session validation, logout (SEC-001..006)."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import (
    generate_session_token,
    hash_password,
    session_expiry,
    verify_password,
)
from app.auth.validators import normalize_email, validate_password
from app.models.session import Session as SessionModel
from app.models.user import User

# Generic message returned for both unknown-email and wrong-password logins
# so callers cannot enumerate registered accounts (SEC-016).
INVALID_CREDENTIALS = "Invalid email or password"


@dataclass(frozen=True)
class AuthResult:
    """Authenticated user plus the session token issued for them."""

    user: User
    token: str


def _get_user_by_email(db: Session, email: str) -> User | None:
    stmt = select(User).where(User.email == email)
    return db.execute(stmt).scalar_one_or_none()


def register(db: Session, email: str, password: str) -> User:
    """Create a new user. Raises ValueError on invalid input or duplicate email."""
    normalized = normalize_email(email)
    validate_password(password)
    if _get_user_by_email(db, normalized) is not None:
        raise ValueError("Email is already registered")
    user = User(email=normalized, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login(db: Session, email: str, password: str) -> AuthResult:
    """Authenticate and issue a session token. Raises ValueError on failure."""
    try:
        normalized = normalize_email(email)
    except ValueError:
        raise ValueError(INVALID_CREDENTIALS) from None
    user = _get_user_by_email(db, normalized)
    if user is None or not verify_password(password, user.password_hash):
        raise ValueError(INVALID_CREDENTIALS)
    token = generate_session_token()
    db.add(
        SessionModel(
            user_id=user.id,
            token=token,
            expires_at=session_expiry(),
        )
    )
    db.commit()
    return AuthResult(user=user, token=token)


def authenticate(db: Session, token: str) -> User | None:
    """Resolve a session token to its user, or None if unknown/expired (SEC-021)."""
    if not token:
        return None
    stmt = select(SessionModel).where(SessionModel.token == token)
    session = db.execute(stmt).scalar_one_or_none()
    if session is None:
        return None
    now = datetime.now(UTC).replace(tzinfo=None)
    if session.expires_at <= now:
        db.delete(session)
        db.commit()
        return None
    return db.get(User, session.user_id)


def logout(db: Session, token: str) -> bool:
    """Revoke a session token. Returns True if a session was revoked (SEC-005)."""
    if not token:
        return False
    stmt = select(SessionModel).where(SessionModel.token == token)
    session = db.execute(stmt).scalar_one_or_none()
    if session is None:
        return False
    db.delete(session)
    db.commit()
    return True
