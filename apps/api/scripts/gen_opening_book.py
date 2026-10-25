"""Regenerate ``app/openings/book_data.py`` from the CC0 chess-openings dataset.

Run from ``apps/api`` with the project venv (it needs ``chess``):

    python scripts/gen_opening_book.py

Source: https://github.com/lichess-org/chess-openings -- "As a collection of
facts, this data set is in the public domain... released under the CC0 Public
Domain Dedication." The repo ships ``a.tsv``..``e.tsv`` with columns
``eco  name  pgn`` (SAN with move numbers); the published ``dist/`` output with
EPD keys is only a CI artifact, so we derive positions here by replaying the
lines.

Nothing at runtime or in CI touches the network: the generated module is
committed. A download failure therefore aborts loudly instead of writing a
truncated book.
"""

from __future__ import annotations

import re
import sys
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import chess

BASE_URL = "https://raw.githubusercontent.com/lichess-org/chess-openings/master/"
ECO_FILES = ("a.tsv", "b.tsv", "c.tsv", "d.tsv", "e.tsv")
GAME_RESULTS = frozenset({"1-0", "0-1", "1/2-1/2", "1/2-0", "0-1/2", "*"})
# Move numbers ("1.", "12...", "1...e5"): SAN never starts with a digit, so any
# run of digits followed by 1-3 dots is a numbered-move marker.
_MOVE_NUMBER = re.compile(r"\d+\.{1,3}")
_COMMENT = re.compile(r"\{[^}]*\}")
_VARIATION = re.compile(r"\([^)]*\)")
_NAG = re.compile(r"\$\d+")
OUTPUT = Path(__file__).resolve().parent.parent / "app" / "openings" / "book_data.py"


def fetch(filename: str) -> str:
    """Return one TSV body, aborting the whole run if the download fails."""
    url = BASE_URL + filename
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            return response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SystemExit(f"Could not download {url}: {exc}") from exc


def san_tokens(pgn: str) -> list[str]:
    """PGN move text to plain SAN tokens, ready for ``Board.push_san``.

    Drops comments, variation braces, NAGs, game results and move numbers, and
    maps ``0-0`` to the ``O-O`` spelling python-chess emits. The published data
    is already that clean; the normalisation keeps a future refresh from
    silently losing rows.
    """
    text = _VARIATION.sub(" ", _COMMENT.sub(" ", pgn))
    text = _NAG.sub(" ", _MOVE_NUMBER.sub(" ", text))
    tokens: list[str] = []
    for raw in text.split():
        if raw in GAME_RESULTS:
            continue
        token = raw.replace("0-0-0", "O-O-O").replace("0-0", "O-O")
        # Trailing annotation glyphs are noise for position lookup.
        token = token.rstrip("!?").strip(".")
        if token:
            tokens.append(token)
    return tokens


def position_epd(tokens: list[str]) -> str | None:
    """Replay a line from the start position; None when any token is illegal."""
    board = chess.Board()
    try:
        for token in tokens:
            board.push_san(token)
    except (ValueError, KeyError):
        return None
    return board.epd()


def rows() -> Iterator[tuple[str, str, str]]:
    """Yield ``(epd, eco, name)`` for every replayable line in the dataset."""
    for filename in ECO_FILES:
        for lineno, line in enumerate(fetch(filename).splitlines()[1:], start=2):
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) != 3:
                print(f"  {filename}:{lineno}: unexpected columns, skipped", file=sys.stderr)
                continue
            eco, name, pgn = (p.strip() for p in parts)
            epd = position_epd(san_tokens(pgn))
            if epd is None:
                print(f"  {filename}:{lineno}: illegal line skipped: {pgn}", file=sys.stderr)
                continue
            # Tabs and newlines would corrupt our own TSV carrier.
            safe_name = name.replace("\t", " ").replace("\n", " ").strip()
            yield epd, eco, safe_name


def specificity(name: str) -> tuple[int, int]:
    """Rank duplicate names for one position: most sub-variations, then longest."""
    return (name.count(":"), len(name))


def build_book() -> dict[str, tuple[str, str]]:
    """Position -> (eco, name), keeping the most specific name per position."""
    book: dict[str, tuple[str, str]] = {}
    for epd, eco, name in rows():
        current = book.get(epd)
        if current is None or specificity(name) > specificity(current[1]):
            book[epd] = (eco, name)
    return book


def emit(book: dict[str, tuple[str, str]]) -> None:
    lines = "\n".join(f"{epd}\t{eco}\t{name}" for epd, (eco, name) in sorted(book.items()))
    header = (
        '"""Generated opening book: position EPD -> (ECO, name) as TSV.\n\n'
        "DO NOT EDIT by hand -- regenerate with `python scripts/gen_opening_book.py`\n"
        "from `apps/api`. Source: https://github.com/lichess-org/chess-openings\n"
        f"(CC0 / public domain). Rows: {len(book)}.\n"
        '"""\n\n'
        "# fmt: off\n"
        "# ruff: noqa\n"
    )
    OUTPUT.write_text(f'{header}BOOK_TSV = """{lines}\n"""\n# fmt: on\n', encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(OUTPUT.parent.parent.parent)} ({len(book)} positions)")


def main() -> None:
    book = build_book()
    if len(book) < 1000:
        raise SystemExit(f"Refusing to write a truncated book ({len(book)} positions)")
    emit(book)


if __name__ == "__main__":
    main()
