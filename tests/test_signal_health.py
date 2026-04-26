import json
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.repositories.signal_repository import SNAPSHOT_SCHEMA_VERSION


def _snapshot() -> dict:
    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "generated_at": "2026-04-26T20:00:00Z",
        "model_version": "test-model",
        "source": "generated",
        "signal_count": 1,
        "signals": [
            {
                "symbol": "ETH",
                "direction": "LONG",
                "timeframe": "15m",
                "confidence": 0.72,
                "regime": "uptrend",
                "thesis": "Test signal.",
                "top_features": [["rsi_14", 0.22]],
            }
        ],
    }


class SignalHealthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self._settings = {
            "signal_provider": settings.signal_provider,
            "signal_file_path": settings.signal_file_path,
            "signal_freshness_warn_hours": settings.signal_freshness_warn_hours,
        }
        self._allow_mock_fallback = os.environ.get("ALLOW_MOCK_FALLBACK")

    def tearDown(self) -> None:
        settings.signal_provider = self._settings["signal_provider"]
        settings.signal_file_path = self._settings["signal_file_path"]
        settings.signal_freshness_warn_hours = self._settings["signal_freshness_warn_hours"]
        if self._allow_mock_fallback is None:
            os.environ.pop("ALLOW_MOCK_FALLBACK", None)
        else:
            os.environ["ALLOW_MOCK_FALLBACK"] = self._allow_mock_fallback

    def test_health_reports_valid_file_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "latest.json"
            path.write_text(json.dumps(_snapshot()), encoding="utf-8")
            settings.signal_provider = "file"
            settings.signal_file_path = str(path)

            response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ok")
        self.assertTrue(body["signal_engine"]["healthy"])
        self.assertEqual(body["signal_engine"]["snapshot"]["status"], "ok")
        self.assertEqual(body["signal_engine"]["signal_count"], 1)
        self.assertEqual(body["signal_engine"]["last_generated_at"], "2026-04-26T20:00:00Z")

    def test_health_reports_mock_provider_without_snapshot_requirement(self) -> None:
        settings.signal_provider = "mock"
        settings.signal_file_path = ""

        body = self.client.get("/health/signals").json()

        self.assertEqual(body["engine"]["status"], "ok")
        self.assertEqual(body["engine"]["snapshot"]["status"], "not_required")
        self.assertTrue(body["engine"]["healthy"])

    def test_health_reports_unhealthy_when_file_missing_and_fallback_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings.signal_provider = "file"
            settings.signal_file_path = str(Path(tmp) / "missing.json")
            os.environ["ALLOW_MOCK_FALLBACK"] = "false"

            response = self.client.get("/health")

        body = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["status"], "unhealthy")
        self.assertFalse(body["signal_engine"]["healthy"])
        self.assertFalse(body["signal_engine"]["snapshot"]["present"])
        self.assertIn("Signal file not found", body["signal_engine"]["error"])


if __name__ == "__main__":
    unittest.main()
