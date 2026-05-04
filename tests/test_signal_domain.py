"""Tests for the Signal domain model (app/domain/signals.py)."""

import pytest
from pydantic import ValidationError

from app.domain.signals import Direction, Signal, Timeframe


class TestDirection:
    def test_values(self):
        assert Direction.LONG == "LONG"
        assert Direction.SHORT == "SHORT"
        assert Direction.FLAT == "FLAT"

    def test_all_members(self):
        assert set(Direction) == {Direction.LONG, Direction.SHORT, Direction.FLAT}


class TestTimeframe:
    def test_values(self):
        assert Timeframe.M15 == "15m"
        assert Timeframe.H1 == "1h"
        assert Timeframe.H4 == "4h"


class TestSignalValidation:
    _valid = dict(
        symbol="ETH",
        direction="LONG",
        timeframe="15m",
        confidence=0.72,
        regime="uptrend",
        thesis="RSI reset from oversold.",
    )

    def test_valid_signal_parses(self):
        s = Signal(**self._valid)
        assert s.symbol == "ETH"
        assert s.direction == "LONG"
        assert s.confidence == 0.72

    def test_confidence_lower_bound(self):
        s = Signal(**{**self._valid, "confidence": 0.0})
        assert s.confidence == 0.0

    def test_confidence_upper_bound(self):
        s = Signal(**{**self._valid, "confidence": 1.0})
        assert s.confidence == 1.0

    def test_confidence_below_zero_rejected(self):
        with pytest.raises(ValidationError):
            Signal(**{**self._valid, "confidence": -0.01})

    def test_confidence_above_one_rejected(self):
        with pytest.raises(ValidationError):
            Signal(**{**self._valid, "confidence": 1.01})

    def test_invalid_direction_rejected(self):
        with pytest.raises(ValidationError):
            Signal(**{**self._valid, "direction": "MAYBE"})

    def test_invalid_timeframe_rejected(self):
        with pytest.raises(ValidationError):
            Signal(**{**self._valid, "timeframe": "5m"})

    def test_top_features_optional(self):
        s = Signal(**self._valid)
        assert s.top_features is None

    def test_top_features_accepted(self):
        feats = [("rsi_14", 0.18), ("macd_hist", 0.12)]
        s = Signal(**{**self._valid, "top_features": feats})
        assert s.top_features == feats

    def test_model_validate_from_dict(self):
        s = Signal.model_validate(self._valid)
        assert s.symbol == "ETH"

    def test_missing_required_field_rejected(self):
        data = dict(self._valid)
        del data["symbol"]
        with pytest.raises(ValidationError):
            Signal(**data)

    @pytest.mark.parametrize("direction", ["LONG", "SHORT", "FLAT"])
    def test_all_directions_accepted(self, direction):
        s = Signal(**{**self._valid, "direction": direction})
        assert s.direction == direction

    @pytest.mark.parametrize("timeframe", ["15m", "1h", "4h"])
    def test_all_timeframes_accepted(self, timeframe):
        s = Signal(**{**self._valid, "timeframe": timeframe})
        assert s.timeframe == timeframe
