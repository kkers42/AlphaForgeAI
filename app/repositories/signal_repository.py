"""
Signal repository — local JSON snapshot source.

Loads signal records from a local JSON file, validates each record into
the Signal domain model, and returns a SignalSnapshot describing both the
signals and the metadata embedded in the snapshot file.

Snapshot format (v2 — object with metadata)
--------------------------------------------
{
  "generated_at":  "2026-04-22T12:00:00Z",
  "model_version": "xgboost-nightly",
  "source":        "local_snapshot",
  "signals":       [ ... ]
}

Legacy format (v1 — bare array) is still accepted so existing files keep
working without a migration step.

Swap guide (SSH/Sentinel source)
---------------------------------
Replace ``_load_raw()`` with a function that fetches the JSON over SSH:

    import subprocess

    def _load_raw() -> dict | list:
        result = subprocess.run(
            ["ssh", "-i", KEY_PATH, f"{USER}@{HOST}",
             "python3 /data/ai-trading-bot/snapshot.py"],
            capture_output=True, text=True, timeout=18,
        )
        return json.loads(result.stdout)

Everything above that function — SignalSnapshot, _parse_snapshot(),
get_signals(), and all error handling — stays exactly the same.
The SSH source already emits the v2 object format, so metadata will
populate automatically.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from app.domain.signals import Signal

log = logging.getLogger(__name__)

_SNAPSHOT_PATH = Path(__file__).resolve().parents[2] / "data" / "signals_snapshot.json"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class SignalSnapshot:
    """
    The result returned by get_signals().

    Carries both the validated signal list and whatever metadata was present
    in the snapshot file (or defaults when metadata is absent).

    ``used_mock_fallback`` is False here and set to True by the service layer
    if it substitutes hardcoded mocks for an empty snapshot.
    """
    signals:           list[Signal]
    source:            str
    generated_at:      str | None = None
    model_version:     str | None = None
    used_mock_fallback: bool = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_raw() -> "dict | list":
    """Read the snapshot file and return the raw parsed JSON."""
    with open(_SNAPSHOT_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _parse_snapshot(raw: "dict | list") -> SignalSnapshot:
    """
    Accept both the v2 object format and the legacy bare-array format.
    Validate each signal record; skip invalid ones with a warning.
    """
    if isinstance(raw, list):
        # Legacy v1 format — bare array, no metadata
        records = raw
        meta: dict = {}
    elif isinstance(raw, dict):
        records = raw.get("signals", [])
        if not isinstance(records, list):
            raise ValueError(
                f"snapshot['signals'] must be a list, got {type(records).__name__}"
            )
        meta = {k: raw.get(k) for k in ("generated_at", "model_version", "source")}
    else:
        raise ValueError(
            f"Snapshot must be a JSON object or array, got {type(raw).__name__}"
        )

    signals: list[Signal] = []
    for i, record in enumerate(records):
        try:
            signals.append(Signal.model_validate(record))
        except ValidationError as exc:
            log.warning("Skipping record %d — validation failed: %s", i, exc)

    return SignalSnapshot(
        signals=signals,
        source=meta.get("source") or "local_snapshot",
        generated_at=meta.get("generated_at"),
        model_version=meta.get("model_version"),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_signals() -> SignalSnapshot:
    """
    Load and validate signals from the local snapshot file.

    Returns a SignalSnapshot with an empty signal list on any I/O or parse
    error — the route always receives a safe value.
    """
    try:
        raw = _load_raw()
    except FileNotFoundError:
        log.warning(
            "signals_snapshot.json not found at %s — returning empty snapshot",
            _SNAPSHOT_PATH,
        )
        return SignalSnapshot(signals=[], source="local_snapshot")
    except (json.JSONDecodeError, ValueError) as exc:
        log.warning("Could not read signals snapshot: %s — returning empty snapshot", exc)
        return SignalSnapshot(signals=[], source="local_snapshot")

    try:
        return _parse_snapshot(raw)
    except ValueError as exc:
        log.warning("Could not parse signals snapshot: %s — returning empty snapshot", exc)
        return SignalSnapshot(signals=[], source="local_snapshot")
