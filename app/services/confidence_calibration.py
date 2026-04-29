from dataclasses import dataclass


@dataclass(frozen=True)
class CalibratedConfidence:
    percent: int
    label: str
    css_class: str


def normalize_percent(value: float | int | None) -> int:
    """
    Normalize confidence or feature importance to a 0-100 integer.

    Current snapshots store confidence as a 0.0–1.0 float. This function also
    accepts future 0–100 values without double-scaling them.

    The boundary value 1 (integer or float) is treated as 100% — i.e. the
    maximum of the 0-1 scale — not as 1%. This mirrors the assumption that any
    value <= 1 belongs to the fractional scale and must be multiplied by 100.

    Migration ambiguity risk: once callers begin supplying values on the 0–100
    scale the threshold ``<= 1`` becomes a trap. A stored value of ``1`` will
    still be interpreted as 100% (correct), but any value in the range (1, 100]
    will pass through unchanged (also correct) while a value of exactly ``1``
    that was genuinely meant to represent 1% on the new scale will be silently
    inflated to 100%. Before switching data sources to the 0–100 scale, ensure
    that no source can produce a value of ``1`` meaning "1 percent"; if
    necessary, replace the ``<= 1`` guard with an explicit scale parameter or a
    sentinel that forces the caller to declare which scale is in use.
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
