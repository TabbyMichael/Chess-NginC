"""Offline opening identification (COA-004).

Names the theory position a ply lands on, from a generated extract of
https://github.com/lichess-org/chess-openings (CC0 / public domain, 3,865
positions). Refresh with `python scripts/gen_opening_book.py`.

Positions are keyed by EPD, which deliberately ignores the move counters and
the en-passant field, so the same theory position reached under a different
clock still matches. The dataset names a position only once it is *defined* by
theory; a ply that matches nothing is simply "out of book", which is why the
review annotation carries the deepest match forward instead of going blank.

Pure lookup: no HTTP, no database, no engine — the review service replays the
plies and asks this module what each position is called.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass

import chess

from app.openings.book_data import BOOK_TSV


@dataclass(frozen=True)
class Opening:
    """One named theory position."""

    eco: str
    name: str

    @property
    def family(self) -> str:
        """Top-level name before the first variation separator.

        ``Sicilian Defense: Najdorf Variation, English Attack`` -> ``Sicilian
        Defense``; used to group every ply that transposed inside one opening.
        """
        return self.name.split(":", 1)[0].strip()

    @property
    def label(self) -> str:
        """``C60 Ruy Lopez`` — the compact form the UI shows."""
        return f"{self.eco} {self.name}"


@functools.cache
def _book() -> dict[str, Opening]:
    """Parse the embedded TSV once per process."""
    book: dict[str, Opening] = {}
    for line in BOOK_TSV.strip().splitlines():
        fields = line.split("\t")
        if len(fields) != 3:
            continue
        epd, eco, name = fields
        book[epd] = Opening(eco=eco, name=name)
    return book


def book_size() -> int:
    """Positions loaded; a floor test guards against a truncated generation."""
    return len(_book())


def lookup_epd(epd: str) -> Opening | None:
    """Name for an EPD key, or None when the position is not book theory."""
    return _book().get(epd)


def opening_after(pre_fen: str, uci: str) -> Opening | None:
    """Name the position reached by playing ``uci`` from ``pre_fen``.

    Defensive by design: a review read must never fail because one stored ply
    is unparseable, so anything chess rejects returns None.
    """
    try:
        board = chess.Board(pre_fen)
        board.push(chess.Move.from_uci(uci))
    except (ValueError, KeyError):
        return None
    return lookup_epd(board.epd())
