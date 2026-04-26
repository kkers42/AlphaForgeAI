import json
import tempfile
import unittest
from pathlib import Path

from app.core.config import settings
from app.repositories.signal_repository import (
    SNAPSHOT_SCHEMA_VERSION,
    validate_snapshot_payload,
    write_snapshot_atomic,
)
from app.services.signal_service import get_signals


def _valid_snapshot(symbol: str = "ETH") -> dict:
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "generated_at": "2026-04-26T20:00:00Z",
        "model_version": "test-model",
        "source": "generated",
        "signal_count": 1,
        "signals": [
            {
                "symbol": symbol,
                "direction": "LONG",
                "timeframe": "15m",
                "confidence": 0.72,
                "regime": "uptrend",
                "thesis": "Test signal.",
                "top_features": [["rsi_14", 0.22]],
            }
        ],
    }


class SnapshotPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._original = {
            "signal_provider": settings.signal_provider,
            "signal_file_path": settings.signal_file_path,
        }

    def tearDown(self) -> None:
        settings.signal_provider = self._original["signal_provider"]
        settings.signal_file_path = self._original["signal_file_path"]

    def test_valid_snapshot_schema_parses_metadata(self) -> None:
        snapshot = validate_snapshot_payload(_valid_snapshot(), "file")

        self.assertEqual(snapshot.status, "ok")
        self.assertEqual(snapshot.source, "generated")
        self.assertEqual(snapshot.schema_version, SNAPSHOT_SCHEMA_VERSION)
        self.assertEqual(snapshot.signal_count, 1)
        self.assertEqual(snapshot.generated_at, "2026-04-26T20:00:00Z")

    def test_persisted_snapshot_requires_schema_when_requested(self) -> None:
        snapshot = _valid_snapshot()
        snapshot.pop("schema_version")

        with self.assertRaises(ValueError):
            validate_snapshot_payload(snapshot, "file", require_schema=True)

    def test_atomic_write_keeps_existing_snapshot_when_validation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "latest.json"
            original = _valid_snapshot("ETH")
            replacement = _valid_snapshot("SOL")
            replacement["signal_count"] = 2

            write_snapshot_atomic(original, path)

            with self.assertRaises(ValueError):
                write_snapshot_atomic(replacement, path)

            persisted = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["signal_count"], 1)
            self.assertEqual(persisted["signals"][0]["symbol"], "ETH")

    def test_missing_file_provider_uses_mock_fallback_in_development(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings.signal_provider = "file"
            settings.signal_file_path = str(Path(tmp) / "missing.json")

            snapshot = get_signals()

            self.assertEqual(snapshot.status, "fallback")
            self.assertEqual(snapshot.source, "mock_fallback")
            self.assertTrue(snapshot.used_mock_fallback)
            self.assertGreater(len(snapshot.signals), 0)
            self.assertIn("Signal file not found", snapshot.error_message or "")


if __name__ == "__main__":
    unittest.main()
