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
    # Stockfish (BEN-001/002/004/006): absolute binary path, empty = PATH lookup.
    # Never accept a path from clients; only env/config (BEN-020).
    stockfish_path: str = ""
    stockfish_depth_limit: int = 15
    stockfish_time_limit_ms: int = 1000
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
