"""Sentinel SSH signal provider — fetches snapshot from remote host via SSH."""

import json
import logging
import subprocess

from app.core.config import settings
from app.repositories.signal_repository import (
    SignalSnapshot,
    _error_snapshot,
    _parse_snapshot,
)

log = logging.getLogger(__name__)

_SOURCE = "sentinel_ssh"


def get_signals() -> SignalSnapshot:
    """Fetch and validate signals from Sentinel via SSH."""
    if not settings.sentinel_ssh_host:
        log.warning("event=provider_load provider=sentinel error=host_not_configured")
        return _error_snapshot(_SOURCE, "SENTINEL_SSH_HOST is not configured")

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
        "event=provider_load provider=sentinel action=ssh_connect "
        "host=%s user=%s timeout=%ds",
        settings.sentinel_ssh_host,
        settings.sentinel_ssh_user,
        timeout,
    )

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout + 2
        )
    except subprocess.TimeoutExpired:
        log.warning(
            "event=provider_load provider=sentinel error=timeout timeout_s=%d host=%s",
            timeout,
            settings.sentinel_ssh_host,
        )
        return _error_snapshot(_SOURCE, f"SSH timeout after {timeout}s")

    if result.returncode != 0:
        stderr_preview = result.stderr.strip()[:200]
        log.warning(
            "event=provider_load provider=sentinel error=nonzero_exit "
            "returncode=%d stderr=%s",
            result.returncode,
            stderr_preview or "(none)",
        )
        return _error_snapshot(
            _SOURCE, f"SSH exited {result.returncode}: {stderr_preview or '(no stderr)'}"
        )

    if not result.stdout.strip():
        log.warning("event=provider_load provider=sentinel error=empty_stdout")
        return _error_snapshot(_SOURCE, "SSH succeeded but stdout was empty")

    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        log.warning(
            "event=provider_load provider=sentinel error=invalid_json exc=%s", exc
        )
        return _error_snapshot(_SOURCE, "Invalid JSON from Sentinel")

    try:
        snapshot = _parse_snapshot(raw, _SOURCE)
    except ValueError as exc:
        log.warning(
            "event=provider_load provider=sentinel error=malformed_payload exc=%s", exc
        )
        return _error_snapshot(_SOURCE, f"Malformed snapshot: {exc}")

    if not snapshot.signals:
        log.info("event=provider_load provider=sentinel status=empty")
        from dataclasses import replace
        return replace(snapshot, status="empty")

    log.info(
        "event=provider_load provider=sentinel status=ok signal_count=%d "
        "model=%s generated_at=%s",
        len(snapshot.signals),
        snapshot.model_version or "unknown",
        snapshot.generated_at or "unknown",
    )
    return snapshot
