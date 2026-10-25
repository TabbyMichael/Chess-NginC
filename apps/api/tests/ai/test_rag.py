"""RAG layer tests: coach indexing + full-text / pattern recall (Phase 11).

These run against the fixture Postgres (the `db` session), because the whole
point of the retrieval layer is the generated `tsvector` column and the GIN index
— which no SQLite-free unit harness could exercise. The engine-derived facts are
stubbed straight into a review payload, so no Stockfish or network is touched.
"""

import uuid

import chess
from sqlalchemy.orm import Session

from app.ai.rag import recall
from app.ai.rag.index import index_review_safe, indexed_count, upsert_review
from app.games.domain import STARTING_FEN
from app.models.game import Game
from app.models.game_review import GameReview
from app.models.user import User

AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"


def _ply(ply: int, uci: str, san: str, pre_fen: str, color: str, quality: str, loss: int) -> dict:
    return {
        "ply": ply,
        "move_number": ply,
        "uci": uci,
        "san": san,
        "pre_fen": pre_fen,
        "color": color,
        "quality": quality,
        "centipawn_loss": loss,
        "best_uci": uci,
        "eval_cp": 0,
        "eval_mate": None,
        "explanation": f"{san} is a {quality}.",
    }


def _review(
    db: Session,
    moves: list[dict],
    *,
    status: str = "completed",
    hero: str = "b",
) -> GameReview:
    """A review row for a fresh (user, game), with the given payload plies."""
    user = User(email=f"coach-{uuid.uuid4().hex}@example.com")
    db.add(user)
    db.commit()
    game = Game(
        user_id=user.id,
        mode="computer",
        status="checkmate",
        fen=chess.Board().fen(),
        version=1,
    )
    db.add(game)
    db.commit()
    review = GameReview(
        game_id=game.id,
        user_id=user.id,
        status=status,
        provider="stockfish",
        depth=15,
        hero_color=hero,
        payload={"moves": moves},
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


_SICILIAN_BLUNDER = {
    "ply": 2,
    "move_number": 1,
    "uci": "c7c5",
    "san": "c5",
    "pre_fen": AFTER_E4,
    "color": "b",
    "quality": "blunder",
    "centipawn_loss": 250,
    "best_uci": "e7e5",
    "eval_cp": -20,
    "eval_mate": None,
    "explanation": "c5 hangs a pawn in the Sicilian Defense.",
}


def test_upsert_indexes_completed_review(db: Session) -> None:
    review = _review(db, [_SICILIAN_BLUNDER])
    assert upsert_review(db, review) == 1
    assert indexed_count(db, review.user_id) == 1
    # Opening family is derived from the offline book, not stored in the payload.
    rows = recall.patterns(db, review.user_id, "b")
    assert rows and rows[0].opening_family == "Sicilian Defense"
    assert rows[0].blunders == 1
    assert rows[0].avg_loss_cp == 250


def test_failed_review_is_not_indexed(db: Session) -> None:
    review = _review(db, [_SICILIAN_BLUNDER], status="failed")
    assert upsert_review(db, review) == 0
    assert indexed_count(db, review.user_id) == 0


def test_reindex_replaces_stale_plies(db: Session) -> None:
    review = _review(
        db,
        [
            _ply(1, "e2e4", "e4", STARTING_FEN, "w", "best", 0),
            _ply(2, "c7c5", "c5", AFTER_E4, "b", "blunder", 200),
        ],
    )
    upsert_review(db, review)
    assert indexed_count(db, review.user_id) == 2
    # A forced re-analysis that shrinks the game must leave no orphan ply behind.
    review.payload = {"moves": [_SICILIAN_BLUNDER]}
    db.add(review)
    db.commit()
    upsert_review(db, review)
    assert indexed_count(db, review.user_id) == 1


def test_patterns_are_scoped_to_the_player(db: Session) -> None:
    mine = _review(db, [_SICILIAN_BLUNDER])
    upsert_review(db, mine)
    other = _review(db, [_SICILIAN_BLUNDER])
    assert recall.patterns(db, other.user_id, "b") == []
    assert recall.patterns(db, mine.user_id, "b") != []


def test_free_text_recall_finds_the_error(db: Session) -> None:
    review = _review(db, [_SICILIAN_BLUNDER])
    upsert_review(db, review)
    hits = recall.free_text_hits(db, review.user_id, "hangs pawn")
    assert hits and hits[0].san == "c5"
    assert hits[0].quality == "blunder"


def test_recall_is_empty_not_raising_when_nothing_matches(db: Session) -> None:
    review = _review(db, [_SICILIAN_BLUNDER])
    upsert_review(db, review)
    assert recall.free_text_hits(db, review.user_id, "zugzwang unicorns") == []
    assert recall.free_text_hits(db, review.user_id, "   ") == []


def test_opening_note_counts_the_players_own_plies(db: Session) -> None:
    review = _review(db, [_SICILIAN_BLUNDER])
    upsert_review(db, review)
    note = recall.opening_note(db, review.user_id, "Sicilian Defense")
    assert "Sicilian Defense" in note
    assert "1" in note  # one recorded error ply in that family
    assert recall.opening_note(db, review.user_id, "") == ""
    assert recall.opening_note(db, review.user_id, "Not A Real Opening") == ""


def test_patterns_text_summarises_the_worst_family(db: Session) -> None:
    review = _review(db, [_SICILIAN_BLUNDER])
    upsert_review(db, review)
    rows = recall.patterns(db, review.user_id, "b")
    text = recall.patterns_text(rows)
    assert "Sicilian Defense" in text
    assert "blunder" in text
    assert recall.patterns_text([]) == ""


def test_index_review_safe_swallows_failures(db: Session) -> None:
    review = _review(db, [_SICILIAN_BLUNDER])
    # A payload that cannot be projected must not raise into the review path.
    review.payload = "not-a-dict"  # type: ignore[assignment]
    assert index_review_safe(db, review) == 0
