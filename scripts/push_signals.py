#!/usr/bin/env python3
"""
Push a signal snapshot from the Sentinel AI bot to the AlphaForgeAI ingest endpoint.

Usage
-----
    python scripts/push_signals.py --snapshot /data/ai-trading-bot/signals.json
    python scripts/push_signals.py --snapshot signals.json --dry-run

Environment variables
---------------------
    ALPHAFORGEAI_API_KEY   Bearer token for POST /api/signals/ingest (required)
    ALPHAFORGEAI_INGEST_URL  Override the default ingest URL (optional)
"""

import argparse
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("push_signals")

DEFAULT_INGEST_URL = "https://alphaforgeai.io/api/signals/ingest"
SNAPSHOT_SCHEMA_VERSION = 1
MAX_RETRIES = 3


def _load_snapshot(path: str) -> dict:
    """Read and return the snapshot JSON. Wraps bare signal arrays in a v1 envelope."""
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)

    if isinstance(raw, list):
        log.info("event=envelope_wrap signal_count=%d", len(raw))
        return {
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "model_version": "alphabot-v1",
            "source": "sentinel_push",
            "signal_count": len(raw),
            "signals": raw,
        }

    if isinstance(raw, dict):
        # Ensure required envelope fields are present
        if "schema_version" not in raw:
            raw["schema_version"] = SNAPSHOT_SCHEMA_VERSION
        if "source" not in raw or not raw["source"]:
            raw["source"] = "sentinel_push"
        if "signal_count" not in raw:
            raw["signal_count"] = len(raw.get("signals", []))
        return raw

    raise ValueError(f"Snapshot root must be a JSON object or array, got {type(raw).__name__}")


def _post(url: str, payload: dict, api_key: str, timeout: int = 30) -> dict:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "push_signals/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def push(snapshot: dict, url: str, api_key: str, dry_run: bool = False) -> bool:
    signal_count = len(snapshot.get("signals", []))
    generated_at = snapshot.get("generated_at", "unknown")

    if dry_run:
        log.info(
            "event=dry_run signal_count=%d generated_at=%s payload_bytes=%d",
            signal_count,
            generated_at,
            len(json.dumps(snapshot)),
        )
        print(json.dumps(snapshot, indent=2))
        return True

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = _post(url, snapshot, api_key)
            log.info(
                "event=push_success signal_count=%d generated_at=%s accepted=%s attempt=%d",
                signal_count,
                generated_at,
                result.get("accepted"),
                attempt,
            )
            return True

        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")[:300]
            if exc.code in (401, 422):
                log.error(
                    "event=push_failed status=%d body=%s — not retrying",
                    exc.code,
                    body,
                )
                return False
            log.warning(
                "event=push_error attempt=%d/%d status=%d body=%s",
                attempt, MAX_RETRIES, exc.code, body,
            )

        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            log.warning(
                "event=push_error attempt=%d/%d error=%s",
                attempt, MAX_RETRIES, exc,
            )

        if attempt < MAX_RETRIES:
            wait = 2 ** attempt
            log.info("event=push_retry wait_s=%d", wait)
            time.sleep(wait)

    log.error("event=push_failed reason=max_retries_exceeded")
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Push Sentinel signals to AlphaForgeAI")
    parser.add_argument("--snapshot", required=True, help="Path to signal snapshot JSON file")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print without sending")
    parser.add_argument("--url", default=None, help="Override ingest URL")
    args = parser.parse_args()

    api_key = os.getenv("ALPHAFORGEAI_API_KEY", "")
    if not api_key and not args.dry_run:
        log.error("event=missing_api_key — set ALPHAFORGEAI_API_KEY env var")
        sys.exit(1)

    url = args.url or os.getenv("ALPHAFORGEAI_INGEST_URL", DEFAULT_INGEST_URL)

    snapshot_path = Path(args.snapshot)
    if not snapshot_path.exists():
        log.error("event=file_not_found path=%s", snapshot_path)
        sys.exit(1)

    try:
        snapshot = _load_snapshot(str(snapshot_path))
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        log.error("event=load_failed error=%s", exc)
        sys.exit(1)

    log.info(
        "event=push_start signal_count=%d generated_at=%s url=%s dry_run=%s",
        len(snapshot.get("signals", [])),
        snapshot.get("generated_at", "unknown"),
        url if not args.dry_run else "(dry-run)",
        args.dry_run,
    )

    ok = push(snapshot, url, api_key, dry_run=args.dry_run)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
