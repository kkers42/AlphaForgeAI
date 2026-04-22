"""
Signal repository — local snapshot and Sentinel SSH sources.

Loads signal records from the configured source, validates each record into
the Signal domain model, and returns a SignalSnapshot describing both the
signals and the metadata embedded in the snapshot.

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

Source selection
-----------------
Controlled by ``settings.signal_source`` (env: ``SIGNAL_SOURCE``):

  ``local_snapshot`` (default)
      Reads ``data/signals_snapshot.json`` from the project root.
      Safe for development and as a fallback when Sentinel is unreachable.

  ``sentinel_ssh``
      Executes ``settings.sentinel_snapshot_command`` on the Sentinel host via
      SSH and parses the JSON written to stdout.  Requires:
        - SENTINEL_SSH_HOST   — IP or hostname (e.g. 192.168.1.40)
        - SENTINEL_SSH_USER   — SSH username (default: kkers)
        - SENTINEL_SSH_KEY_PATH — path to private key (optional; omit to use
                                  the SSH agent or default key)

      SSH failure (timeout, non-zero exit, invalid JSON) returns an empty
      SignalSnapshot — the service layer decides whether to fall back to mocks.

Extension point (add a new source)
------------------------------------
1. Implement a ``_load_<name>_raw() -> dict | list`` function below.
2. Add the ``"<name>"`` case to the dispatcher in ``get_signals()``.
Everything above the loaders — SignalSnapshot, _parse_snapshot(), error
handling, the service, the route, and all templates — is unchanged.
"""

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from app.core.config import settings
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
    in the snapshot (or defaults when metadata is absent).

    ``used_mock_fallback`` is False here; the service layer sets it to True
    if it substitutes hardcoded mocks for an empty snapshot.
    """
    signals:            list[Signal]
    source:             str
    generated_at:       str | None = None
    model_version:      str | None = None
    used_mock_fallback: bool = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_local_snapshot_raw() -> "dict | list":
    """Read the local snapshot file and return the raw parsed JSON."""
    with open(_SNAPSHOT_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _load_sentinel_snapshot_raw() -> "dict | list":
    """
    SSH to Sentinel, run the snapshot script, and return the parsed JSON.

    Raises
    ------
    ValueError
        If SENTINEL_SSH_HOST is not configured.
    RuntimeError
        If the SSH command exits with a non-zero return code.
    subprocess.TimeoutExpired
        If the SSH call does not complete within the timeout.
    json.JSONDecodeError
        If stdout is not valid JSON.
    """
    if not settings.sentinel_ssh_host:
        raise ValueError(
            "SENTINEL_SSH_HOST is not configured — set the env var to enable "
            "the sentinel_ssh source."
        )

    cmd = ["ssh"]
    if settings.sentinel_ssh_key_path:
        cmd += ["-i", settings.sentinel_ssh_key_path]
    cmd += [
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=15",
        f"{settings.sentinel_ssh_user}@{settings.sentinel_ssh_host}",
        settings.sentinel_snapshot_command,
    ]

    log.debug(
        "Fetching Sentinel snapshot via SSH: %s@%s — %s",
        settings.sentinel_ssh_user,
        settings.sentinel_ssh_host,
        settings.sentinel_snapshot_command,
    )

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)

    if result.returncode != 0:
        stderr_preview = result.stderr.strip()[:300]
        raise RuntimeError(
            f"SSH to Sentinel exited {result.returncode}: {stderr_preview}"
        )

    return json.loads(result.stdout)


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
    Load and validate signals from the configured source.

    Source is determined by ``settings.signal_source``:
      - ``"local_snapshot"``  → reads data/signals_snapshot.json
      - ``"sentinel_ssh"``    → fetches snapshot from Sentinel via SSH

    Returns a SignalSnapshot with an empty signal list on any I/O, network,
    or parse error — the caller always receives a safe value.
    """
    source_label = settings.signal_source

    try:
        if source_label == "sentinel_ssh":
            raw = _load_sentinel_snapshot_raw()
        else:
            raw = _load_local_snapshot_raw()
    except FileNotFoundError:
        log.warning(
            "Snapshot file not found at %s — returning empty snapshot",
            _SNAPSHOT_PATH,
        )
        return SignalSnapshot(signals=[], source=source_label)
    except subprocess.TimeoutExpired:
        log.warning(
            "SSH to Sentinel timed out (%s) — returning empty snapshot",
            settings.sentinel_ssh_host,
        )
        return SignalSnapshot(signals=[], source=source_label)
    except (json.JSONDecodeError, ValueError, RuntimeError, OSError) as exc:
        log.warning(
            "Could not load snapshot (source=%s): %s — returning empty snapshot",
            source_label, exc,
        )
        return SignalSnapshot(signals=[], source=source_label)

    try:
        snapshot = _parse_snapshot(raw)
        # When the snapshot metadata omits a source tag, use the configured
        # source label so the UI always shows the active source correctly.
        if not snapshot.source or snapshot.source == "local_snapshot":
            if source_label == "sentinel_ssh":
                from dataclasses import replace
                snapshot = replace(snapshot, source="sentinel_ssh")
        return snapshot
    except ValueError as exc:
        log.warning(
            "Could not parse snapshot: %s — returning empty snapshot", exc
        )
        return SignalSnapshot(signals=[], source=source_label)
