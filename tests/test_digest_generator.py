"""Tests for the daily signal digest generator."""

import pytest

from app.domain.signals import Direction, Signal, Timeframe
from app.services.digest_generator import (
    MarketSummary,
    SetupSummary,
    SignalDigest,
    _build_market_summary,
    _build_strongest_setups,
    _headline,
    _render_digest,
    generate_digest,
)


def _sig(
    symbol="ETH",
    direction="LONG",
    timeframe="15m",
    confidence=0.74,
    regime="uptrend",
    top_features=None,
):
    return Signal(
        symbol=symbol,
        direction=direction,
        timeframe=timeframe,
        confidence=confidence,
        regime=regime,
        thesis="Original thesis.",
        top_features=top_features or [("rsi_14", 0.18)],
    )


_LONG_SIGS = [
    _sig("ETH", "LONG", confidence=0.80),
    _sig("SOL", "LONG", confidence=0.75),
    _sig("INJ", "LONG", confidence=0.72),
    _sig("AVAX", "LONG", confidence=0.68),
]
_SHORT_SIGS = [
    _sig("DOGE", "SHORT", confidence=0.63, regime="downtrend"),
]
_FLAT_SIGS = [
    _sig("BTC", "FLAT", confidence=0.51, regime="ranging"),
]
_MIXED = _LONG_SIGS + _SHORT_SIGS + _FLAT_SIGS


class TestBuildMarketSummary:
    def test_empty_signals_neutral(self):
        m = _build_market_summary([])
        assert m.tone == "neutral"
        assert m.total == 0

    def test_counts_correct(self):
        m = _build_market_summary(_MIXED)
        assert m.long_count == 4
        assert m.short_count == 1
        assert m.flat_count == 1
        assert m.total == 6

    def test_bullish_tone_when_long_dominant(self):
        sigs = [_sig(direction="LONG")] * 6 + [_sig(direction="SHORT")] * 2
        m = _build_market_summary(sigs)
        assert m.tone == "bullish"

    def test_bearish_tone_when_short_dominant(self):
        sigs = [_sig(direction="SHORT")] * 6 + [_sig(direction="LONG")] * 2
        m = _build_market_summary(sigs)
        assert m.tone == "bearish"

    def test_mixed_tone_when_balanced(self):
        sigs = [_sig(direction="LONG")] * 3 + [_sig(direction="SHORT")] * 3
        m = _build_market_summary(sigs)
        assert m.tone == "mixed"

    def test_avg_confidence_computed(self):
        sigs = [_sig(confidence=0.60), _sig(confidence=0.80)]
        m = _build_market_summary(sigs)
        assert m.avg_confidence == pytest.approx(0.70, abs=0.01)

    def test_top_regime_most_common(self):
        sigs = [
            _sig(regime="uptrend"),
            _sig(regime="uptrend"),
            _sig(regime="ranging"),
        ]
        m = _build_market_summary(sigs)
        assert m.top_regime == "uptrend"

    def test_summary_line_non_empty(self):
        m = _build_market_summary(_MIXED)
        assert len(m.summary_line) > 10

    def test_summary_line_deterministic(self):
        m1 = _build_market_summary(_MIXED)
        m2 = _build_market_summary(_MIXED)
        assert m1.summary_line == m2.summary_line


class TestBuildStrongestSetups:
    def test_returns_list_of_setup_summary(self):
        result = _build_strongest_setups(_MIXED, top_n=3)
        assert all(isinstance(s, SetupSummary) for s in result)

    def test_top_n_respected(self):
        result = _build_strongest_setups(_MIXED, top_n=3)
        assert len(result) <= 3

    def test_sorted_by_confidence_descending(self):
        result = _build_strongest_setups(_MIXED, top_n=10)
        confidences = [s.signal.confidence for s in result]
        assert confidences == sorted(confidences, reverse=True)

    def test_flat_signals_excluded(self):
        result = _build_strongest_setups(_FLAT_SIGS + _LONG_SIGS, top_n=10)
        for s in result:
            assert s.signal.direction != "FLAT"

    def test_empty_signals_returns_empty(self):
        assert _build_strongest_setups([], top_n=5) == []

    def test_all_flat_returns_empty(self):
        assert _build_strongest_setups(_FLAT_SIGS, top_n=5) == []

    def test_thesis_is_populated(self):
        result = _build_strongest_setups(_LONG_SIGS, top_n=2)
        for s in result:
            assert s.thesis.setup_rationale
            assert s.thesis.invalidation

    def test_headline_non_empty(self):
        result = _build_strongest_setups(_LONG_SIGS, top_n=2)
        for s in result:
            assert len(s.headline) > 5


class TestHeadline:
    def test_contains_symbol(self):
        h = _headline(_sig(symbol="ETH"))
        assert "ETH" in h

    def test_contains_timeframe(self):
        h = _headline(_sig(timeframe="1h"))
        assert "1h" in h

    def test_long_headline_no_short_words(self):
        h = _headline(_sig(direction="LONG"))
        assert "SHORT" not in h

    def test_short_headline_no_long_buy_words(self):
        h = _headline(_sig(direction="SHORT"))
        assert "LONG" not in h

    def test_deterministic(self):
        sig = _sig()
        assert _headline(sig) == _headline(sig)


class TestRenderDigest:
    def _market(self):
        return _build_market_summary(_MIXED)

    def _setups(self):
        return _build_strongest_setups(_MIXED, top_n=3)

    def test_returns_string(self):
        result = _render_digest(self._market(), self._setups(), "2026-05-01T12:00:00Z")
        assert isinstance(result, str)

    def test_contains_date(self):
        result = _render_digest(self._market(), self._setups(), "2026-05-01T12:00:00Z")
        assert "2026-05-01" in result

    def test_contains_market_overview_header(self):
        result = _render_digest(self._market(), self._setups(), "2026-05-01T12:00:00Z")
        assert "## Market Overview" in result

    def test_contains_strongest_setups_header(self):
        result = _render_digest(self._market(), self._setups(), "2026-05-01T12:00:00Z")
        assert "## Strongest Setups" in result

    def test_contains_disclaimer(self):
        result = _render_digest(self._market(), self._setups(), "2026-05-01T12:00:00Z")
        assert "Not financial advice" in result

    def test_empty_setups_placeholder(self):
        result = _render_digest(self._market(), [], "2026-05-01T12:00:00Z")
        assert "No directional setups" in result


class TestGenerateDigest:
    def test_returns_signal_digest(self):
        result = generate_digest(_MIXED)
        assert isinstance(result, SignalDigest)

    def test_generated_at_set(self):
        result = generate_digest(_MIXED)
        assert result.generated_at

    def test_market_summary_populated(self):
        result = generate_digest(_MIXED)
        assert result.market_summary.total == len(_MIXED)

    def test_strongest_setups_limited(self):
        result = generate_digest(_MIXED, top_n=2)
        assert len(result.strongest_setups) <= 2

    def test_digest_content_is_string(self):
        result = generate_digest(_MIXED)
        assert isinstance(result.digest_content, str)
        assert len(result.digest_content) > 100

    def test_empty_signals(self):
        result = generate_digest([])
        assert result.market_summary.tone == "neutral"
        assert result.strongest_setups == []

    def test_digest_content_contains_symbol_of_top_setup(self):
        result = generate_digest(_MIXED, top_n=1)
        if result.strongest_setups:
            symbol = result.strongest_setups[0].signal.symbol
            assert symbol in result.digest_content
