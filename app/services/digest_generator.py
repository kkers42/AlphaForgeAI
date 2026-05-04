"""
Daily Signal Digest Generator.

Produces three publish-ready artifacts from a snapshot of signals:

  1. market_summary   — overall market tone (bullish / bearish / mixed / neutral)
                        with signal counts and average confidence
  2. strongest_setups — top-N signals ranked by confidence, each with a
                        one-line headline and the full structured thesis
  3. digest_content   — a markdown-formatted blog/email body ready to publish

All output is deterministic for a given snapshot so the same signals always
produce the same digest.
"""

import hashlib
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from app.domain.signals import Direction, Signal
from app.services.thesis_generator import SignalThesis, generate_thesis


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class SetupSummary:
    signal: Signal
    headline: str
    thesis: SignalThesis


@dataclass
class MarketSummary:
    tone: str                 # "bullish" | "bearish" | "mixed" | "neutral"
    long_count: int
    short_count: int
    flat_count: int
    total: int
    avg_confidence: float
    top_regime: str
    summary_line: str


@dataclass
class SignalDigest:
    generated_at: str
    market_summary: MarketSummary
    strongest_setups: list[SetupSummary]
    digest_content: str       # publish-ready markdown


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_digest(signals: list[Signal], top_n: int = 5) -> SignalDigest:
    """
    Build a full daily digest from the provided signal list.

    Parameters
    ----------
    signals : list of Signal objects (from any provider)
    top_n   : number of top setups to feature (default: 5)

    Returns
    -------
    SignalDigest with market_summary, strongest_setups, and digest_content.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    market = _build_market_summary(signals)
    setups = _build_strongest_setups(signals, top_n)
    content = _render_digest(market, setups, now)

    return SignalDigest(
        generated_at=now,
        market_summary=market,
        strongest_setups=setups,
        digest_content=content,
    )


# ---------------------------------------------------------------------------
# Market summary
# ---------------------------------------------------------------------------

def _build_market_summary(signals: list[Signal]) -> MarketSummary:
    if not signals:
        return MarketSummary(
            tone="neutral",
            long_count=0,
            short_count=0,
            flat_count=0,
            total=0,
            avg_confidence=0.0,
            top_regime="unknown",
            summary_line="No signals available for today's digest.",
        )

    long_sigs  = [s for s in signals if s.direction == Direction.LONG]
    short_sigs = [s for s in signals if s.direction == Direction.SHORT]
    flat_sigs  = [s for s in signals if s.direction == Direction.FLAT]

    long_count  = len(long_sigs)
    short_count = len(short_sigs)
    flat_count  = len(flat_sigs)
    total       = len(signals)

    avg_conf = round(sum(s.confidence for s in signals) / total, 2)

    # Most common regime
    regime_counts: dict[str, int] = {}
    for s in signals:
        regime_counts[s.regime] = regime_counts.get(s.regime, 0) + 1
    top_regime = max(regime_counts, key=lambda r: regime_counts[r])

    # Market tone
    long_pct  = long_count / total
    short_pct = short_count / total
    if long_pct >= 0.55:
        tone = "bullish"
    elif short_pct >= 0.55:
        tone = "bearish"
    elif abs(long_pct - short_pct) <= 0.10:
        tone = "mixed"
    else:
        tone = "neutral"

    summary_line = _tone_summary(tone, long_count, short_count, flat_count, avg_conf, top_regime)

    return MarketSummary(
        tone=tone,
        long_count=long_count,
        short_count=short_count,
        flat_count=flat_count,
        total=total,
        avg_confidence=avg_conf,
        top_regime=top_regime,
        summary_line=summary_line,
    )


_TONE_LINES: dict[str, list[str]] = {
    "bullish": [
        "The model is leaning strongly long today with {longs} buy setups against {shorts} shorts. "
        "Dominant regime: {regime}. Average confidence sits at {conf}% — above the action threshold.",

        "{longs} of {total} signals are long-biased in a {regime} environment. "
        "Today's session favours trend-following long exposure over counter-trend plays.",
    ],
    "bearish": [
        "Bearish bias dominates with {shorts} short setups and only {longs} on the long side. "
        "Regime: {regime}. Model confidence averaging {conf}% — proceed with defined risk.",

        "The model is leaning short: {shorts} signals flagged for downside against {longs} longs. "
        "In a {regime} environment, the path of least resistance is lower.",
    ],
    "mixed": [
        "Today's signals are split — {longs} long, {shorts} short, {flats} flat — in a {regime} market. "
        "No strong directional edge. Selective, high-confidence setups only.",

        "Mixed read: equal weighting across directions with a {regime} backdrop. "
        "Average confidence {conf}%. Focus on the highest-conviction setups only.",
    ],
    "neutral": [
        "{flats} of {total} signals are FLAT with {longs} long and {shorts} short. "
        "The model sees limited edge in current conditions. Patience is a position.",

        "Regime unclear. {flats} FLAT signals, {longs} long, {shorts} short. "
        "Average confidence {conf}%. Waiting for clearer structure before deploying size.",
    ],
}


def _tone_summary(
    tone: str,
    longs: int,
    shorts: int,
    flats: int,
    conf: float,
    regime: str,
) -> str:
    total = longs + shorts + flats
    templates = _TONE_LINES[tone]
    # Deterministic selection from tone + counts
    key = f"{tone}:{longs}:{shorts}:{flats}"
    idx = int(hashlib.sha256(key.encode()).hexdigest(), 16) % len(templates)
    return templates[idx].format(
        longs=longs,
        shorts=shorts,
        flats=flats,
        total=total,
        conf=int(round(conf * 100)),
        regime=regime,
    )


# ---------------------------------------------------------------------------
# Strongest setups
# ---------------------------------------------------------------------------

def _build_strongest_setups(signals: list[Signal], top_n: int) -> list[SetupSummary]:
    # Only directional (non-FLAT) signals qualify as "setups"
    directional = [s for s in signals if s.direction != Direction.FLAT]
    directional.sort(key=lambda s: s.confidence, reverse=True)
    top = directional[:top_n]

    return [
        SetupSummary(
            signal=sig,
            headline=_headline(sig),
            thesis=generate_thesis(sig),
        )
        for sig in top
    ]


_HEADLINE_LONG = [
    "{symbol} ({tf}) — LONG at {conf}% confidence | {regime}",
    "Buy setup: {symbol} {tf} — {conf}% model conviction | {regime} regime",
    "{symbol} long signal on the {tf} | confidence {conf}% | {regime}",
]
_HEADLINE_SHORT = [
    "{symbol} ({tf}) — SHORT at {conf}% confidence | {regime}",
    "Short setup: {symbol} {tf} — {conf}% model conviction | {regime} regime",
    "{symbol} short signal on the {tf} | confidence {conf}% | {regime}",
]


def _headline(sig: Signal) -> str:
    key = f"{sig.symbol}:{sig.direction}:{sig.timeframe}"
    seed = int(hashlib.sha256(key.encode()).hexdigest(), 16) % (2 ** 32)
    rng = random.Random(seed)
    pool = _HEADLINE_LONG if sig.direction == Direction.LONG else _HEADLINE_SHORT
    template = rng.choice(pool)
    return template.format(
        symbol=sig.symbol,
        tf=sig.timeframe,
        conf=int(round(sig.confidence * 100)),
        regime=sig.regime,
    )


# ---------------------------------------------------------------------------
# Digest rendering (markdown)
# ---------------------------------------------------------------------------

def _render_digest(
    market: MarketSummary,
    setups: list[SetupSummary],
    generated_at: str,
) -> str:
    date_str = generated_at[:10]  # "YYYY-MM-DD"
    lines: list[str] = [
        f"# AlphaForge Signal Digest — {date_str}",
        "",
        "## Market Overview",
        "",
        f"**Tone:** {market.tone.upper()}  ",
        f"**Signals:** {market.long_count} long · {market.short_count} short · {market.flat_count} flat  ",
        f"**Avg Confidence:** {int(round(market.avg_confidence * 100))}%  ",
        f"**Dominant Regime:** {market.top_regime}  ",
        "",
        market.summary_line,
        "",
        "---",
        "",
        "## Strongest Setups",
        "",
    ]

    if not setups:
        lines.append("*No directional setups meet the confidence threshold today.*")
    else:
        for i, setup in enumerate(setups, start=1):
            sig = setup.signal
            t = setup.thesis
            lines += [
                f"### {i}. {setup.headline}",
                "",
                f"**Setup Rationale:** {t.setup_rationale}",
                "",
                f"**Invalidation:** {t.invalidation}",
                "",
                f"**Risk:** {t.risk_thesis}",
                "",
                f"**Catalyst Watch:** {t.catalyst_notes}",
                "",
            ]

    lines += [
        "---",
        "",
        f"*Generated by AlphaForgeAI — {generated_at} — model: synthetic-v1*",
        "*Not financial advice. For research and entertainment purposes only.*",
    ]

    return "\n".join(lines)
