"""Engine provider interface (Phase 9, ANL-001).

Pluggable analysis seam: Stockfish supplies chess facts (evals, best lines,
MultiPV); the custom engine supplies fast local analysis. Classification and
coaching consume the structured result — never raw engine output.

Per architecture: providers do search/evaluation only. No HTTP, no DB.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.games.domain import Color


@dataclass(frozen=True)
class PrincipalVariation:
    """One engine line: move, score, and the continuation (UCI moves)."""

    move: str  # UCI of the first move in this line
    score_cp: int  # centipawns from the side-to-move's perspective
    mate_in: int | None = None  # moves to mate (signed: + favors mover)
    pv: tuple[str, ...] = ()  # full principal variation in UCI


@dataclass(frozen=True)
class AnalysisResult:
    """Structured analysis of one position (the engine truth layer)."""

    fen: str
    lines: tuple[PrincipalVariation, ...] = ()
    depth: int = 0
    nodes_searched: int = 0
    time_ms: int = 0
    provider: str = "unknown"

    @property
    def best(self) -> PrincipalVariation | None:
        """Return the top line, or None when no lines were produced."""
        return self.lines[0] if self.lines else None


@dataclass(frozen=True)
class AnalyseRequest:
    """Bounded request for position analysis."""

    fen: str
    depth: int = 15
    multipv: int = 3
    max_time_ms: int = 1000
    for_color: Color = Color.WHITE
    extra: dict[str, str] = field(default_factory=dict)


class EngineProvider(Protocol):
    """Pluggable analysis provider (ANL-001)."""

    name: str

    def analyse(self, request: AnalyseRequest) -> AnalysisResult:
        """Analyse a position, returning ranked principal variations."""
        ...

    def close(self) -> None:
        """Release whatever resources the engine holds (ANL-003).

        A batch caller (a review pass) opens one process and must hand it back.
        Repeatable and safe to call on a provider that never started anything.
        """
        ...


class BatchedEngineProvider(EngineProvider, Protocol):
    """A provider a batch may hold open (ANL-003).

    `with` on the local adapter keeps one warm process across a review pass; on
    a hosted provider it only keeps the connection pool and the learned score
    convention. Both honor the protocol, so a review pass cannot tell — and must
    not care — which engine it is talking to.
    """

    def __enter__(self) -> EngineProvider:
        """Start holding the engine for the calls that follow."""
        ...

    def __exit__(self, *exc_info: object) -> None:
        """Hand the engine back. Idempotent with `close`."""
        ...
