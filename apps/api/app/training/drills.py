"""The drill catalog: hand-written core puzzles plus a generated, verified bulk.

Teaching needs a sentence of prose per idea, which is why the ``CURATED``
tuple — one crisp example per skill — is authored by hand. The bulk of the
hundreds of positions on the Learn page is built by :mod:`app.training.generate`
from geometric templates and then filtered through ``verify.verify()``, the same
python-chess prover the curated drills pass through (re-run in
``scripts/check_drills.py``). So ``DRILLS = CURATED + generated``: the hand-written
set first (the ramp and the tests key off the curated ``mate-1`` opening every
mate theme), then several hundred machine-verified additions. An unsound or
mislabelled position — hand-written or generated — fails the build rather than
quietly mis-teaching a player.

Each theme is one skill card. `level` orders the drills inside a skill from
easy to hard; the training ramp picks the level the player is ready for.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Card title per theme (drills sharing a theme are one skill on the Learn page).
THEME_NAMES = {
    "mate": "Checkmate",
    "hanging": "Hanging Pieces",
    "fork": "Forks",
    "pin": "Pins",
    "backrank": "Back-Rank Safety",
    "endgame": "Endgames",
    "skewer": "Skewers",
    "discovered": "Discovered Attacks",
}

THEME_ORDER = (
    "mate",
    "hanging",
    "fork",
    "pin",
    "skewer",
    "discovered",
    "backrank",
    "endgame",
)


@dataclass(frozen=True)
class Drill:
    """One verified puzzle: a position, its answer, and the teaching line.

    The three trailing fields exist so a puzzle mined from a player's own game
    (``source='game'``) is carried by the same type as a curated drill: its
    ``theme`` is ``'missed'`` and ``game_id``/``ply`` point back at the review.
    Curated drills leave them at the defaults.
    """

    key: str  # stable id, doubles as the point slot (f"drill:{key}")
    theme: str  # mate|hanging|fork|pin|backrank|endgame ('missed' for mined)
    name: str  # skill title shown on the card
    level: int  # 1..3 within the theme
    fen: str
    solution: str  # uci
    alternatives: tuple[str, ...] = field(default_factory=tuple)  # other accepted ucis
    # Forced continuation, opponent replies included.
    line: tuple[str, ...] = field(default_factory=tuple)
    prompt: str = ""
    why: str = ""
    source: str = "drill"  # 'drill' (curated) | 'game' (mined from the player's reviews)
    game_id: int | None = None  # set only for mined puzzles
    ply: int | None = None  # set only for mined puzzles


def _mate(key: str, level: int, fen: str, solution: str, why: str) -> Drill:
    return Drill(
        key=key,
        theme="mate",
        name=THEME_NAMES["mate"],
        level=level,
        fen=fen,
        solution=solution,
        prompt="It is mate in one. Find it.",
        why=why,
    )


CURATED: tuple[Drill, ...] = (
    # --- Checkmate ----------------------------------------------------------
    _mate(
        "mate-1",
        1,
        "6k1/5ppp/8/8/8/8/8/R6K w - - 0 1",
        "a1a8",
        "The rook slides to the eighth rank where the king's own pawns "
        "wall it in — the classic back-rank mate.",
    ),
    _mate(
        "mate-2",
        2,
        "7k/8/6K1/8/8/8/8/4Q3 w - - 0 1",
        "e1e8",
        "The queen checks along the rank while your king already covers the "
        "escape squares. Mate needs both: a check plus a cut-off.",
    ),
    _mate(
        "mate-3",
        3,
        "6rk/6pp/8/4N3/8/8/8/K7 w - - 0 1",
        "e5f7",
        "A knight on f7 checks a king smothered by its own rook and pawns — "
        "no escape square, nothing that can capture. The smothered mate.",
    ),
    # --- Hanging pieces -----------------------------------------------------
    Drill(
        key="hanging-1",
        theme="hanging",
        name=THEME_NAMES["hanging"],
        level=1,
        fen="4k3/8/8/2q5/8/2R5/8/4K3 w - - 0 1",
        solution="c3c5",
        prompt="Find the move that wins material.",
        why="The black queen stands undefended. A piece nobody protects is "
        "'hanging' — just take it. Here the rook collects a whole queen for free.",
    ),
    Drill(
        key="hanging-2",
        theme="hanging",
        name=THEME_NAMES["hanging"],
        level=2,
        fen="4k3/8/8/1r6/3N4/8/8/4K3 w - - 0 1",
        solution="d4b5",
        prompt="Find the move that wins material.",
        why="Scan for the pieces no one is watching. The rook on b5 has no "
        "defender, so the knight simply lifts it off the board.",
    ),
    Drill(
        key="hanging-3",
        theme="hanging",
        name=THEME_NAMES["hanging"],
        level=3,
        fen="4k3/8/8/8/8/3q4/4P3/4K3 w - - 0 1",
        solution="e2d3",
        prompt="Find the move that wins material.",
        why="Even the humblest pawn can take a prize. The black queen wandered "
        "onto d3 where the e2 pawn attacks it — a pawn capture wins the queen.",
    ),
    # --- Forks --------------------------------------------------------------
    Drill(
        key="fork-1",
        theme="fork",
        name=THEME_NAMES["fork"],
        level=1,
        fen="3r3k/8/8/4N3/8/8/8/7K w - - 0 1",
        solution="e5f7",
        line=("h8g8", "f7d8"),
        prompt="One knight, two targets. Win the rook.",
        why="The knight jumps to f7 with check, attacking the king and the "
        "rook at once. Black must move out of check, then the knight takes the "
        "rook. That double hit is a fork.",
    ),
    Drill(
        key="fork-2",
        theme="fork",
        name=THEME_NAMES["fork"],
        level=2,
        fen="k3r3/8/8/1N6/8/8/8/6K1 w - - 0 1",
        solution="b5c7",
        line=("a8b8", "c7e8"),
        prompt="One knight, two targets. Win the rook.",
        why="Nc7 checks the king on a8 while also eyeing the rook on e8. A "
        "fork only works when the forked piece is more valuable than a tempo — "
        "here the king must step aside and the rook falls.",
    ),
    Drill(
        key="fork-3",
        theme="fork",
        name=THEME_NAMES["fork"],
        level=3,
        fen="2q3k1/8/8/3N4/8/8/8/6K1 w - - 0 1",
        solution="d5e7",
        line=("g8h8", "e7c8"),
        prompt="One knight, two targets. Win the queen.",
        why="The royal fork: Ne7 checks the king and attacks the queen on c8 "
        "in the same move. Black answers the check, then the knight scoops up "
        "the queen. King + queen on one square is the biggest fork there is.",
    ),
    # --- Pins ---------------------------------------------------------------
    Drill(
        key="pin-1",
        theme="pin",
        name=THEME_NAMES["pin"],
        level=1,
        fen="4k3/8/8/4b3/8/5N2/8/4KR2 w - - 0 1",
        solution="f3e5",
        prompt="A piece frozen to the king. Take it.",
        why="The rook on e1 pins the bishop on e5 to the black king, so the "
        "bishop cannot legally move off the e-file. A pinned piece defends "
        "nothing — the knight simply captures it.",
    ),
    Drill(
        key="pin-2",
        theme="pin",
        name=THEME_NAMES["pin"],
        level=2,
        fen="r3k3/8/2n5/1B1P4/8/8/8/R3K3 w - - 0 1",
        solution="d5c6",
        prompt="A piece frozen to the king. Take it.",
        why="The bishop on b5 pins the knight on c6 to the king on e8. The "
        "knight cannot step sideways to recapture, so the pawn takes it for "
        "free. Pinned pieces are sitting ducks.",
    ),
    Drill(
        key="pin-3",
        theme="pin",
        name=THEME_NAMES["pin"],
        level=3,
        fen="r2k4/8/8/3n4/4P3/8/8/3R3K w - - 0 1",
        solution="e4d5",
        prompt="A piece frozen to the king. Take it.",
        why="The rook on d1 pins the knight on d5 to the king on d8. Knights "
        "never move along a file anyway, so the pin costs it all its mobility — "
        "the e4 pawn wins the knight.",
    ),
    # --- Back-rank safety ---------------------------------------------------
    Drill(
        key="backrank-1",
        theme="backrank",
        name=THEME_NAMES["backrank"],
        level=1,
        fen="k7/8/8/4r3/8/6n1/5PPP/6K1 w - - 0 1",
        solution="h2h3",
        prompt="Your king is about to be mated on the back rank. Give it air.",
        why="Black threatens Re1#. The fix is 'luft': push a rook pawn one step "
        "so the king gets an escape square on the second rank. Here h3 saves "
        "the game before the mate can happen.",
    ),
    Drill(
        key="backrank-2",
        theme="backrank",
        name=THEME_NAMES["backrank"],
        level=2,
        fen="7k/5ppp/8/8/8/6N1/5PPP/R5K1 b - - 0 1",
        solution="h7h6",
        prompt="White is lining up a back-rank mate. Make an escape square.",
        why="White's rook and knight aim at g8/h8. The same idea in reverse: "
        "as Black, h6 cracks open an escape square on h7 so Ra8 can no longer "
        "mate. King safety is a move before the mate, not after.",
    ),
    Drill(
        key="backrank-3",
        theme="backrank",
        name=THEME_NAMES["backrank"],
        level=3,
        fen="k7/8/8/r7/8/6n1/5PPP/6K1 w - - 0 1",
        solution="h2h3",
        prompt="The rook wants the eighth rank. Create luft.",
        why="Here the black rook is ready to drop to a1#. Note the escape is "
        "still one pawn push — but you had to see the threat a full move early. "
        "Back-rank danger is about counting who reaches the rank first.",
    ),
    # --- Endgames -----------------------------------------------------------
    Drill(
        key="endgame-1",
        theme="endgame",
        name=THEME_NAMES["endgame"],
        level=1,
        fen="7k/4P3/8/8/8/8/8/4K1R1 w - - 0 1",
        solution="e7e8q",
        prompt="The pawn reaches the last rank. What does it become?",
        why="A pawn that makes it to the eighth rank promotes to a queen — "
        "800 extra centipawns in one move. When the road is clear, push it home.",
    ),
    Drill(
        key="endgame-2",
        theme="endgame",
        name=THEME_NAMES["endgame"],
        level=2,
        fen="4n2k/3P4/8/8/8/8/8/4K3 w - - 0 1",
        solution="d7e8q",
        prompt="Promote, capturing what blocks the way.",
        why="The pawn captures the knight on e8 and promotes on the same move. "
        "A promotion with capture both removes a defender and turns a pawn into "
        "a queen — the double purpose that ends most pawn races.",
    ),
    Drill(
        key="endgame-3",
        theme="endgame",
        name=THEME_NAMES["endgame"],
        level=3,
        fen="k7/8/7P/8/8/8/8/4K1R1 w - - 0 1",
        solution="h6h7",
        line=("a8b8", "h7h8q"),
        prompt="Escort the passer: push, then queen.",
        why="With the far king unable to reach, the pawn pushes to h7 and "
        "promotes next move. In pawn endings an outside passed pawn that the "
        "enemy king is too far to stop is already a queen on layaway.",
    ),
)

# Generated, per-(theme, level) capped catalog appended after the curated set.
# Imported here at the bottom so ``generate`` can rely on ``Drill``/``THEME_NAMES``
# above without a circular-import cycle at module load.
from app.training.generate import generated_drills  # noqa: E402

DRILLS: tuple[Drill, ...] = CURATED + generated_drills()
