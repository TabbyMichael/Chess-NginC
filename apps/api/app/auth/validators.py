"""Input validation for identity operations (SEC-002)."""

import re

# Practical approximation of RFC 5322 local@domain (backend gate; the DB
# unique constraint on users.email is the final authority on duplicates).
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

MIN_PASSWORD_LENGTH = 8
MAX_EMAIL_LENGTH = 255


def normalize_email(email: str) -> str:
    """Trim and lowercase an email address. Raises ValueError if invalid."""
    cleaned = email.strip().lower()
    if not cleaned:
        raise ValueError("Email must not be empty")
    if len(cleaned) > MAX_EMAIL_LENGTH:
        raise ValueError("Email is too long")
    if not EMAIL_RE.match(cleaned):
        raise ValueError("Invalid email address")
    return cleaned


def validate_password(password: str) -> None:
    """Enforce minimum password policy. Raises ValueError on violation."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError("Password must be at least 8 characters")
