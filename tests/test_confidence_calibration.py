import unittest

from app.services.confidence_calibration import (
    calibrate_confidence,
    normalize_percent,
)


class ConfidenceCalibrationTests(unittest.TestCase):
    def test_normalizes_fractional_confidence_to_percent(self) -> None:
        self.assertEqual(normalize_percent(0.74), 74)

    def test_accepts_existing_percent_scale(self) -> None:
        self.assertEqual(normalize_percent(82), 82)

    def test_clamps_to_percent_bounds(self) -> None:
        self.assertEqual(normalize_percent(-0.5), 0)
        self.assertEqual(normalize_percent(120), 100)

    def test_confidence_thresholds_are_standardized(self) -> None:
        self.assertEqual(calibrate_confidence(0.80).label, "High")
        self.assertEqual(calibrate_confidence(0.65).label, "Medium")
        self.assertEqual(calibrate_confidence(0.64).label, "Low")


if __name__ == "__main__":
    unittest.main()
