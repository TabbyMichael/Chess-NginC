"""Offline opening book (COA-004): position lookups against the generated CC0
extract of lichess-org/chess-openings.

Names are asserted *from the dataset*, not from memory, so a regeneration that
picks up an upstream rename shows up here as a deliberate diff rather than a
mystery mismatch.
"""

import importlib.util
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import chess
import pytest

from app.openings.book import Opening, book_size, lookup_epd, opening_after
from app.openings.book_data import BOOK_TSV

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

RUY_LOPEZ_EP = "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq -"

# The Queen's Indian row whose PGN line ends in `Bb4+`. The `+` must have been
# replayable before the position was keyed, or this row would be PGN text.
BB4_PLUS_EPD = "rn1qk2r/pbpp1ppp/1p2pn2/8/1bPP4/4PN2/PP1N1PPP/R1BQKB1R w KQkq -"

GENERATOR = Path(__file__).resolve().parents[1] / "scripts" / "gen_opening_book.py"


@pytest.fixture(scope="module")
def gen() -> ModuleType:
    """`scripts/gen_opening_book.py` loaded by path: a build tool, not a package,
    and its normalisation rules are exactly what the lookups above depend on.
    Importing it makes no network call — `main()` only runs as a script.
    """
    spec = importlib.util.spec_from_file_location("gen_opening_book", GENERATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _epd_after(*sans: str) -> str:
    board = chess.Board(START_FEN)
    for san in sans:
        board.push_san(san)
    return board.epd()


class TestBookData:
    def test_book_is_loaded_and_not_truncated(self) -> None:
        # A partial download would otherwise pass every lookup test silently.
        assert book_size() >= 3000

    def test_keys_are_positions_not_pgn_text(self) -> None:
        for line in BOOK_TSV.strip().splitlines():
            fields = line.split("\t")
            assert len(fields) == 3, fields
            epd, eco, name = fields
            assert len(epd.split()) == 4, epd
            assert not any(char in epd for char in "+#*!?$"), epd
            assert 1 <= len(eco) <= 3 and eco.isalnum(), eco
            assert name.strip() == name
            chess.Board(f"{epd} 0 1")  # a key chess itself accepts as a position

    def test_rows_are_keyed_uniquely(self) -> None:
        keys = [line.split("\t")[0] for line in BOOK_TSV.strip().splitlines()]
        assert len(keys) == len(set(keys)) == book_size()


class TestLookup:
    @pytest.mark.parametrize(
        ("sans", "eco", "name"),
        [
            (("e4",), "B00", "King's Pawn Game"),
            (("e4", "e5", "Nf3", "Nc6", "Bb5"), "C60", "Ruy Lopez"),
            (("e4", "e6", "d4", "d5"), "C00", "French Defense"),
            (
                ("e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6"),
                "B90",
                "Sicilian Defense: Najdorf Variation",
            ),
            (("d4", "Nf6", "c4", "e6", "Nc3", "Bb4"), "E20", "Nimzo-Indian Defense"),
        ],
    )
    def test_known_theory_positions(self, sans: tuple[str, ...], eco: str, name: str) -> None:
        found = lookup_epd(_epd_after(*sans))
        assert found is not None
        assert (found.eco, found.name) == (eco, name)

    def test_castling_is_keyed_by_the_castled_position(self) -> None:
        # The Ruy Lopez row that reaches this position writes `0-0`/`O-O`; both
        # have to land on the same EPD as a board that actually castled.
        found = lookup_epd(_epd_after("e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "Nf6", "O-O"))
        assert found is not None
        assert (found.eco, found.name) == ("C78", "Ruy Lopez: Morphy Defense")

    def test_check_suffix_does_not_break_a_key(self) -> None:
        found = lookup_epd(BB4_PLUS_EPD)
        assert found is not None
        assert found.eco == "E14"
        assert "Bb4+" in found.name

    def test_unknown_position_returns_none(self) -> None:
        assert lookup_epd(chess.Board(START_FEN).epd()) is None
        assert lookup_epd("8/8/8/8/8/8/8/8 w - - 0 1") is None

    def test_counters_and_en_passant_do_not_change_the_key(self) -> None:
        board = chess.Board(START_FEN)
        board.push_san("e4")  # double push: an ep square and fresh counters
        keyed = board.epd()
        # The same position recorded with a live ep square and different clocks.
        clocked = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 41 23"
        assert chess.Board(clocked).epd() == keyed
        assert lookup_epd(keyed) is not None


class TestOpeningAfter:
    def test_names_the_landing_position(self) -> None:
        board = chess.Board(START_FEN)
        for san in ("e4", "e5", "Nf3", "Nc6"):
            board.push_san(san)
        found = opening_after(board.fen(), "f1b5")
        assert found is not None
        assert found.eco == "C60"

    def test_illegal_or_unparseable_input_is_not_an_error(self) -> None:
        # A stored review is read-time annotated: one odd ply must not raise.
        assert opening_after("not a fen", "e2e4") is None
        assert opening_after(START_FEN, "e2e9") is None
        assert opening_after(START_FEN, "") is None


class TestOpeningModel:
    def test_family_is_the_name_before_the_first_variation(self) -> None:
        opening = Opening(eco="B90", name="Sicilian Defense: Najdorf Variation, English Attack")
        assert opening.family == "Sicilian Defense"

    def test_family_of_a_bare_name_is_the_name(self) -> None:
        assert Opening(eco="C60", name="Ruy Lopez").family == "Ruy Lopez"

    def test_label_is_the_compact_ui_form(self) -> None:
        assert Opening(eco="C60", name="Ruy Lopez").label == "C60 Ruy Lopez"


class TestBookGeneration:
    """The normalisation the committed book depends on (``scripts/``)."""

    def test_move_numbers_and_results_are_dropped(self, gen: ModuleType) -> None:
        assert gen.san_tokens("1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 1/2-1/2") == [
            "e4",
            "c5",
            "Nf3",
            "d6",
            "d4",
            "cxd4",
            "Nxd4",
        ]

    def test_comments_variations_and_nags_are_dropped(self, gen: ModuleType) -> None:
        assert gen.san_tokens("1. e4 {classical} (1. d4 d5) 1... c5 $1 2. Nf3 *") == [
            "e4",
            "c5",
            "Nf3",
        ]

    def test_numerical_castling_becomes_o_o(self, gen: ModuleType) -> None:
        assert gen.san_tokens("1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. 0-0 Be7 0-1") == [
            "e4",
            "e5",
            "Nf3",
            "Nc6",
            "Bb5",
            "a6",
            "Ba4",
            "Nf6",
            "O-O",
            "Be7",
        ]
        assert gen.san_tokens("1. d4 d5 2. Bf4 Bf5 3. e3 e6 4. Bd3 Bd6 5. 0-0-0 0-0")[-2:] == [
            "O-O-O",
            "O-O",
        ]

    def test_a_full_pgn_line_replays_to_the_same_position(self, gen: ModuleType) -> None:
        # What the generator writes must equal what a real board reaches: the
        # row "1.e4 e5 2.Nf3 Nc6 3.Bb5+ a6 4.Ba4 Nf6 5.O-O Be7 1-0" keys C91.
        line = "1. e4 e5 2. Nf3 Nc6 3. Bb5+ a6 4. Ba4 Nf6 5. O-O Be7 1-0"
        assert gen.position_epd(gen.san_tokens(line)) == _epd_after(
            "e4", "e5", "Nf3", "Nc6", "Bb5", "a6", "Ba4", "Nf6", "O-O", "Be7"
        )

    def test_illegal_line_yields_no_position(self, gen: ModuleType) -> None:
        assert gen.position_epd(gen.san_tokens("1. e4 e5 2. Xz4")) is None

    def test_duplicate_position_keeps_the_most_specific_name(
        self, gen: ModuleType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_rows() -> Iterator[tuple[str, str, str]]:
            yield RUY_LOPEZ_EP, "C60", "Ruy Lopez"
            yield RUY_LOPEZ_EP, "C78", "Ruy Lopez: Morphy Defense"
            yield RUY_LOPEZ_EP, "C60", "Ruy Lopez: Deferred"

        monkeypatch.setattr(gen, "rows", fake_rows)
        assert gen.build_book()[RUY_LOPEZ_EP] == ("C78", "Ruy Lopez: Morphy Defense")

    def test_specificity_ranks_variations_then_length(self, gen: ModuleType) -> None:
        assert gen.specificity("Sicilian Defense: Najdorf Variation") > gen.specificity(
            "Sicilian Defense"
        )
        assert gen.specificity("French Defense: Advance, Best Line") > gen.specificity(
            "French Defense: Advance"
        )

    def test_a_truncated_book_is_refused(
        self, gen: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # The floor turns a partial download into a loud failure instead of a
        # committed book that quietly names nothing. Writing into a temp path
        # keeps the committed book untouched.
        out = tmp_path / "book_data.py"
        monkeypatch.setattr(gen, "OUTPUT", out)
        monkeypatch.setattr(gen, "build_book", lambda: {})
        with pytest.raises(SystemExit):
            gen.main()
        assert not out.exists()

    def test_the_carrier_module_round_trips(
        self, gen: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # The book ships as a Python module rather than a data file, so what is
        # written has to import back with the same rows.
        out = tmp_path / "book_data.py"
        monkeypatch.setattr(gen, "OUTPUT", out)
        book = {RUY_LOPEZ_EP: ("C60", "Ruy Lopez")}
        gen.emit(book)
        spec = importlib.util.spec_from_file_location("written_book", out)
        assert spec is not None and spec.loader is not None
        written = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(written)
        assert written.BOOK_TSV.strip().split("\t") == [RUY_LOPEZ_EP, "C60", "Ruy Lopez"]
