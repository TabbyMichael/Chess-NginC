"""Custom chess engine with minimax and alpha-beta pruning."""

import time
from typing import Literal

import chess

from app.engine.domain import EngineConfig, EngineResult
from app.engine.evaluator import evaluate_position
from app.games.domain import Color


class ChessEngine:
    """A search-based chess engine with configurable depth."""

    def __init__(self, config: EngineConfig | None = None) -> None:
        self.config = config or EngineConfig()
        self._nodes_searched = 0
        self._cancelled = False
        self._deadline_ms = 0.0

    def search(self, board: chess.Board, for_color: Color) -> EngineResult:
        """Search for the best move from the current position."""
        start_time = time.time()
        self._nodes_searched = 0
        self._cancelled = False
        self._deadline_ms = start_time * 1000 + self.config.max_time_ms

        best_move = None
        best_score = -float("inf")
        depth = self.config.max_depth

        # Get legal moves
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            # No legal moves - game over
            return EngineResult(
                best_move="",
                score=evaluate_position(board, for_color),
                depth=0,
                nodes_searched=0,
                time_ms=0,
                termination="completed",
            )

        # Search each move
        for move in legal_moves:
            board.push(move)
            score = -self._minimax(board, depth - 1, -float("inf"), float("inf"), for_color)
            board.pop()

            if score > best_score:
                best_score = score
                best_move = move.uci()

            # Check for timeout
            if self._is_timeout():
                break

        elapsed_ms = int((time.time() - start_time) * 1000)
        termination: Literal["completed", "timeout", "cancelled"]
        if self._cancelled:
            termination = "cancelled"
        elif self._is_timeout():
            termination = "timeout"
        else:
            termination = "completed"

        return EngineResult(
            best_move=best_move or legal_moves[0].uci(),
            score=int(best_score),
            depth=depth,
            nodes_searched=self._nodes_searched,
            time_ms=elapsed_ms,
            termination=termination,
        )

    def cancel(self) -> None:
        """Cancel the current search."""
        self._cancelled = True

    def _minimax(
        self,
        board: chess.Board,
        depth: int,
        alpha: float,
        beta: float,
        for_color: Color,
    ) -> float:
        """Minimax with alpha-beta pruning."""
        self._nodes_searched += 1

        if self._cancelled or self._is_timeout():
            return 0

        if depth == 0 or board.is_game_over():
            return evaluate_position(board, for_color)

        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return evaluate_position(board, for_color)

        # Maximize for current player
        score = -float("inf")
        for move in legal_moves:
            board.push(move)
            value = -self._minimax(board, depth - 1, -beta, -alpha, for_color)
            board.pop()

            score = max(score, value)
            alpha = max(alpha, score)

            if alpha >= beta:
                break  # Beta cutoff

        return score

    def _is_timeout(self) -> bool:
        """Check if the search has exceeded its time limit."""
        return time.time() * 1000 > self._deadline_ms
