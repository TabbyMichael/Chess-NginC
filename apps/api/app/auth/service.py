"""Auth service: registration, login, sessions, password reset, Google sign-in."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth.security import (
    generate_reset_token,
    generate_session_token,
    hash_password,
    hash_reset_token,
    reset_token_expiry,
    session_expiry,
    verify_password,
)
from app.auth.validators import normalize_email, validate_password
from app.models.password_reset_token import PasswordResetToken
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


def _issue_session(db: Session, user: User) -> str:
    """Create and persist a session row; returns the raw token."""
    token = generate_session_token()
    db.add(
        SessionModel(
            user_id=user.id,
            token=token,
            expires_at=session_expiry(),
        )
    )
    db.commit()
    return token


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
    if user is None or user.password_hash is None:
        # Same generic error whether or not the account exists (SEC-016); a
        # Google-only account must use the reset flow to set a password.
        raise ValueError(INVALID_CREDENTIALS)
    if not verify_password(password, user.password_hash):
        raise ValueError(INVALID_CREDENTIALS)
    return AuthResult(user=user, token=_issue_session(db, user))


def login_with_google(db: Session, email: str) -> AuthResult:
    """Sign in (or upsert) an account from a verified Google email.

    Callers must verify the ID token first (`app.auth.google`); the email
    passed here comes from the validated token, never from the client.
    """
    normalized = normalize_email(email)
    user = _get_user_by_email(db, normalized)
    if user is None:
        user = User(email=normalized, password_hash=None)
        db.add(user)
        db.commit()
        db.refresh(user)
    return AuthResult(user=user, token=_issue_session(db, user))


def begin_password_reset(db: Session, email: str) -> str | None:
    """Issue a reset token for the account; returns the raw token or None.

    None means "no account for this email" — the caller must respond
    identically either way so logins cannot be enumerated (SEC-016).
    """
    try:
        normalized = normalize_email(email)
    except ValueError:
        return None
    user = _get_user_by_email(db, normalized)
    if user is None:
        return None
    raw_token = generate_reset_token()
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_reset_token(raw_token),
            expires_at=reset_token_expiry(),
        )
    )
    db.commit()
    return raw_token


def complete_password_reset(db: Session, raw_token: str, password: str) -> None:
    """Consume a reset token and set the new password. Raises ValueError.

    Successful resets invalidate every existing session for the account.
    """
    validate_password(password)
    stmt = select(PasswordResetToken).where(
        PasswordResetToken.token_hash == hash_reset_token(raw_token)
    )
    token_row = db.execute(stmt).scalar_one_or_none()
    if token_row is None or token_row.used_at is not None:
        raise ValueError("This reset link is not valid")
    now = datetime.now(UTC).replace(tzinfo=None)
    if token_row.expires_at <= now:
        raise ValueError("This reset link has expired")
    user = db.get(User, token_row.user_id)
    if user is None:
        raise ValueError("This reset link is not valid")
    user.password_hash = hash_password(password)
    token_row.used_at = now
    db.execute(delete(SessionModel).where(SessionModel.user_id == user.id))
    db.commit()


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
