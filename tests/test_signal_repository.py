"""Tests for the signal repository layer (app/repositories/signal_repository.py)."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from app.repositories.signal_repository import (
    SignalSnapshot,
    _error_snapshot,
    _parse_snapshot,
    get_signals_from_file,
)


_VALID_SIGNAL = {
    "symbol": "ETH",
    "direction": "LONG",
    "timeframe": "15m",
    "confidence": 0.72,
    "regime": "uptrend",
    "thesis": "RSI reset from oversold.",
}


class TestErrorSnapshot:
    def test_returns_snapshot(self):
        snap = _error_snapshot("test", "something went wrong")
        assert isinstance(snap, SignalSnapshot)

    def test_status_is_error(self):
        snap = _error_snapshot("test", "boom")
        assert snap.status == "error"

    def test_signals_empty(self):
        snap = _error_snapshot("test", "boom")
        assert snap.signals == []

    def test_error_message_preserved(self):
        snap = _error_snapshot("test", "boom")
        assert snap.error_message == "boom"

    def test_source_preserved(self):
        snap = _error_snapshot("mysource", "x")
        assert snap.source == "mysource"


class TestParseSnapshot:
    def test_v2_object_format(self):
        raw = {
            "generated_at": "2026-05-01T12:00:00Z",
            "model_version": "xgboost-v1",
            "source": "sentinel",
            "signals": [_VALID_SIGNAL],
        }
        snap = _parse_snapshot(raw, "sentinel")
        assert len(snap.signals) == 1
        assert snap.generated_at == "2026-05-01T12:00:00Z"
        assert snap.model_version == "xgboost-v1"

    def test_v1_bare_array_format(self):
        snap = _parse_snapshot([_VALID_SIGNAL], "local_snapshot")
        assert len(snap.signals) == 1

    def test_invalid_record_skipped(self):
        bad = {"symbol": "BAD", "direction": "MAYBE", "confidence": 5.0, "regime": "x", "thesis": "y"}
        snap = _parse_snapshot({"signals": [_VALID_SIGNAL, bad]}, "test")
        assert len(snap.signals) == 1
        assert snap.signals[0].symbol == "ETH"

    def test_all_invalid_records_returns_empty_signals(self):
        bad = {"symbol": "X", "direction": "MAYBE", "confidence": 9.9, "regime": "x", "thesis": "y"}
        snap = _parse_snapshot({"signals": [bad]}, "test")
        assert snap.signals == []

    def test_empty_signals_array(self):
        snap = _parse_snapshot({"signals": []}, "test")
        assert snap.signals == []

    def test_status_ok(self):
        snap = _parse_snapshot([_VALID_SIGNAL], "local_snapshot")
        assert snap.status == "ok"

    def test_invalid_root_type_raises(self):
        with pytest.raises(ValueError):
            _parse_snapshot("not-a-dict-or-list", "test")

    def test_signals_key_not_a_list_raises(self):
        with pytest.raises(ValueError):
            _parse_snapshot({"signals": "should-be-a-list"}, "test")

    def test_source_falls_back_to_label(self):
        raw = {"signals": [_VALID_SIGNAL]}  # no "source" key
        snap = _parse_snapshot(raw, "my_label")
        assert snap.source == "my_label"

    def test_multiple_signals_all_parsed(self):
        raw = {"signals": [_VALID_SIGNAL, {**_VALID_SIGNAL, "symbol": "BTC"}]}
        snap = _parse_snapshot(raw, "test")
        assert len(snap.signals) == 2


class TestGetSignalsFromFile:
    def _write_snapshot(self, path: Path, data) -> None:
        path.write_text(json.dumps(data), encoding="utf-8")

    def test_valid_file_returns_ok(self, tmp_path):
        f = tmp_path / "signals.json"
        self._write_snapshot(f, {"signals": [_VALID_SIGNAL]})
        with patch("app.repositories.signal_repository.settings") as mock_cfg:
            mock_cfg.signal_file_path = str(f)
            snap = get_signals_from_file()
        assert snap.status == "ok"
        assert len(snap.signals) == 1

    def test_missing_file_returns_error(self):
        with patch("app.repositories.signal_repository.settings") as mock_cfg:
            mock_cfg.signal_file_path = "/nonexistent/path/signals.json"
            snap = get_signals_from_file()
        assert snap.status == "error"
        assert snap.signals == []

    def test_empty_path_returns_error(self):
        with patch("app.repositories.signal_repository.settings") as mock_cfg:
            mock_cfg.signal_file_path = ""
            snap = get_signals_from_file()
        assert snap.status == "error"

    def test_invalid_json_returns_error(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("not-json{{{", encoding="utf-8")
        with patch("app.repositories.signal_repository.settings") as mock_cfg:
            mock_cfg.signal_file_path = str(f)
            snap = get_signals_from_file()
        assert snap.status == "error"

    def test_empty_signals_array_returns_empty_status(self, tmp_path):
        f = tmp_path / "empty.json"
        self._write_snapshot(f, {"signals": []})
        with patch("app.repositories.signal_repository.settings") as mock_cfg:
            mock_cfg.signal_file_path = str(f)
            snap = get_signals_from_file()
        assert snap.status == "empty"
        assert snap.signals == []

    def test_v1_bare_array_accepted(self, tmp_path):
        f = tmp_path / "v1.json"
        self._write_snapshot(f, [_VALID_SIGNAL])
        with patch("app.repositories.signal_repository.settings") as mock_cfg:
            mock_cfg.signal_file_path = str(f)
            snap = get_signals_from_file()
        assert snap.status == "ok"
        assert len(snap.signals) == 1
