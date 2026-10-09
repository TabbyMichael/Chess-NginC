"""Domain errors for chess rules and moves."""


class ChessRulesError(Exception):
    """Base class for chess-rules errors."""


class InvalidMoveError(ChessRulesError):
    """A UCI string could not be parsed into a move."""

    def __init__(self, uci: str) -> None:
        self.uci = uci
        super().__init__(f"Invalid move syntax: {uci!r}")


class IllegalMoveError(ChessRulesError):
    """A move is not legal in the current position."""

    def __init__(self, uci: str, fen: str) -> None:
        self.uci = uci
        self.fen = fen
        super().__init__(f"Illegal move {uci!r} in position {fen!r}")


class InvalidFenError(ChessRulesError):
    """A FEN string does not describe a valid chess position."""

    def __init__(self, fen: str) -> None:
        self.fen = fen
        super().__init__(f"Invalid FEN: {fen!r}")
