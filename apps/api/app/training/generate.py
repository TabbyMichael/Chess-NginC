"""Parametric drill families, machine-verified through :mod:`app.training.verify`.

The hand-written catalog (``drills.CURATED``) carries the prose and the six core
skills. This module grows the Learn catalog well past a few hundred positions by
*constructing* each idea from a small set of geometric templates and then keeping
only the ones ``verify.verify()`` proves sound. The generator is a candidate
factory, not an oracle: every emitted drill is re-checked by the same pattern
prover the curated drills pass through, so a template that drifts (a "hanging"
piece that is actually defended, a mate that is not a mate) is dropped rather
than shipped.

Motif honesty lives here, soundness lives in ``verify``: a candidate must both
describe its theme (the guards below) and net the material/mate the theme claims
(``verify``). ``generated_drills()`` is deterministic — fixed square iteration and
per-(theme, level) caps — so the composed catalog has stable keys across runs.
"""

from __future__ import annotations

from collections.abc import Iterator

import chess

from app.training.drills import THEME_NAMES, Drill
from app.training.verify import _opponent_to_move, mate_in_one_exists, verify

WHITE = chess.WHITE
BLACK = chess.BLACK

# Value of a capture, used only to keep the generator's targets clearly winning.
_VALUE = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 320,
    chess.ROOK: 500,
    chess.QUEEN: 900,
}

# Ceiling per (theme, level). Large-geometry families (hanging, discovered, pin,
# endgame) can fill this; tighter ones (mate, backrank, skewer) land well under
# and ``verify`` prunes the rest. Tuned so the composed catalog tops 800 while the
# whole ``DRILLS`` import stays a third of a second.
_CAP = 48

# Undefended/black pieces worth grabbing, in "hardest to spot" order for levels.
_HANG_TARGETS = (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT)


def _build(placement: dict[int, chess.Piece], turn: chess.Color) -> chess.Board:
    """A fresh board from ``{square: Piece}`` and the side to move."""
    board = chess.Board()
    board.clear()
    for sq, piece in placement.items():
        board.set_piece_at(sq, piece)
    board.turn = turn
    return board


def _P(pt: int, color: chess.Color) -> chess.Piece:
    return chess.Piece(pt, color)


def _uci(src: int, dst: int, promo: int | None = None) -> str:
    move = chess.Move(src, dst, promotion=promo)
    return move.uci()


# 0-based file/rank indices for ``chess.square(file, rank)`` (the library has no
# chess.RANK_n / chess.knight_attacks module helpers).
FILE_A, FILE_B, FILE_C, FILE_D, FILE_E, FILE_F, FILE_G, FILE_H = range(8)
RANK_1, RANK_2, RANK_3, RANK_4, RANK_5, RANK_6, RANK_7, RANK_8 = range(8)
FILES = range(FILE_A, FILE_H + 1)
RANKS = range(RANK_1, RANK_8 + 1)


def _attacks(piece_type: int, sq: int) -> list[int]:
    """Squares a lone ``piece_type`` on ``sq`` attacks, colour-agnostic."""
    probe = chess.Board()
    probe.clear()
    probe.set_piece_at(sq, chess.Piece(piece_type, WHITE))
    return sorted(chess.SquareSet(probe.attacks(sq)))


def _adjacent(a: int, b: int) -> bool:
    return (
        max(
            abs(chess.square_file(a) - chess.square_file(b)),
            abs(chess.square_rank(a) - chess.square_rank(b)),
        )
        <= 1
    )


def _legal(board: chess.Board, uci: str) -> bool:
    try:
        return board.is_legal(chess.Move.from_uci(uci))
    except ValueError:
        return False


# --- Checkmate -------------------------------------------------------------


def _mate_candidates() -> Iterator[tuple[int, str, str, tuple[str, ...], str]]:
    """Back-rank rook mates (rook slides to the eighth rank) + smothered mates."""
    shelter = (chess.F7, chess.G7, chess.H7)  # black king's own pawns, king on g8
    bk = chess.G8
    wk = chess.H1
    base = {bk: _P(chess.KING, BLACK), wk: _P(chess.KING, WHITE)}
    base.update({sq: _P(chess.PAWN, BLACK) for sq in shelter})
    for f in range(FILE_A, FILE_E + 1):  # a-file .. e-file; f/h adjoin the g8 king
        dest = chess.square(f, RANK_8)
        for rank in RANKS:  # rook's start rank on that file (0-based)
            start = chess.square(f, rank)
            home = _uci(start, dest)
            board = _build({**base, start: _P(chess.ROOK, WHITE)}, WHITE)
            if rank == RANK_8 or not _legal(board, home):
                continue
            level = 1 if rank == RANK_1 else (2 if rank <= RANK_4 else 3)
            yield (
                level,
                board.fen(),
                home,
                (),
                "The rook reaches the eighth rank; the king's own pawns leave it no "
                "escape square. Back-rank mate.",
            )

    # Smothered: knight to f7 mates a king boxed in by its rook and pawns.
    smothered = {
        chess.H8: _P(chess.KING, BLACK),
        chess.G8: _P(chess.ROOK, BLACK),
        chess.G7: _P(chess.PAWN, BLACK),
        chess.H7: _P(chess.PAWN, BLACK),
        wk: _P(chess.KING, WHITE),
    }
    for start in _attacks(chess.KNIGHT, chess.F7):
        if start in smothered:
            continue
        board = _build({**smothered, start: _P(chess.KNIGHT, WHITE)}, WHITE)
        if _legal(board, _uci(start, chess.F7)):
            yield (
                3,
                board.fen(),
                _uci(start, chess.F7),
                (),
                "The knight lands on f7 checking a king smothered by its own pieces — "
                "nothing can capture it and the king cannot move. The smothered mate.",
            )


# --- Hanging pieces --------------------------------------------------------


def _hanging_candidates() -> Iterator[tuple[int, str, str, tuple[str, ...], str]]:
    """Capture an undefended black piece along a rank, file or knight leap."""
    wk, bk = chess.A1, chess.H8
    for target_pt in _HANG_TARGETS:
        level = {chess.QUEEN: 1, chess.ROOK: 2, chess.BISHOP: 3, chess.KNIGHT: 3}[target_pt]
        for tsq in chess.SQUARES:
            if tsq in (wk, bk) or _adjacent(tsq, bk):
                continue  # adjacent to the king => it has a defender
            for attacker_pt, origin in _hanging_attackers(tsq, wk, bk):
                board = _build(
                    {
                        wk: _P(chess.KING, WHITE),
                        bk: _P(chess.KING, BLACK),
                        tsq: _P(target_pt, BLACK),
                        origin: _P(attacker_pt, WHITE),
                    },
                    WHITE,
                )
                if board.is_check():  # do not start from a position where we already check
                    continue
                cap = _uci(origin, tsq)
                if not _legal(board, cap):
                    continue
                if board.is_attacked_by(BLACK, tsq):  # must be truly undefended
                    continue
                yield (level, board.fen(), cap, (), _HANG_WHY[target_pt])


def _hanging_attackers(tsq: int, wk: int, bk: int) -> list[tuple[int, int]]:
    """Legal white pieces that can capture on ``tsq`` from a clear line."""
    out: list[tuple[int, int]] = []
    # Rook along the rank/file, one clear step away from the target.
    for rook_sq in _line_squares(tsq):
        if rook_sq in (wk, bk):
            continue
        out.append((chess.ROOK, rook_sq))
    for knight_sq in _attacks(chess.KNIGHT, tsq):
        if knight_sq not in (wk, bk):
            out.append((chess.KNIGHT, knight_sq))
    return out


def _line_squares(tsq: int) -> list[int]:
    """Rook-origin squares on tsq's rank and file that slide straight onto it."""
    f, r = chess.square_file(tsq), chess.square_rank(tsq)
    origins: list[int] = []
    for sf in range(f + 1, 8):  # to the right on the rank
        origins.append(chess.square(sf, r))
        break  # the nearest clear square already reaches tsq
    for sf in range(f - 1, -1, -1):
        origins.append(chess.square(sf, r))
        break
    for sr in range(r + 1, 8):
        origins.append(chess.square(f, sr))
        break
    for sr in range(r - 1, -1, -1):
        origins.append(chess.square(f, sr))
        break
    return origins


_HANG_WHY = {
    chess.QUEEN: "The black queen has no defender. A piece nobody protects is "
    "'hanging' — just take it and the queen is yours.",
    chess.ROOK: "Scan for the pieces no one is watching. This rook stands "
    "undefended, so the capture wins clean material.",
    chess.BISHOP: "A bishop left without a protector is free. Grab it — an "
    "undefended piece is only a pawn's worth of risk at worst.",
    chess.KNIGHT: "Even a knight can be hanging. When no black piece covers the "
    "square, the capture nets a full minor piece.",
}


# --- Pins ------------------------------------------------------------------


def _pin_candidates() -> Iterator[tuple[int, str, str, tuple[str, ...], str]]:
    """A black piece pinned to its king by a rook, then captured by a knight."""
    wk = chess.H1
    for victim_pt in _HANG_TARGETS:
        level = {chess.QUEEN: 3, chess.ROOK: 1, chess.BISHOP: 2, chess.KNIGHT: 3}[victim_pt]
        for f in range(FILE_A, FILE_H):  # pin file a..g (h1 is the white king's file)
            king_sq = chess.square(f, RANK_8)
            rook_sq = chess.square(f, RANK_1)
            for vr in range(RANK_2, RANK_7):  # victim between the two
                victim = chess.square(f, vr)
                if _adjacent(victim, king_sq):
                    continue  # king would defend it
                for origin in _pin_knight_origins(victim, {wk, king_sq, rook_sq, victim}):
                    board = _build(
                        {
                            wk: _P(chess.KING, WHITE),
                            king_sq: _P(chess.KING, BLACK),
                            rook_sq: _P(chess.ROOK, WHITE),
                            victim: _P(victim_pt, BLACK),
                            origin: _P(chess.KNIGHT, WHITE),
                        },
                        WHITE,
                    )
                    if not board.is_pinned(BLACK, victim):
                        continue
                    if board.is_attacked_by(BLACK, victim):
                        continue
                    cap = _uci(origin, victim)
                    if not _legal(board, cap):
                        continue
                    yield (
                        level,
                        board.fen(),
                        cap,
                        (),
                        "The rook pins that piece to the king, so it cannot move to "
                        "defend itself. A pinned piece guards nothing — take it.",
                    )


def _pin_knight_origins(victim: int, used: set[int]) -> list[int]:
    """Knight squares that attack ``victim`` and sit off the pin file."""
    origins = []
    for sq in _attacks(chess.KNIGHT, victim):
        if sq in used or chess.square_file(sq) == chess.square_file(victim):
            continue
        origins.append(sq)
    return origins[:1]  # one origin per pin keeps the catalog varied, not spammed


# --- Forks -----------------------------------------------------------------


# (fork square, king square, level): the knight on the fork square checks the king
# and attacks a target on its other squares; the king must move, then it is taken.
_FORK_TEMPLATES = (
    (chess.F7, chess.H8, 1),
    (chess.C7, chess.A8, 1),
    (chess.E7, chess.G8, 2),
    (chess.F2, chess.H1, 2),
    (chess.C2, chess.A1, 2),
    (chess.E2, chess.G1, 3),
    (chess.G6, chess.H8, 3),
    (chess.B6, chess.A8, 3),
)


def _fork_candidates() -> Iterator[tuple[int, str, str, tuple[str, ...], str]]:
    wk = chess.D4
    for fork_sq, king_sq, level in _FORK_TEMPLATES:
        fork_attacks = _attacks(chess.KNIGHT, fork_sq)
        for origin in fork_attacks:
            if origin in (king_sq, wk):
                continue
            for target_pt in (chess.ROOK, chess.QUEEN):
                for target_sq in fork_attacks:
                    if target_sq in (king_sq, origin, wk) or _adjacent(target_sq, king_sq):
                        continue
                    built = _try_fork(fork_sq, king_sq, origin, target_pt, target_sq, wk)
                    if built is not None:
                        fen, sol, line = built
                        why = (
                            "One knight hits two targets at once. It checks the king "
                            "and attacks the "
                            + ("queen" if target_pt == chess.QUEEN else "rook")
                            + "; the king must move out of check, then the knight takes."
                        )
                        yield (level, fen, sol, line, why)


def _try_fork(
    fork_sq: int, king_sq: int, origin: int, target_pt: int, target_sq: int, wk: int
) -> tuple[str, str, tuple[str, ...]] | None:
    """Simulate the fork; return (fen, solution, line) when it really wins material."""
    board = _build(
        {
            wk: _P(chess.KING, WHITE),
            king_sq: _P(chess.KING, BLACK),
            target_sq: _P(target_pt, BLACK),
            origin: _P(chess.KNIGHT, WHITE),
        },
        WHITE,
    )
    start_fen = board.fen()
    solution = _uci(origin, fork_sq)
    if not _legal(board, solution):
        return None
    board.push(chess.Move.from_uci(solution))
    if not board.is_check():
        return None
    reply = _one_king_move(board, king_sq)
    if reply is None:
        return None
    board.push(chess.Move.from_uci(reply))
    capture = _uci(fork_sq, target_sq)
    if not _legal(board, capture):
        return None
    if board.is_attacked_by(BLACK, target_sq):
        return None
    return start_fen, solution, (reply, capture)


def _one_king_move(board: chess.Board, king_sq: int) -> str | None:
    """A legal king move that steps out of check, or None if there isn't one."""
    for move in board.legal_moves:
        if move.from_square == king_sq:
            return move.uci()
    return None


# --- Skewers ---------------------------------------------------------------


# Rook checks the king along a file/rank; the king steps off the line and the
# rook scoops up a bigger piece that sat behind it.
def _skewer_candidates() -> Iterator[tuple[int, str, str, tuple[str, ...], str]]:
    wk = chess.E4
    for target_pt in (chess.ROOK, chess.QUEEN):
        # File skewers: rook slides onto the file to check the king, takes behind.
        for f in range(8):
            for kr in range(RANK_3, RANK_6):
                # Rook target = easy; a queen skewered behind a king high on the
                # board takes longer to see, so it ranks up the ramp.
                level = 1 if target_pt == chess.ROOK else (3 if kr >= RANK_5 else 2)
                for tr in range(kr + 2, RANK_8 + 1):
                    target_sq = chess.square(f, tr)
                    built = _try_skewer_file(f, kr, target_sq, target_pt, wk)
                    if built is not None:
                        sol, line, fen = built
                        yield (level, fen, sol, line, _SKEWER_WHY)


def _try_skewer_file(
    f: int, kr: int, target_sq: int, target_pt: int, wk: int
) -> tuple[str, tuple[str, ...], str] | None:
    """Build a file skewer: a rank-1 rook slide checks the king, then takes behind."""
    king_sq = chess.square(f, kr)
    rook_sq = chess.square(f, RANK_1)
    start = chess.square(FILE_H if f != FILE_H else FILE_A, RANK_1)
    if len({wk, rook_sq, start, king_sq, target_sq}) < 5:
        return None
    probe = _build(
        {
            wk: _P(chess.KING, WHITE),
            start: _P(chess.ROOK, WHITE),
            king_sq: _P(chess.KING, BLACK),
            target_sq: _P(target_pt, BLACK),
        },
        WHITE,
    )
    start_fen = probe.fen()
    solution = _uci(start, rook_sq)
    if not _legal(probe, solution):
        return None
    probe.push(chess.Move.from_uci(solution))
    if not probe.is_check():
        return None
    reply = _one_king_move(probe, king_sq)
    if reply is None:
        return None
    probe.push(chess.Move.from_uci(reply))
    grab = _uci(rook_sq, target_sq)
    if not _legal(probe, grab):
        return None
    return solution, (reply, grab), start_fen


_SKEWER_WHY = (
    "The rook checks along the line; the king must step off it, exposing the piece "
    "behind. Checking a king that shields a bigger target is a skewer — the reverse "
    "of a pin."
)


# --- Discovered attacks ----------------------------------------------------


def _discovered_candidates() -> Iterator[tuple[int, str, str, tuple[str, ...], str]]:
    """A piece moves with capture, uncovering a rook's check along the file."""
    wk = chess.E2
    for f in range(8):
        rook_sq = chess.square(f, RANK_1)
        king_sq = chess.square(f, RANK_8)
        for blocker_r in (RANK_4, RANK_5):
            blocker = chess.square(f, blocker_r)
            if blocker in (rook_sq, king_sq):
                continue
            for target_pt in (chess.ROOK, chess.QUEEN, chess.BISHOP, chess.KNIGHT):
                for dest in _attacks(chess.KNIGHT, blocker):
                    if dest in (rook_sq, king_sq, blocker, wk) or _adjacent(dest, king_sq):
                        continue
                    built = _try_discovered(f, blocker, dest, target_pt, wk)
                    if built is not None:
                        level, fen, sol = built
                        yield (level, fen, sol, (), _DISCOVERED_WHY)


def _try_discovered(
    f: int, blocker: int, dest: int, target_pt: int, wk: int
) -> tuple[int, str, str] | None:
    rook_sq = chess.square(f, RANK_1)
    king_sq = chess.square(f, RANK_8)
    board = _build(
        {
            wk: _P(chess.KING, WHITE),
            rook_sq: _P(chess.ROOK, WHITE),
            blocker: _P(chess.KNIGHT, WHITE),
            king_sq: _P(chess.KING, BLACK),
            dest: _P(target_pt, BLACK),
        },
        WHITE,
    )
    if board.is_attacked_by(BLACK, dest):
        return None
    if board.is_check():  # blocked, so the discovered check is not yet on
        return None
    if board.is_pinned(WHITE, blocker):
        return None
    start_fen = board.fen()
    move = _uci(blocker, dest)
    if not _legal(board, move):
        return None
    board.push(chess.Move.from_uci(move))
    if not board.is_check():  # the move must uncover the rook's check
        return None
    level = {chess.QUEEN: 2, chess.ROOK: 1, chess.BISHOP: 3, chess.KNIGHT: 3}[target_pt]
    return level, start_fen, move


_DISCOVERED_WHY = (
    "The knight leaps away capturing a piece and, by clearing the file, reveals the "
    "rook's check on the king. One move, two threats: that is a discovered attack."
)


# --- Endgames --------------------------------------------------------------


def _endgame_candidates() -> Iterator[tuple[int, str, str, tuple[str, ...], str]]:
    wk = chess.A1
    # E1 — a clear pawn promotes to a queen.
    for f in range(8):
        promo_sq = chess.square(f, RANK_8)
        pawn_sq = chess.square(f, RANK_7)
        for bk in (chess.H8, chess.A8, chess.H1, chess.A5, chess.F5):
            if _adjacent(bk, promo_sq) or bk in (pawn_sq, promo_sq, wk):
                continue
            board = _build(
                {
                    wk: _P(chess.KING, WHITE),
                    pawn_sq: _P(chess.PAWN, WHITE),
                    bk: _P(chess.KING, BLACK),
                },
                WHITE,
            )
            sol = _uci(pawn_sq, promo_sq, chess.QUEEN)
            if _legal(board, sol):
                yield (
                    1,
                    board.fen(),
                    sol,
                    (),
                    "The pawn reaches the eighth rank and promotes to a queen — the "
                    "single biggest swing on the board.",
                )
    # E2 — promote *with capture*: the pawn takes a piece on the eighth rank.
    for f in range(8):
        pawn_sq = chess.square(f, RANK_7)
        for nf in (f - 1, f + 1):
            if not 0 <= nf <= 7:
                continue
            cap_sq = chess.square(nf, RANK_8)
            if cap_sq == wk or pawn_sq == wk:
                continue
            for cap_pt in (chess.KNIGHT, chess.BISHOP, chess.ROOK):
                for bk in (chess.H8, chess.A8, chess.A5, chess.H1):
                    if bk in (pawn_sq, cap_sq) or _adjacent(bk, cap_sq):
                        continue
                    board = _build(
                        {
                            wk: _P(chess.KING, WHITE),
                            pawn_sq: _P(chess.PAWN, WHITE),
                            cap_sq: _P(cap_pt, BLACK),
                            bk: _P(chess.KING, BLACK),
                        },
                        WHITE,
                    )
                    sol = _uci(pawn_sq, cap_sq, chess.QUEEN)
                    if _legal(board, sol):
                        yield (
                            2,
                            board.fen(),
                            sol,
                            (),
                            "The pawn captures the piece blocking its path and promotes "
                            "on the same move — removing a defender and queening at once.",
                        )
    # E3 — an outside passer the enemy king is too far to catch.
    for f in range(8):
        start = chess.square(f, RANK_6)
        mid = chess.square(f, RANK_7)
        top = chess.square(f, RANK_8)
        bk = chess.square(FILE_A if f > FILE_D else FILE_H, RANK_1)
        if bk == wk or bk in (start, mid, top) or _adjacent(bk, top):
            continue
        board = _build(
            {wk: _P(chess.KING, WHITE), start: _P(chess.PAWN, WHITE), bk: _P(chess.KING, BLACK)},
            WHITE,
        )
        start_fen = board.fen()
        push = _uci(start, mid)
        if not _legal(board, push):
            continue
        board.push(chess.Move.from_uci(push))
        reply = _one_king_move(board, bk)
        if reply is None:
            reply = _any_black_move(board)
        board.push(chess.Move.from_uci(reply))
        queen = _uci(mid, top, chess.QUEEN)
        if _legal(board, queen):
            yield (
                3,
                start_fen,
                push,
                (reply, queen),
                "Push the passed pawn one step and it promotes next move; an outside "
                "passer the enemy king cannot reach is a queen on layaway.",
            )


def _any_black_move(board: chess.Board) -> str:
    return next(iter(board.legal_moves)).uci()


# --- Back-rank safety ------------------------------------------------------


_BACK_PAWNS = (chess.F2, chess.G2, chess.H2)


def _backrank_candidates() -> Iterator[tuple[int, str, str, tuple[str, ...], str]]:
    wk = chess.G1
    bk = chess.H4
    base = {
        wk: _P(chess.KING, WHITE),
        bk: _P(chess.KING, BLACK),
        **{sq: _P(chess.PAWN, WHITE) for sq in _BACK_PAWNS},
    }
    for f in range(FILE_A, FILE_E + 1):  # a..e — f/g/h files are screened by our pawns
        for threat_pt in (chess.ROOK, chess.QUEEN):
            threat = chess.square(f, RANK_8)
            for pawn in _BACK_PAWNS:
                push = _uci(pawn, chess.square(chess.square_file(pawn), RANK_3))
                board = _build({**base, threat: _P(threat_pt, BLACK)}, WHITE)
                if not _legal(board, push):
                    continue
                if not mate_in_one_exists(_opponent_to_move(board)):
                    continue
                after = board.copy()
                after.push(chess.Move.from_uci(push))
                if mate_in_one_exists(_opponent_to_move(after)):
                    continue
                level = 1 if pawn == chess.H2 else (2 if pawn == chess.G2 else 3)
                yield (
                    level,
                    board.fen(),
                    push,
                    (),
                    "Black is one move from mate on the back rank. Push a rook pawn for "
                    "'luft' — an escape square on the second rank — before the mate lands.",
                )


# --- Multi-move sequences --------------------------------------------------

# Verified forced-line puzzles. These are produced by an *offline* authoring
# sweep (a confined black king that always has exactly one legal reply, mated on
# the final player ply), then re-certified here at import through ``verify()``.
# Embedding them keeps catalog import fast — hunting these lines live would cost
# tens of seconds every load, and the multi-move family is inherently a small,
# hand-checked set rather than a parametric template. ``verify()`` is the safety
# net: any transcription slip is pruned, never shipped. Entry shape is
# ``(level, fen, line)`` where ``line`` is the full alternating, player-first
# line; ``level`` = player-move count - 1 (2 moves = 1, 3 = 2, 4 = 3).
_SEQUENCE_SEEDS: tuple[tuple[int, str, tuple[str, ...]], ...] = (
    (1, "6k1/Q4ppp/8/8/8/8/Q7/K7 w - - 0 1", ("a7f7", "g8h8", "f7g8")),
    (1, "7k/6pp/8/8/Q7/8/Q7/K7 w - - 0 1", ("a2g8", "h8g8", "a4e8")),
    (1, "k7/pp6/Q7/8/8/8/Q7/K7 w - - 0 1", ("a2d5", "a8b8", "a6b7")),
    (1, "1k6/ppp5/8/8/3Q4/8/Q7/K7 w - - 0 1", ("a2a7", "b8c8", "a7a8")),
    (1, "2k5/1pppQ3/8/8/8/Q7/8/K7 w - - 0 1", ("e7d8", "c8d8", "a3f8")),
    (1, "3k4/2ppp3/Q7/8/8/8/Q7/K7 w - - 0 1", ("a6c8", "d8c8", "a2a8")),
    (1, "6k1/Q4ppp/8/8/8/8/Q7/K7 w - - 0 1", ("a7f7", "g8h8", "f7f8")),
    (1, "7k/6pp/8/1Q6/8/8/Q7/K7 w - - 0 1", ("a2g8", "h8g8", "b5e8")),
    (1, "k7/pp6/Q7/8/8/8/Q7/K7 w - - 0 1", ("a2d5", "a8b8", "d5d8")),
    (1, "1k6/ppp5/8/8/8/4Q3/Q7/K7 w - - 0 1", ("a2a7", "b8c8", "e3e8")),
    (1, "2k5/1ppp4/5Q2/8/8/Q7/8/K7 w - - 0 1", ("f6d8", "c8d8", "a3f8")),
    (1, "3k4/1Qppp3/8/8/8/8/Q7/K7 w - - 0 1", ("b7c8", "d8c8", "a2a8")),
    (1, "6k1/Q4ppp/8/8/8/8/Q7/K7 w - - 0 1", ("a7f7", "g8h8", "f7e8")),
    (1, "7k/6pp/2Q5/8/8/8/Q7/K7 w - - 0 1", ("a2g8", "h8g8", "c6e8")),
    (1, "k7/pp6/Q7/8/8/8/Q7/K7 w - - 0 1", ("a2d5", "a8b8", "d5b7")),
    (1, "1k6/ppp5/8/8/3Q4/Q7/8/K7 w - - 0 1", ("a3a7", "b8c8", "a7a8")),
    (1, "2k5/1ppp4/8/6Q1/8/Q7/8/K7 w - - 0 1", ("g5d8", "c8d8", "a3f8")),
    (1, "3k4/2pppQ2/8/8/8/8/Q7/K7 w - - 0 1", ("f7e8", "d8e8", "a2g8")),
    (1, "6k1/Q4ppp/8/8/8/8/Q7/K7 w - - 0 1", ("a7f7", "g8h8", "a2a8")),
    (1, "7k/3Q2pp/8/8/8/8/Q7/K7 w - - 0 1", ("a2g8", "h8g8", "d7e8")),
    (1, "k7/pp6/Q7/8/8/8/Q7/K7 w - - 0 1", ("a2g2", "a8b8", "a6b7")),
    (1, "1k6/ppp5/8/8/8/Q3Q3/8/K7 w - - 0 1", ("a3a7", "b8c8", "e3e8")),
    (1, "2k5/1ppp4/8/8/7Q/Q7/8/K7 w - - 0 1", ("h4d8", "c8d8", "a3f8")),
    (1, "3k4/2ppp3/6Q1/8/8/8/Q7/K7 w - - 0 1", ("g6e8", "d8e8", "a2g8")),
    (1, "6k1/Q4ppp/8/8/8/8/Q7/K7 w - - 0 1", ("a2f7", "g8h8", "f7f8")),
    (1, "7k/6pp/8/8/8/8/Q3Q3/K7 w - - 0 1", ("a2g8", "h8g8", "e2e8")),
    (1, "k7/pp6/Q7/8/8/8/Q7/K7 w - - 0 1", ("a2g2", "a8b8", "g2b7")),
    (1, "1k6/ppp5/8/Q7/Q7/8/8/K7 w - - 0 1", ("a5a7", "b8c8", "a7a8")),
    (1, "2k5/1ppp4/8/1Q6/Q7/8/8/K7 w - - 0 1", ("b5d7", "c8b8", "d7e8")),
    (1, "3k4/2ppp3/8/7Q/8/8/Q7/K7 w - - 0 1", ("h5e8", "d8e8", "a2g8")),
    (1, "6k1/Q4ppp/8/8/8/8/Q7/K7 w - - 0 1", ("a2f7", "g8h8", "f7e8")),
    (1, "7k/6pp/8/8/8/4Q3/Q7/K7 w - - 0 1", ("a2g8", "h8g8", "e3e8")),
    (1, "k7/pp6/8/3Q4/8/8/Q7/K7 w - - 0 1", ("a2a6", "a8b8", "a6b7")),
    (1, "1k6/ppp5/8/Q7/Q7/8/8/K7 w - - 0 1", ("a5a7", "b8c8", "a4e8")),
    (1, "2k5/1ppp4/8/1Q6/Q7/8/8/K7 w - - 0 1", ("b5d7", "c8b8", "d7d8")),
    (1, "3k4/2ppp3/Q7/8/8/Q7/8/K7 w - - 0 1", ("a6c8", "d8c8", "a3a8")),
    (1, "6k1/Q4ppp/8/8/8/8/Q7/K7 w - - 0 1", ("a2f7", "g8h8", "f7g7")),
    (1, "7k/6pp/8/8/4Q3/8/Q7/K7 w - - 0 1", ("a2g8", "h8g8", "e4e8")),
    (1, "k7/pp6/8/3Q4/8/8/Q7/K7 w - - 0 1", ("a2a6", "a8b8", "d5d8")),
    (1, "1k6/ppp5/Q7/8/Q7/8/8/K7 w - - 0 1", ("a6a7", "b8c8", "a7a8")),
    (2, "6k1/3Q1ppp/8/8/8/8/Q7/K7 w - - 0 1", ("a2f7", "g8h8", "f7g8", "h8g8", "d7e8")),
    (2, "7k/6pp/7Q/8/8/Q7/8/K7 w - - 0 1", ("a3c3", "h8g8", "c3c8", "g8f7", "h6e6")),
    (2, "k7/pp6/8/8/8/5Q2/Q7/K7 w - - 0 1", ("a2a6", "a8b8", "f3f8", "b8c7", "a6d6")),
    (2, "1k6/ppp5/8/8/8/Q7/Q7/K7 w - - 0 1", ("a3a7", "b8c8", "a2e6", "c8d8", "a7b8")),
    (2, "2k5/1ppp4/8/1Q6/Q7/8/8/K7 w - - 0 1", ("b5d7", "c8b8", "d7c8", "b8c8", "a4e8")),
    (2, "3k4/2ppp3/8/8/1Q6/Q7/8/K7 w - - 0 1", ("b4e7", "d8c8", "a3a6", "c8b8", "e7f8")),
    (2, "6k1/4Qppp/8/8/8/8/Q7/K7 w - - 0 1", ("a2f7", "g8h8", "f7g8", "h8g8", "e7e8")),
    (2, "7k/6pp/7Q/Q7/8/8/8/K7 w - - 0 1", ("a5c3", "h8g8", "c3c8", "g8f7", "h6e6")),
    (2, "k7/pp6/Q7/8/8/Q7/8/K7 w - - 0 1", ("a3f3", "a8b8", "f3f8", "b8c7", "a6d6")),
    (2, "1k6/ppp5/8/8/8/Q7/Q7/K7 w - - 0 1", ("a3a7", "b8c8", "a2e6", "c8d8", "a7a8")),
    (2, "2k5/1ppp4/2Q5/8/Q7/8/8/K7 w - - 0 1", ("c6d7", "c8b8", "d7c8", "b8c8", "a4e8")),
    (2, "3k4/2ppp3/8/8/1Q6/Q7/8/K7 w - - 0 1", ("b4e7", "d8c8", "a3a6", "c8b8", "e7e8")),
    (2, "6k1/5ppp/6Q1/8/8/8/Q7/K7 w - - 0 1", ("a2f7", "g8h8", "f7g8", "h8g8", "g6e8")),
    (2, "7k/6pp/Q7/8/8/2Q5/8/K7 w - - 0 1", ("a6h6", "h8g8", "c3c8", "g8f7", "h6e6")),
    (2, "k7/pp6/8/8/8/Q4Q2/8/K7 w - - 0 1", ("a3a6", "a8b8", "f3f8", "b8c7", "a6d6")),
    (2, "1k6/ppp5/8/8/8/Q7/Q7/K7 w - - 0 1", ("a3a7", "b8c8", "a2e6", "c8d8", "a7d4")),
    (2, "2k5/1ppp4/8/8/Q7/8/3Q4/K7 w - - 0 1", ("a4d7", "c8b8", "d7e8", "b8a7", "d2a5")),
    (2, "3k4/2ppp3/8/8/1Q6/Q7/8/K7 w - - 0 1", ("b4e7", "d8c8", "a3a6", "c8b8", "e7d8")),
    (2, "6k1/5ppp/8/7Q/8/8/Q7/K7 w - - 0 1", ("a2f7", "g8h8", "f7g8", "h8g8", "h5e8")),
    (2, "7k/6pp/7Q/8/8/8/1Q6/K7 w - - 0 1", ("b2c3", "h8g8", "c3c8", "g8f7", "h6e6")),
    (2, "k7/pp6/8/8/Q7/5Q2/8/K7 w - - 0 1", ("a4a6", "a8b8", "f3f8", "b8c7", "a6d6")),
    (2, "1k6/ppp5/8/8/Q7/8/Q7/K7 w - - 0 1", ("a4a7", "b8c8", "a2e6", "c8d8", "a7b8")),
    (2, "2k5/1ppp4/8/8/Q7/8/3Q4/K7 w - - 0 1", ("a4d7", "c8b8", "d7d8", "b8a7", "d2a5")),
    (2, "3k4/2ppp3/8/8/1Q6/Q7/8/K7 w - - 0 1", ("b4e7", "d8c8", "a3a6", "c8b8", "e7b4")),
    (2, "6k1/Q4ppp/6Q1/8/8/8/8/K7 w - - 0 1", ("a7f7", "g8h8", "f7g8", "h8g8", "g6e8")),
    (2, "7k/6pp/7Q/8/8/1Q6/8/K7 w - - 0 1", ("b3c3", "h8g8", "c3c8", "g8f7", "h6e6")),
    (2, "k7/pp6/8/Q7/8/5Q2/8/K7 w - - 0 1", ("a5a6", "a8b8", "f3f8", "b8c7", "a6d6")),
    (2, "1k6/ppp5/8/8/Q7/8/Q7/K7 w - - 0 1", ("a4a7", "b8c8", "a2e6", "c8d8", "a7a8")),
    (2, "2k5/1ppp4/8/8/Q7/8/3Q4/K7 w - - 0 1", ("d2d7", "c8b8", "d7c8", "b8c8", "a4e8")),
    (2, "3k4/2ppp3/8/2Q5/8/Q7/8/K7 w - - 0 1", ("c5e7", "d8c8", "a3a6", "c8b8", "e7f8")),
    (2, "6k1/Q4ppp/8/7Q/8/8/8/K7 w - - 0 1", ("a7f7", "g8h8", "f7g8", "h8g8", "h5e8")),
    (2, "7k/6pp/7Q/8/1Q6/8/8/K7 w - - 0 1", ("b4c3", "h8g8", "c3c8", "g8f7", "h6e6")),
    (2, "k7/pp6/Q7/8/8/1Q6/8/K7 w - - 0 1", ("b3f3", "a8b8", "f3f8", "b8c7", "a6d6")),
    (2, "1k6/ppp5/8/8/Q7/8/Q7/K7 w - - 0 1", ("a4a7", "b8c8", "a2e6", "c8d8", "a7d4")),
    (2, "2k5/1ppp4/8/8/Q7/3Q4/8/K7 w - - 0 1", ("d3d7", "c8b8", "d7c8", "b8c8", "a4e8")),
    (2, "3k4/2ppp3/8/2Q5/8/Q7/8/K7 w - - 0 1", ("c5e7", "d8c8", "a3a6", "c8b8", "e7e8")),
    (2, "6k1/3Q1ppp/8/8/8/1Q6/8/K7 w - - 0 1", ("b3f7", "g8h8", "f7g8", "h8g8", "d7e8")),
    (2, "7k/6pp/1Q6/8/8/2Q5/8/K7 w - - 0 1", ("b6h6", "h8g8", "c3c8", "g8f7", "h6e6")),
    (2, "k7/pp6/Q7/8/8/2Q5/8/K7 w - - 0 1", ("c3f3", "a8b8", "f3f8", "b8c7", "a6d6")),
    (2, "1k6/ppp5/8/Q7/8/8/Q7/K7 w - - 0 1", ("a5a7", "b8c8", "a2e6", "c8d8", "a7b8")),
    (
        3,
        "6k1/5ppp/8/8/8/3Q4/2Q5/K7 w - - 0 1",
        ("d3h7", "g8f8", "c2c5", "f8e8", "h7h8", "e8d7", "h8c8"),
    ),
    (
        3,
        "7k/6pp/7Q/8/8/Q7/8/K7 w - - 0 1",
        ("a3c3", "h8g8", "c3c8", "g8f7", "c8e6", "f7f8", "h6f4"),
    ),
    (
        3,
        "k7/pp6/8/8/8/5Q2/Q7/K7 w - - 0 1",
        ("a2a6", "a8b8", "f3f8", "b8c7", "f8d6", "c7c8", "a6c4"),
    ),
    (
        3,
        "1k6/ppp5/8/8/8/Q7/Q7/K7 w - - 0 1",
        ("a3a7", "b8c8", "a7a8", "c8d7", "a2d5", "d7e7", "a8d8"),
    ),
    (
        3,
        "2k5/1ppp4/8/8/Q7/3Q4/8/K7 w - - 0 1",
        ("a4d7", "c8b8", "d7d8", "b8a7", "d8c7", "a7a8", "d3a3"),
    ),
    (
        3,
        "3k4/2ppp3/8/8/1Q6/Q7/8/K7 w - - 0 1",
        ("b4e7", "d8c8", "e7f8", "c8b7", "f8a8", "b7b6", "a8a6"),
    ),
    (
        3,
        "6k1/5ppp/8/8/8/3Q4/2Q5/K7 w - - 0 1",
        ("d3h7", "g8f8", "c2c5", "f8e8", "h7g8", "e8d7", "g8c8"),
    ),
    (
        3,
        "7k/6pp/7Q/Q7/8/8/8/K7 w - - 0 1",
        ("a5c3", "h8g8", "c3c8", "g8f7", "c8e6", "f7f8", "h6f4"),
    ),
    (
        3,
        "k7/pp6/Q7/8/8/Q7/8/K7 w - - 0 1",
        ("a3f3", "a8b8", "f3f8", "b8c7", "f8d6", "c7c8", "a6c4"),
    ),
    (
        3,
        "1k6/ppp5/8/8/Q7/8/Q7/K7 w - - 0 1",
        ("a4a7", "b8c8", "a7a8", "c8d7", "a2d5", "d7e7", "a8d8"),
    ),
    (
        3,
        "2k5/1ppp4/3Q4/8/Q7/8/8/K7 w - - 0 1",
        ("a4d7", "c8b8", "d7e8", "b8a7", "e8a4", "a7b8", "d6f8"),
    ),
    (
        3,
        "3k4/2ppp3/8/8/1Q6/Q7/8/K7 w - - 0 1",
        ("b4e7", "d8c8", "e7f8", "c8b7", "f8a8", "b7b6", "a3a5"),
    ),
    (
        3,
        "6k1/5ppp/8/8/4Q3/8/2Q5/K7 w - - 0 1",
        ("e4h7", "g8f8", "c2c5", "f8e8", "h7h8", "e8d7", "h8c8"),
    ),
    (
        3,
        "7k/6pp/Q7/8/8/2Q5/8/K7 w - - 0 1",
        ("a6h6", "h8g8", "c3c8", "g8f7", "c8e6", "f7f8", "h6f4"),
    ),
    (
        3,
        "k7/pp6/8/8/8/Q4Q2/8/K7 w - - 0 1",
        ("a3a6", "a8b8", "f3f8", "b8c7", "f8d6", "c7c8", "a6c4"),
    ),
    (
        3,
        "1k6/ppp5/8/Q7/8/8/Q7/K7 w - - 0 1",
        ("a5a7", "b8c8", "a7a8", "c8d7", "a2d5", "d7e7", "a8d8"),
    ),
    (
        3,
        "2k5/1ppp4/3Q4/8/Q7/8/8/K7 w - - 0 1",
        ("a4d7", "c8b8", "d7e8", "b8a7", "e8a4", "a7b8", "d6d8"),
    ),
    (
        3,
        "3k4/2ppp3/8/8/1Q6/Q7/8/K7 w - - 0 1",
        ("b4e7", "d8c8", "e7f8", "c8b7", "f8a8", "b7b6", "a3b4"),
    ),
    (
        3,
        "6k1/5ppp/8/8/4Q3/8/2Q5/K7 w - - 0 1",
        ("e4h7", "g8f8", "c2c5", "f8e8", "h7g8", "e8d7", "g8c8"),
    ),
    (
        3,
        "7k/6pp/7Q/8/8/8/1Q6/K7 w - - 0 1",
        ("b2c3", "h8g8", "c3c8", "g8f7", "c8e6", "f7f8", "h6f4"),
    ),
    (
        3,
        "k7/pp6/8/8/Q7/5Q2/8/K7 w - - 0 1",
        ("a4a6", "a8b8", "f3f8", "b8c7", "f8d6", "c7c8", "a6c4"),
    ),
    (
        3,
        "1k6/ppp5/Q7/8/8/8/Q7/K7 w - - 0 1",
        ("a6a7", "b8c8", "a7a8", "c8d7", "a2d5", "d7e7", "a8d8"),
    ),
    (
        3,
        "2k5/1ppp4/3Q4/8/Q7/8/8/K7 w - - 0 1",
        ("a4d7", "c8b8", "d7e8", "b8a7", "d6c7", "a7a6", "e8a4"),
    ),
    (
        3,
        "3k4/2ppp3/8/8/1Q6/Q7/8/K7 w - - 0 1",
        ("b4e7", "d8c8", "e7f8", "c8b7", "a3a8", "b7b6", "f8b4"),
    ),
    (
        3,
        "6k1/5ppp/8/5Q2/8/8/2Q5/K7 w - - 0 1",
        ("f5h7", "g8f8", "c2c5", "f8e8", "h7h8", "e8d7", "h8c8"),
    ),
    (
        3,
        "7k/6pp/7Q/8/8/1Q6/8/K7 w - - 0 1",
        ("b3c3", "h8g8", "c3c8", "g8f7", "c8e6", "f7f8", "h6f4"),
    ),
    (
        3,
        "k7/pp6/8/Q7/8/5Q2/8/K7 w - - 0 1",
        ("a5a6", "a8b8", "f3f8", "b8c7", "f8d6", "c7c8", "a6c4"),
    ),
    (
        3,
        "1k6/ppp5/1Q6/8/8/8/Q7/K7 w - - 0 1",
        ("b6a7", "b8c8", "a7a8", "c8d7", "a2d5", "d7e7", "a8d8"),
    ),
    (
        3,
        "2k5/1ppp4/3Q4/8/Q7/8/8/K7 w - - 0 1",
        ("a4d7", "c8b8", "d7d8", "b8a7", "d8c7", "a7a8", "c7b8"),
    ),
    (
        3,
        "3k4/2ppp3/8/8/1Q6/Q7/8/K7 w - - 0 1",
        ("b4e7", "d8c8", "e7e8", "c8b7", "e8a8", "b7b6", "a8a6"),
    ),
    (
        3,
        "6k1/5ppp/8/5Q2/8/8/2Q5/K7 w - - 0 1",
        ("f5h7", "g8f8", "c2c5", "f8e8", "h7g8", "e8d7", "g8c8"),
    ),
    (
        3,
        "7k/6pp/7Q/8/1Q6/8/8/K7 w - - 0 1",
        ("b4c3", "h8g8", "c3c8", "g8f7", "c8e6", "f7f8", "h6f4"),
    ),
    (
        3,
        "k7/pp6/R7/Q7/8/8/8/K7 w - - 0 1",
        ("a6a7", "a8b8", "a5b6", "b8c8", "b6b7", "c8d8", "b7b8"),
    ),
    (
        3,
        "1k6/ppp5/8/2Q5/8/8/Q7/K7 w - - 0 1",
        ("c5a7", "b8c8", "a7a8", "c8d7", "a2d5", "d7e7", "a8d8"),
    ),
    (
        3,
        "2k5/1ppp4/3Q4/8/Q7/8/8/K7 w - - 0 1",
        ("a4d7", "c8b8", "d7d8", "b8a7", "d8c7", "a7a8", "c7a5"),
    ),
    (
        3,
        "3k4/2ppp3/8/8/1Q6/Q7/8/K7 w - - 0 1",
        ("b4e7", "d8c8", "e7e8", "c8b7", "e8a8", "b7b6", "a3a5"),
    ),
    (
        3,
        "6k1/5ppp/6Q1/8/8/8/2Q5/K7 w - - 0 1",
        ("g6h7", "g8f8", "c2c5", "f8e8", "h7h8", "e8d7", "h8c8"),
    ),
    (
        3,
        "7k/6pp/1Q6/8/8/2Q5/8/K7 w - - 0 1",
        ("b6h6", "h8g8", "c3c8", "g8f7", "c8e6", "f7f8", "h6f4"),
    ),
    (
        3,
        "k7/pp6/R7/Q7/8/8/8/K7 w - - 0 1",
        ("a6a7", "a8b8", "a5b6", "b8c8", "b6b7", "c8d8", "b7a8"),
    ),
    (
        3,
        "1k6/ppp5/8/2Q5/8/8/Q7/K7 w - - 0 1",
        ("a2a7", "b8c8", "a7a8", "c8d7", "c5d5", "d7e7", "a8d8"),
    ),
)

_SEQUENCE_WHY = (
    "Every defensive reply is forced: each check leaves the king exactly one "
    "square, so the whole line is known in advance. Find your move at each turn "
    "and the mate arrives on its own — this is how a combination is counted, one "
    "forced ply at a time."
)


def _sequence_drills() -> Iterator[Drill]:
    """Build the multi-move set from the seed table; ``verify`` is the proof.

    One puzzle per position: the seed table has a few repeated start FENs with
    different lines, and shipping two keys for the same board would mean the same
    position grading a different move 'wrong'. Keep the first verified line per FEN.
    """
    per_level: dict[int, list[Drill]] = {1: [], 2: [], 3: []}
    seen_fens: set[str] = set()
    for level, fen, line in _SEQUENCE_SEEDS:
        if fen in seen_fens:
            continue
        drill = Drill(
            key=f"gen-sequence-{level}-{len(per_level[level])}",
            theme="sequence",
            name=THEME_NAMES["sequence"],
            level=level,
            fen=fen,
            solution=line[0],
            line=tuple(line[1:]),
            moves=tuple(line),
            prompt=_PROMPT["sequence"],
            why=_SEQUENCE_WHY,
        )
        if verify(drill) is None:
            seen_fens.add(fen)
            per_level[level].append(drill)
    for level in (1, 2, 3):
        yield from per_level[level]


# --- Assembly --------------------------------------------------------------


def _theme_drills(
    name: str, source: Iterator[tuple[int, str, str, tuple[str, ...], str]]
) -> Iterator[Drill]:
    per_level: dict[int, list[Drill]] = {1: [], 2: [], 3: []}
    for level, fen, solution, line, why in source:
        if len(per_level[level]) >= _CAP:
            continue
        drill = Drill(
            key=f"gen-{name}-{level}-{len(per_level[level])}",
            theme=name,
            name=THEME_NAMES[name],
            level=level,
            fen=fen,
            solution=solution,
            line=tuple(line),
            prompt=_PROMPT[name],
            why=why,
        )
        if verify(drill) is None:
            per_level[level].append(drill)
    for level in (1, 2, 3):
        yield from per_level[level]


_PROMPT = {
    "mate": "It is mate in one. Find it.",
    "hanging": "Find the move that wins material.",
    "fork": "One piece, two targets. Win material.",
    "pin": "A piece frozen to the king. Take it.",
    "backrank": "Your king is about to be mated on the back rank. Give it air.",
    "endgame": "Make the pawn a queen.",
    "skewer": "Check the king, then take what hides behind it.",
    "discovered": "One move unmasks another. Win material.",
    "sequence": "Play the whole forced line — each reply is forced.",
}


def generated_drills() -> tuple[Drill, ...]:
    """Every generated drill, ``verify``-clean, deterministic keys and order."""
    sources = {
        "mate": _mate_candidates(),
        "hanging": _hanging_candidates(),
        "fork": _fork_candidates(),
        "pin": _pin_candidates(),
        "backrank": _backrank_candidates(),
        "endgame": _endgame_candidates(),
        "skewer": _skewer_candidates(),
        "discovered": _discovered_candidates(),
    }
    drills: list[Drill] = []
    for name, source in sources.items():
        drills.extend(_theme_drills(name, source))
    drills.extend(_sequence_drills())
    return tuple(drills)
