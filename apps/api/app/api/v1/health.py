"""Health-check endpoints: liveness + readiness (REL-007)."""

from fastapi import APIRouter
from sqlalchemy import text

from app.core.database import engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Report service liveness."""
    return {"status": "ok"}


@router.get("/ready")
def ready() -> dict[str, str]:
    """Report readiness: app + database reachable (REL-007)."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        return {"status": "not-ready"}
    return {"status": "ready"}
