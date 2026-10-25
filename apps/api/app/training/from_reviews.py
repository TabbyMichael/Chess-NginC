"""Personal puzzles mined from the player's own analysed games (REV-005).

No content is invented: every puzzle is a position the player actually faced,
and the answer is the move the engine already recommended in that game's
review. We only surface a move when the review has one we can trust — a hero
mistake/blunder with a big centipawn loss and a legal `best_uci` — and we skip
anything the stored payload cannot reproduce on a real board, so an odd or
stale review can never mint a broken puzzle.
"""

from __future__ import annotations

from collections.abc import Iterator

import chess
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.game_review import GameReview
from app.training.drills import Drill

# Only genuinely costly moves become puzzles; an inaccuracy is too close to
# call "the move you missed", so the floor sits at the mistake threshold.
MINE_MIN_LOSS_CP = 120
_HERO_QUALITIES = ("mistake", "blunder")


def _to_puzzle(review: GameReview, move: dict) -> Drill | None:
    """One review ply → a mined puzzle, or None when it is unusable."""
    if move.get("color") != review.hero_color:
        return None
    if move.get("quality") not in _HERO_QUALITIES:
        return None
    if int(move.get("centipawn_loss") or 0) < MINE_MIN_LOSS_CP:
        return None
    best_uci = move.get("best_uci") or ""
    pre_fen = move.get("pre_fen") or ""
    if not best_uci or not pre_fen:
        return None
    try:
        board = chess.Board(pre_fen)
    except ValueError:
        return None
    if not board.is_valid():
        return None
    try:
        move_obj = chess.Move.from_uci(best_uci)
    except ValueError:
        return None
    if move_obj not in board.legal_moves:
        return None
    ply = int(move.get("ply") or 0)
    return Drill(
        key=f"mine:{review.game_id}:{ply}",
        theme="missed",
        name="A move you missed",
        level=3 if move.get("quality") == "blunder" else 2,
        fen=pre_fen,
        solution=best_uci,
        prompt="Find the move you missed",
        why=move.get("explanation") or "",
        source="game",
        game_id=review.game_id,
        ply=ply,
    )


def _hero_moves(review: GameReview) -> Iterator[Drill]:
    """Yield (already-usable) mined puzzles from one completed review, in ply order."""
    payload = review.payload or {}
    for move in payload.get("moves", []):
        puzzle = _to_puzzle(review, move)
        if puzzle is not None:
            yield puzzle


def mine_puzzles(db: Session, user_id: int, limit: int = 20) -> list[Drill]:
    """The caller's unsolved-looking missed moves, deduped and capped at `limit`.

    Deduped on (position, answer): the same blunder reproduced in two games is
    one drill, so the list never padding itself out of repeat mistakes.
    """
    rows = db.execute(
        select(GameReview)
        .where(GameReview.user_id == user_id, GameReview.status == "completed")
        .order_by(GameReview.game_id.desc())
    ).scalars()
    seen: set[tuple[str, str]] = set()
    out: list[Drill] = []
    for review in rows:
        for puzzle in _hero_moves(review):
            signature = (puzzle.fen, puzzle.solution)
            if signature in seen:
                continue
            seen.add(signature)
            out.append(puzzle)
            if len(out) >= limit:
                return out
    return out


def mine_by_key(db: Session, user_id: int, key: str) -> Drill | None:
    """Resolve one `mine:{game_id}:{ply}` key by re-reading the stored review.

    Returns None when the key is not the caller's, its game is no longer in
    their completed reviews, or the move is no longer mineable — which is what
    lets a `mine:` solve verify against the answer without trusting the client.
    """
    prefix = "mine:"
    if not key.startswith(prefix):
        return None
    try:
        _, game_part, ply_part = key.split(":", 2)
        game_id, ply = int(game_part), int(ply_part)
    except ValueError:
        return None
    review = db.execute(
        select(GameReview).where(
            GameReview.user_id == user_id,
            GameReview.game_id == game_id,
            GameReview.status == "completed",
        )
    ).scalar_one_or_none()
    if review is None:
        return None
    for puzzle in _hero_moves(review):
        if puzzle.ply == ply:
            return puzzle
    return None
