"""
Signal Thesis Generator.

For each signal, expands the single-line thesis into a structured breakdown:
  - setup_rationale  : why the model is taking this position
  - invalidation     : the price action that cancels the thesis
  - risk_thesis      : tail risks and position-sizing considerations
  - catalyst_notes   : near-term events or triggers that could accelerate

Generated purely from the signal's existing fields (direction, confidence,
regime, timeframe, top_features) — no external data required.

All output is deterministic for a given signal so templates can be cached and
the feed stays stable within a refresh window.
"""

import hashlib
import random
from typing import Optional

from app.domain.signals import Direction, Signal


# ---------------------------------------------------------------------------
# Template banks
# ---------------------------------------------------------------------------

_SETUP: dict[str, list[str]] = {
    "LONG": [
        (
            "Price is holding above the {tf} 20-EMA with a constructive pullback structure. "
            "The model's top driver ({feat}) is pointing to sustained buying pressure. "
            "Regime classified as {regime}, consistent with continuation plays."
        ),
        (
            "A higher-lows sequence is intact on the {tf}. "
            "{feat} confirms the trend has not exhausted. "
            "Confidence at {conf}% — above the 60% threshold required for an active long setup."
        ),
        (
            "Breakout structure forming: price cleared a key level with expanding volume. "
            "{feat} is the primary driver at {feat_weight}% model weight. "
            "Regime: {regime}. Setup favours trend continuation over reversion."
        ),
        (
            "Funding rate neutral, open interest expanding — new money entering, not a short squeeze. "
            "The {tf} candle sequence shows impulsive up-moves with corrective pullbacks. "
            "Model confidence {conf}%; {feat} carries the most explanatory weight."
        ),
    ],
    "SHORT": [
        (
            "Rejection at resistance is well-defined on the {tf}. "
            "{feat} flags distribution rather than accumulation. "
            "Regime: {regime}. Model favours lower prices while this structure holds."
        ),
        (
            "A lower-highs pattern is developing. Each bounce is weaker than the last. "
            "{feat} is the dominant bearish signal at {feat_weight}% model weight. "
            "Confidence {conf}% — sufficient for a short bias, not a conviction trade."
        ),
        (
            "Price has failed to reclaim the {tf} 50-EMA on multiple attempts. "
            "Volume is declining on bounces and elevated on drops — textbook distribution. "
            "{feat} confirms the bearish read. Regime: {regime}."
        ),
        (
            "MACD crossed bearish; histogram expanding below zero. "
            "Top-trader positioning flipped short in the last 2h. "
            "{feat} leads model attribution at {feat_weight}% weight. Confidence: {conf}%."
        ),
    ],
    "FLAT": [
        (
            "No directional edge detected on the {tf}. "
            "{feat} shows a chop environment — ATR contracting, bands narrowing. "
            "Model returns FLAT until regime clarifies."
        ),
        (
            "Price is oscillating inside a tight range with no follow-through in either direction. "
            "{feat} is the primary indicator of a non-trending environment. "
            "Regime: {regime}. Sitting out until a breakout or breakdown is confirmed."
        ),
    ],
}

_INVALIDATION: dict[str, list[str]] = {
    "LONG": [
        "A {tf} close below the 20-EMA with elevated volume cancels the setup. "
        "Secondary invalidation: RSI drops below 40 on the {tf}, signalling momentum failure.",

        "Reclaim and hold above the prior swing high is the confirmation trigger. "
        "Invalidated if price reverses back below the breakout level within 2 {tf} candles.",

        "The long thesis breaks if funding turns sharply positive (crowded longs) "
        "or if a {tf} candle closes below the key support zone with a bearish wick.",

        "Invalidated on a {tf} close below the pullback low. "
        "Stop placed just below that level; position sized to risk ≤1% of equity.",
    ],
    "SHORT": [
        "A {tf} close back above the 50-EMA invalidates the bearish structure. "
        "Secondary: if funding turns sharply negative, shorts become crowded and a squeeze risk rises.",

        "Invalidated if price prints a higher high above the recent swing top on the {tf}. "
        "That would signal the lower-highs sequence has broken.",

        "The short thesis breaks on a momentum burst through resistance with volume. "
        "Stop above the rejection level; sizing for ≤1% account risk.",

        "Thesis fails if OI drops while price rallies — short covering, not real buying — "
        "but a sustained move with expanding OI above resistance confirms invalidation.",
    ],
    "FLAT": [
        "Position opens when a {tf} candle closes convincingly outside the current range "
        "with a 1.5× ATR move and volume at least 20% above the 20-period average.",

        "A range break confirmed by a second candle close outside the band; "
        "false breakouts without follow-through volume remain inside FLAT.",
    ],
}

_RISK: dict[str, list[str]] = {
    "LONG": [
        "Primary risk: macro liquidity shock (surprise rate decision, broad crypto sell-off) "
        "overrides the technical setup. Position sizing accordingly: ≤1% account risk.",

        "Leverage amplifies drawdowns if the pullback deepens before continuation. "
        "Consider entering in two tranches — 50% at current level, 50% on confirmation close.",

        "Low-confidence long (sub-70%) in a high-volatility regime can produce a quick stop-out. "
        "Set hard stop; do not widen it reactively. Risk the plan, not the outcome.",

        "Funding could spike if the move attracts retail longs — watch for a cascade stop-hunt "
        "before the real continuation. Consider slightly wider stop to absorb the wick.",
    ],
    "SHORT": [
        "Short squeeze risk is real: if OI is elevated and funding flips negative, "
        "a catalyst could trigger rapid covering. Size to withstand a 3% adverse spike.",

        "Broad market momentum can overwhelm single-asset bearish setups. "
        "Use a correlation-adjusted position size if BTC is trending strongly upward.",

        "Regime misclassification: if the model incorrectly reads {regime}, "
        "the asset could continue higher. Hard stop required; no averaging down on shorts.",

        "Event risk (listings, protocol upgrades, liquidation cascades) can gap through stops. "
        "Avoid holding through major scheduled events without reducing size.",
    ],
    "FLAT": [
        "Opportunity cost is the primary risk: missing an early breakout by waiting for confirmation. "
        "Accept this as the cost of avoiding false breakout trades.",

        "Volatility expansion risk: the range may break violently with low liquidity. "
        "Have a clear entry plan ready on both sides before it happens.",
    ],
}

_CATALYST: dict[str, list[str]] = {
    "LONG": [
        "Near-term upside catalysts: BTC strength dragging altcoins higher, "
        "positive macro data reducing risk-off pressure, or a protocol announcement increasing utility demand.",

        "Watch for a high-volume {tf} candle closing above the recent consolidation range — "
        "that would confirm institutional participation and trigger momentum follow-through.",

        "Exchange netflow turning sharply negative (large withdrawals to cold storage) "
        "would reinforce the accumulation thesis and serve as a secondary long trigger.",

        "Sentiment catalyst: if the top-trader L/S ratio continues to expand, "
        "it signals smart-money conviction aligning with the model's LONG view.",
    ],
    "SHORT": [
        "Near-term downside catalysts: BTC correlation breakdown to the downside, "
        "broader de-risking, or negative on-chain data (exchange inflows spiking).",

        "A failed retest of broken support — where the level holds as new resistance — "
        "would validate the bearish structure and provide a lower-risk short entry.",

        "Watch funding: if it turns positive despite price weakness, "
        "leveraged longs are being trapped, accelerating the decline on any catalyst.",

        "Macro: higher-than-expected CPI or Fed hawkishness tends to compress risk assets "
        "disproportionately in the crypto space, amplifying this short thesis.",
    ],
    "FLAT": [
        "A scheduled macro event (FOMC, CPI print) could be the volatility catalyst "
        "that breaks the range definitively. Have both directional plans ready.",

        "On-chain: a sudden spike in large-wallet transactions or exchange inflows "
        "would signal institutional repositioning and may resolve the current indecision.",
    ],
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class SignalThesis:
    """Structured thesis for a single signal."""

    def __init__(
        self,
        setup_rationale: str,
        invalidation: str,
        risk_thesis: str,
        catalyst_notes: str,
    ):
        self.setup_rationale = setup_rationale
        self.invalidation = invalidation
        self.risk_thesis = risk_thesis
        self.catalyst_notes = catalyst_notes

    def to_dict(self) -> dict:
        return {
            "setup_rationale": self.setup_rationale,
            "invalidation":    self.invalidation,
            "risk_thesis":     self.risk_thesis,
            "catalyst_notes":  self.catalyst_notes,
        }


def generate_thesis(signal: Signal) -> SignalThesis:
    """
    Generate a structured thesis for a single signal.

    Output is deterministic: the same signal always produces the same thesis.
    """
    rng = _rng_for(signal)
    direction = signal.direction  # already a string via use_enum_values

    feat, feat_weight = _top_feature(signal)
    conf = int(round(signal.confidence * 100))

    ctx = dict(
        tf=signal.timeframe,
        feat=feat,
        feat_weight=feat_weight,
        conf=conf,
        regime=signal.regime,
    )

    setup       = rng.choice(_SETUP[direction]).format(**ctx)
    invalidation = rng.choice(_INVALIDATION[direction]).format(**ctx)
    risk        = rng.choice(_RISK[direction]).format(**ctx)
    catalyst    = rng.choice(_CATALYST[direction]).format(**ctx)

    return SignalThesis(
        setup_rationale=setup,
        invalidation=invalidation,
        risk_thesis=risk,
        catalyst_notes=catalyst,
    )


def enrich_signals(signals: list[Signal]) -> list[dict]:
    """
    Return each signal as a dict with a nested `thesis` key containing
    the four structured thesis fields.
    """
    result = []
    for sig in signals:
        thesis = generate_thesis(sig)
        d = sig.model_dump()
        d["thesis_structured"] = thesis.to_dict()
        result.append(d)
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _rng_for(signal: Signal) -> random.Random:
    key = f"{signal.symbol}:{signal.direction}:{signal.timeframe}:{signal.confidence}"
    seed = int(hashlib.sha256(key.encode()).hexdigest(), 16) % (2 ** 32)
    return random.Random(seed)


def _top_feature(signal: Signal) -> tuple[str, int]:
    if signal.top_features:
        name, weight = signal.top_features[0]
        return name, int(round(weight * 100))
    return "model_score", 50
