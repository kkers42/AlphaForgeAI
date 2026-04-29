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

    def test_normalize_percent_none_returns_zero(self) -> None:
        self.assertEqual(normalize_percent(None), 0)

    def test_normalize_percent_zero_float_returns_zero(self) -> None:
        self.assertEqual(normalize_percent(0.0), 0)

    def test_normalize_percent_one_float_returns_hundred(self) -> None:
        self.assertEqual(normalize_percent(1.0), 100)

    def test_normalize_percent_one_int_returns_hundred(self) -> None:
        self.assertEqual(normalize_percent(1), 100)

    def test_calibrate_confidence_css_class_high(self) -> None:
        self.assertEqual(calibrate_confidence(0.80).css_class, "high")

    def test_calibrate_confidence_css_class_mid(self) -> None:
        self.assertEqual(calibrate_confidence(0.65).css_class, "mid")

    def test_calibrate_confidence_css_class_low(self) -> None:
        self.assertEqual(calibrate_confidence(0.64).css_class, "low")


if __name__ == "__main__":
    unittest.main()
