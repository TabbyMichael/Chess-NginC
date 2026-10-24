"""Training service: the ramp, per-skill progress, and the answer verdict.

The attempt log is the only state. Level, streak and progress are all derived
from it on read, so there is no mutable counter to drift. The verdict is decided
here in Python — the browser may preview legal targets, but "solved" is never
trusted from the client (architecture rule: the frontend does not determine
outcomes), and a puzzle payload handed to the client carries no answer.
"""

from __future__ import annotations

import chess
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.achievements import service as achievement_service
from app.achievements.catalog import Achievement
from app.games.service import award_ledger
from app.training import from_reviews
from app.training.drills import DRILLS, THEME_NAMES, THEME_ORDER, Drill
from app.training.models import TrainingAttempt

_LEVEL_MIN = 1
_LEVEL_MAX = 3

# Curated catalog indexed by key for O(1) resolution at answer time.
_BY_KEY: dict[str, Drill] = {d.key: d for d in DRILLS if d.source == "drill"}


class PuzzleNotFoundError(Exception):
    """Key resolves to no puzzle for this player (mapped to 404)."""


class IllegalAttemptError(Exception):
    """UCI is unparsable or not legal in the puzzle position (mapped to 422)."""


def _clamp(level: int) -> int:
    return max(_LEVEL_MIN, min(_LEVEL_MAX, level))


def next_level(recent: list[bool]) -> int:
    """The signed change the ramp applies after these attempts.

    Pure and history-window based: three correct in a row steps up, two wrong
    in a row steps down, anything else holds. The caller clamps the result to
    1..3, so the same rule can drive both the read (summary) and the write.
    """
    if len(recent) >= 3 and all(recent[-3:]):
        return 1
    if len(recent) >= 2 and not recent[-1] and not recent[-2]:
        return -1
    return 0


def _level_from(rows: list[TrainingAttempt]) -> int:
    """The level to offer next for one theme, from its chronological attempts."""
    if not rows:
        return _LEVEL_MIN
    current = rows[-1].level
    return _clamp(current + next_level([row.solved for row in rows]))


def _attempts(db: Session, user_id: int) -> list[TrainingAttempt]:
    return list(
        db.execute(
            select(TrainingAttempt)
            .where(TrainingAttempt.user_id == user_id)
            .order_by(TrainingAttempt.created_at, TrainingAttempt.id)
        ).scalars()
    )


def _solved_keys(attempts: list[TrainingAttempt]) -> set[str]:
    return {a.puzzle_key for a in attempts if a.solved}


def _theme_level(attempts: list[TrainingAttempt], theme: str) -> int:
    return _level_from([a for a in attempts if a.theme == theme])


def summary(db: Session, user_id: int) -> dict:
    """Per-skill progress plus headline totals for the Learn page (LEARN-003)."""
    attempts = _attempts(db, user_id)
    solved_keys = _solved_keys(attempts)
    themes: dict[str, dict] = {}
    for theme in THEME_ORDER:
        rows = [a for a in attempts if a.theme == theme]
        cleared = len({a.puzzle_key for a in rows if a.solved})
        total = sum(1 for d in DRILLS if d.theme == theme)
        themes[theme] = {
            "label": THEME_NAMES[theme],
            "solved": cleared,
            "attempts": len(rows),
            "level": _level_from(rows),
            "pct": round(cleared / total, 4) if total else 0.0,
        }
    streak = 0
    for row in reversed(attempts):
        if not row.solved:
            break
        streak += 1
    mine_available = sum(
        1 for p in from_reviews.mine_puzzles(db, user_id) if p.key not in solved_keys
    )
    return {
        "themes": themes,
        "puzzles_solved": len(solved_keys),
        "streak": streak,
        "mine_available": mine_available,
    }


def _pick_drill(theme: str, level: int, solved_keys: set[str]) -> Drill | None:
    """The best curated drill for a theme: current level first, then closest unsolved."""
    theme_drills = [d for d in DRILLS if d.theme == theme]
    unsolved = [d for d in theme_drills if d.key not in solved_keys]
    if not unsolved:
        return None
    at_level = [d for d in unsolved if d.level == level]
    if at_level:
        return at_level[0]
    return min(unsolved, key=lambda d: (abs(d.level - level), d.level))


def _next_mine(db: Session, user_id: int, solved_keys: set[str]) -> Drill | None:
    for puzzle in from_reviews.mine_puzzles(db, user_id):
        if puzzle.key not in solved_keys:
            return puzzle
    return None


def next_puzzle(
    db: Session, user_id: int, theme: str | None = None, source: str | None = None
) -> Drill | None:
    """The next puzzle to show, or None when everything is solved.

    Never returns an answer to the client — the router serializes this stripped
    of `solution`, `alternatives` and `line` (a test asserts they are absent).
    """
    solved_keys = _solved_keys(_attempts(db, user_id))
    if source == "game":
        return _next_mine(db, user_id, solved_keys)
    if theme:
        drill = _pick_drill(theme, _theme_level(_attempts(db, user_id), theme), solved_keys)
        return drill if drill is not None else _next_mine(db, user_id, solved_keys)
    for candidate in THEME_ORDER:
        drill = _pick_drill(candidate, _theme_level(_attempts(db, user_id), candidate), solved_keys)
        if drill is not None:
            return drill
    return _next_mine(db, user_id, solved_keys)


def _resolve(db: Session, user_id: int, key: str) -> Drill:
    """A puzzle by key: curated catalog, else a `mine:` re-read from the review."""
    if key.startswith("mine:"):
        puzzle = from_reviews.mine_by_key(db, user_id, key)
        if puzzle is None:
            raise PuzzleNotFoundError(f"Puzzle {key} not found")
        return puzzle
    drill = _BY_KEY.get(key)
    if drill is None:
        raise PuzzleNotFoundError(f"Puzzle {key} not found")
    return drill


def _validate(puzzle: Drill, uci: str) -> chess.Board:
    """Return the puzzle board, raising :class:`IllegalAttemptError` on a bad move."""
    board = chess.Board(puzzle.fen)
    try:
        move = chess.Move.from_uci(uci)
    except ValueError as exc:
        raise IllegalAttemptError(f"Unparsable move: {uci}") from exc
    if move not in board.legal_moves:
        raise IllegalAttemptError(f"Illegal move for this position: {uci}")
    return board


def _reveal(puzzle: Drill, solved: bool, points: int, unlocked: list[Achievement]) -> dict:
    """The answer payload shown only *after* an attempt (never in the puzzle)."""
    board = chess.Board(puzzle.fen)
    move = chess.Move.from_uci(puzzle.solution)
    san = board.san(move)
    continuation: list[str] = []
    walk = board.copy()
    walk.push(move)
    for uci in puzzle.line:
        reply = chess.Move.from_uci(uci)
        continuation.append(walk.san(reply))
        walk.push(reply)
    return {
        "solved": solved,
        "solution_san": san,
        "solution_from": chess.SQUARE_NAMES[move.from_square],
        "solution_to": chess.SQUARE_NAMES[move.to_square],
        "why": puzzle.why,
        "continuation": continuation,
        "points_awarded": points,
        "unlocked_achievements": unlocked,
    }


def _record(
    db: Session, user_id: int, puzzle: Drill, uci: str, solved: bool
) -> tuple[int, list[Achievement]]:
    """Append the attempt, award first-solve points, then evaluate achievements."""
    prior_theme_solved = db.execute(
        select(TrainingAttempt.id)
        .where(
            TrainingAttempt.user_id == user_id,
            TrainingAttempt.theme == puzzle.theme,
            TrainingAttempt.solved.is_(True),
        )
        .limit(1)
    ).first()
    db.add(
        TrainingAttempt(
            user_id=user_id,
            puzzle_key=puzzle.key,
            source=puzzle.source,
            theme=puzzle.theme,
            level=puzzle.level,
            solved=solved,
            uci=uci,
            game_id=puzzle.game_id,
            ply=puzzle.ply,
        )
    )
    db.commit()

    points = 0
    if solved:
        points += award_ledger(db, user_id, "drill", f"drill:{puzzle.key}")
        if prior_theme_solved is None and puzzle.theme != "missed":
            points += award_ledger(db, user_id, "theme_clear", f"theme:{puzzle.theme}")
    unlocked = achievement_service.flush(db, user_id)
    return points, unlocked


def record_attempt(db: Session, user_id: int, key: str, uci: str) -> dict:
    """Grade a submitted move against the puzzle's answer and reveal it."""
    puzzle = _resolve(db, user_id, key)
    _validate(puzzle, uci)  # illegal / unparsable -> 422 before anything is stored
    solved = uci == puzzle.solution or uci in puzzle.alternatives
    points, unlocked = _record(db, user_id, puzzle, uci, solved)
    return _reveal(puzzle, solved, points, unlocked)


def record_sequence_attempt(db: Session, user_id: int, key: str, played: list[str]) -> dict:
    """Grade a multi-move puzzle by exact-line replay, one attempt per resolved run.

    The client replays the forced line ply by ply: it submits its own moves in
    order (cumulative), and the server auto-plays the scripted opponent reply
    after each. An in-progress run logs nothing and returns ``complete=False``
    with the new position so the board advances; only a full correct line (one
    solved attempt, points) or a wrong ply (one failed attempt, the answer
    revealed) writes a row. The verdict stays server-side, as with single moves.
    """
    puzzle = _resolve(db, user_id, key)
    moves = puzzle.moves
    if not moves:
        raise IllegalAttemptError(f"Puzzle {key} is not a multi-move sequence")
    if not played:
        raise IllegalAttemptError("No moves submitted")
    player_plies = (len(moves) + 1) // 2
    if len(played) > player_plies:
        raise IllegalAttemptError("Too many moves for this puzzle")

    board = chess.Board(puzzle.fen)
    played_san: list[str] = []
    for j, uci in enumerate(played):
        try:
            mv = chess.Move.from_uci(uci)
        except ValueError as exc:
            raise IllegalAttemptError(f"Unparsable move: {uci}") from exc
        if mv not in board.legal_moves:
            raise IllegalAttemptError(f"Illegal move for this position: {uci}")
        if uci != moves[2 * j]:
            # Legal but not the line's move: one failed attempt, reveal the answer.
            points, unlocked = _record(db, user_id, puzzle, uci, solved=False)
            payload = _reveal(puzzle, solved=False, points=points, unlocked=unlocked)
            payload.update(
                {"complete": True, "position_fen": board.fen(), "played_san": played_san}
            )
            return payload
        played_san.append(board.san(mv))
        board.push(mv)
        if 2 * j + 1 < len(moves):  # scripted forced reply
            board.push(chess.Move.from_uci(moves[2 * j + 1]))

    if len(played) == player_plies:
        # Whole line found: the final player ply delivered mate/gain.
        points, unlocked = _record(db, user_id, puzzle, moves[-1], solved=True)
        payload = _reveal(puzzle, solved=True, points=points, unlocked=unlocked)
        payload.update({"complete": True, "position_fen": board.fen(), "played_san": played_san})
        return payload

    # Correct so far but unfinished: log nothing, advance the board, reveal no answer.
    return {
        "solved": False,
        "complete": False,
        "solution_san": "",
        "solution_from": "",
        "solution_to": "",
        "why": "",
        "continuation": [],
        "points_awarded": 0,
        "unlocked_achievements": [],
        "position_fen": board.fen(),
        "played_san": played_san,
    }


def reveal(db: Session, user_id: int, key: str) -> dict:
    """ "Show me": give the answer and log a no-credit attempt (no point, no solve)."""
    puzzle = _resolve(db, user_id, key)
    _record(db, user_id, puzzle, puzzle.solution, solved=False)
    return _reveal(puzzle, solved=False, points=0, unlocked=[])
