# Chess Engine API — production image (REL-001/REL-010).
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv/api

# Install runtime deps first for layer caching.
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --no-cache-dir .

# Migrations ship with the image; applied as a controlled deploy step (REL-006).
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

EXPOSE 8000

# Default: migrate then serve. Compose overrides keep this contract.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
