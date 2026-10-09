"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.auth import router as auth_router
from app.api.v1.health import router as health_router
from app.core.database import settings

API_V1_PREFIX = "/api/v1"

app = FastAPI(title="Chess Engine API", version="0.1.0")

# Explicit CORS allowlist from settings (SEC-014); no wildcard with cookies.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)

app.include_router(health_router, prefix=API_V1_PREFIX)
app.include_router(auth_router, prefix=API_V1_PREFIX)


@app.get("/")
def root() -> dict[str, str]:
    """Return a minimal root response."""
    return {"service": "chess-engine-api", "docs": "/docs"}
