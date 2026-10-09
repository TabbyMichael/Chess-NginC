# Chess Engine API

FastAPI backend for the chess engine project. Modular monolith under `/api/v1`.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Run

```bash
uvicorn app.main:app --reload
```

## Checks

```bash
ruff check . && ruff format --check .
mypy app
pytest
```
