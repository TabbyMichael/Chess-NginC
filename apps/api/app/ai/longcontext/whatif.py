"""What-if lines: a bounded live Stockfish pass for "how else could this go?".

Long context answers what *did* happen from the stored review; it cannot answer
what *would* happen, because a ply the player never played was never analysed.
That is the one job of this module: ask the engine, on a tight budget, for a few
alternative continuations from a position and hand back SAN lines.

Everything here degrades to "no alternatives" rather than raising — a coach
answer must still stand on the stored facts when there is no engine to reach.
"""

from __future__ import annotations

from dataclasses import dataclass

import chess

from app.core.telemetry import engine_timer, record_engine_unavailable
from app.engine.factory import open_stockfish_provider
from app.engine.provider import AnalyseRequest
from app.engine.stockfish import StockfishUnavailableError
from app.games.domain import Color
from app.games.errors import EngineUnavailableError

# Deliberately shallower/shorter than a review pass: this is an on-demand
# illustration for one position, not a re-analysis of the game.
WHATIF_DEPTH = 12
WHATIF_MULTIPV = 3
WHATIF_TIME_MS = 800


@dataclass(frozen=True)
class AltLine:
    """One alternative continuation, spoken from the hero's point of view."""

    san: str  # SAN of the first move (what to play instead)
    uci: str
    score_cp_hero: int  # centipawns from the hero's perspective
    mate_in_hero: int | None  # signed moves to mate, + favoring the hero
    pv_san: tuple[str, ...]  # the continuation in SAN, hero move first
    pv_uci: tuple[str, ...] = ()  # the same continuation in raw UCI, for board walks


def _for_color(hero: str) -> Color:
    return Color.WHITE if hero == "w" else Color.BLACK


def _to_san(fen: str, pv: tuple[str, ...], limit: int = 4) -> tuple[str, ...]:
    """Replay a UCI principal variation into SAN, stopping at the first illegality.

    The engine reports raw coordinates; a coach speaks SAN, and a line that stops
    being legal halfway (a stale cached FEN) is better truncated than fabricated.
    """
    try:
        board = chess.Board(fen)
    except (ValueError, KeyError):
        return ()
    sans: list[str] = []
    for uci in pv[:limit]:
        try:
            move = chess.Move.from_uci(uci)
        except ValueError:
            break
        if move not in board.legal_moves:
            break
        sans.append(board.san(move))
        board.push(move)
    return tuple(sans)


def alternative_lines(fen: str, hero: str, *, limit: int = WHATIF_MULTIPV) -> list[AltLine]:
    """Ranked alternative moves for ``hero`` in ``fen``; empty when no engine.

    The engine always scores from the side to move; when the hero is not the one
    to move the lines are flipped so a positive number still means "good for you".
    """
    try:
        board = chess.Board(fen)
    except (ValueError, KeyError):
        return []
    if board.is_game_over() or not board.piece_map():
        return []

    hero_is_white = hero != "b"
    side_is_white = board.turn == chess.WHITE
    from_mover = side_is_white == hero_is_white

    try:
        with open_stockfish_provider(for_review=False) as provider, engine_timer(provider.name):
            result = provider.analyse(
                AnalyseRequest(
                    fen=fen,
                    depth=WHATIF_DEPTH,
                    multipv=WHATIF_MULTIPV,
                    max_time_ms=WHATIF_TIME_MS,
                    for_color=_for_color(hero),
                )
            )
    except (StockfishUnavailableError, EngineUnavailableError):
        # The answer degrades to "no alternatives" offline, but the outage is
        # still an outage: count it (MON-004) before swallowing it.
        record_engine_unavailable()
        return []

    lines: list[AltLine] = []
    for line in result.lines[:limit]:
        sans = _to_san(fen, line.pv)
        if not sans:
            continue
        score = line.score_cp if from_mover else -line.score_cp
        mate = line.mate_in if from_mover else (-line.mate_in if line.mate_in is not None else None)
        lines.append(
            AltLine(
                san=sans[0],
                uci=line.move,
                score_cp_hero=score,
                mate_in_hero=mate,
                pv_san=sans,
                pv_uci=tuple(line.pv),
            )
        )
    return lines


def lines_to_text(lines: list[AltLine], hero: str) -> str:
    """Render alternatives as short coach-readable SAN strings."""
    if not lines:
        return ""
    side = "Black" if hero == "b" else "White"
    parts: list[str] = []
    for line in lines:
        continuation = " ".join(line.pv_san)
        if line.mate_in_hero is not None:
            verdict = "forces mate"
        else:
            verdict = f"({line.score_cp_hero / 100:+.2f} for {side})"
        parts.append(f"{continuation} {verdict}")
    return "; ".join(parts)
