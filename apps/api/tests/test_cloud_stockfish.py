"""Hosted engine provider and provider-choice tests (Phase 10).

The live API cannot be exercised from CI (and the project's key currently sits
behind a billing gate), so the transport is faked at the `requests` Session
boundary: everything above the wire — payload parsing, bounds, retry policy,
error summaries, the score-perspective probe — is the real code.

The factory tests then pin the choice between the two providers: local when a
binary resolves, hosted when only a key is configured, one clear error when
neither is.
"""

from __future__ import annotations

import pytest

from app.core.database import settings
from app.engine import cloud_stockfish
from app.engine.cloud_stockfish import CloudStockfishConfig, CloudStockfishProvider
from app.engine.factory import open_stockfish_provider, stockfish_provider_name
from app.engine.provider import AnalyseRequest
from app.engine.stockfish import StockfishProvider, StockfishUnavailableError
from app.games.domain import Color

STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
BLACK_TO_MOVE_FEN = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"


class FakeResponse:
    """The slice of requests.Response the provider actually reads."""

    def __init__(
        self,
        status_code: int,
        body: object = None,
        headers: dict[str, str] | None = None,
        raise_json: bool = False,
        reason: str = "OK",
    ) -> None:
        self.status_code = status_code
        self._body = body
        self._raise_json = raise_json
        self.headers = headers or {}
        self.reason = reason

    def json(self) -> object:
        if self._raise_json:
            raise ValueError("not json")
        return self._body


class FakeSession:
    """Scripted transport: pops one response per POST, records every request."""

    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []
        self.closed = 0

    def post(
        self,
        url: str,
        json: dict | None = None,
        headers: dict | None = None,
        timeout: object = None,
    ):
        self.calls.append((url, json or {}))
        nxt = self.responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    def close(self) -> None:
        self.closed += 1


def eval_payload(cp: int = 35, *, best: str = "e2e4") -> dict:
    """A response in the documented /v1/eval shape."""
    return {
        "eval": {"type": "cp", "value": cp},
        "bestmove": best,
        "pvs": [
            {"rank": 1, "eval": {"type": "cp", "value": cp}, "moves": [best, "e7e5"]},
            {"rank": 2, "eval": {"type": "cp", "value": cp - 12}, "moves": ["d2d4", "d7d5"]},
            {"rank": 3, "eval": {"type": "cp", "value": cp - 25}, "moves": ["g1f3", "g8f6"]},
        ],
        "depth": 12,
        "nodes": 451203,
        "engine": "stockfish-19",
        "cached": False,
        "cost_units": 2,
    }


def make_provider(
    responses: list[object], *, config: CloudStockfishConfig | None = None
) -> CloudStockfishProvider:
    provider = CloudStockfishProvider(config or CloudStockfishConfig(api_key="sk_test"))
    provider._session = FakeSession(responses)  # type: ignore[assignment]
    return provider


@pytest.fixture(autouse=True)
def _fresh_calibration_cache() -> None:
    """Pin the score convention per test, and never let a probe reach the network.

    The probed convention is process-wide state. Seeding it to mover-POV keeps an
    `auto` provider from firing a real calibration request for tests that are not
    about calibration, and the explicit-perspective tests overwrite it anyway.
    """
    cloud_stockfish._CALIBRATION_CACHE["pov_is_white"] = False
    yield
    cloud_stockfish.reset_score_calibration_cache()


# --- the /v1/eval contract ---------------------------------------------------------


def test_parses_the_documented_eval_response() -> None:
    provider = make_provider([FakeResponse(200, eval_payload())])
    result = provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=10, multipv=3))
    assert result.provider == "stockfish-cloud"
    assert result.fen == STARTING_FEN
    assert [line.move for line in result.lines] == ["e2e4", "d2d4", "g1f3"]
    assert result.lines[0].score_cp == 35
    assert result.lines[0].pv == ("e2e4", "e7e5")
    assert result.depth == 12
    assert result.nodes_searched == 451203


def test_posts_fen_depth_and_movetime_to_the_eval_endpoint() -> None:
    session_provider = make_provider([FakeResponse(200, eval_payload())])
    session_provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=8, multipv=2, max_time_ms=700))
    url, body = session_provider._session.calls[0]  # type: ignore[union-attr]
    assert url.endswith("/eval")
    assert body == {"fen": STARTING_FEN, "depth": 8, "multipv": 2, "movetime_ms": 700}


def test_depth_is_clamped_to_the_plan_ceiling() -> None:
    provider = make_provider(
        [FakeResponse(200, eval_payload())],
        config=CloudStockfishConfig(api_key="sk_test", max_depth=14),
    )
    provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=25, multipv=1))
    assert provider._session.calls[0][1]["depth"] == 14  # type: ignore[union-attr]


def test_review_mode_may_ask_deeper_than_play_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Live play stays inside the tight adapter bounds whatever the plan allows;
    a review pass may go to the review ceiling — otherwise the two would silently
    grade against different truth."""
    monkeypatch.setattr(cloud_stockfish, "_CALIBRATION_CACHE", {"pov_is_white": False})
    deep_plan = CloudStockfishConfig(api_key="k", max_depth=30)
    bare = make_provider([FakeResponse(200, eval_payload())], config=deep_plan)
    bare.analyse(AnalyseRequest(fen=STARTING_FEN, depth=25, multipv=1))
    assert bare._session.calls[0][1]["depth"] == 15  # type: ignore[union-attr]

    review = CloudStockfishProvider(deep_plan, for_review=True)
    review._session = FakeSession([FakeResponse(200, eval_payload())])  # type: ignore[assignment]
    review.analyse(AnalyseRequest(fen=STARTING_FEN, depth=25, multipv=1))
    assert review._session.calls[0][1]["depth"] == 25  # type: ignore[union-attr]


def test_multipv_never_exceeds_the_api_limit() -> None:
    provider = make_provider([FakeResponse(200, eval_payload())])
    provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=10, multipv=50))
    assert provider._session.calls[0][1]["multipv"] == cloud_stockfish.CLOUD_MAX_MULTIPV  # type: ignore[union-attr]


def test_missing_pvs_falls_back_to_the_reported_bestmove() -> None:
    body = {"bestmove": "d2d4", "eval": {"type": "cp", "value": 18}}
    provider = make_provider([FakeResponse(200, body)])
    result = provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=5, multipv=1))
    assert result.best is not None
    assert (result.best.move, result.best.score_cp) == ("d2d4", 18)


def test_unusable_pv_entries_are_dropped_not_guessed() -> None:
    body = {
        "pvs": [
            {"moves": ["e2e4"], "eval": {"type": "cp", "value": 30}},
            {"moves": ["d2d4"], "eval": None},
            "junk",
        ]
    }
    provider = make_provider([FakeResponse(200, body)])
    result = provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=5, multipv=3))
    assert [line.move for line in result.lines] == ["e2e4"]


def test_mate_scores_use_the_shared_centipawn_ruler() -> None:
    mate_body = {"pvs": [{"moves": ["d8h4"], "eval": {"type": "mate", "value": 1}}]}
    provider = make_provider([FakeResponse(200, mate_body)])
    provider2 = make_provider([FakeResponse(200, mate_body)])
    # White to move, mate delivered in one: mate_in is +1 and the score wins
    # from the mover's view. Asked for Black's view both flip — mate_in -1
    # says Black is the one being mated, exactly like the local adapter.
    result = provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=5, multipv=1))
    best = result.best
    assert best is not None
    assert best.mate_in == 1
    assert best.score_cp == 19_990  # 20000 - 10, the adapter's mate magnitude

    black_view = AnalyseRequest(fen=STARTING_FEN, depth=5, multipv=1, for_color=Color.BLACK)
    against = provider2.analyse(black_view)
    assert against.best is not None
    assert (against.best.score_cp, against.best.mate_in) == (-19_990, -1)


# --- score perspective (the undocumented part) -------------------------------------


def test_white_pov_is_flipped_for_black_and_left_alone_for_white() -> None:
    cfg = CloudStockfishConfig(api_key="k", score_pov="white")
    white = make_provider([FakeResponse(200, eval_payload(cp=40))], config=cfg)
    result = white.analyse(AnalyseRequest(fen=STARTING_FEN, depth=5, multipv=1))
    assert result.best is not None and result.best.score_cp == 40  # White to move: no flip

    black = make_provider([FakeResponse(200, eval_payload(cp=40))], config=cfg)
    black_view = AnalyseRequest(fen=STARTING_FEN, depth=5, multipv=1, for_color=Color.BLACK)
    result = black.analyse(black_view)
    # White to move under White-POV: the mover's view is already White's, so
    # only the requested for_color flip applies.
    assert result.best is not None and result.best.score_cp == -40


def test_mover_pov_is_never_flipped() -> None:
    cfg = CloudStockfishConfig(api_key="k", score_pov="mover")
    black = make_provider([FakeResponse(200, eval_payload(cp=40))], config=cfg)
    result = black.analyse(
        AnalyseRequest(fen=BLACK_TO_MOVE_FEN, depth=5, multipv=1, for_color=Color.BLACK)
    )
    assert result.best is not None and result.best.score_cp == 40  # mover: no flip

    white = make_provider([FakeResponse(200, eval_payload(cp=40))], config=cfg)
    result = white.analyse(AnalyseRequest(fen=STARTING_FEN, depth=5, multipv=1))
    assert result.best is not None and result.best.score_cp == 40


def test_calibration_probes_once_and_caches_the_convention(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Black a queen up reads negative only under White-POV, so the probe must
    conclude `pov_is_white` — and never ask again for the next position."""
    posts: list[dict] = []

    class CalibrateSession:
        def post(
            self,
            url: str,
            json: dict | None = None,
            headers: dict | None = None,
            timeout: object = None,
        ):
            posts.append(json or {})
            cp = -1200 if json and json.get("fen") == cloud_stockfish._CALIBRATION_FEN else 30
            line = {"moves": ["g2g1q"], "eval": {"type": "cp", "value": cp}}
            return FakeResponse(200, {"pvs": [line]})

        def close(self) -> None:
            return None

    monkeypatch.setattr(cloud_stockfish.requests, "Session", CalibrateSession)
    cloud_stockfish.reset_score_calibration_cache()  # the fixture pins it; this test probes
    provider = CloudStockfishProvider(CloudStockfishConfig(api_key="k"))
    first = provider.analyse(AnalyseRequest(fen=BLACK_TO_MOVE_FEN, depth=5, multipv=1))
    second = provider.analyse(AnalyseRequest(fen=BLACK_TO_MOVE_FEN, depth=5, multipv=1))

    assert len(posts) == 3  # one probe + two analyses, not one probe per analysis
    assert first.best is not None and first.best.score_cp == 30  # -30 flipped to mover-POV
    assert second.best is not None and second.best.score_cp == 30


def test_a_failing_calibration_probe_defaults_to_mover_pov(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guessing White-POV on a failed probe would invert every review grade;
    the safe default is the convention UCI itself uses."""

    class ProbeFails:
        def post(self, url, json=None, headers=None, timeout=None):
            fen = (json or {}).get("fen")
            if fen == cloud_stockfish._CALIBRATION_FEN:
                raise cloud_stockfish.requests.ConnectTimeout("probe timed out")
            if fen != BLACK_TO_MOVE_FEN:
                raise AssertionError(f"unexpected analysis request: {fen}")
            return FakeResponse(200, eval_payload(cp=-40))

        def close(self):
            return None

    monkeypatch.setattr(cloud_stockfish.requests, "Session", ProbeFails)
    cloud_stockfish.reset_score_calibration_cache()
    provider = CloudStockfishProvider(CloudStockfishConfig(api_key="k"))
    # Asked for the mover's own view: after a failed probe the score must
    # arrive unflipped, not inverted by a guessed White-POV convention.
    result = provider.analyse(
        AnalyseRequest(fen=BLACK_TO_MOVE_FEN, depth=5, multipv=1, for_color=Color.BLACK)
    )
    assert result.best is not None and result.best.score_cp == -40
    assert cloud_stockfish._CALIBRATION_CACHE["pov_is_white"] is False


# --- failure and retry policy -------------------------------------------------------


def test_missing_key_fails_before_any_http() -> None:
    provider = make_provider([], config=CloudStockfishConfig(api_key=""))
    with pytest.raises(StockfishUnavailableError, match="STOCKFISH_API_KEY"):
        provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=5, multipv=1))
    assert provider._session.calls == []  # type: ignore[union-attr]


def test_payment_problem_is_reported_without_leaking_the_key() -> None:
    problem = {
        "type": "https://stockfishapi.com/errors/payment_required",
        "title": "Payment method required",
        "detail": "Add an unexpired card to use the free plan.",
        "next_action": "Add a card in the dashboard billing page.",
    }
    provider = make_provider([FakeResponse(402, problem, reason="Payment Required")])
    with pytest.raises(StockfishUnavailableError) as excinfo:
        provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=5, multipv=1))
    message = str(excinfo.value)
    assert "Payment method required" in message
    assert "Add a card" in message
    assert "sk_test" not in message


def test_transient_status_is_retried_once_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    waits: list[float] = []
    monkeypatch.setattr(cloud_stockfish.time, "sleep", lambda s: waits.append(s))
    provider = make_provider(
        [
            FakeResponse(
                503, {"title": "Engine busy"}, headers={"Retry-After": "1"}, reason="Busy"
            ),
            FakeResponse(200, eval_payload()),
        ]
    )
    result = provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=5, multipv=1))
    assert len(provider._session.calls) == 2  # type: ignore[union-attr]
    assert waits == [1.0]
    assert result.best is not None


def test_retry_after_is_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    waits: list[float] = []
    monkeypatch.setattr(cloud_stockfish.time, "sleep", lambda s: waits.append(s))
    provider = make_provider(
        [
            FakeResponse(
                429, {"title": "Slow down"}, headers={"Retry-After": "600"}, reason="Too Many"
            ),
            FakeResponse(200, eval_payload()),
        ]
    )
    provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=5, multipv=1))
    assert waits == [cloud_stockfish.CLOUD_MAX_RETRY_WAIT_S]


def test_a_second_transient_failure_still_raises_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cloud_stockfish.time, "sleep", lambda s: None)
    provider = make_provider(
        [
            FakeResponse(500, {"title": "Boom"}, reason="Server Error"),
            FakeResponse(500, {"title": "Boom"}, reason="Server Error"),
        ]
    )
    with pytest.raises(StockfishUnavailableError, match="Boom"):
        provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=5, multipv=1))


def test_transport_error_becomes_unavailable_with_no_body_detail() -> None:
    provider = make_provider(
        [
            cloud_stockfish.requests.ConnectTimeout("timed out"),
            cloud_stockfish.requests.ConnectTimeout("timed out"),
        ]
    )
    with pytest.raises(StockfishUnavailableError, match="ConnectTimeout"):
        provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=5, multipv=1))


def test_non_json_success_is_not_invented_as_zero() -> None:
    provider = make_provider([FakeResponse(200, "<html>maintenance</html>", raise_json=True)])
    with pytest.raises(StockfishUnavailableError, match="non-JSON"):
        provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=5, multipv=1))


def test_unparsable_fen_fails_before_the_network() -> None:
    provider = make_provider([])
    with pytest.raises(StockfishUnavailableError, match="read the position"):
        provider.analyse(AnalyseRequest(fen="not a fen at all", depth=5, multipv=1))
    assert provider._session.calls == []  # type: ignore[union-attr]


def test_context_manager_hands_the_pool_back_and_is_idempotent() -> None:
    provider = make_provider([FakeResponse(200, eval_payload())])
    with provider as opened:
        opened.analyse(AnalyseRequest(fen=STARTING_FEN, depth=5, multipv=1))
    session = provider._session
    assert isinstance(session, FakeSession)
    assert session.closed == 1
    provider.close()  # a batch caller and the `with` may both close it
    assert session.closed == 2


# --- the factory: which engine answers ----------------------------------------------


def test_factory_prefers_the_local_binary_even_when_a_key_is_set(
    fake_binary: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "stockfish_api_key", "sk_test", raising=False)
    monkeypatch.setattr(settings, "stockfish_path", fake_binary, raising=False)
    with open_stockfish_provider() as provider:
        assert isinstance(provider, StockfishProvider)
    assert stockfish_provider_name() == "stockfish"


def test_factory_falls_back_to_the_hosted_engine_without_a_binary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PATH", "/nonexistent")
    monkeypatch.setattr(settings, "stockfish_api_key", "sk_test", raising=False)
    provider = open_stockfish_provider()
    assert isinstance(provider, CloudStockfishProvider)
    assert stockfish_provider_name() == "stockfish-cloud"
    provider.close()


def test_factory_names_both_fixes_when_neither_engine_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PATH", "/nonexistent")
    with pytest.raises(StockfishUnavailableError) as excinfo:
        open_stockfish_provider()
    message = str(excinfo.value)
    assert "STOCKFISH_PATH" in message and "STOCKFISH_API_KEY" in message


def test_factory_passes_the_base_url_and_key_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "/nonexistent")
    monkeypatch.setattr(settings, "stockfish_api_key", "sk_test", raising=False)
    base_url = "https://example.test/v1"
    monkeypatch.setattr(settings, "stockfish_api_base_url", base_url, raising=False)
    provider = open_stockfish_provider()
    assert isinstance(provider, CloudStockfishProvider)
    assert provider._config.api_key == "sk_test"
    assert provider._config.base_url == "https://example.test/v1"
    provider.close()


# --- shared daily-unit budget (Phase 12A, RL-003 / MON-006) -------------------------


def _gauge_value(name: str) -> float:
    from app.core.telemetry import CLOUD_UNITS_USED_TODAY

    for sample in CLOUD_UNITS_USED_TODAY.collect():
        for s in sample.samples:
            if s.name == name:
                return s.value
    return -1.0


def _counter_total(name: str, status: str) -> float:
    from app.core.telemetry import CLOUD_UPSTREAM_ERRORS_TOTAL

    for sample in CLOUD_UPSTREAM_ERRORS_TOTAL.collect():
        for s in sample.samples:
            if s.name == name and s.labels.get("status") == status:
                return s.value
    return -1.0


def test_units_for_depth_matches_plan_pricing() -> None:
    # Free plan: one unit up to depth 7, two for the 8–14 it caps at.
    assert cloud_stockfish.units_for_depth(6) == 1
    assert cloud_stockfish.units_for_depth(7) == 1
    assert cloud_stockfish.units_for_depth(8) == 2
    assert cloud_stockfish.units_for_depth(14) == 2


def test_budget_trips_before_upstream_does(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "cloud_daily_unit_budget", 3)
    provider = make_provider([FakeResponse(200, eval_payload()), FakeResponse(200, eval_payload())])
    provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=14, multipv=1))  # costs 2
    assert _gauge_value("cloud_units_used_today") == 2
    # 2 used + 2 estimated > 3: the guard says no without touching the wire.
    with pytest.raises(StockfishUnavailableError, match="daily budget exhausted"):
        provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=14, multipv=1))
    assert len(provider._session.calls) == 1  # type: ignore[union-attr]


def test_cost_units_from_the_response_are_authoritative(monkeypatch: pytest.MonkeyPatch) -> None:
    # A response that says it cost 1 (e.g. a shallow call) draws 1, not the
    # depth estimate — the pot must reflect the vendor's meter, not ours.
    monkeypatch.setattr(settings, "cloud_daily_unit_budget", 3)
    cheap = eval_payload()
    cheap["cost_units"] = 1
    provider = make_provider([FakeResponse(200, cheap)] * 2)
    provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=14, multipv=1))
    provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=14, multipv=1))
    # Two depth-14 calls estimated at 2 each but metered at 1: the pot moved 2,
    # not 4 — and the second call still fit (1 used + 2 est <= 3).
    assert _gauge_value("cloud_units_used_today") == 2
    assert len(provider._session.calls) == 2  # type: ignore[union-attr]


def test_zero_budget_disables_the_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    # Accounts with a real plan opt out entirely: no counter, no refusals.
    monkeypatch.setattr(settings, "cloud_daily_unit_budget", 0)
    provider = make_provider([FakeResponse(200, eval_payload())] * 3)
    for _ in range(3):
        provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=14, multipv=1))
    assert len(provider._session.calls) == 3  # type: ignore[union-attr]


def test_upstream_client_errors_are_counted_by_status() -> None:
    name = "cloud_upstream_errors_total"
    before = _counter_total(name, "402")
    provider = make_provider(
        [FakeResponse(402, {"title": "Payment method required"}, reason="Payment Required")]
    )
    with pytest.raises(StockfishUnavailableError):
        provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=5, multipv=1))
    assert _counter_total(name, "402") == before + 1


def test_reset_daily_budget_forgets_the_day(monkeypatch: pytest.MonkeyPatch) -> None:
    # The hook conftest leans on between tests: used units and the trip go away.
    monkeypatch.setattr(settings, "cloud_daily_unit_budget", 3)
    provider = make_provider([FakeResponse(200, eval_payload())] * 2)
    provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=14, multipv=1))
    assert _gauge_value("cloud_units_used_today") == 2
    cloud_stockfish.reset_daily_budget()
    assert _gauge_value("cloud_units_used_today") == 0
    provider.analyse(AnalyseRequest(fen=STARTING_FEN, depth=14, multipv=1))  # fits again
