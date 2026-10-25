"""Win expectancy model (ANL-004): the centipawn/mate score a review already
stores, turned into one 1..99 number the UI and the narrator can speak."""

import pytest

from app.engine.win_probability import MAX_PCT, MIN_PCT, win_pct


class TestWinPct:
    def test_level_position_is_a_coin_flip(self) -> None:
        assert win_pct(0) == 50

    def test_one_pawn_is_worth_about_three_quarters(self) -> None:
        # 100 cp = 200 Elo of expectancy = 76% — the number the model is built on.
        assert win_pct(100) == 76
        assert win_pct(-100) == 24

    @pytest.mark.parametrize(
        ("cp", "expected"),
        [(20, 56), (50, 64), (150, 85), (200, 91), (300, 97)],
    )
    def test_pinned_curve(self, cp: int, expected: int) -> None:
        assert win_pct(cp) == expected

    def test_monotonic_in_advantage(self) -> None:
        values = [win_pct(cp) for cp in range(-1200, 1201, 25)]
        assert values == sorted(values)

    def test_symmetric_about_level(self) -> None:
        # Solved on the magnitude and mirrored, so this holds exactly, not
        # approximately — the eval bar and the two players' numbers must agree.
        for cp in (-900, -317, -101, -20, -1, 0, 1, 20, 101, 317, 900):
            assert win_pct(-cp) == 100 - win_pct(cp)

    def test_never_claims_certainty(self) -> None:
        for cp in range(-2000, 2001, 7):
            assert MIN_PCT <= win_pct(cp) <= MAX_PCT

    def test_saturates_at_the_ends(self) -> None:
        assert win_pct(400) == 99
        assert win_pct(-400) == 1
        assert win_pct(5000) == 99

    def test_returns_an_int(self) -> None:
        assert isinstance(win_pct(37), int)


class TestMateScores:
    @pytest.mark.parametrize("mate", [1, 3, 5])
    def test_near_mate_is_decisive(self, mate: int) -> None:
        assert win_pct(0, mate) == 99
        assert win_pct(0, -mate) == 1

    @pytest.mark.parametrize("mate", [6, 12])
    def test_far_mate_is_winning_not_done(self, mate: int) -> None:
        assert win_pct(0, mate) == 95
        assert win_pct(0, -mate) == 5

    def test_mate_outranks_a_huge_centipawn_score(self) -> None:
        # A forced mate for White is not "9 pawns better for White": the sign of
        # the mate decides, whatever the centipawns claim.
        assert win_pct(-900, 3) == 99
        assert win_pct(900, -3) == 1

    def test_zero_mate_falls_through_to_centipawns(self) -> None:
        # Providers emit mate=0 for "no mate found", which must not read as
        # "White is mated".
        assert win_pct(50, 0) == win_pct(50)
