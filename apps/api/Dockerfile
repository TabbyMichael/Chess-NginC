# Chess Engine API — production image (REL-001/REL-010).
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv/api

# Real Stockfish opponent (PLAY-001) + review analysis need the binary in the
# image; provenance is recorded in app/engine/stockfish.py (GPL-3.0, BEN-003).
RUN apt-get update \
    && apt-get install -y --no-install-recommends stockfish \
    && rm -rf /var/lib/apt/lists/*

# Install runtime deps first for layer caching.
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --no-cache-dir .

# Migrations ship with the image; applied as a controlled deploy step (REL-006).
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

EXPOSE 8000

# Default: migrate then serve. Compose overrides keep this contract.
# --ws-max-size 4096 bounds WS frames at the server BEFORE buffering, closing
# oversized floods (TD-012 note: the app-level 4KB cap applies post-read).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --ws-max-size 4096"]
