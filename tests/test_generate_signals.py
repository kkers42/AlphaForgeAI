"""Tests for the signal generation pipeline (scripts/generate_signals.py)."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

# Make the repo root importable so scripts/ can be reached
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.generate_signals import (
    ASSETS,
    TIMEFRAMES,
    _build_signal,
    _hour_bucket,
    _seed_rng,
    generate,
    main,
)


_NOW = datetime(2026, 5, 1, 14, 0, 0, tzinfo=timezone.utc)


class TestHourBucket:
    def test_returns_int(self):
        assert isinstance(_hour_bucket(_NOW), int)

    def test_same_hour_same_bucket(self):
        a = datetime(2026, 5, 1, 14, 0, 0, tzinfo=timezone.utc)
        b = datetime(2026, 5, 1, 14, 59, 59, tzinfo=timezone.utc)
        assert _hour_bucket(a) == _hour_bucket(b)

    def test_different_hour_different_bucket(self):
        a = datetime(2026, 5, 1, 14, 0, 0, tzinfo=timezone.utc)
        b = datetime(2026, 5, 1, 15, 0, 0, tzinfo=timezone.utc)
        assert _hour_bucket(a) != _hour_bucket(b)

    def test_different_day_different_bucket(self):
        a = datetime(2026, 5, 1, 14, 0, 0, tzinfo=timezone.utc)
        b = datetime(2026, 5, 2, 14, 0, 0, tzinfo=timezone.utc)
        assert _hour_bucket(a) != _hour_bucket(b)


class TestSeedRng:
    def test_same_inputs_same_sequence(self):
        bucket = _hour_bucket(_NOW)
        r1 = _seed_rng("BTC", bucket)
        r2 = _seed_rng("BTC", bucket)
        assert r1.random() == r2.random()

    def test_different_symbols_different_sequence(self):
        bucket = _hour_bucket(_NOW)
        r1 = _seed_rng("BTC", bucket)
        r2 = _seed_rng("ETH", bucket)
        assert r1.random() != r2.random()

    def test_different_buckets_different_sequence(self):
        r1 = _seed_rng("BTC", 1000)
        r2 = _seed_rng("BTC", 2000)
        assert r1.random() != r2.random()


class TestBuildSignal:
    def test_returns_required_keys(self):
        sig = _build_signal("ETH", _NOW)
        for key in ("symbol", "direction", "timeframe", "confidence", "regime", "thesis", "top_features"):
            assert key in sig, f"Missing key: {key}"

    def test_symbol_preserved(self):
        assert _build_signal("BTC", _NOW)["symbol"] == "BTC"

    def test_direction_valid(self):
        sig = _build_signal("ETH", _NOW)
        assert sig["direction"] in ("LONG", "SHORT", "FLAT")

    def test_timeframe_valid(self):
        sig = _build_signal("ETH", _NOW)
        assert sig["timeframe"] in TIMEFRAMES

    def test_confidence_long_range(self):
        # Sample many symbols to hit LONG direction and check range
        for symbol in ASSETS:
            sig = _build_signal(symbol, _NOW)
            if sig["direction"] == "LONG":
                assert 0.58 <= sig["confidence"] <= 0.85, sig

    def test_confidence_short_range(self):
        for symbol in ASSETS:
            sig = _build_signal(symbol, _NOW)
            if sig["direction"] == "SHORT":
                assert 0.55 <= sig["confidence"] <= 0.80, sig

    def test_confidence_flat_range(self):
        for symbol in ASSETS:
            sig = _build_signal(symbol, _NOW)
            if sig["direction"] == "FLAT":
                assert 0.40 <= sig["confidence"] <= 0.60, sig

    def test_top_features_is_list(self):
        sig = _build_signal("ETH", _NOW)
        assert isinstance(sig["top_features"], list)

    def test_top_features_count(self):
        sig = _build_signal("ETH", _NOW)
        assert 2 <= len(sig["top_features"]) <= 4

    def test_top_features_structure(self):
        sig = _build_signal("ETH", _NOW)
        for feat in sig["top_features"]:
            assert len(feat) == 2
            assert isinstance(feat[0], str)
            assert isinstance(feat[1], float)

    def test_deterministic_same_hour(self):
        a = _build_signal("SOL", _NOW)
        b = _build_signal("SOL", _NOW)
        assert a == b

    def test_different_hour_may_differ(self):
        t2 = datetime(2026, 5, 1, 15, 0, 0, tzinfo=timezone.utc)
        a = _build_signal("SOL", _NOW)
        b = _build_signal("SOL", t2)
        # Different hours use different seeds — very unlikely to be identical
        assert a != b


class TestGenerate:
    def test_returns_required_keys(self):
        snap = generate(asset_count=5)
        for key in ("generated_at", "model_version", "source", "signals"):
            assert key in snap

    def test_model_version(self):
        assert generate(asset_count=3)["model_version"] == "synthetic-v1"

    def test_source(self):
        assert generate(asset_count=3)["source"] == "generated"

    def test_generated_at_format(self):
        ts = generate(asset_count=3)["generated_at"]
        # Should parse as ISO 8601
        datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")

    def test_signal_count_respected(self):
        for n in (1, 5, 10):
            snap = generate(asset_count=n)
            assert len(snap["signals"]) == n

    def test_max_signal_count_capped_by_asset_universe(self):
        snap = generate(asset_count=1000)
        assert len(snap["signals"]) == len(ASSETS)

    def test_signals_are_valid_dicts(self):
        snap = generate(asset_count=5)
        for sig in snap["signals"]:
            assert sig["direction"] in ("LONG", "SHORT", "FLAT")
            assert 0.0 <= sig["confidence"] <= 1.0

    def test_deterministic_within_hour(self):
        a = generate(asset_count=8)
        b = generate(asset_count=8)
        assert a["signals"] == b["signals"]

    def test_json_serializable(self):
        snap = generate(asset_count=5)
        payload = json.dumps(snap)
        assert json.loads(payload)["model_version"] == "synthetic-v1"


class TestMain:
    def test_dry_run_prints_json(self, capsys):
        with patch("sys.argv", ["generate_signals.py", "--dry-run", "--assets", "3"]):
            main()
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data["signals"]) == 3

    def test_write_creates_file(self, tmp_path):
        snapshot_target = tmp_path / "signals_snapshot.json"
        with (
            patch("sys.argv", ["generate_signals.py", "--assets", "4"]),
            patch("scripts.generate_signals.SNAPSHOT_PATH", snapshot_target),
        ):
            main()
        assert snapshot_target.exists()
        data = json.loads(snapshot_target.read_text())
        assert len(data["signals"]) == 4
