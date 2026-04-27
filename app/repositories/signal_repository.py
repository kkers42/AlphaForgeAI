"""
Signal repository — local snapshot and Sentinel SSH sources.

Loads signal records from the configured source, validates each record into
the Signal domain model, and returns a SignalSnapshot describing the signals,
their metadata, and the outcome of the load attempt.

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
        - SENTINEL_SSH_HOST             — IP or hostname (e.g. 192.168.1.40)
        - SENTINEL_SSH_USER             — SSH username (default: kkers)
        - SENTINEL_SSH_KEY_PATH         — path to private key (optional)
        - SENTINEL_SSH_TIMEOUT          — seconds before subprocess timeout (default: 18)
        - SENTINEL_SSH_STRICT_HOST_KEY  — true/false (default: false)

      SSH failure of any kind returns an error SignalSnapshot; the service
      layer decides whether to fall back to mocks.

SignalSnapshot.status values
-----------------------------
  "ok"       — signals loaded and parsed without errors
  "empty"    — source responded but returned zero valid signals
  "error"    — load or parse failed; error_message carries a short diagnosis
  "fallback" — set by the service layer when it substitutes mock signals

Extension point (add a new source)
------------------------------------
1. Implement a ``_load_<name>_raw() -> dict | list`` function below.
2. Add the ``"<name>"`` case to the dispatcher in ``get_signals()``.
Everything above the loaders — SignalSnapshot, _parse_snapshot(), error
handling, the service, the route, and all templates — is unchanged.
"""

import json
import logging
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from app.core.config import settings
from app.domain.signals import Signal

log = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SNAPSHOT_PATH = _REPO_ROOT / "data" / "signals_snapshot.json"
SNAPSHOT_SCHEMA_VERSION = 1
LATEST_SNAPSHOT_PATH = _REPO_ROOT / "data" / "signals" / "latest.json"

_FRESHNESS_WARN_HOURS = 2
_FRESHNESS_FAIL_HOURS = 24


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class SignalSnapshot:
    """
    The result returned by get_signals().

    Carries the validated signal list, snapshot metadata, and the outcome of
    the load attempt (``status`` / ``error_message``).

    status
    ------
    "ok"       — data loaded and validated successfully
    "empty"    — source returned no valid signals (not an error, just nothing there)
    "error"    — load or parse failed; error_message has a short diagnosis
    "fallback" — service substituted mock signals; error_message may still carry
                 the original source failure reason

    used_mock_fallback
    ------------------
    False here; the service sets it to True when it substitutes mocks.
    """
    signals:            list[Signal]
    source:             str
    generated_at:       str | None = None
    model_version:      str | None = None
    schema_version:     int | None = None
    signal_count:       int | None = None
    used_mock_fallback: bool = False
    status:             str = "ok"       # "ok" | "empty" | "error" | "fallback"
    error_message:      str | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _error_snapshot(source: str, message: str) -> SignalSnapshot:
    """Return a safe empty snapshot tagged with the given error message."""
    return SignalSnapshot(
        signals=[],
        source=source,
        status="error",
        error_message=message,
    )


def _load_local_snapshot_raw() -> "dict | list":
    """Read the local snapshot file and return the raw parsed JSON."""
    with open(_SNAPSHOT_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _load_file_raw() -> "dict | list":
    """Read the file at settings.signal_file_path and return the raw parsed JSON."""
    path_str = settings.signal_file_path
    if not path_str:
        raise ValueError("SIGNAL_FILE_PATH is not configured")
    path = Path(path_str)
    if not path.is_absolute():
        path = _REPO_ROOT / path
    with open(path, encoding="utf-8") as fh:
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
        If the subprocess does not complete within sentinel_ssh_timeout_seconds.
    json.JSONDecodeError
        If stdout is not valid JSON.
    """
    if not settings.sentinel_ssh_host:
        raise ValueError("SENTINEL_SSH_HOST is not configured")

    strict = "yes" if settings.sentinel_ssh_strict_host_key_checking else "no"
    timeout = settings.sentinel_ssh_timeout_seconds

    cmd = ["ssh"]
    if settings.sentinel_ssh_key_path:
        cmd += ["-i", settings.sentinel_ssh_key_path]
    cmd += [
        "-o", f"StrictHostKeyChecking={strict}",
        "-o", f"ConnectTimeout={timeout}",
        f"{settings.sentinel_ssh_user}@{settings.sentinel_ssh_host}",
        settings.sentinel_snapshot_command,
    ]

    log.debug(
        "Sentinel SSH: %s@%s timeout=%ds cmd=%s",
        settings.sentinel_ssh_user,
        settings.sentinel_ssh_host,
        timeout,
        settings.sentinel_snapshot_command,
    )

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 2)

    if result.returncode != 0:
        stderr_preview = result.stderr.strip()[:200]
        raise RuntimeError(
            f"SSH exited {result.returncode}: {stderr_preview or '(no stderr)'}"
        )

    if not result.stdout.strip():
        raise RuntimeError("SSH succeeded but stdout was empty")

    return json.loads(result.stdout)


def _parse_snapshot(raw: "dict | list", source_label: str) -> SignalSnapshot:
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
        meta = {
            k: raw.get(k)
            for k in (
                "generated_at",
                "model_version",
                "source",
                "schema_version",
                "signal_count",
            )
        }
    else:
        raise ValueError(
            f"Snapshot root must be a JSON object or array, got {type(raw).__name__}"
        )

    signals: list[Signal] = []
    skipped = 0
    for i, record in enumerate(records):
        try:
            signals.append(Signal.model_validate(record))
        except ValidationError as exc:
            skipped += 1
            log.warning(
                "Skipping record %d (source=%s) — validation failed: %s",
                i, source_label, exc,
            )

    if skipped:
        log.warning(
            "%d of %d signal records were invalid and skipped (source=%s)",
            skipped, skipped + len(signals), source_label,
        )

    # If the snapshot's own "source" tag is absent, fall back to the
    # configured source label so the UI always shows the right value.
    resolved_source = meta.get("source") or source_label
    if source_label == "sentinel_ssh" and resolved_source == "local_snapshot":
        resolved_source = "sentinel_ssh"

    return SignalSnapshot(
        signals=signals,
        source=resolved_source,
        generated_at=meta.get("generated_at"),
        model_version=meta.get("model_version"),
        schema_version=meta.get("schema_version"),
        signal_count=(
            meta.get("signal_count")
            if meta.get("signal_count") is not None
            else len(signals)
        ),
        status="ok",
    )


def validate_snapshot_payload(
    raw: "dict | list",
    source_label: str = "file",
    require_schema: bool = False,
) -> SignalSnapshot:
    """
    Validate a snapshot payload and return its parsed SignalSnapshot.

    Legacy local snapshots may omit persistence metadata.  Persisted latest
    snapshots use schema_version=1 and must carry generated_at, source, and a
    signal_count that matches the signals array.
    """
    if require_schema and not (isinstance(raw, dict) and "schema_version" in raw):
        raise ValueError("persisted snapshot must include schema_version")

    if isinstance(raw, dict) and "schema_version" in raw:
        schema_version = raw.get("schema_version")
        if schema_version != SNAPSHOT_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported schema_version {schema_version!r}; "
                f"expected {SNAPSHOT_SCHEMA_VERSION}"
            )
        if not isinstance(raw.get("generated_at"), str) or not raw["generated_at"]:
            raise ValueError("snapshot['generated_at'] must be a non-empty string")
        try:
            datetime.fromisoformat(raw["generated_at"].replace("Z", "+00:00"))
        except ValueError:
            raise ValueError(
                "snapshot['generated_at'] must be a valid ISO 8601 datetime, "
                f"got {raw['generated_at']!r}"
            )
        if not isinstance(raw.get("source"), str) or not raw["source"]:
            raise ValueError("snapshot['source'] must be a non-empty string")
        records = raw.get("signals")
        if not isinstance(records, list):
            raise ValueError(
                f"snapshot['signals'] must be a list, got {type(records).__name__}"
            )
        signal_count = raw.get("signal_count")
        if not isinstance(signal_count, int):
            raise ValueError("snapshot['signal_count'] must be an integer")
        if signal_count != len(records):
            raise ValueError(
                "snapshot['signal_count'] does not match signals length "
                f"({signal_count} != {len(records)})"
            )

    return _parse_snapshot(raw, source_label)


def write_snapshot_atomic(snapshot: dict, path: Path = LATEST_SNAPSHOT_PATH) -> SignalSnapshot:
    """
    Safely persist the latest generated snapshot.

    The payload is validated before and after JSON serialization.  The target
    file is replaced only after the temp file is fully written and validated.
    """
    parsed = validate_snapshot_payload(snapshot, "generated", require_schema=True)
    payload = json.dumps(snapshot, indent=2) + "\n"

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(payload, encoding="utf-8")

    try:
        with open(tmp_path, encoding="utf-8") as fh:
            validate_snapshot_payload(json.load(fh), "generated", require_schema=True)
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    return parsed


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_signals_from_file() -> SignalSnapshot:
    """
    Load and validate signals from the file at SIGNAL_FILE_PATH.

    Returns a SignalSnapshot on all paths — never raises.
    """
    source_label = "file"
    try:
        raw = _load_file_raw()

    except FileNotFoundError:
        log.warning(
            "[signal_repository] file: file not found at %s",
            settings.signal_file_path,
        )
        return _error_snapshot(
            source_label,
            f"Signal file not found: {settings.signal_file_path or '(path not set)'}",
        )

    except ValueError as exc:
        log.warning("[signal_repository] file: config error — %s", exc)
        return _error_snapshot(source_label, f"Config error: {exc}")

    except json.JSONDecodeError as exc:
        log.warning("[signal_repository] file: invalid JSON — %s", exc)
        return _error_snapshot(source_label, "Invalid JSON in signal file")

    except OSError as exc:
        log.warning("[signal_repository] file: I/O error — %s", exc)
        return _error_snapshot(source_label, f"I/O error: {exc}")

    try:
        configured_path = Path(settings.signal_file_path)
        if not configured_path.is_absolute():
            configured_path = _REPO_ROOT / configured_path
        require_schema = configured_path.resolve() == LATEST_SNAPSHOT_PATH
        snapshot = validate_snapshot_payload(
            raw,
            source_label,
            require_schema=require_schema,
        )
    except ValueError as exc:
        log.warning("[signal_repository] file: malformed payload — %s", exc)
        return _error_snapshot(source_label, f"Malformed snapshot: {exc}")

    if snapshot.generated_at:
        try:
            generated_dt = datetime.fromisoformat(snapshot.generated_at.replace("Z", "+00:00"))
            age_hours = (datetime.now(timezone.utc) - generated_dt).total_seconds() / 3600
            if age_hours > _FRESHNESS_FAIL_HOURS:
                log.warning(
                    "[signal_repository] file: snapshot is %.1fh old (generated=%s) — "
                    "exceeds %dh threshold; returning error to prevent stale data",
                    age_hours, snapshot.generated_at, _FRESHNESS_FAIL_HOURS,
                )
                return _error_snapshot(
                    source_label,
                    f"Snapshot is {age_hours:.1f}h old (limit: {_FRESHNESS_FAIL_HOURS}h); "
                    "run generate_signals.py to refresh",
                )
            if age_hours > _FRESHNESS_WARN_HOURS:
                log.warning(
                    "[signal_repository] file: snapshot is %.1fh old (generated=%s) — "
                    "consider running generate_signals.py",
                    age_hours, snapshot.generated_at,
                )
        except ValueError:
            log.warning(
                "[signal_repository] file: could not parse generated_at=%r for age check",
                snapshot.generated_at,
            )

    if not snapshot.signals:
        log.info("[signal_repository] file: loaded but contains no valid signals")
        from dataclasses import replace
        return replace(snapshot, status="empty")

    log.info(
        "[signal_repository] file: loaded %d signal(s) (model=%s generated=%s)",
        len(snapshot.signals),
        snapshot.model_version or "unknown",
        snapshot.generated_at or "unknown",
    )
    return snapshot


def get_signals() -> SignalSnapshot:
    """
    Load and validate signals from the configured source.

    Source is determined by ``settings.signal_source``:
      - ``"local_snapshot"`` → reads data/signals_snapshot.json
      - ``"sentinel_ssh"``   → fetches snapshot from Sentinel via SSH

    Returns a SignalSnapshot on all paths — never raises.
    status field reflects the outcome:
      "ok"    → signals present and valid
      "empty" → source responded but no valid signals
      "error" → load or parse failed (error_message carries the reason)
    """
    source_label = settings.signal_source

    # ── Load raw data ────────────────────────────────────────────────────────
    try:
        if source_label == "sentinel_ssh":
            raw = _load_sentinel_snapshot_raw()
        else:
            raw = _load_local_snapshot_raw()

    except FileNotFoundError:
        log.warning(
            "[signal_repository] local_snapshot: file not found at %s",
            _SNAPSHOT_PATH,
        )
        return _error_snapshot(source_label, "Snapshot file not found")

    except subprocess.TimeoutExpired:
        log.warning(
            "[signal_repository] sentinel_ssh: timed out after %ds (host=%s)",
            settings.sentinel_ssh_timeout_seconds,
            settings.sentinel_ssh_host,
        )
        return _error_snapshot(
            source_label,
            f"SSH timeout after {settings.sentinel_ssh_timeout_seconds}s",
        )

    except ValueError as exc:
        # Misconfiguration (e.g. missing host)
        log.warning("[signal_repository] sentinel_ssh: config error — %s", exc)
        return _error_snapshot(source_label, f"Config error: {exc}")

    except RuntimeError as exc:
        # Non-zero SSH exit or empty stdout
        log.warning("[signal_repository] sentinel_ssh: SSH error — %s", exc)
        return _error_snapshot(source_label, f"SSH error: {exc}")

    except json.JSONDecodeError as exc:
        log.warning(
            "[signal_repository] %s: invalid JSON from source — %s",
            source_label, exc,
        )
        return _error_snapshot(source_label, "Invalid JSON from source")

    except OSError as exc:
        log.warning(
            "[signal_repository] %s: I/O error reading snapshot — %s",
            source_label, exc,
        )
        return _error_snapshot(source_label, f"I/O error: {exc}")

    # ── Parse and validate ───────────────────────────────────────────────────
    try:
        snapshot = _parse_snapshot(raw, source_label)
    except ValueError as exc:
        log.warning(
            "[signal_repository] %s: malformed snapshot payload — %s",
            source_label, exc,
        )
        return _error_snapshot(source_label, f"Malformed snapshot: {exc}")

    # ── Classify empty vs ok ─────────────────────────────────────────────────
    if not snapshot.signals:
        log.info(
            "[signal_repository] %s: snapshot loaded but contains no valid signals",
            source_label,
        )
        from dataclasses import replace
        return replace(snapshot, status="empty")

    log.info(
        "[signal_repository] %s: loaded %d signal(s) (model=%s generated=%s)",
        source_label,
        len(snapshot.signals),
        snapshot.model_version or "unknown",
        snapshot.generated_at or "unknown",
    )
    return snapshot
