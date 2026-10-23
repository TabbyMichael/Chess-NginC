"""Password-reset email dispatch.

With `SMTP_HOST` configured the message goes out over SMTP (STARTTLS on the
usual submission ports). Without it (local development) the reset link is
logged to stdout instead — never fail the request because email is down;
the caller already returned the anti-enumeration response by then.
"""

import logging
import smtplib
from email.message import EmailMessage

from app.core.database import settings

logger = logging.getLogger("chess-engine-api.auth.email")


def build_reset_link(raw_token: str) -> str:
    """Full web URL the user clicks to reset their password."""
    base = settings.reset_link_base.rstrip("/")
    return f"{base}/reset-password?token={raw_token}"


def send_password_reset_email(email: str, raw_token: str) -> None:
    """Send (or, in dev, log) a password-reset link. Errors are logged only."""
    link = build_reset_link(raw_token)
    if not settings.smtp_host:
        # Dev fallback: the token is delivered via the server log so the flow
        # is testable without an SMTP provider. Never do this in production —
        # set SMTP_HOST there.
        logger.info("Password reset link for %s: %s", email, link)
        return

    message = EmailMessage()
    message["Subject"] = "Reset your Chess NginC password"
    message["From"] = settings.smtp_from or settings.smtp_username
    message["To"] = email
    message.set_content(
        "You asked to reset your Chess NginC password.\n\n"
        f"Open this link to choose a new password:\n\n{link}\n\n"
        f"This link expires in {settings.password_reset_ttl_minutes} minutes "
        "and can be used only once.\n"
        "If you did not request this, no action is needed.\n"
    )
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            if settings.smtp_port == 587:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
    except Exception:  # noqa: BLE001 — delivery must never break the request
        logger.exception("Failed to send password reset email to %s", email)
