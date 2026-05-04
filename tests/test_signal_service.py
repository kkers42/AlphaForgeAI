"""Tests for the signal service layer (app/services/signal_service.py)."""

from unittest.mock import patch, MagicMock

import pytest

from app.domain.signals import Signal, Direction, Timeframe
from app.repositories.signal_repository import SignalSnapshot
from app.services.signal_service import get_mock_signals, get_signals


_MOCK_SIGNAL = Signal(
    symbol="ETH",
    direction=Direction.LONG,
    timeframe=Timeframe.M15,
    confidence=0.75,
    regime="uptrend",
    thesis="Test thesis.",
)

_OK_SNAPSHOT = SignalSnapshot(signals=[_MOCK_SIGNAL], source="file", status="ok")
_EMPTY_SNAPSHOT = SignalSnapshot(signals=[], source="file", status="empty")
_ERROR_SNAPSHOT = SignalSnapshot(signals=[], source="file", status="error", error_message="load failed")


class TestGetMockSignals:
    def test_returns_list(self):
        result = get_mock_signals()
        assert isinstance(result, list)

    def test_all_items_are_signals(self):
        for sig in get_mock_signals():
            assert isinstance(sig, Signal)

    def test_non_empty(self):
        assert len(get_mock_signals()) > 0

    def test_confidence_in_range(self):
        for sig in get_mock_signals():
            assert 0.0 <= sig.confidence <= 1.0

    def test_directions_valid(self):
        valid = {"LONG", "SHORT", "FLAT"}
        for sig in get_mock_signals():
            assert sig.direction in valid


class TestGetSignalsMockProvider:
    def _patch_settings(self, provider="mock", environment="development", allow_fallback=True):
        mock_cfg = MagicMock()
        mock_cfg.signal_provider = provider
        mock_cfg.environment = environment
        mock_cfg.allow_mock_fallback = allow_fallback
        mock_cfg.signal_confluence = False
        return patch("app.services.signal_service.settings", mock_cfg)

    def test_mock_provider_returns_signals(self):
        with self._patch_settings(provider="mock"):
            snap = get_signals()
        assert len(snap.signals) > 0

    def test_mock_provider_source_is_mock(self):
        with self._patch_settings(provider="mock"):
            snap = get_signals()
        assert snap.source == "mock"

    def test_mock_provider_no_mock_fallback_flag(self):
        with self._patch_settings(provider="mock"):
            snap = get_signals()
        assert snap.used_mock_fallback is False

    def test_mock_provider_status_ok(self):
        with self._patch_settings(provider="mock"):
            snap = get_signals()
        assert snap.status == "ok"


class TestGetSignalsFileProvider:
    def _setup(self, snapshot, allow_fallback=True):
        mock_cfg = MagicMock()
        mock_cfg.signal_provider = "file"
        mock_cfg.environment = "development"
        mock_cfg.allow_mock_fallback = allow_fallback
        mock_cfg.signal_confluence = False
        return (
            patch("app.services.signal_service.settings", mock_cfg),
            patch("app.providers.file_provider.get_signals", return_value=snapshot),
        )

    def test_ok_snapshot_returned_as_is(self):
        p1, p2 = self._setup(_OK_SNAPSHOT)
        with p1, p2:
            snap = get_signals()
        assert snap.signals == [_MOCK_SIGNAL]
        assert snap.source == "file"

    def test_empty_snapshot_with_fallback_returns_mocks(self):
        p1, p2 = self._setup(_EMPTY_SNAPSHOT, allow_fallback=True)
        with p1, p2:
            snap = get_signals()
        assert snap.used_mock_fallback is True
        assert snap.source == "mock_fallback"
        assert len(snap.signals) > 0

    def test_empty_snapshot_without_fallback_returns_empty(self):
        p1, p2 = self._setup(_EMPTY_SNAPSHOT, allow_fallback=False)
        with p1, p2:
            snap = get_signals()
        assert snap.signals == []
        assert snap.used_mock_fallback is False

    def test_error_snapshot_with_fallback_uses_mock(self):
        p1, p2 = self._setup(_ERROR_SNAPSHOT, allow_fallback=True)
        with p1, p2:
            snap = get_signals()
        assert snap.used_mock_fallback is True

    def test_error_snapshot_without_fallback_returns_empty(self):
        p1, p2 = self._setup(_ERROR_SNAPSHOT, allow_fallback=False)
        with p1, p2:
            snap = get_signals()
        assert snap.signals == []
        assert snap.status == "error"

    def test_fallback_preserves_original_error_message(self):
        p1, p2 = self._setup(_ERROR_SNAPSHOT, allow_fallback=True)
        with p1, p2:
            snap = get_signals()
        assert snap.error_message == "load failed"
