#!/usr/bin/env python3
"""
Signal generation pipeline — synthetic model v1.

Writes data/signals_snapshot.json in the v2 envelope format consumed by
the AlphaForgeAI file provider (SIGNAL_PROVIDER=file).

Signals are seeded by (symbol + UTC-hour) so the output is deterministic
within a given hour window and rotates automatically on every subsequent run.

Replace _build_signal() with real XGBoost feature inference once the
data pipeline feeds live candle features from Sentinel.

Usage
-----
    python scripts/generate_signals.py             # write snapshot and exit
    python scripts/generate_signals.py --dry-run   # print JSON only, no write
    python scripts/generate_signals.py --assets 8  # limit to N assets
"""

import argparse
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

REPO_ROOT     = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = REPO_ROOT / "data" / "signals_snapshot.json"

# ── Asset universe ─────────────────────────────────────────────────────────────

ASSETS = [
    "BTC", "ETH", "SOL", "XRP", "AVAX", "LINK", "DOT", "INJ",
    "SUI", "ARB", "OP", "NEAR", "AAVE", "UNI", "DOGE",
    "SHIB", "PEPE", "WIF", "BONK", "LTC",
]

TIMEFRAMES = ["15m", "1h", "4h"]

# ── Feature pools by direction ─────────────────────────────────────────────────

_FEATURES: dict[str, list[str]] = {
    "LONG": [
        "rsi_14", "ema_20_dist", "macd_hist", "volume_ratio",
        "oi_change_1h", "ls_ratio", "higher_lows_count",
        "breakout_4h_res", "exchange_netflow_1h", "top_trader_ls",
        "consec_closes_above_ema", "bb_lower_bounce",
    ],
    "SHORT": [
        "ema_50_rejection_count", "volume_on_bounce", "oi_trend",
        "rsi_divergence", "funding_rate", "macd_crossunder",
        "bb_upper_reject", "lower_highs_count", "top_trader_ls",
    ],
    "FLAT": [
        "atr_14", "bb_width", "adx_14", "regime_score",
        "ema_cluster_dist", "chop_index", "volatility_ratio",
    ],
}

# ── Regime labels ──────────────────────────────────────────────────────────────

_REGIMES: dict[str, list[str]] = {
    "LONG":  ["uptrend", "breakout", "accumulation"],
    "SHORT": ["downtrend", "distribution", "reversal"],
    "FLAT":  ["ranging", "consolidation", "chop"],
}

# ── Thesis sentence templates ──────────────────────────────────────────────────
# Placeholders filled at generation time: {rsi}, {rsi_low}, {ls}, {tf},
# {n}, {h}, {pct}, {pct_mo}

_THESIS: dict[str, list[str]] = {
    "LONG": [
        (
            "RSI 14 recovered above {rsi} after a clean pullback to the 20-EMA. "
            "Open interest expanding while funding rate stays neutral. "
            "L/S ratio at {ls} — spot buyers absorbing futures pressure."
        ),
        (
            "Higher-lows structure intact on the {tf}. MACD crossed bullish above signal line. "
            "Funding rate neutral — no crowded longs to unwind. "
            "Top-trader L/S at {ls}, slightly elevated but not extreme."
        ),
        (
            "{n} consecutive {tf} closes above the 20-EMA with increasing volume. "
            "Top-trader long/short flipped bullish in the last 2h. "
            "RSI at {rsi} — momentum present, not yet overbought."
        ),
        (
            "Broke above 4h resistance with volume confirmation on the {tf}. "
            "Exchange netflow negative — withdrawals outpacing deposits, "
            "consistent with accumulation rather than distribution."
        ),
        (
            "Bollinger Band lower-bounce confirmed with a {tf} close above the midline. "
            "RSI reset from {rsi_low} back to {rsi} — momentum recovering without being extended. "
            "OI rising while price holds: real buyers stepping in."
        ),
    ],
    "SHORT": [
        (
            "Failed to reclaim the 50-EMA on {n} attempts — each bounce weaker than the last. "
            "Volume declining on bounces, elevated on drops. "
            "OI flat while price drifts lower: not a squeeze setup, just distribution."
        ),
        (
            "Lower-highs sequence established on the {tf}. "
            "RSI rejected from {rsi} at the midline — failed recovery. "
            "Funding rate slightly positive: still longs to flush."
        ),
        (
            "MACD crossed bearish below signal line with histogram expanding. "
            "Top-trader long/short flipped short in the last 2h. "
            "Volume spike on the breakdown candle confirms conviction."
        ),
        (
            "Repeated rejection from the upper Bollinger Band over {n} {tf} candles. "
            "OI declining alongside price — longs exiting, not a short squeeze setup. "
            "RSI at {rsi}, overbought territory with divergence forming."
        ),
    ],
    "FLAT": [
        (
            "Price consolidating in a {pct}% band for {h} hours. "
            "ATR contracting, Bollinger Bands squeezing. "
            "No directional edge — model returning FLAT to avoid chop."
        ),
        (
            "Regime unclear — oscillating between EMA clusters on the {tf} with no follow-through. "
            "Confidence below the 0.55 threshold. No trade."
        ),
        (
            "ADX below 20 — trend strength insufficient. "
            "Chop index elevated: mean-reverting environment. "
            "Waiting for regime clarification before committing direction."
        ),
        (
            "Volatility contracting sharply over the last {h} hours. "
            "Bollinger Bands at {pct_mo}% of their 30-day average width. "
            "FLAT pending a volatility expansion trigger."
        ),
    ],
}


# ── Core helpers ───────────────────────────────────────────────────────────────

def _hour_bucket(now: datetime) -> int:
    """Integer that changes every UTC hour — used as the RNG seed component."""
    return now.year * 1_000_000 + now.timetuple().tm_yday * 10_000 + now.hour * 100


def _seed_rng(symbol: str, bucket: int) -> random.Random:
    """Deterministic RNG for this (symbol, hour) pair."""
    key  = f"{symbol}:{bucket}".encode()
    seed = int(hashlib.sha256(key).hexdigest(), 16) % (2 ** 32)
    return random.Random(seed)


def _build_signal(symbol: str, now: datetime) -> dict:
    """Generate one synthetic signal, stable within the current UTC hour."""
    bucket = _hour_bucket(now)
    rng    = _seed_rng(symbol, bucket)

    # Direction: slight LONG bias reflects typical bull-market training data
    direction = rng.choices(
        ["LONG", "SHORT", "FLAT"],
        weights=[0.45, 0.30, 0.25],
    )[0]

    timeframe = rng.choice(TIMEFRAMES)
    regime    = rng.choice(_REGIMES[direction])

    # Confidence bands by direction
    if direction == "FLAT":
        confidence = round(rng.uniform(0.40, 0.60), 2)
    elif direction == "LONG":
        confidence = round(rng.uniform(0.58, 0.85), 2)
    else:
        confidence = round(rng.uniform(0.55, 0.80), 2)

    # Top features: 2–4 features with normalised importances
    feat_pool    = _FEATURES[direction]
    n_feats      = rng.randint(2, min(4, len(feat_pool)))
    chosen_feats = rng.sample(feat_pool, n_feats)
    raw_weights  = [rng.uniform(0.08, 0.28) for _ in chosen_feats]
    total        = sum(raw_weights)
    # Scale so importances sum to a realistic 0.55–0.75 range
    scale        = rng.uniform(0.55, 0.75) / total
    top_features = [
        [f, round(w * scale, 2)]
        for f, w in sorted(zip(chosen_feats, raw_weights), key=lambda x: -x[1])
    ]

    # Thesis
    template = rng.choice(_THESIS[direction])
    rsi_val  = rng.randint(42, 68) if direction in ("LONG", "FLAT") else rng.randint(55, 74)
    thesis   = template.format(
        rsi     = rsi_val,
        rsi_low = rng.randint(28, 38),
        ls      = round(rng.uniform(1.15, 1.55), 2),
        tf      = timeframe,
        n       = rng.randint(2, 4),
        h       = rng.randint(4, 14),
        pct     = round(rng.uniform(0.8, 2.0), 1),
        pct_mo  = rng.randint(28, 55),
    )

    return {
        "symbol":       symbol,
        "direction":    direction,
        "timeframe":    timeframe,
        "confidence":   confidence,
        "regime":       regime,
        "thesis":       thesis,
        "top_features": top_features,
    }


# ── Public API ─────────────────────────────────────────────────────────────────

def generate(asset_count: int = 12) -> dict:
    """
    Generate a full v2 snapshot envelope.

    Returns a dict ready to be JSON-serialised.  The asset subset and all
    signal values are stable within the current UTC hour; running the script
    twice in the same hour produces identical output.
    """
    now    = datetime.now(timezone.utc)
    bucket = _hour_bucket(now)

    # Stable asset selection for this hour window
    sel_rng = random.Random(
        int(hashlib.sha256(f"select:{bucket}".encode()).hexdigest(), 16) % (2 ** 32)
    )
    assets = sorted(sel_rng.sample(ASSETS, min(asset_count, len(ASSETS))))

    signals = [_build_signal(symbol, now) for symbol in assets]

    return {
        "generated_at":  now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model_version": "synthetic-v1",
        "source":        "generated",
        "signals":       signals,
    }


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate signals_snapshot.json for AlphaForgeAI"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print JSON to stdout instead of writing the snapshot file",
    )
    parser.add_argument(
        "--assets",
        type=int,
        default=12,
        metavar="N",
        help="Number of assets to include per run (default: 12, max: %(default)s)",
    )
    args = parser.parse_args()

    snapshot = generate(asset_count=args.assets)
    payload  = json.dumps(snapshot, indent=2)

    if args.dry_run:
        print(payload)
        return

    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_PATH.write_text(payload + "\n", encoding="utf-8")
    print(
        f"[generate_signals] wrote {len(snapshot['signals'])} signals"
        f" to {SNAPSHOT_PATH}  (generated_at={snapshot['generated_at']})"
    )


if __name__ == "__main__":
    main()
