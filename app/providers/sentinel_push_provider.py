"""
sentinel_push provider — reads the live signal snapshot from GCS.

The Sentinel AI bot pushes a v1 snapshot every 15 min via
``POST /api/signals/ingest``.  That endpoint writes to GCS.
This provider reads from the same GCS object so all Cloud Run instances
see identical, up-to-date signal data regardless of which instance serves a request.

Fallback chain
--------------
1. GCS download (primary — always authoritative)
2. Local file at SIGNAL_FILE_PATH (cold-start / GCS unavailable)
"""

import logging

from app.core.config import settings
from app.repositories.signal_repository import (
    SignalSnapshot,
    _error_snapshot,
    _parse_snapshot,
)
from app.services import gcs_signals

log = logging.getLogger(__name__)

_SOURCE = "sentinel_push"


def get_signals() -> SignalSnapshot:
    """Load signals from GCS, falling back to the local file if GCS is unavailable."""
    bucket = settings.gcs_signals_bucket

    # 1. Try GCS (primary)
    raw = gcs_signals.download_snapshot(bucket_name=bucket)

    # 2. Fall back to local file (cold-start / GCS unavailable)
    if raw is None:
        local_path = settings.signal_file_path
        if local_path:
            import json
            try:
                with open(local_path, encoding="utf-8") as fh:
                    raw = json.load(fh)
                log.info(
                    "event=provider_load provider=sentinel_push source=local_file path=%s",
                    local_path,
                )
            except Exception as exc:
                log.warning(
                    "event=provider_load provider=sentinel_push source=local_file error=%s", exc
                )

    if raw is None:
        log.warning("event=provider_load provider=sentinel_push error=no_data_available")
        return _error_snapshot(_SOURCE, "No signal data available (GCS empty, no local fallback)")

    try:
        snapshot = _parse_snapshot(raw, _SOURCE)
    except ValueError as exc:
        log.warning(
            "event=provider_load provider=sentinel_push error=malformed_payload exc=%s", exc
        )
        return _error_snapshot(_SOURCE, f"Malformed snapshot: {exc}")

    if not snapshot.signals:
        log.info("event=provider_load provider=sentinel_push status=empty")
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
