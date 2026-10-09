"""Versioned benchmark position suite (BEN-009).

Small, stable, hand-picked positions covering openings, tactics, and
endgames. Versioned so results stay comparable across engine changes.
"""

BENCHMARK_SUITE_VERSION = "v1"

# (fen, description)
BENCHMARK_POSITIONS: tuple[tuple[str, str], ...] = (
    (
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        "starting position",
    ),
    (
        "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
        "italian opening",
    ),
    (
        "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq c6 0 2",
        "sicilian opening",
    ),
    (
        "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
        "giuoco piano middlegame",
    ),
    (
        "r2qk2r/ppp1bppp/2n2n2/3pp3/3PP3/2N2N2/PPP1BPPP/R2QK2R w KQkq - 0 8",
        "central tension",
    ),
    (
        "2rr3k/pp3ppp/2n2n2/3p4/3P4/2N2N2/PP2BPPP/R2Q1RK1 w - - 0 14",
        "hanging pawns structure",
    ),
    (
        "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 5",
        "tactical pin on f7",
    ),
    (
        "3r2k1/pp3ppp/2n2n2/3p4/3P1B2/2N2N2/PP3PPP/R2Q1RK1 w - - 0 16",
        "bishop vs knight ending edge",
    ),
    (
        "8/5pk1/5p1p/8/8/3K4/5PPP/8 w - - 0 1",
        "king and pawn endgame",
    ),
    (
        "6k1/5ppp/8/8/8/8/5PPP/4R1K1 w - - 0 1",
        "rook endgame lucena-adjacent",
    ),
    (
        "r1bq1rk1/pp1bpppp/2n2n2/2p1P3/2B1P3/2N2N2/PPP2PPP/R1BQ1RK1 w - - 0 8",
        "isolated queen pawn",
    ),
    (
        "rnbqkb1r/pp2pppp/5n2/3p4/3P1B2/3B1P2/PPP3PP/RN1QK2R b KQkq - 0 6",
        "london system structure",
    ),
)


def get_suite() -> tuple[tuple[str, str], ...]:
    """Return the versioned benchmark suite (BEN-009)."""
    return BENCHMARK_POSITIONS
