"""Chess engine domain types: configuration, results, and evaluation."""

from dataclasses import dataclass
from enum import IntEnum
from typing import Literal


class EngineDifficulty(IntEnum):
    """Engine strength levels (higher = stronger)."""

    EASY = 1
    MEDIUM = 3
    HARD = 5


@dataclass(frozen=True)
class EngineConfig:
    """Configuration for the chess engine."""

    difficulty: EngineDifficulty = EngineDifficulty.MEDIUM
    max_depth: int = 3
    max_time_ms: int = 5000  # 5 second default


@dataclass(frozen=True)
class EngineResult:
    """Result of an engine search."""

    best_move: str  # UCI notation
    score: int  # Centipawns (positive = good for current side)
    depth: int
    nodes_searched: int
    time_ms: int
    termination: Literal["completed", "timeout", "cancelled"]
