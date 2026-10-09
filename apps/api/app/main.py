"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api.v1.health import router as health_router

API_V1_PREFIX = "/api/v1"

app = FastAPI(title="Chess Engine API", version="0.1.0")

app.include_router(health_router, prefix=API_V1_PREFIX)


@app.get("/")
def root() -> dict[str, str]:
    """Return a minimal root response."""
    return {"service": "chess-engine-api", "docs": "/docs"}
