"""Human coaching lines for reviewed moves (REVIEW-004).

Turns the raw engine facts (grade, centipawn loss, best alternative, eval
swing) into one-or-two-sentence plain-language feedback per move — the text
the review page shows under each move. Pure text: no engine, no DB.
"""

from __future__ import annotations

import chess

_PIECE_NAMES = {"p": "pawn", "n": "knight", "b": "bishop", "r": "rook", "q": "queen"}


def _pawns(clamped: int) -> str:
    """'{3.1} pawns' phrasing for a centipawn swing; softer for tiny swings."""
    pawns = abs(clamped) / 100
    if pawns < 0.5:
        return "a small edge"
    return f"{pawns:.1f} pawns"


def _best_san(pre_fen: str, best_uci: str) -> str | None:
    try:
        return chess.Board(pre_fen).san(chess.Move.from_uci(best_uci))
    except (ValueError, KeyError):
        return None


def _capture_phrase(board: chess.Board, move: chess.Move) -> str:
    # On en passant the captured pawn sits one rank behind the destination.
    victim_square = move.to_square ^ (0x10 if board.is_en_passant(move) else 0)
    victim = board.piece_at(victim_square)
    if victim is None:
        return ""
    color = "white" if victim.color == chess.WHITE else "black"
    return f" — taking {color}’s {_PIECE_NAMES.get(victim.symbol(), 'piece')}"


def explain_move(
    pre_fen: str,
    move: chess.Move,
    quality: str,
    loss_cp: int,
    eval_after_cp: int,
    best_uci: str,
    is_best: bool,
) -> str:
    """One coaching sentence for a classified move, from the mover's view.

    `eval_after_cp` is the evaluation after the move in centipawns from the
    MOVER's perspective (positive = mover is better).
    """
    board = chess.Board(pre_fen)
    san = board.san(move)
    capture = _capture_phrase(board, move)

    board.push(move)
    if board.is_checkmate():
        gave_check = " — checkmate!"
    elif board.is_check():
        gave_check = " and leaves the opponent in check"
    else:
        gave_check = ""

    alt = _best_san(pre_fen, best_uci)

    if quality == "good" and not is_best:
        # Small loss, or a forced move pinned to 'good': no coaching needed.
        return f"{san} is solid{capture}{gave_check}, just {loss_cp} cp under the best line."
    if is_best:
        if quality == "brilliant":
            return (
                f"{san} is the engine’s top choice{capture} — a real sacrifice "
                "finding the strongest idea on the board."
            )
        if quality == "best":
            return f"{san} is exactly what the engine wants{capture}{gave_check}. Well played."
        return (
            f"{san} keeps the position at its full engine value"
            f"{capture}{gave_check}. Practically perfect."
        )
    if quality == "inaccuracy":
        prefer = f" Prefer {alt}." if alt else ""
        return f"{san} is a step in the wrong direction — {_pawns(loss_cp)} given up.{prefer}"
    if quality == "mistake":
        prefer = f" {alt} was much stronger." if alt else ""
        return f"{san} is a mistake: the evaluation drops by {_pawns(loss_cp)}{capture}.{prefer}"
    # blunder
    turned = " and hands over a winning position" if eval_after_cp < -300 else ""
    prefer = f" The way back was {alt}." if alt else ""
    return f"{san} is a blunder — it gives up {_pawns(loss_cp)}{turned}{capture}.{prefer}"
