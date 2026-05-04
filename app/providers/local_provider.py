"""Local-snapshot signal provider — reads data/signals_snapshot.json."""

import json
import logging
from pathlib import Path

from app.repositories.signal_repository import (
    SignalSnapshot,
    _error_snapshot,
    _parse_snapshot,
)

log = logging.getLogger(__name__)

_SNAPSHOT_PATH = Path(__file__).resolve().parents[2] / "data" / "signals_snapshot.json"
_SOURCE = "local_snapshot"


def get_signals() -> SignalSnapshot:
    """Load and validate signals from the local snapshot file."""
    try:
        with open(_SNAPSHOT_PATH, encoding="utf-8") as fh:
            raw = json.load(fh)
    except FileNotFoundError:
        log.warning(
            "event=provider_load provider=local error=file_not_found path=%s",
            _SNAPSHOT_PATH,
        )
        return _error_snapshot(_SOURCE, "Snapshot file not found")
    except json.JSONDecodeError as exc:
        log.warning(
            "event=provider_load provider=local error=invalid_json exc=%s", exc
        )
        return _error_snapshot(_SOURCE, "Invalid JSON in snapshot file")
    except OSError as exc:
        log.warning(
            "event=provider_load provider=local error=io_error exc=%s", exc
        )
        return _error_snapshot(_SOURCE, f"I/O error: {exc}")

    try:
        snapshot = _parse_snapshot(raw, _SOURCE)
    except ValueError as exc:
        log.warning(
            "event=provider_load provider=local error=malformed_payload exc=%s", exc
        )
        return _error_snapshot(_SOURCE, f"Malformed snapshot: {exc}")

    if not snapshot.signals:
        log.info("event=provider_load provider=local status=empty")
        from dataclasses import replace
        return replace(snapshot, status="empty")

    log.info(
        "event=provider_load provider=local status=ok signal_count=%d "
        "model=%s generated_at=%s",
        len(snapshot.signals),
        snapshot.model_version or "unknown",
        snapshot.generated_at or "unknown",
    )
    return snapshot
