"""Drill soundness verification (pure python-chess, no engine).

Hand-authored teaching content needs proof, not trust: a drill that does not
actually teach what its `theme` claims would quietly mis-grade a player. Every
drill is re-checked here, and `verify_all()` is run by both the test suite and
``scripts/check_drills.py`` so an unsound addition fails the build rather than a
person's memory.

Checks are by pattern, never by search — the whole point is a fast, deterministic
guarantee (see architecture D12 / TD-019 for the honest limits of that).
"""

from __future__ import annotations

import chess

from app.training.drills import Drill

# Piece values in centipawns for the material-gain themes.
_PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 320,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}
# One pawn is the floor: a "win the material" drill must net at least this over
# the whole forced line, else it is trading, not winning.
MIN_GAIN_CP = 100

# Themes proved by a durable material gain along the line.
_MATERIAL_THEMES = frozenset({"hanging", "fork", "pin", "endgame", "skewer", "discovered"})
# Themes proved by checkmate delivered by the solution itself.
_MATE_THEMES = frozenset({"mate"})
# Multi-move puzzles proved by replaying a whole forced line (opponent replies
# are forced, so the line is deterministic and the win is real without a search).
_SEQUENCE_THEMES = frozenset({"sequence"})
# Every theme the catalog is allowed to use.
VALID_THEMES = _MATE_THEMES | _MATERIAL_THEMES | frozenset({"backrank"}) | _SEQUENCE_THEMES


def material_balance(board: chess.Board) -> int:
    """White-minus-Black material in centipawns (positive = White ahead)."""
    total = 0
    for piece in board.piece_map().values():
        value = _PIECE_VALUES[piece.piece_type]
        total += value if piece.color == chess.WHITE else -value
    return total


def _balance_for(board: chess.Board, color: chess.Color) -> int:
    balance = material_balance(board)
    return balance if color == chess.WHITE else -balance


def mate_in_one_exists(board: chess.Board) -> bool:
    """Return whether the side to move has any move that checkmates."""
    for move in board.legal_moves:
        board.push(move)
        mated = board.is_checkmate()
        board.pop()
        if mated:
            return True
    return False


def _opponent_to_move(board: chess.Board) -> chess.Board:
    """The same pieces with the other side to move, to test a live threat.

    Castling rights and the en-passant square are cleared (the flip can make
    them nonsensical) — that is harmless for a mate-in-one probe. The caller
    only ever asks about a position where the mover is not in check, so the
    flip yields a valid board.
    """
    fields = board.fen().split(" ")
    fields[1] = "w" if fields[1] == "b" else "b"
    fields[2] = "-"
    fields[3] = "-"
    return chess.Board(" ".join(fields))


def _push_all(board: chess.Board, ucis: tuple[str, ...]) -> bool:
    """Push each uci legally; False on the first illegal/unparsable one."""
    for uci in ucis:
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            return False
        if move not in board.legal_moves:
            return False
        board.push(move)
    return True


def _parse(uci: str) -> chess.Move | None:
    try:
        return chess.Move.from_uci(uci)
    except ValueError:
        return None


def _verify_mate(board: chess.Board, solution: chess.Move) -> str | None:
    board.push(solution)
    if not board.is_checkmate():
        return "solution does not deliver checkmate"
    return None


def _verify_material(drill: Drill, board: chess.Board, solution: chess.Move) -> str | None:
    mover = board.turn
    before = _balance_for(board, mover)
    after = board.copy()
    after.push(solution)
    if not _push_all(after, drill.line):
        return "continuation line is not legal move by move"
    if not after.is_valid():
        return "position after the line is not valid"
    gained = _balance_for(after, mover) - before
    if gained < MIN_GAIN_CP:
        return f"line nets only {gained}cp for the mover (needs >= {MIN_GAIN_CP})"
    return None


def _verify_backrank(board: chess.Board, solution: chess.Move) -> str | None:
    # Before escaping, the opponent must have a live back-rank mate (threat on).
    if not mate_in_one_exists(_opponent_to_move(board)):
        return "opponent has no mate-in-one threat before the escape"
    after = board.copy()
    after.push(solution)
    if not after.is_valid():
        return "position after the escape is not valid"
    # The escape genuinely defuses it: the same opponent turn now has no mate.
    if mate_in_one_exists(_opponent_to_move(after)):
        return "escape fails to remove the mate-in-one threat"
    return None


def _verify_sequence(drill: Drill, board: chess.Board) -> str | None:
    """Prove a multi-move line: every ply legal, opponent replies forced, ends
    in checkmate or a decisive material gain. No search — the forced replies make
    the line deterministic, so replaying it *is* the proof."""
    moves = drill.moves
    if len(moves) < 3 or len(moves) % 2 == 0:
        return "sequence needs an odd-length line of at least 3 plies"
    mover = board.turn
    before = _balance_for(board, mover)
    walk = board.copy()
    last = len(moves) - 1
    for i, uci in enumerate(moves):
        mv = _parse(uci)
        if mv is None or mv not in walk.legal_moves:
            return f"sequence ply {i} ({uci!r}) is not legal"
        if i % 2 == 1 and len(list(walk.legal_moves)) != 1:
            return f"opponent ply {i} is not a forced reply"
        walk.push(mv)
        if i < last and (walk.is_checkmate() or walk.is_stalemate()):
            return f"line resolves prematurely at ply {i}"
    if walk.is_checkmate():
        return None
    gained = _balance_for(walk, mover) - before
    if gained < MIN_GAIN_CP:
        return f"sequence ends in neither mate nor a >= {MIN_GAIN_CP}cp gain (only {gained}cp)"
    return None


def verify(drill: Drill) -> str | None:
    """Return a problem description, or None when the drill is sound."""
    try:
        board = chess.Board(drill.fen)
    except ValueError:
        return "FEN does not load"
    if not board.is_valid():
        return "FEN is not a valid position"
    if drill.theme not in VALID_THEMES:
        return f"unknown theme {drill.theme!r}"
    if board.is_checkmate() or board.is_stalemate():
        return "side to move is already mated or stalemated"

    solution = _parse(drill.solution)
    if solution is None:
        return "solution is not valid UCI"
    if solution not in board.legal_moves:
        return "solution is not a legal move"

    # Every accepted alternative must be a legal move in the start position too.
    for uci in drill.alternatives:
        alt = _parse(uci)
        if alt is None or alt not in board.legal_moves:
            return f"alternative {uci!r} is not a legal move"

    if drill.theme in _SEQUENCE_THEMES:
        return _verify_sequence(drill, board)
    if drill.theme in _MATE_THEMES:
        verdict = _verify_mate(board, solution)
        if verdict is None:
            for uci in drill.alternatives:
                alt = _parse(uci)
                probe = board.copy()
                probe.push(alt)  # type: ignore[arg-type]
                if not probe.is_checkmate():
                    return f"alternative {uci!r} does not deliver checkmate"
        return verdict
    if drill.theme in _MATERIAL_THEMES:
        return _verify_material(drill, board, solution)
    return _verify_backrank(board, solution)


def verify_all(drills: tuple[Drill, ...]) -> list[str]:
    """Every problem across the catalog, keyed by drill for a readable failure."""
    problems: list[str] = []
    seen: set[str] = set()
    for drill in drills:
        if drill.key in seen:
            problems.append(f"{drill.key}: duplicate key")
        seen.add(drill.key)
        problem = verify(drill)
        if problem is not None:
            problems.append(f"{drill.key}: {problem}")
    return problems
