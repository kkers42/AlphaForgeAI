"""Tests for the multi-timeframe confluence engine."""

import pytest

from app.domain.signals import Direction, Signal, Timeframe
from app.services.confluence_engine import evaluate_confluence, filter_confluent, _elevate


def _sig(symbol="ETH", direction="LONG", timeframe="15m", confidence=0.70, regime="uptrend"):
    return Signal(
        symbol=symbol,
        direction=direction,
        timeframe=timeframe,
        confidence=confidence,
        regime=regime,
        thesis="Test thesis.",
    )


class TestElevate:
    def test_single_signal_returns_unchanged(self):
        sig = _sig()
        result = _elevate([sig])
        assert len(result) == 1
        assert result[0].confluence is None

    def test_full_confluence_three_timeframes(self):
        sigs = [
            _sig(timeframe="5m",  confidence=0.65),
            _sig(timeframe="15m", confidence=0.70),
            _sig(timeframe="1h",  confidence=0.72),
        ]
        result = _elevate(sigs)
        assert len(result) == 1
        assert result[0].confluence == "full"

    def test_full_confluence_picks_highest_confidence(self):
        sigs = [
            _sig(timeframe="5m",  confidence=0.65),
            _sig(timeframe="15m", confidence=0.80),
            _sig(timeframe="1h",  confidence=0.72),
        ]
        result = _elevate(sigs)
        # Primary is the 15m (highest raw), boosted by 0.10
        assert result[0].confidence == min(round(0.80 + 0.10, 2), 0.95)

    def test_full_confluence_confidence_capped_at_0_95(self):
        sigs = [
            _sig(timeframe="5m",  confidence=0.90),
            _sig(timeframe="15m", confidence=0.91),
            _sig(timeframe="1h",  confidence=0.92),
        ]
        result = _elevate(sigs)
        assert result[0].confidence == 0.95

    def test_partial_confluence_two_timeframes(self):
        sigs = [
            _sig(timeframe="5m",  confidence=0.65),
            _sig(timeframe="15m", confidence=0.70),
            _sig(timeframe="1h",  confidence=0.60, direction="SHORT"),
        ]
        result = _elevate(sigs)
        assert len(result) == 1
        assert result[0].confluence == "partial"

    def test_partial_confidence_boost(self):
        sigs = [
            _sig(timeframe="5m",  confidence=0.70),
            _sig(timeframe="15m", confidence=0.75),
            _sig(timeframe="1h",  confidence=0.60, direction="SHORT"),
        ]
        result = _elevate(sigs)
        assert result[0].confidence == min(round(0.75 + 0.05, 2), 0.90)

    def test_partial_confluence_capped_at_0_90(self):
        sigs = [
            _sig(timeframe="5m",  confidence=0.88),
            _sig(timeframe="15m", confidence=0.88),
            _sig(timeframe="1h",  confidence=0.60, direction="SHORT"),
        ]
        result = _elevate(sigs)
        assert result[0].confidence == 0.90

    def test_no_confluence_different_directions(self):
        sigs = [
            _sig(timeframe="5m",  direction="LONG",  confidence=0.70),
            _sig(timeframe="15m", direction="SHORT", confidence=0.70),
            _sig(timeframe="1h",  direction="FLAT",  confidence=0.50),
        ]
        result = _elevate(sigs)
        # One direction per TF, no majority — returns all unchanged
        assert all(s.confluence is None for s in result)

    def test_all_flat_no_confluence(self):
        sigs = [
            _sig(timeframe="5m",  direction="FLAT", confidence=0.50),
            _sig(timeframe="15m", direction="FLAT", confidence=0.52),
        ]
        result = _elevate(sigs)
        assert all(s.confluence is None for s in result)

    def test_confluence_timeframes_field_set(self):
        sigs = [
            _sig(timeframe="5m",  confidence=0.65),
            _sig(timeframe="15m", confidence=0.70),
            _sig(timeframe="1h",  confidence=0.72),
        ]
        result = _elevate(sigs)
        assert set(result[0].confluence_timeframes) == {"5m", "15m", "1h"}


class TestEvaluateConfluence:
    def test_single_timeframe_signals_pass_through(self):
        sigs = [_sig("ETH", timeframe="15m"), _sig("BTC", timeframe="15m")]
        result = evaluate_confluence(sigs)
        assert len(result) == 2
        assert all(s.confluence is None for s in result)

    def test_4h_signals_pass_through_untouched(self):
        sig = _sig("BTC", timeframe="4h")
        result = evaluate_confluence([sig])
        assert len(result) == 1
        assert result[0].confluence is None
        assert result[0].timeframe == "4h"

    def test_multi_symbol_each_evaluated_independently(self):
        sigs = [
            _sig("ETH", timeframe="5m",  confidence=0.70),
            _sig("ETH", timeframe="15m", confidence=0.72),
            _sig("ETH", timeframe="1h",  confidence=0.68),
            _sig("BTC", timeframe="5m",  confidence=0.65, direction="SHORT"),
            _sig("BTC", timeframe="15m", confidence=0.67, direction="SHORT"),
            _sig("BTC", timeframe="1h",  confidence=0.63, direction="SHORT"),
        ]
        result = evaluate_confluence(sigs)
        # Should collapse to one elevated signal per symbol
        assert len(result) == 2
        symbols = {s.symbol for s in result}
        assert symbols == {"ETH", "BTC"}
        for s in result:
            assert s.confluence == "full"

    def test_mixed_confluent_and_non_confluent(self):
        sigs = [
            # ETH: full confluence
            _sig("ETH", timeframe="5m",  confidence=0.70),
            _sig("ETH", timeframe="15m", confidence=0.72),
            _sig("ETH", timeframe="1h",  confidence=0.68),
            # SOL: single TF only
            _sig("SOL", timeframe="15m", confidence=0.65),
        ]
        result = evaluate_confluence(sigs)
        eth = next(s for s in result if s.symbol == "ETH")
        sol = next(s for s in result if s.symbol == "SOL")
        assert eth.confluence == "full"
        assert sol.confluence is None

    def test_empty_input(self):
        assert evaluate_confluence([]) == []


class TestFilterConfluent:
    def test_keeps_only_confluent(self):
        sigs = [
            _sig("ETH", timeframe="5m",  confidence=0.70),
            _sig("ETH", timeframe="15m", confidence=0.72),
            _sig("ETH", timeframe="1h",  confidence=0.68),
            _sig("BTC", timeframe="15m", confidence=0.65),
        ]
        evaluated = evaluate_confluence(sigs)
        filtered = filter_confluent(evaluated)
        assert all(s.confluence is not None for s in filtered)
        symbols = {s.symbol for s in filtered}
        assert "ETH" in symbols
        assert "BTC" not in symbols

    def test_empty_when_no_confluence(self):
        sigs = [_sig("ETH", timeframe="15m")]
        evaluated = evaluate_confluence(sigs)
        assert filter_confluent(evaluated) == []
