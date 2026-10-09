"""Chess-rules adapter over python-chess.

This module is the single place that imports the ``chess`` library, keeping the
domain model (:mod:`app.games.domain`) independent of the concrete rules engine.
"""

import chess

from app.games.domain import STARTING_FEN, Color, GameStatus, Move
from app.games.errors import IllegalMoveError, InvalidMoveError


class ChessRules:
    """Adapter for legal move generation, validation, and status detection."""

    def __init__(self, fen: str | None = None) -> None:
        self._board = chess.Board(fen if fen is not None else STARTING_FEN)

    @classmethod
    def initial_fen(cls) -> str:
        """Return the FEN of the standard starting position."""
        return STARTING_FEN

    @property
    def fen(self) -> str:
        return self._board.fen()

    @property
    def turn(self) -> Color:
        return Color.WHITE if self._board.turn == chess.WHITE else Color.BLACK

    @property
    def legal_move_ucis(self) -> list[str]:
        return [move.uci() for move in self._board.legal_moves]

    def is_legal(self, uci: str) -> bool:
        """Return whether ``uci`` is a legal move in the current position."""
        move = self._parse_uci(uci)
        return move in self._board.legal_moves

    def apply_move(self, uci: str) -> Move:
        """Apply a legal move, returning it as UCI + SAN.

        Raises :class:`InvalidMoveError` for unparsable UCI and
        :class:`IllegalMoveError` for moves that are not legal.
        """
        move = self._parse_uci(uci)
        if move not in self._board.legal_moves:
            raise IllegalMoveError(uci, self.fen)
        san = self._board.san(move)
        self._board.push(move)
        return Move(uci=move.uci(), san=san)

    def is_check(self) -> bool:
        return self._board.is_check()

    def status(self) -> GameStatus:
        """Derive the game status from the current position."""
        if self._board.is_checkmate():
            return GameStatus.CHECKMATE
        if self._board.is_stalemate():
            return GameStatus.STALEMATE
        if self._board.is_insufficient_material():
            return GameStatus.DRAW
        # Fifty-move rule and threefold repetition are added in CHS-014/CHS-016.
        return GameStatus.ACTIVE

    def _parse_uci(self, uci: str) -> chess.Move:
        try:
            return chess.Move.from_uci(uci)
        except ValueError as exc:
            raise InvalidMoveError(uci) from exc
