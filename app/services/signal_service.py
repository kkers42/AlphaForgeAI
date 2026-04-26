"""
Signal service layer.

Calls the repository and decides whether to fall back to hardcoded mocks.
Returns a SignalSnapshot that the route unpacks into template context.

Fallback policy
---------------
Mock fallback is controlled by ``settings.allow_mock_fallback``:

- development (default) → True   — UI is never blank during local work
- production  (default) → False  — empty snapshot surfaces as empty feed;
                                    no silent data injection

Override at runtime with the ALLOW_MOCK_FALLBACK env var.

Swap guide (live source)
-------------------------
Point at a different repository by changing this import:

    from app.repositories.sentinel_repository import get_signals as _repo_get_signals

The rest of this file — fallback logic, return type, mock data — is unchanged.
"""

import logging
from dataclasses import replace

from app.core.config import settings
from app.domain.signals import Direction, Signal, Timeframe
from app.repositories.signal_repository import SignalSnapshot
from app.repositories.signal_repository import (
    get_signals as _repo_get_signals,
    get_signals_from_file as _repo_get_signals_from_file,
)

log = logging.getLogger(__name__)


def get_signals() -> SignalSnapshot:
    """
    Return a SignalSnapshot from the configured provider.

    Provider selection (SIGNAL_PROVIDER env var):
      "mock" — hardcoded mock signals served directly as the primary source.
      "file" — signals loaded from SIGNAL_FILE_PATH; falls back to mocks if
               the file is missing/invalid and allow_mock_fallback is True.
      other  — legacy SIGNAL_SOURCE path (local_snapshot / sentinel_ssh).

    If any provider returns no signals and ``settings.allow_mock_fallback``
    is True the response is replaced with hardcoded mocks.
    """
    provider = settings.signal_provider

    # ── Mock provider: serve mocks directly (no file I/O) ───────────────────
    if provider == "mock":
        log.info(
            "signal_provider=mock — serving mock signals as primary source "
            "(environment=%s)",
            settings.environment,
        )
        return SignalSnapshot(
            signals=get_mock_signals(),
            source="mock",
            used_mock_fallback=False,
            status="ok",
        )

    # ── File provider: load from SIGNAL_FILE_PATH ────────────────────────────
    if provider == "file":
        snapshot = _repo_get_signals_from_file()
    else:
        # Legacy: local_snapshot / sentinel_ssh via SIGNAL_SOURCE
        snapshot = _repo_get_signals()

    if not snapshot.signals:
        if settings.allow_mock_fallback:
            log.info(
                "Repository returned no signals (status=%s) — using mock fallback "
                "(allow_mock_fallback=True, environment=%s)",
                snapshot.status,
                settings.environment,
            )
            # Preserve error_message from the original snapshot so the UI can
            # show both "mock fallback active" and the original failure reason.
            return replace(
                snapshot,
                signals=get_mock_signals(),
                source="mock_fallback",
                used_mock_fallback=True,
                status="fallback",
            )
        log.info(
            "Repository returned no signals (status=%s) — returning empty feed "
            "(allow_mock_fallback=False, environment=%s)",
            snapshot.status,
            settings.environment,
        )

    return snapshot


# ---------------------------------------------------------------------------
# Mock signals — fallback only, not the primary source
# ---------------------------------------------------------------------------

def get_mock_signals() -> list[Signal]:
    """
    Hardcoded mock signals used only as a fallback when the snapshot is
    empty or unavailable and allow_mock_fallback is True.

    Values reflect plausible model output, not live market data.
    """
    return [
        Signal(
            symbol="ETH",
            direction=Direction.LONG,
            timeframe=Timeframe.M15,
            confidence=0.74,
            regime="uptrend",
            thesis=(
                "RSI 14 recovered above 48 after a clean pullback to the 20-EMA. "
                "Open interest expanding while funding rate stays neutral. "
                "L/S ratio at 1.42 — spot buyers absorbing futures pressure."
            ),
            top_features=[
                ("rsi_14", 0.18),
                ("oi_change_1h", 0.15),
                ("ls_ratio", 0.13),
                ("ema_20_dist", 0.11),
            ],
        ),
        Signal(
            symbol="SOL",
            direction=Direction.LONG,
            timeframe=Timeframe.H1,
            confidence=0.68,
            regime="uptrend",
            thesis=(
                "Higher-lows structure intact on the 1h. MACD crossed bullish above signal line. "
                "Funding rate neutral — no crowded longs to unwind. "
                "Top-trader L/S at 1.28, slightly elevated but not extreme."
            ),
            top_features=[
                ("macd_hist", 0.21),
                ("higher_lows_count", 0.16),
                ("funding_rate", 0.12),
                ("top_trader_ls", 0.10),
            ],
        ),
        Signal(
            symbol="INJ",
            direction=Direction.LONG,
            timeframe=Timeframe.M15,
            confidence=0.77,
            regime="uptrend",
            thesis=(
                "Three consecutive 15m closes above the 20-EMA with increasing volume. "
                "Top-trader long/short flipped bullish in the last 2h. "
                "RSI at 59 — momentum present, not yet overbought."
            ),
            top_features=[
                ("consec_closes_above_ema", 0.22),
                ("top_trader_ls", 0.19),
                ("rsi_14", 0.14),
                ("volume_ratio", 0.11),
            ],
        ),
        Signal(
            symbol="AVAX",
            direction=Direction.LONG,
            timeframe=Timeframe.M15,
            confidence=0.71,
            regime="uptrend",
            thesis=(
                "Broke above 4h resistance with volume confirmation on the 15m. "
                "Exchange netflow negative — withdrawals outpacing deposits, "
                "consistent with accumulation rather than distribution."
            ),
            top_features=[
                ("breakout_4h_res", 0.20),
                ("exchange_netflow_1h", 0.17),
                ("volume_ratio", 0.13),
            ],
        ),
        Signal(
            symbol="DOGE",
            direction=Direction.SHORT,
            timeframe=Timeframe.M15,
            confidence=0.63,
            regime="downtrend",
            thesis=(
                "Failed to reclaim the 50-EMA on three attempts — each bounce weaker than the last. "
                "Volume declining on bounces, elevated on drops. "
                "OI flat while price drifts lower: not a squeeze setup, just distribution."
            ),
            top_features=[
                ("ema_50_rejection_count", 0.19),
                ("volume_on_bounce", 0.15),
                ("oi_trend", 0.12),
            ],
        ),
        Signal(
            symbol="BTC",
            direction=Direction.FLAT,
            timeframe=Timeframe.M15,
            confidence=0.51,
            regime="ranging",
            thesis=(
                "Price consolidating in a 1.3% band for 8 hours. "
                "ATR contracting, Bollinger Bands squeezing. "
                "No directional edge — model returning FLAT to avoid chop."
            ),
            top_features=[
                ("atr_14", 0.24),
                ("bb_width", 0.18),
                ("adx_14", 0.16),
            ],
        ),
        Signal(
            symbol="LINK",
            direction=Direction.FLAT,
            timeframe=Timeframe.H1,
            confidence=0.46,
            regime="ranging",
            thesis=(
                "Regime unclear — oscillating between EMA clusters on the 1h with no follow-through. "
                "Confidence below the 0.55 threshold. No trade."
            ),
            top_features=[
                ("regime_score", 0.27),
                ("ema_cluster_dist", 0.19),
            ],
        ),
    ]
