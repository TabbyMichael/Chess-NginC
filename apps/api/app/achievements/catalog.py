"""Achievement catalog (ACH-001/ACH-002).

A pure, declarative list: every achievement names one statistic from
`app.achievements.stats` and the value that statistic must reach. No DB, no
HTTP — unlocking is a comparison against the player's current stats, so the
catalog can grow without migrations and the frontend can show exact progress
for locked achievements.

Ladders are generated from (family, thresholds) so a few dozen lines describe
hundreds of achievements; titles use roman numerals ("Pawn Storm IV") with
hand-named overrides for the steps worth a punchier word.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

MIN_CATALOG_SIZE = 200  # the product requirement: more than 200 achievements


class Tier(StrEnum):
    """Rarity bands, derived from how deep in a ladder an achievement sits."""

    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    DIAMOND = "diamond"
    LEGENDARY = "legendary"


@dataclass(frozen=True)
class Achievement:
    """One unlockable achievement."""

    key: str
    title: str
    description: str
    metric: str  # stat name (see app.achievements.stats.PlayerStats)
    threshold: int  # unlocked when stats[metric] >= threshold
    tier: Tier
    group: str  # ladder family, for gallery filtering


@dataclass(frozen=True)
class Ladder:
    """A family of threshold milestones over one stat."""

    metric: str
    group: str
    family: str  # title base, e.g. 'Pawn Storm'
    noun: str  # description tail, e.g. 'moves played'
    thresholds: tuple[int, ...]
    flavors: dict[int, str] | None = None  # threshold -> hand-written title


_ROMAN = (
    "I",
    "II",
    "III",
    "IV",
    "V",
    "VI",
    "VII",
    "VIII",
    "IX",
    "X",
    "XI",
    "XII",
    "XIII",
    "XIV",
    "XV",
    "XVI",
    "XVII",
    "XVIII",
    "XIX",
    "XX",
)


def _tier(index: int, count: int) -> Tier:
    """Spread a ladder's steps evenly across the five rarity bands."""
    if count <= 1:
        return Tier.BRONZE
    position = index / (count - 1)
    for bound, tier in (
        (0.20, Tier.BRONZE),
        (0.45, Tier.SILVER),
        (0.70, Tier.GOLD),
        (0.90, Tier.DIAMOND),
    ):
        if position <= bound:
            return tier
    return Tier.LEGENDARY


def _build(ladder: Ladder) -> list[Achievement]:
    count = len(ladder.thresholds)
    out: list[Achievement] = []
    for index, threshold in enumerate(ladder.thresholds):
        title = (ladder.flavors or {}).get(threshold) or f"{ladder.family} {_ROMAN[index]}"
        out.append(
            Achievement(
                key=f"{ladder.metric}-{threshold}",
                title=title,
                description=f"{threshold} {ladder.noun}.",
                metric=ladder.metric,
                threshold=threshold,
                tier=_tier(index, count),
                group=ladder.group,
            )
        )
    return out


LADDERS: tuple[Ladder, ...] = (
    # --- Volume of play -----------------------------------------------------
    Ladder(
        "moves_total",
        "play",
        "Turn Taker",
        "moves played across your games",
        (
            1,
            5,
            10,
            25,
            50,
            100,
            150,
            200,
            300,
            400,
            500,
            750,
            1000,
            1500,
            2000,
            3000,
            5000,
            7500,
            10000,
            15000,
        ),
        {1: "First Move", 100: "Centurion", 1000: "Kilocounter"},
    ),
    Ladder(
        "games_total",
        "play",
        "Contender",
        "games started",
        (1, 2, 3, 5, 10, 20, 30, 50, 75, 100, 150, 200, 300, 500),
        {1: "First Game", 100: "Century Club"},
    ),
    Ladder(
        "games_completed",
        "play",
        "Finisher",
        "games played to the end",
        (1, 3, 5, 10, 20, 30, 50, 75, 100, 150, 200, 300),
        {1: "Dust Off"},
    ),
    # --- Results ------------------------------------------------------------
    Ladder(
        "wins",
        "result",
        "Victor",
        "games won",
        (1, 2, 3, 5, 8, 10, 15, 20, 30, 40, 50, 75, 100, 150, 200, 300),
        {1: "First Blood", 100: "Century Champion"},
    ),
    Ladder(
        "losses",
        "result",
        "Resilient",
        "games lost and played on",
        (1, 5, 10, 25, 50, 100, 150, 200),
        {1: "Learning Experience"},
    ),
    Ladder(
        "draws",
        "result",
        "Equilibrist",
        "games drawn",
        (1, 3, 5, 10, 20, 35, 50, 100),
        {1: "Handshake"},
    ),
    Ladder(
        "points",
        "points",
        "Point Collector",
        "lifetime points",
        (1, 10, 25, 50, 100, 200, 350, 500, 1000, 1750, 2500, 4000, 6000, 10000, 17500, 25000),
        {1: "Pocket Change", 1000: "Point Thousand"},
    ),
    # --- Tactics on the board ------------------------------------------------
    Ladder(
        "captures",
        "tactics",
        "Harvester",
        "capturing moves",
        (1, 3, 5, 10, 20, 35, 50, 75, 100, 150, 200, 300, 500, 750),
        {1: "First Capture"},
    ),
    Ladder(
        "checks",
        "tactics",
        "Agitator",
        "checks delivered",
        (1, 5, 10, 20, 35, 50, 100, 150, 250, 400),
        {1: "Hello!"},
    ),
    Ladder(
        "checkmates",
        "tactics",
        "Closer",
        "checkmates delivered",
        (1, 3, 5, 10, 20, 35, 50, 100, 150, 250),
        {1: "Checkmate!"},
    ),
    Ladder(
        "castles",
        "tactics",
        "Castler",
        "castlings",
        (1, 2, 5, 10, 20, 35, 50, 100),
        {1: "Safe King"},
    ),
    Ladder(
        "promotions",
        "tactics",
        "Overachiever",
        "pawn promotions",
        (1, 2, 5, 10, 20, 35, 50, 100),
        {1: "New Queen"},
    ),
    # --- Piece mastery -------------------------------------------------------
    Ladder(
        "pawn_moves",
        "pieces",
        "Pawn Pusher",
        "pawn moves",
        (1, 10, 25, 50, 100, 200, 350, 500, 750, 1000),
    ),
    Ladder(
        "knight_moves",
        "pieces",
        "Horseman",
        "knight moves",
        (1, 10, 25, 50, 100, 200, 350, 500, 750, 1000),
    ),
    Ladder(
        "bishop_moves",
        "pieces",
        "Diagonalist",
        "bishop moves",
        (1, 10, 25, 50, 100, 200, 350, 500, 750, 1000),
    ),
    Ladder(
        "rook_moves",
        "pieces",
        "File Controller",
        "rook moves",
        (1, 10, 25, 50, 100, 200, 350, 500, 750, 1000),
    ),
    Ladder(
        "queen_moves",
        "pieces",
        "Heavy Artillery",
        "queen moves",
        (1, 10, 25, 50, 100, 200, 350, 500, 750, 1000),
    ),
    Ladder(
        "king_moves",
        "pieces",
        "Adventurous Monarch",
        "king moves",
        (1, 5, 10, 25, 50, 100, 200, 350),
    ),
    Ladder(
        "piece_variety",
        "pieces",
        "Well Rounded",
        "different piece types moved",
        (1, 2, 3, 4, 5, 6),
        {6: "Full Arsenal"},
    ),
    # --- Endurance -----------------------------------------------------------
    Ladder(
        "longest_game",
        "endurance",
        "Marathoner",
        "plies in your longest game",
        (20, 30, 40, 60, 80, 100, 120, 150),
        {20: "Sticking Around"},
    ),
    Ladder(
        "active_days",
        "habit",
        "Regular",
        "days with recorded play",
        (1, 2, 3, 5, 7, 14, 21, 30, 60, 100, 180, 365),
        {1: "Day One", 365: "Full Circle"},
    ),
    Ladder(
        "best_streak_days",
        "habit",
        "Streak Keeper",
        "consecutive days played",
        (2, 3, 5, 7, 14, 30, 60, 100),
        {7: "Week Warrior"},
    ),
    # --- Review & improvement --------------------------------------------------
    Ladder(
        "reviews_completed",
        "review",
        "Student",
        "games reviewed with the engine",
        (1, 2, 3, 5, 10, 20, 35, 50, 75, 100),
        {1: "Postmortem"},
    ),
    Ladder(
        "best_accuracy",
        "review",
        "Precision",
        "accuracy score in a reviewed game",
        (50, 60, 70, 75, 80, 85, 90, 95),
        {95: "Machine-like"},
    ),
    Ladder(
        "brilliant_found",
        "review",
        "Spark Seeker",
        "brilliant moves found in reviews",
        (1, 2, 5, 10, 20, 35, 50, 100),
        {1: "First Sparkle"},
    ),
    Ladder(
        "blunder_free_games",
        "review",
        "Clean Player",
        "reviewed games without a single blunder",
        (1, 2, 5, 10, 20, 35),
        {1: "No Regrets"},
    ),
    Ladder(
        "engine_moves",
        "engine",
        "Sparring Partner",
        "engine moves played against you",
        (1, 5, 10, 25, 50, 100, 200, 350),
        {1: "Met the Machine"},
    ),
    # --- Modes ---------------------------------------------------------------
    Ladder(
        "computer_games",
        "mode",
        "Bot Buster",
        "games against the engine",
        (1, 3, 5, 10, 20, 35, 50, 100),
        {1: "Man vs Machine"},
    ),
    Ladder(
        "online_games",
        "mode",
        "Net Player",
        "online games against humans",
        (1, 2, 3, 5, 10, 20, 35, 50, 100, 150),
        {1: "First Match"},
    ),
    Ladder(
        "local_games",
        "mode",
        "Over the Board",
        "local hot-seat games",
        (1, 3, 5, 10, 20, 35),
        {1: "Same Table"},
    ),
    Ladder(
        "online_wins",
        "mode",
        "Ladder Legend",
        "online games won",
        (1, 2, 3, 5, 10, 20, 35, 50),
        {1: "First Online Win"},
    ),
    Ladder(
        "computer_wins",
        "mode",
        "Giant Slayer",
        "games won against the engine",
        (1, 3, 5, 10, 20, 35, 50, 100),
        {1: "Checkmated the Bot"},
    ),
    # --- Training & drills ---------------------------------------------------
    Ladder(
        "puzzles_solved",
        "training",
        "Puzzle Solver",
        "drills and puzzles solved",
        (1, 5, 10, 20, 35, 50, 75, 100, 150, 200, 300),
        {1: "First Solve"},
    ),
    Ladder(
        "drill_streak",
        "training",
        "Sharp Streak",
        "puzzles solved in a row",
        (1, 3, 5, 10, 20, 30),
        {1: "Warming Up", 10: "On a Roll"},
    ),
)


def _build_catalog() -> tuple[Achievement, ...]:
    entries: list[Achievement] = []
    for ladder in LADDERS:
        entries.extend(_build(ladder))
    return tuple(entries)


CATALOG: tuple[Achievement, ...] = _build_catalog()

_BY_KEY: dict[str, Achievement] = {a.key: a for a in CATALOG}
assert len(_BY_KEY) == len(CATALOG), "achievement keys must be unique"
assert len(CATALOG) >= MIN_CATALOG_SIZE, "the catalog must hold 200+ achievements"


def achievement_by_key(key: str) -> Achievement | None:
    """Look one achievement up by its stable key."""
    return _BY_KEY.get(key)


def metric_names() -> set[str]:
    """Every stat the catalog depends on (used to validate the stats layer)."""
    return {a.metric for a in CATALOG}
