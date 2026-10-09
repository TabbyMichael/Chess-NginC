"""Chess domain types: game modes, status, and the game/move models.

These types are deliberately independent of python-chess. The rules adapter
(:mod:`app.games.rules`) is the only module that imports the ``chess`` library.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID, uuid4

# Standard chess starting position (FEN). Cross-checked against python-chess in tests.
STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


class GameMode(StrEnum):
    """Who plays the moves."""

    LOCAL = "local"  # two players on the same device
    COMPUTER = "computer"  # human vs. engine


class Color(StrEnum):
    """Side to move or piece color."""

    WHITE = "white"
    BLACK = "black"


class GameStatus(StrEnum):
    """Lifecycle state of a game."""

    ACTIVE = "active"
    CHECKMATE = "checkmate"
    STALEMATE = "stalemate"
    DRAW = "draw"
    RESIGNED = "resigned"
    ABANDONED = "abandoned"


@dataclass(frozen=True)
class Move:
    """A single move in both UCI and SAN notation."""

    uci: str
    san: str


@dataclass
class Game:
    """A chess game's domain state, with no persistence concerns."""

    id: UUID = field(default_factory=uuid4)
    mode: GameMode = GameMode.LOCAL
    status: GameStatus = GameStatus.ACTIVE
    fen: str = STARTING_FEN
    moves: list[Move] = field(default_factory=list)
