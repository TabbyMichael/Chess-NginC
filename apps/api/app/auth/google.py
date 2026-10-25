"""Google Sign-In: verify ID tokens server-side (never trust the client).

The frontend obtains an ID token (`credential`) from Google Identity
Services; we validate its signature/issuer/audience with `google-auth`
against the configured `GOOGLE_CLIENT_ID` and take the *verified* email
from the token payload — the client-provided email is never used.
"""

import logging

from google.auth import exceptions as google_exceptions
from google.auth.transport.requests import Request
from google.oauth2 import id_token as google_id_token

from app.core.database import settings

logger = logging.getLogger("chess-engine-api.auth.google")


def google_signin_enabled() -> bool:
    """True when a Google OAuth client ID is configured."""
    return bool(settings.google_client_id)


def verify_credential(credential: str) -> str | None:
    """Verify a Google ID token and return its (lowercased) email.

    Returns None when the token is invalid, expired, not addressed to us,
    or the email is not verified by Google.
    """
    if not settings.google_client_id:
        return None
    try:
        payload = google_id_token.verify_oauth2_token(
            credential, Request(), settings.google_client_id
        )
    except (google_exceptions.GoogleAuthError, ValueError):
        logger.info("Rejected an invalid Google ID token")
        return None
    if payload.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
        return None
    if not payload.get("email") or payload.get("email_verified") is not True:
        return None
    email: str = payload["email"].strip().lower()
    return email
