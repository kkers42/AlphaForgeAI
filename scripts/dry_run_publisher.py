"""
Dry-run script: demonstrate a complete source-aware publisher output for BTC.

Usage:
    python scripts/dry_run_publisher.py

Shows:
  - Evidence object (AlphaForge signals + market data + risk factors)
  - Claude prompt that would be sent to generate the blog post
  - 3 X post variants
  - SEO score on a sample article

No API calls are made to blog ingest or tweet service — read-only demo.
"""

import json
import sys
import os
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.publisher.evidence_builder import build_evidence, AlphaForgeSignal, Evidence
from app.publisher.x_post_generator import generate_x_posts
from app.publisher.seo_scorer import score_blog_post, score_x_post

# ── Mock signals (as if from /api/signals/snapshot) ─────────────────────────

MOCK_SNAPSHOT = {
    "generated_at": "2026-07-06T11:00:00Z",
    "signal_count": 5,
    "is_stale": False,
    "signals": [
        {
            "symbol": "BTC",
            "direction": "LONG",
            "confidence": 0.86,
            "regime": "bullish",
            "timeframe": "1h",
            "thesis": "BTC reclaimed the short-term momentum band with improving volume and neutral funding. RSI reset from oversold. Dominant regime: bullish trend.",
            "confluence": "full",
        },
        {
            "symbol": "ETH",
            "direction": "LONG",
            "confidence": 0.74,
            "regime": "uptrend",
            "timeframe": "4h",
            "thesis": "ETH volume expanding above 20-session average. L/S ratio turning bullish. Stochastic exiting oversold.",
            "confluence": "partial",
        },
        {
            "symbol": "SOL",
            "direction": "SHORT",
            "confidence": 0.61,
            "regime": "downtrend",
            "timeframe": "1h",
            "thesis": "SOL showing distribution pattern with declining volume on bounces. OI elevated — squeeze risk if price breaks support.",
            "confluence": None,
        },
        {
            "symbol": "INJ",
            "direction": "LONG",
            "confidence": 0.79,
            "regime": "bullish",
            "timeframe": "4h",
            "thesis": "INJ breaking above consolidation range with strong volume confirmation. Regime: bullish.",
            "confluence": "partial",
        },
        {
            "symbol": "AVAX",
            "direction": "FLAT",
            "confidence": 0.55,
            "regime": "ranging",
            "timeframe": "1h",
            "thesis": "AVAX consolidating. No directional edge. Wait for breakout with volume confirmation.",
            "confluence": None,
        },
    ],
}

# ── Build evidence ────────────────────────────────────────────────────────────

print("=" * 60)
print("STEP 1: Building Evidence Object")
print("=" * 60)

evidence = build_evidence(
    signals_snapshot=MOCK_SNAPSHOT,
    fetch_market_data=True,
    symbols=["BTC", "ETH", "SOL"],
)

ev_dict = evidence.to_dict()
print(json.dumps(ev_dict, indent=2))

# ── Claude prompt preview ─────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("STEP 2: Claude Prompt (what n8n would send)")
print("=" * 60)

def build_claude_prompt(ev: Evidence, date: str) -> str:
    sig_lines = []
    for s in ev.alphaforge_signals[:5]:
        conf_pct = int(round(s.confidence * 100))
        conf_line = f"  - {s.symbol}: {s.direction} | {conf_pct}% confidence | Regime: {s.regime} | Confluence: {s.confluence or 'none'}"
        sig_lines.append(conf_line)

    mkt_lines = []
    for sym, mkt in ev.market_data.items():
        if mkt.price:
            price_str = f"${mkt.price:,.0f}" if mkt.price > 100 else f"${mkt.price:.4f}"
            change_str = f" ({mkt.change_24h:+.1f}% 24h)" if mkt.change_24h is not None else ""
            mkt_lines.append(f"  - {sym}: {price_str}{change_str}")

    risk_lines = "\n".join(f"  - {r}" for r in ev.risk_factors)

    return f"""Date: {date}
Market Tone (AlphaForge): {ev.market_tone.upper()}

AlphaForge Signals (Tier 1 — proprietary data):
{chr(10).join(sig_lines) if sig_lines else '  - No signals available'}

Market Data (Tier 3 — CoinGecko):
{chr(10).join(mkt_lines) if mkt_lines else '  - Market data unavailable'}

Risk Factors:
{risk_lines}

Sources used: {', '.join(ev.sources_used)}

Write a daily market brief that:
1. States market direction clearly (Bullish/Bearish/Neutral) in the first paragraph
2. Covers BTC and ETH with specific signal data and market data
3. Includes AlphaForge signal confidence and regime for each asset mentioned
4. Includes a 'Sources & Confidence' section at the end
5. Uses search-intent title format (e.g. 'Why Is Bitcoin Going Up Today?')
6. Length: 500-800 words
7. Do not make unsupported claims — only reference data provided above
"""

prompt = build_claude_prompt(evidence, "2026-07-06")
print(prompt)

# ── X post variants ───────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("STEP 3: X Post Variants")
print("=" * 60)

posts = generate_x_posts(
    evidence=evidence,
    article_title="Why Is Bitcoin Going Up Today? AlphaForge Signal Turns Bullish",
    article_slug="why-is-bitcoin-going-up-today-alphaforge-signal-turns-bullish-2026-07-06",
)

print("\n--- VARIANT 1: Signal Card ---")
print(posts.signal_card)
print(f"\nLength: {len(posts.signal_card)} chars")

print("\n--- VARIANT 2: Hook Post ---")
print(posts.hook)
print(f"\nLength: {len(posts.hook)} chars")

print("\n--- VARIANT 3: Risk-Aware ---")
print(posts.risk_aware)
print(f"\nLength: {len(posts.risk_aware)} chars")

# ── SEO score on sample article ───────────────────────────────────────────────

print("\n" + "=" * 60)
print("STEP 4: SEO Score — Sample Article")
print("=" * 60)

SAMPLE_ARTICLE = """
# Why Is Bitcoin Going Up Today? AlphaForge Signal Turns Bullish

**Market Status: Bullish**

Bitcoin is showing renewed momentum today as AlphaForge's ML signal engine
registers a BUY signal with 86% confidence in a bullish regime. Volume is
expanding above the 20-session average, and funding rates remain neutral —
a constructive combination that historically precedes continuation moves.

## Market Overview

The overall market tone is bullish. AlphaForge sees 3 long signals against 1 short
and 1 flat, with average confidence at 71%. BTC is the highest-conviction setup.

## What Is Moving

**Bitcoin ($BTC):** AlphaForge signal — BUY, 86% confidence, bullish regime, full
confluence across 3 timeframes. Price is recovering with improving volume.

**Ethereum ($ETH):** AlphaForge signal — BUY, 74% confidence, uptrend regime.
Volume is expanding above the 20-session average.

## Key Stories

Funding rates remain neutral across major venues — a bullish signal in itself.
When price rises without funding overheating, the move tends to be structurally
stronger than leverage-driven pumps.

## Risk Factors

- High-confidence signals may indicate crowded positioning — watch for mean
  reversion if funding overheats.
- Resistance near recent highs — a rejection here would invalidate the bullish thesis.

## Closing Note

The setup is strong, but risk management is non-negotiable. Size positions
for the risk, not for the conviction.

---

*This post is for informational purposes only and does not constitute financial advice.*

## Sources & Confidence

Data used:
- AlphaForge ML signal engine (BUY, 86% confidence)
- AlphaForge regime detector (bullish)
- CoinGecko market data
- AlphaForge confluence engine

Confidence level: High

The signal is supported by model confidence, improving volume, full confluence,
and neutral funding. Risk remains if price rejects resistance or funding overheats.
"""

score = score_blog_post(
    title="Why Is Bitcoin Going Up Today? AlphaForge Signal Turns Bullish",
    content=SAMPLE_ARTICLE,
    has_alphaforge_data=True,
)

print(f"\nScore: {score.score}/100  |  {'PASS' if score.passed else 'FAIL'}")
print("Breakdown:", json.dumps(score.breakdown, indent=2))
if score.feedback:
    print("Feedback:")
    for f in score.feedback:
        print(f"  - {f}")
else:
    print("  No issues found — content meets threshold.")

# ── X post score ──────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("STEP 5: X Post Score — Signal Card Variant")
print("=" * 60)

x_score = score_x_post(posts.signal_card, has_alphaforge_data=True)
print(f"\nScore: {x_score.score}/100  |  {'PASS' if x_score.passed else 'FAIL'}")
if x_score.feedback:
    for f in x_score.feedback:
        print(f"  - {f}")
else:
    print("  No issues — X post meets threshold.")

print("\n" + "=" * 60)
print("Dry run complete.")
print("=" * 60)
