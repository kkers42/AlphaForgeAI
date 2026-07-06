"""Tests for the source-aware publisher modules."""

import pytest
from app.publisher.evidence_builder import (
    build_evidence,
    AlphaForgeSignal,
    Evidence,
    _infer_risk_factors,
)
from app.publisher.seo_scorer import score_blog_post, score_x_post
from app.publisher.x_post_generator import generate_x_posts, _trim_tweet


# ── Fixtures ──────────────────────────────────────────────────────────────────

MOCK_SNAPSHOT = {
    "generated_at": "2026-07-06T11:00:00Z",
    "signal_count": 3,
    "is_stale": False,
    "signals": [
        {
            "symbol": "BTC",
            "direction": "LONG",
            "confidence": 0.86,
            "regime": "bullish",
            "timeframe": "1h",
            "thesis": "BTC reclaimed momentum band. Volume improving. Funding neutral.",
            "confluence": "full",
        },
        {
            "symbol": "ETH",
            "direction": "LONG",
            "confidence": 0.74,
            "regime": "uptrend",
            "timeframe": "4h",
            "thesis": "ETH volume expanding above average. L/S turning bullish.",
            "confluence": "partial",
        },
        {
            "symbol": "SOL",
            "direction": "SHORT",
            "confidence": 0.61,
            "regime": "downtrend",
            "timeframe": "1h",
            "thesis": "SOL showing distribution. OI elevated.",
            "confluence": None,
        },
    ],
}

STALE_SNAPSHOT = {**MOCK_SNAPSHOT, "is_stale": True}


# ── EvidenceBuilder tests ─────────────────────────────────────────────────────

def test_build_evidence_from_signals():
    ev = build_evidence(
        signals_snapshot=MOCK_SNAPSHOT,
        fetch_market_data=False,
    )
    assert len(ev.alphaforge_signals) == 3
    assert ev.market_tone == "bullish"  # 2 LONG vs 1 SHORT → bullish
    assert "AlphaForge ML signal engine" in ev.sources_used
    assert ev.asset == "BTC"
    assert ev.direction == "long"
    assert "BTC" in ev.top_assets_by_confidence


def test_build_evidence_stale_signals_excluded():
    ev = build_evidence(
        signals_snapshot=STALE_SNAPSHOT,
        fetch_market_data=False,
    )
    # Stale signals should be excluded
    assert len(ev.alphaforge_signals) == 0
    assert ev.market_tone == "neutral"


def test_build_evidence_no_snapshot():
    ev = build_evidence(
        signals_snapshot=None,
        fetch_market_data=False,
    )
    assert len(ev.alphaforge_signals) == 0
    assert ev.asset is None


def test_evidence_to_dict():
    ev = build_evidence(signals_snapshot=MOCK_SNAPSHOT, fetch_market_data=False)
    d = ev.to_dict()
    assert "alphaforge_signals" in d
    assert "market_data" in d
    assert "risk_factors" in d
    assert "sources" in d
    assert "market_tone" in d
    assert d["market_tone"] == "bullish"
    assert len(d["alphaforge_signals"]) == 3


def test_evidence_market_tone_bearish():
    snapshot = {
        **MOCK_SNAPSHOT,
        "signals": [
            {"symbol": "BTC", "direction": "SHORT", "confidence": 0.80, "regime": "bearish", "timeframe": "1h", "thesis": "test", "confluence": None},
            {"symbol": "ETH", "direction": "SHORT", "confidence": 0.75, "regime": "bearish", "timeframe": "4h", "thesis": "test", "confluence": None},
            {"symbol": "SOL", "direction": "LONG", "confidence": 0.55, "regime": "ranging", "timeframe": "1h", "thesis": "test", "confluence": None},
        ]
    }
    ev = build_evidence(signals_snapshot=snapshot, fetch_market_data=False)
    assert ev.market_tone == "bearish"


def test_risk_factors_generated():
    ev = build_evidence(signals_snapshot=MOCK_SNAPSHOT, fetch_market_data=False)
    assert len(ev.risk_factors) > 0
    assert isinstance(ev.risk_factors[0], str)


# ── SEO scorer tests ──────────────────────────────────────────────────────────

GOOD_ARTICLE = """
# Why Is Bitcoin Going Up Today? AlphaForge Signal Turns Bullish

**Market Status: Bullish.** Bitcoin is showing renewed momentum as AlphaForge's ML signal engine
registers a BUY with 86% confidence in a bullish regime. Volume is expanding above average
and funding rates remain neutral.

## Market Overview

The overall market tone is bullish. AlphaForge sees 2 long signals vs 1 short.

## What Is Moving

**Bitcoin ($BTC):** AlphaForge signal — BUY, 86% confidence, bullish regime, full confluence.
Price is recovering with improving volume.

## Risk Factors

- High-confidence signals may indicate crowded positioning — monitor for funding overheating.
- Resistance near recent highs could invalidate the bullish thesis.

## Closing Note

Setup is strong but risk management is non-negotiable.

This post is for informational purposes only and does not constitute financial advice.

## Sources & Confidence

Data used: AlphaForge ML signal engine, CoinGecko market data
Confidence level: High
Reason: Signal supported by model confidence and full confluence.
"""

GENERIC_ARTICLE = """
# Daily Crypto Market Update

The crypto market is moving today. Bitcoin and Ethereum are showing some changes.
Prices are fluctuating. In conclusion, it is important to note that markets can go up or down.
As an AI, I cannot predict the future.
"""


def test_good_article_scores_above_threshold():
    result = score_blog_post(
        title="Why Is Bitcoin Going Up Today? AlphaForge Signal Turns Bullish",
        content=GOOD_ARTICLE,
        has_alphaforge_data=True,
    )
    assert result.passed
    assert result.score >= 80


def test_generic_article_fails_threshold():
    result = score_blog_post(
        title="Daily Crypto Market Update",
        content=GENERIC_ARTICLE,
        has_alphaforge_data=False,
    )
    assert not result.passed
    assert result.score < 80


def test_generic_title_penalized():
    result = score_blog_post(
        title="Daily Crypto Market Update",
        content=GOOD_ARTICLE,
        has_alphaforge_data=True,
    )
    assert result.breakdown["title_search_intent"] == 0
    assert "generic" in " ".join(result.feedback).lower()


def test_missing_sources_section():
    result = score_blog_post(
        title="Why Is Bitcoin Going Up Today?",
        content="Bitcoin is showing bullish signals. AlphaForge: BUY, 86% confidence, bullish regime. Volume expanding. Risk: funding may overheat.",
        has_alphaforge_data=True,
    )
    assert result.breakdown["sources_section"] == 0


def test_ai_language_penalized():
    result = score_blog_post(
        title="Bitcoin Analysis Today",
        content="In conclusion, it is worth noting that as an AI I cannot predict markets. Bitcoin shows bullish signals with AlphaForge confidence at 86%.",
        has_alphaforge_data=True,
    )
    assert result.breakdown["ai_language_penalty"] < 0


# ── X post scorer ─────────────────────────────────────────────────────────────

GOOD_X_POST = """Bitcoin Signal Update

AlphaForge: BUY
Confidence: 86%
Regime: bullish

BTC reclaimed momentum band with improving volume and neutral funding.

Risk: High-confidence signals may indicate crowded positioning.

$BTC #Bitcoin"""

def test_good_x_post_passes():
    result = score_x_post(GOOD_X_POST, has_alphaforge_data=True)
    assert result.passed
    assert result.score >= 80


def test_too_many_hashtags_penalized():
    text = "Bitcoin is bullish #BTC #Crypto #Bitcoin #AlphaForge #Trading $BTC"
    result = score_x_post(text, has_alphaforge_data=False)
    assert result.breakdown["hashtag_count"] < 15


# ── X post generator tests ────────────────────────────────────────────────────

def test_generate_x_posts_with_signal():
    ev = build_evidence(signals_snapshot=MOCK_SNAPSHOT, fetch_market_data=False)
    posts = generate_x_posts(
        evidence=ev,
        article_title="Why Is Bitcoin Going Up Today?",
        article_slug="why-is-bitcoin-going-up-today-2026-07-06",
    )
    assert posts.signal_card
    assert posts.hook
    assert posts.risk_aware
    # All variants should mention BTC (top confidence signal)
    assert "BTC" in posts.signal_card or "Bitcoin" in posts.signal_card
    # All under 280 chars
    assert len(posts.signal_card) <= 280
    assert len(posts.hook) <= 280
    assert len(posts.risk_aware) <= 280


def test_generate_x_posts_no_signals():
    ev = build_evidence(signals_snapshot=None, fetch_market_data=False)
    posts = generate_x_posts(
        evidence=ev,
        article_title="Crypto Market Update",
        article_slug="crypto-market-update-2026-07-06",
    )
    # Should still produce something
    assert posts.signal_card
    assert len(posts.signal_card) <= 280


def test_trim_tweet_respects_limit():
    long_text = "a" * 300
    trimmed = _trim_tweet(long_text)
    assert len(trimmed) <= 280
    assert trimmed.endswith("...")


def test_trim_tweet_short_passthrough():
    short_text = "Hello world $BTC"
    assert _trim_tweet(short_text) == short_text


def test_x_posts_to_dict():
    ev = build_evidence(signals_snapshot=MOCK_SNAPSHOT, fetch_market_data=False)
    posts = generate_x_posts(evidence=ev, article_title="Test", article_slug="test-2026-07-06")
    d = posts.to_dict()
    assert "signal_card" in d
    assert "hook" in d
    assert "risk_aware" in d
