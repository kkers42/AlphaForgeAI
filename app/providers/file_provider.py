"""File-based signal provider — loads signals from SIGNAL_FILE_PATH."""

import json
import logging

from app.core.config import settings
from app.repositories.signal_repository import (
    SignalSnapshot,
    _error_snapshot,
    _parse_snapshot,
)

log = logging.getLogger(__name__)

_SOURCE = "file"


def get_signals() -> SignalSnapshot:
    """Load and validate signals from the file at settings.signal_file_path."""
    path = settings.signal_file_path
    if not path:
        log.warning("event=provider_load provider=file error=path_not_set")
        return _error_snapshot(_SOURCE, "SIGNAL_FILE_PATH is not configured")

    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except FileNotFoundError:
        log.warning("event=provider_load provider=file error=file_not_found path=%s", path)
        return _error_snapshot(_SOURCE, f"Signal file not found: {path}")
    except json.JSONDecodeError as exc:
        log.warning("event=provider_load provider=file error=invalid_json path=%s exc=%s", path, exc)
        return _error_snapshot(_SOURCE, "Invalid JSON in signal file")
    except OSError as exc:
        log.warning("event=provider_load provider=file error=io_error path=%s exc=%s", path, exc)
        return _error_snapshot(_SOURCE, f"I/O error: {exc}")

    try:
        snapshot = _parse_snapshot(raw, _SOURCE)
    except ValueError as exc:
        log.warning("event=provider_load provider=file error=malformed_payload exc=%s", exc)
        return _error_snapshot(_SOURCE, f"Malformed snapshot: {exc}")

    if not snapshot.signals:
        log.info("event=provider_load provider=file status=empty path=%s", path)
        from dataclasses import replace
        return replace(snapshot, status="empty")

    log.info(
        "event=provider_load provider=file status=ok signal_count=%d "
        "model=%s generated_at=%s",
        len(snapshot.signals),
        snapshot.model_version or "unknown",
        snapshot.generated_at or "unknown",
    )
    return snapshot
