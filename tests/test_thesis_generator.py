"""Tests for the signal thesis generator."""

import pytest

from app.domain.signals import Direction, Signal, Timeframe
from app.services.thesis_generator import (
    SignalThesis,
    _rng_for,
    _top_feature,
    enrich_signals,
    generate_thesis,
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
        top_features=top_features or [("rsi_14", 0.18), ("macd_hist", 0.12)],
    )


class TestRngFor:
    def test_same_signal_same_rng_sequence(self):
        sig = _sig()
        r1 = _rng_for(sig)
        r2 = _rng_for(sig)
        assert r1.random() == r2.random()

    def test_different_symbol_different_rng(self):
        r1 = _rng_for(_sig(symbol="ETH"))
        r2 = _rng_for(_sig(symbol="BTC"))
        assert r1.random() != r2.random()

    def test_different_confidence_different_rng(self):
        r1 = _rng_for(_sig(confidence=0.70))
        r2 = _rng_for(_sig(confidence=0.80))
        assert r1.random() != r2.random()


class TestTopFeature:
    def test_returns_first_feature(self):
        sig = _sig(top_features=[("rsi_14", 0.18), ("macd_hist", 0.12)])
        name, weight = _top_feature(sig)
        assert name == "rsi_14"
        assert weight == 18

    def test_no_features_returns_fallback(self):
        sig = Signal(
            symbol="ETH", direction="LONG", timeframe="15m",
            confidence=0.72, regime="uptrend", thesis="x",
        )
        name, weight = _top_feature(sig)
        assert name == "model_score"
        assert weight == 50

    def test_weight_converted_to_percent(self):
        sig = _sig(top_features=[("vol_ratio", 0.25)])
        _, weight = _top_feature(sig)
        assert weight == 25


class TestGenerateThesis:
    @pytest.mark.parametrize("direction", ["LONG", "SHORT", "FLAT"])
    def test_returns_signal_thesis(self, direction):
        sig = _sig(direction=direction)
        result = generate_thesis(sig)
        assert isinstance(result, SignalThesis)

    @pytest.mark.parametrize("direction", ["LONG", "SHORT", "FLAT"])
    def test_all_fields_non_empty(self, direction):
        sig = _sig(direction=direction)
        t = generate_thesis(sig)
        assert t.setup_rationale
        assert t.invalidation
        assert t.risk_thesis
        assert t.catalyst_notes

    def test_deterministic_for_same_signal(self):
        sig = _sig()
        t1 = generate_thesis(sig)
        t2 = generate_thesis(sig)
        assert t1.setup_rationale == t2.setup_rationale
        assert t1.invalidation == t2.invalidation
        assert t1.risk_thesis == t2.risk_thesis
        assert t1.catalyst_notes == t2.catalyst_notes

    def test_different_signals_may_differ(self):
        t1 = generate_thesis(_sig(symbol="ETH"))
        t2 = generate_thesis(_sig(symbol="BTC"))
        # Very unlikely to be identical
        assert t1.setup_rationale != t2.setup_rationale or t1.invalidation != t2.invalidation

    def test_timeframe_appears_in_output(self):
        sig = _sig(timeframe="1h")
        t = generate_thesis(sig)
        combined = t.setup_rationale + t.invalidation + t.risk_thesis + t.catalyst_notes
        assert "1h" in combined

    def test_no_unfilled_placeholders(self):
        for direction in ["LONG", "SHORT", "FLAT"]:
            sig = _sig(direction=direction)
            t = generate_thesis(sig)
            for field in (t.setup_rationale, t.invalidation, t.risk_thesis, t.catalyst_notes):
                assert "{" not in field, f"Unfilled placeholder in: {field}"

    def test_to_dict_keys(self):
        t = generate_thesis(_sig())
        d = t.to_dict()
        assert set(d.keys()) == {"setup_rationale", "invalidation", "risk_thesis", "catalyst_notes"}


class TestEnrichSignals:
    def test_returns_list_of_dicts(self):
        result = enrich_signals([_sig()])
        assert isinstance(result, list)
        assert isinstance(result[0], dict)

    def test_thesis_structured_key_present(self):
        result = enrich_signals([_sig()])
        assert "thesis_structured" in result[0]

    def test_thesis_structured_has_four_fields(self):
        structured = enrich_signals([_sig()])[0]["thesis_structured"]
        assert set(structured.keys()) == {
            "setup_rationale", "invalidation", "risk_thesis", "catalyst_notes"
        }

    def test_original_signal_fields_preserved(self):
        sig = _sig(symbol="SOL", confidence=0.77)
        result = enrich_signals([sig])[0]
        assert result["symbol"] == "SOL"
        assert result["confidence"] == 0.77

    def test_empty_list_returns_empty(self):
        assert enrich_signals([]) == []

    def test_multiple_signals_each_enriched(self):
        sigs = [_sig("ETH"), _sig("BTC"), _sig("SOL")]
        result = enrich_signals(sigs)
        assert len(result) == 3
        for r in result:
            assert "thesis_structured" in r
