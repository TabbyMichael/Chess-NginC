"""Which Stockfish we can actually reach (Phase 10, PLAY-001 / REVIEW-001).

Both the opponent and the review pass need a real engine, and a deployment may
have a local binary, an API key, both, or neither. That choice used to live at
every call site, each hard-wired to the local adapter — so a host without a
binary returned 503 while a perfectly good key sat in the environment. One
function makes the call, from settings only (BEN-020), so play and review can
never drift apart on which engine answered a position.

Preference is local-first: a binary already on the machine is free, has no rate
limit, and is not capped at the hosted plan's depth. The cloud provider is the
fallback, never the default, and never silently shares a request budget with a
local engine that was there all along.
"""

from __future__ import annotations

from app.core.database import settings
from app.engine import stockfish
from app.engine.cloud_stockfish import CloudStockfishConfig, CloudStockfishProvider
from app.engine.provider import BatchedEngineProvider
from app.engine.stockfish import (
    StockfishConfig,
    StockfishProvider,
    StockfishUnavailableError,
)


def open_stockfish_provider(*, for_review: bool = False) -> BatchedEngineProvider:
    """Open a Stockfish provider, local binary first and hosted as the fallback.

    Raises StockfishUnavailableError when neither is available; the message
    names both fixes so an operator can act on it without reading the code.
    """
    binary = _available_binary()
    if binary is None:
        return _cloud_provider(for_review=for_review)
    return StockfishProvider(StockfishConfig(path=binary), for_review=for_review)


def stockfish_provider_name() -> str:
    """Label for ledger/review rows: which engine will answer the next request."""
    return "stockfish" if _available_binary() is not None else CloudStockfishProvider.name


def _available_binary() -> str | None:
    """The configured or packaged binary, or None when there is genuinely none.

    Resolved through the module rather than a private name so the probe list stays
    patchable: the test world has no packaged engine, and a developer's Homebrew
    install must not silently change which provider a test asserts on.
    """
    try:
        return stockfish.resolve_binary(settings.stockfish_path)
    except StockfishUnavailableError:
        return None


def _cloud_provider(*, for_review: bool) -> BatchedEngineProvider:
    """A hosted provider, or the one error explaining why nothing is available."""
    api_key = settings.stockfish_api_key
    if not api_key:
        # MON-004 counts at the failure's surfacing point (opponent/review/
        # what-if), not here — the same outage must not increment twice just
        # because the factory is where the answer is "nothing".
        raise StockfishUnavailableError(
            "No Stockfish available: install the 'stockfish' package, set "
            "STOCKFISH_PATH, or configure STOCKFISH_API_KEY for the hosted engine."
        )
    return CloudStockfishProvider(
        CloudStockfishConfig(api_key=api_key, base_url=settings.stockfish_api_base_url),
        for_review=for_review,
    )
