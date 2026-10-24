#!/usr/bin/env python3
"""Backfill the coach index from already-stored reviews (Phase 11, COACH-D6).

The reviews endpoint indexes a game the moment its analysis completes, so a
fresh deployment needs nothing here. This script exists for the one gap: reviews
that were stored *before* the coach index shipped have no searchable projection.

It re-projects completed reviews through the same idempotent writer the live
path uses (`upsert_review` replaces a game's whole row set), so it is safe to run
more than once and safe to interrupt.

Usage (from apps/api, with the app's environment / .env in scope):

    python scripts/index_reviews.py                 # every completed review
    python scripts/index_reviews.py --user-id 42    # one player
    python scripts/index_reviews.py --limit 500     # first 500 reviews
    python scripts/index_reviews.py --dry-run       # report, touch nothing
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make `app` importable when run as a plain script from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.ai.rag.index import upsert_review  # noqa: E402
from app.core.database import SessionLocal  # noqa: E402
from app.models.game_review import GameReview  # noqa: E402


def backfill(*, user_id: int | None, limit: int | None, dry_run: bool) -> int:
    """Index completed reviews; return the total number of ply rows written."""
    stmt = select(GameReview).where(GameReview.status == "completed").order_by(GameReview.id)
    if user_id is not None:
        stmt = stmt.where(GameReview.user_id == user_id)
    if limit is not None:
        stmt = stmt.limit(limit)

    total = 0
    reviews = 0
    with SessionLocal() as db:
        for review in db.scalars(stmt):
            reviews += 1
            if dry_run:
                plies = len((review.payload or {}).get("moves", []))
                print(f"would index game {review.game_id} (user {review.user_id}): {plies} plies")
                total += plies
                continue
            written = upsert_review(db, review)
            total += written
            print(f"indexed game {review.game_id} (user {review.user_id}): {written} rows")

    label = "would index" if dry_run else "indexed"
    print(f"{label} {reviews} review(s), {total} ply row(s) total")
    return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill the coach full-text index.")
    parser.add_argument("--user-id", type=int, default=None, help="restrict to one player")
    parser.add_argument("--limit", type=int, default=None, help="max reviews to process")
    parser.add_argument(
        "--dry-run", action="store_true", help="report what would be indexed, write nothing"
    )
    args = parser.parse_args(argv)
    backfill(user_id=args.user_id, limit=args.limit, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
