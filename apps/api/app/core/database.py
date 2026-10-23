"""Database configuration and session management (REL-001/REL-002/REL-008)."""

import logging
import sys
from collections.abc import Generator

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Settings(BaseSettings):
    """Application settings with database configuration.

    Production rules (REL-001/REL-002): every secret comes from the environment;
    `secret_key` has no usable default — the app refuses to start with the
    development placeholder when APP_ENV=production.
    """

    app_env: str = "development"
    database_url: str = "postgresql+psycopg://tabbymichael@localhost:5432/chess"
    secret_key: str = "change-me-in-development-only"
    cookie_secure: bool = False
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    session_ttl_hours: int = 24 * 7  # 7 days
    auth_rate_limit_per_minute: int = 10
    # Password reset (SEC): short-lived single-use tokens. `reset_link_base`
    # is the public web origin used to build the emailed link. SMTP is
    # optional — with no `smtp_host` the link is logged (dev convenience).
    password_reset_ttl_minutes: int = 60
    reset_link_base: str = "http://localhost:5173"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    # Google Sign-In (WEB auth): OAuth 2.0 client ID verified server-side.
    # Empty = Google sign-in disabled; never commit a real value.
    google_client_id: str = ""
    # Stockfish (BEN-001/002/004/006): absolute binary path, empty = PATH lookup.
    # Never accept a path from clients; only env/config (BEN-020).
    stockfish_path: str = ""
    stockfish_depth_limit: int = 15
    stockfish_time_limit_ms: int = 1000
    # Hosted Stockfish API (stockfishapi.com): cloud engine fallback when no
    # local binary exists. Key comes ONLY from env (.env, never committed);
    # empty = cloud provider disabled. Never log or return the key.
    stockfish_api_key: str = ""
    stockfish_api_base_url: str = "https://stockfishapi.com/v1"
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()

if settings.app_env == "production" and settings.secret_key == "change-me-in-development-only":
    raise RuntimeError("REFUSE TO START: set a unique SECRET_KEY in production (REL-002).")

# Structured logging (REL-008): single-line timestamped records to stdout.
logging.basicConfig(
    stream=sys.stdout,
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("chess-engine-api")


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


# Create engine
engine = create_engine(settings.database_url, echo=False)

# Create session factory
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    """Dependency for getting a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
