from dataclasses import dataclass
from datetime import datetime, timezone

from app.core.config import settings


@dataclass(frozen=True)
class SignalStaleness:
    is_stale: bool
    action: str
    age_seconds: int | None
    stale_after_hours: int


def parse_utc_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
    except ValueError:
        return None


def evaluate_signal_staleness(generated_at: str | None) -> SignalStaleness:
    generated = parse_utc_timestamp(generated_at)
    age_seconds: int | None = None
    is_stale = False

    if generated and settings.signal_stale_after_hours > 0:
        age_seconds = max(
            int((datetime.now(timezone.utc) - generated).total_seconds()),
            0,
        )
        is_stale = age_seconds > settings.signal_stale_after_hours * 3600

    action = settings.signal_stale_action
    if action not in {"mark", "filter"}:
        action = "mark"

    return SignalStaleness(
        is_stale=is_stale,
        action=action,
        age_seconds=age_seconds,
        stale_after_hours=settings.signal_stale_after_hours,
    )
