"""Hosted Stockfish provider (stockfishapi.com).

Deliberate exception to "the engine never does HTTP" (provider.py): when a
deployment has no local binary, the computer opponent and game review still
need Stockfish, and a hosted API is the only way to get it. The HTTP boundary
lives here and nowhere else — services and classification keep talking to the
same EngineProvider seam, so going back to a local binary is a config change,
not a rewrite.

Every failure surfaces as StockfishUnavailableError with a summary that is safe
to show an operator: never the API key, never a raw exception string.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any, Literal, cast

import chess
import requests

from app.core.database import settings
from app.core.telemetry import record_cloud_upstream_error, set_cloud_units_used_today
from app.engine.provider import AnalyseRequest, AnalysisResult, PrincipalVariation
from app.engine.stockfish import (
    REVIEW_MAX_DEPTH,
    REVIEW_MAX_TIME_MS,
    STOCKFISH_MAX_DEPTH,
    STOCKFISH_MAX_TIME_MS,
    StockfishUnavailableError,
)
from app.games.domain import Color

CLOUD_TIMEOUT_S = 20.0
CLOUD_ATTEMPTS = 2
CLOUD_MAX_RETRY_WAIT_S = 5.0
CLOUD_RETRY_DELAY_S = 0.5

# The free tier caps depth at 14; deeper requests cost more units and are
# refused. Callers may raise this with an explicit plan-aware config.
CLOUD_DEFAULT_MAX_DEPTH = 14
CLOUD_MAX_MULTIPV = 10

# The API does not document whether a score is from the side-to-move's or
# White's point of view, and guessing wrong silently inverts every review grade.
# So the first call probes a position with one unambiguous answer and learns the
# convention instead of assuming it: Black to move, a queen up and about to
# mate, which any sane engine scores very favorably for Black.
_CALIBRATION_FEN = "4k3/8/8/8/8/8/6q1/4K3 b - - 0 1"
_CALIBRATION_DEPTH = 8

ScorePov = Literal["auto", "mover", "white"]


@dataclass(frozen=True)
class CloudStockfishConfig:
    """Configuration for the hosted Stockfish API."""

    api_key: str = ""
    base_url: str = "https://stockfishapi.com/v1"
    engine: str = "latest"
    max_depth: int = CLOUD_DEFAULT_MAX_DEPTH
    timeout_s: float = CLOUD_TIMEOUT_S
    score_pov: ScorePov = "auto"

    def bounded(self, *, for_review: bool = False) -> CloudStockfishConfig:
        """Clamp the request bounds: review may search deeper than live play."""
        ceiling = REVIEW_MAX_DEPTH if for_review else STOCKFISH_MAX_DEPTH
        return replace(self, max_depth=max(1, min(self.max_depth, ceiling)))


class CloudStockfishProvider:
    """EngineProvider backed by a hosted Stockfish API.

    Stateless apart from a cached score-convention probe, so a review pass can
    reuse one instance: there is no process to keep warm, only the calibration
    result to keep.
    """

    name = "stockfish-cloud"

    def __init__(
        self, config: CloudStockfishConfig | None = None, *, for_review: bool = False
    ) -> None:
        self._config = config or CloudStockfishConfig()
        self._for_review = for_review
        self._session = requests.Session()

    def __enter__(self) -> CloudStockfishProvider:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        """Drop the pooled connection. Idempotent (EngineProvider contract)."""
        self._session.close()

    def analyse(self, request: AnalyseRequest) -> AnalysisResult:
        """Analyse one position through the hosted API."""
        cfg = self._config.bounded(for_review=self._for_review)
        depth = max(1, min(cfg.max_depth, request.depth or cfg.max_depth))
        multipv = max(1, min(request.multipv, CLOUD_MAX_MULTIPV))
        board = _board_for(request.fen)
        time_ceiling = REVIEW_MAX_TIME_MS if self._for_review else STOCKFISH_MAX_TIME_MS
        limit_ms = max(1, min(request.max_time_ms, time_ceiling))

        start = time.time()
        payload = self._post(
            cfg, {"fen": request.fen, "depth": depth, "multipv": multipv, "movetime_ms": limit_ms}
        )
        lines = _lines_from_response(payload, cfg, board, request.for_color)
        elapsed_ms = int((time.time() - start) * 1000)
        return AnalysisResult(
            fen=request.fen,
            lines=lines,
            depth=_as_int(payload.get("depth"), default=depth),
            nodes_searched=_as_int(payload.get("nodes")),
            time_ms=elapsed_ms,
            provider=self.name,
        )

    def _post(self, cfg: CloudStockfishConfig, body: dict[str, Any]) -> dict[str, Any]:
        """POST /eval with one bounded retry; any failure becomes Unavailable."""
        if not cfg.api_key:
            raise StockfishUnavailableError("No Stockfish API key configured (STOCKFISH_API_KEY).")
        # RL-003: the plan's 2,000 units/day is one pot for the whole account,
        # so the app stops drawing from it before upstream has to say no.
        estimate = units_for_depth(_as_int(body.get("depth"), default=cfg.max_depth))
        _reserve_daily_units(estimate)
        headers = {"Authorization": f"Bearer {cfg.api_key}", "Accept": "application/json"}
        url = f"{cfg.base_url.rstrip('/')}/eval"
        last: Exception | None = None
        for attempt in range(CLOUD_ATTEMPTS):
            try:
                response = self._session.post(
                    url, json=body, headers=headers, timeout=cfg.timeout_s
                )
            except requests.RequestException as exc:
                # Transport errors carry no key and no server body.
                last = exc
                if attempt + 1 < CLOUD_ATTEMPTS:
                    time.sleep(CLOUD_RETRY_DELAY_S)
                    continue
                raise StockfishUnavailableError(
                    f"Stockfish API unreachable: {type(exc).__name__}"
                ) from exc
            if response.status_code == 200:
                data = _json_body(response)
                if data is None:
                    raise StockfishUnavailableError("Stockfish API returned a non-JSON body.")
                # The response reports what the call actually cost; fall back
                # to the depth estimate when a version stops sending it.
                _consume_daily_units(max(0, _as_int(data.get("cost_units"), default=estimate)))
                return data
            record_cloud_upstream_error(response.status_code)  # 402/429 = plan trouble
            if _retryable(response.status_code) and attempt + 1 < CLOUD_ATTEMPTS:
                time.sleep(_retry_wait_s(response))
                continue
            raise StockfishUnavailableError(_problem_summary(response))
        raise StockfishUnavailableError(f"Stockfish API failed: {type(last).__name__}")


# --- shared daily-unit budget (Phase 12A, RL-003/D15) ----------------------------
# The free plan caps the *account* at 2,000 units/day, so one bored player
# re-reviewing games could empty the pot for everyone. This is the app-wide
# counter that says no first — with a clean operator-facing error instead of a
# wave of upstream 402/429s. It only ever runs on the cloud route: the factory
# keeps a local binary ahead of it (D7), and settings.cloud_daily_unit_budget=0
# disables it entirely for accounts with a real plan.

_BUDGET_LOCK = threading.Lock()
_budget_state: dict[str, Any] = {"date": "", "used": 0}


def units_for_depth(depth: int) -> int:
    """Plan pricing: one unit up to depth 7, two for the 8–14 the API allows."""
    return 1 if depth <= 7 else 2


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


def _reserve_daily_units(estimate: int) -> None:
    """Refuse the request if the pot cannot cover it (day rolls over at UTC)."""
    budget = settings.cloud_daily_unit_budget
    today = _today()
    with _BUDGET_LOCK:
        if _budget_state["date"] != today:
            _budget_state["date"] = today
            _budget_state["used"] = 0
        used = int(_budget_state["used"] or 0)
        if budget > 0 and used + estimate > budget:
            raise StockfishUnavailableError(
                f"Hosted engine daily budget exhausted ({used} of {budget} units used "
                "today). It refills tomorrow UTC, or install a local Stockfish binary."
            )


def _consume_daily_units(units: int) -> None:
    today = _today()
    with _BUDGET_LOCK:
        if _budget_state["date"] != today:
            _budget_state["date"] = today
            _budget_state["used"] = 0
        _budget_state["used"] = int(_budget_state["used"] or 0) + units
        set_cloud_units_used_today(int(_budget_state["used"]))


def reset_daily_budget() -> None:
    """Forget the day's usage. Tests use this; production just rolls over."""
    with _BUDGET_LOCK:
        _budget_state["date"] = ""
        _budget_state["used"] = 0
    set_cloud_units_used_today(0)


def _as_int(value: Any, *, default: int = 0) -> int:
    """Read an API counter that may arrive as a number, a string, or missing."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _flip(cp: int, mate_in: int | None) -> tuple[int, int | None]:
    """Negate a score and its mate distance together."""
    return -cp, (-mate_in if mate_in is not None else None)


def _lines_from_response(
    payload: dict[str, Any],
    cfg: CloudStockfishConfig,
    board: chess.Board,
    for_color: Color,
) -> tuple[PrincipalVariation, ...]:
    """Build side-to-move-POV lines, matching the local adapter's convention."""
    raw = payload.get("pvs")
    if not isinstance(raw, list) or not raw:
        # Fall back to the single best line the API always reports.
        best = payload.get("bestmove")
        moves = [best] if isinstance(best, str) and best else []
        raw = [{"moves": moves, "eval": payload.get("eval")}]
    lines: list[PrincipalVariation] = []
    for item in raw:
        if isinstance(item, dict) and (line := _line_from_pv(item, cfg, board, for_color)):
            lines.append(line)
    return tuple(lines)


def _line_from_pv(
    item: dict[str, Any], cfg: CloudStockfishConfig, board: chess.Board, for_color: Color
) -> PrincipalVariation | None:
    """One `pvs` entry to a PrincipalVariation; None if it holds no usable score."""
    moves = [m for m in (item.get("moves") or []) if isinstance(m, str)]
    score = _raw_score(item.get("eval"))
    if score is None:
        return None
    cp, mate_in = score
    if _score_pov_is_white(cfg) and board.turn == chess.BLACK:
        # Undo White-POV so the value reads from the mover's side — the
        # convention the shared adapter (and the review service) expects.
        cp, mate_in = _flip(cp, mate_in)
    if (board.turn == chess.WHITE) != (for_color == Color.WHITE):
        cp, mate_in = _flip(cp, mate_in)
    return PrincipalVariation(
        move=moves[0] if moves else "", score_cp=cp, mate_in=mate_in, pv=tuple(moves)
    )


def _score_pov_is_white(cfg: CloudStockfishConfig) -> bool:
    """Resolve the API's score perspective, probing once and caching the answer."""
    if cfg.score_pov == "white":
        return True
    if cfg.score_pov == "mover":
        return False
    cached = _CALIBRATION_CACHE.get("pov_is_white")
    return _calibrate(cfg) if cached is None else cached


def _calibrate(cfg: CloudStockfishConfig) -> bool:
    """Learn the score convention from a position with one obvious answer.

    A queen up with Black to move must read favorable to Black, so a positive
    score means the API already reports the side to move's view and a negative
    one means it reports White's. If the probe itself fails we assume the
    side-to-move convention (what UCI and python-chess use) rather than invert
    every grade on a guess.
    """
    with _CALIBRATION_LOCK:
        cached = _CALIBRATION_CACHE.get("pov_is_white")
        if cached is not None:
            return cached
        probe = replace(cfg, max_depth=min(cfg.max_depth, _CALIBRATION_DEPTH), score_pov="auto")
        pov_is_white = False
        try:
            payload = CloudStockfishProvider(probe)._post(
                probe, {"fen": _CALIBRATION_FEN, "depth": probe.max_depth, "multipv": 1}
            )
            lines = payload.get("pvs")
            first = (
                lines[0] if isinstance(lines, list) and lines and isinstance(lines[0], dict) else {}
            )
            score = _raw_score(first.get("eval") or payload.get("eval"))
            cp = score[0] if score is not None else 0
            # Black to move here: a positive cp means "good for the mover".
            pov_is_white = cp < 0
        except Exception:
            pov_is_white = False
        _CALIBRATION_CACHE["pov_is_white"] = pov_is_white
        return pov_is_white


def reset_score_calibration_cache() -> None:
    """Forget the probed convention. Tests use this; production never needs to."""
    with _CALIBRATION_LOCK:
        _CALIBRATION_CACHE["pov_is_white"] = None


_CALIBRATION_LOCK = threading.Lock()
_CALIBRATION_CACHE: dict[str, bool | None] = {"pov_is_white": None}


def _retryable(status: int) -> bool:
    """Transient server-side statuses worth one more attempt."""
    return status in (429, 500, 502, 503, 504)


def _retry_wait_s(response: requests.Response) -> float:
    """Honor Retry-After, but never block a request for long."""
    raw = response.headers.get("Retry-After")
    try:
        claimed = float(raw) if raw is not None else 0.0
    except (TypeError, ValueError):
        claimed = 0.0
    if claimed <= 0:
        claimed = CLOUD_RETRY_DELAY_S
    return min(claimed, CLOUD_MAX_RETRY_WAIT_S)


def _json_body(response: requests.Response) -> dict[str, Any] | None:
    """Decoded JSON object, or None when the body is not one."""
    try:
        data = response.json()
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _problem_summary(response: requests.Response) -> str:
    """An operator-facing one-liner from an RFC 9457 problem body.

    Only the documented status/title/detail/next_action fields are read; they
    carry no credentials, and the raw body is never echoed.
    """
    data = _json_body(response) or {}
    detail = data.get("detail")
    title = str(data.get("title") or detail or response.reason or "error")
    extra = f" ({detail})" if detail and title != str(detail) else ""
    next_action = f" Next step: {data['next_action']}." if data.get("next_action") else ""
    return f"Stockfish API HTTP {response.status_code}: {title}{extra}{next_action}"


def _raw_score(score: Any) -> tuple[int, int | None] | None:
    """API Score object ({type: cp|mate, value}) to (centipawns, mate_in)."""
    if not isinstance(score, dict):
        return None
    score = cast("dict[str, object]", score)
    kind = score.get("type")
    try:
        value = int(score.get("value"))
    except (TypeError, ValueError):
        return None
    if kind == "mate":
        magnitude = max(0, 20000 - abs(value) * 10)
        return (magnitude if value > 0 else -magnitude), (value or None)
    if kind == "cp":
        return value, None
    return None


def _board_for(fen: str) -> chess.Board:
    """Parse the FEN the request was built on, for side-to-move arithmetic."""
    try:
        return chess.Board(fen)
    except ValueError as exc:
        raise StockfishUnavailableError(
            f"Stockfish API could not read the position: {exc}"
        ) from exc
