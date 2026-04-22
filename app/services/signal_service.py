"""
Signal service layer.

Primary source: local JSON snapshot via SignalRepository.
Fallback:       get_mock_signals() — used only when the snapshot returns nothing,
                so the UI is never blank during development or if the file is absent.

Swap guide (live source)
-------------------------
To point at a different repository, change the import:

    from app.repositories.sentinel_repository import get_signals  # SSH source

The rest of this file — and the route — stay unchanged.
"""

import logging

from app.domain.signals import Direction, Signal, Timeframe
from app.repositories.signal_repository import get_signals as _repo_get_signals

log = logging.getLogger(__name__)


def get_signals() -> list[Signal]:
    """
    Return signals from the configured repository.

    Falls back to mock data if the repository returns an empty list,
    so the page always has content during development.
    """
    signals = _repo_get_signals()
    if signals:
        return signals
    log.info("Repository returned no signals — falling back to mock data")
    return get_mock_signals()


def get_mock_signals() -> list[Signal]:
    """
    Hardcoded mock signals.

    Kept as an explicit fallback only — not the primary source.
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
