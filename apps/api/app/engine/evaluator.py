"""Position evaluation for the chess engine."""

import chess

from app.games.domain import Color

# Piece values in centipawns
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000,  # King value for terminal positions
}


def evaluate_position(board: chess.Board, for_color: Color) -> int:
    """Evaluate a chess position in centipawns.

    Positive score = good for for_color.
    """
    # Check for terminal positions
    if board.is_checkmate():
        # The side to move lost
        return -20000 if board.turn == chess.WHITE else 20000

    if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
        return 0

    # Material evaluation
    score = 0

    for piece_type, value in PIECE_VALUES.items():
        white_count = len(board.pieces(piece_type, chess.WHITE))
        black_count = len(board.pieces(piece_type, chess.BLACK))
        score += (white_count - black_count) * value

    # Adjust for perspective
    if for_color == Color.BLACK:
        score = -score

    return score
