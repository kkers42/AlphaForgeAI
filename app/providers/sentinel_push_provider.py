"""sentinel_push provider — reads from GCS-mounted snapshot, source-labelled as sentinel_push."""

import json
import logging

from app.core.config import settings
from app.repositories.signal_repository import (
    SignalSnapshot,
    _error_snapshot,
    _parse_snapshot,
)

log = logging.getLogger(__name__)

_SOURCE = "sentinel_push"


def get_signals() -> SignalSnapshot:
    """Load signals from the GCS-mounted snapshot file (same path as file provider)."""
    path = settings.signal_file_path
    if not path:
        log.warning("event=provider_load provider=sentinel_push error=path_not_set")
        return _error_snapshot(_SOURCE, "SIGNAL_FILE_PATH is not configured")

    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except FileNotFoundError:
        log.warning("event=provider_load provider=sentinel_push error=file_not_found path=%s", path)
        return _error_snapshot(_SOURCE, f"Signal file not found: {path}")
    except json.JSONDecodeError as exc:
        log.warning("event=provider_load provider=sentinel_push error=invalid_json exc=%s", exc)
        return _error_snapshot(_SOURCE, "Invalid JSON in signal file")
    except OSError as exc:
        log.warning("event=provider_load provider=sentinel_push error=io_error exc=%s", exc)
        return _error_snapshot(_SOURCE, f"I/O error: {exc}")

    try:
        snapshot = _parse_snapshot(raw, _SOURCE)
    except ValueError as exc:
        log.warning("event=provider_load provider=sentinel_push error=malformed_payload exc=%s", exc)
        return _error_snapshot(_SOURCE, f"Malformed snapshot: {exc}")

    if not snapshot.signals:
        log.info("event=provider_load provider=sentinel_push status=empty path=%s", path)
        from dataclasses import replace
        return replace(snapshot, status="empty")

    log.info(
        "event=provider_load provider=sentinel_push status=ok signal_count=%d "
        "model=%s generated_at=%s",
        len(snapshot.signals),
        snapshot.model_version or "unknown",
        snapshot.generated_at or "unknown",
    )
    return snapshot
