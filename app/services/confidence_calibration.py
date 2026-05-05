from dataclasses import dataclass


@dataclass(frozen=True)
class CalibratedConfidence:
    percent: int
    label: str
    css_class: str


def normalize_percent(value: float | int | None) -> int:
    """
    Normalize confidence or feature importance to a 0-100 integer.

    Current snapshots store confidence as 0.0-1.0. This also accepts future
    0-100 values without double-scaling them.
    """
    if value is None:
        return 0

    numeric = float(value)
    if numeric <= 1:
        numeric *= 100

    return max(0, min(100, round(numeric)))


def calibrate_confidence(value: float | int | None) -> CalibratedConfidence:
    percent = normalize_percent(value)

    if percent >= 80:
        return CalibratedConfidence(percent=percent, label="High", css_class="high")
    if percent >= 65:
        return CalibratedConfidence(percent=percent, label="Medium", css_class="mid")
    return CalibratedConfidence(percent=percent, label="Low", css_class="low")


def confidence_percent(value: float | int | None) -> int:
    return calibrate_confidence(value).percent


def confidence_label(value: float | int | None) -> str:
    return calibrate_confidence(value).label


def confidence_css_class(value: float | int | None) -> str:
    return calibrate_confidence(value).css_class
