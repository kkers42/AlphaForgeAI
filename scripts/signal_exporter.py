#!/usr/bin/env python3
"""
signal_exporter.py — Sentinel live signal exporter.

Reads the latest prediction line from each xgb_runner ``{ASSET}_live.log``,
builds a schema_version=1 snapshot compatible with AlphaForgeAI's ingest
endpoint, and POSTs it via HTTPS.

Usage
-----
    /home/kkers/trading-venv/bin/python3 /data/ai-trading-bot/signal_exporter.py

Cron (offset from candle_fetcher to avoid contention, runs 2 min after):
    15,30,45,0 * * * * /home/kkers/trading-venv/bin/python3 \\
        /data/ai-trading-bot/signal_exporter.py \\
        >> /data/ai-trading-bot/logs/signal_exporter.log 2>&1

Environment
-----------
    ALPHAFORGEAI_INGEST_KEY  — Bearer token for POST /api/signals/ingest  (required)
    ALPHAFORGEAI_URL         — Base URL (default: https://alphaforgeai.io)
"""

import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

# ── Config ────────────────────────────────────────────────────────────────────

BASE_DIR   = Path("/data/ai-trading-bot")
LOG_DIR    = BASE_DIR / "logs"
API_URL    = os.getenv("ALPHAFORGEAI_URL", "https://alphaforgeai.io").rstrip("/")
API_KEY    = os.getenv("ALPHAFORGEAI_INGEST_KEY", "")
INGEST_URL = f"{API_URL}/api/signals/ingest"

ALL_ASSETS = [
    "BTC", "ETH", "SOL", "XRP", "AVAX", "LTC", "BCH",
    "LINK", "DOT", "UNI", "AAVE", "NEAR", "APT", "FIL",
    "INJ", "SUI", "ARB", "OP", "POL", "COMP", "SNX", "CRV",
    "DOGE", "SHIB", "PEPE", "WIF", "BONK", "FLOKI",
    "ZEC", "ATOM", "GRT", "AXS",
]

# Matches: [14:32] [DOGE] $0.11153 | LONG 52.3% < 62% [downtrend] — skip
# Also handles ≥ (unicode) and >= for the threshold comparison operator
_SIGNAL_RE = re.compile(
    r"^\[(\d{2}:\d{2})\] \[(\w+)\] \$([0-9.]+) \| (\w+) ([0-9.]+)% [<≥>=]+ [0-9.]+% \[(\w+)\] — (.+)$"
)

# Matches: Model loaded from: /data/.../BTC/xgboost_classification_20260504_032557.pkl
_MODEL_FILE_RE = re.compile(r"Model loaded from:.+/([^/]+\.pkl)")
# Matches: [BTC] Model: 3-class wf_acc=0.7839 wf_f1=0.4605
_MODEL_ACC_RE  = re.compile(r"wf_acc=([0-9.]+)")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [signal_exporter] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("signal_exporter")


# ── Log parsers ───────────────────────────────────────────────────────────────

def _read_tail(path: Path, n: int = 300) -> list[str]:
    """Return the last *n* lines of *path*, newest-last."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.readlines()[-n:]
    except OSError:
        return []


def _parse_signal(asset: str, today: str) -> dict | None:
    """Return a signal dict for *asset* based on its live log, or None."""
    lines = _read_tail(LOG_DIR / f"{asset}_live.log")
    for line in reversed(lines):
        m = _SIGNAL_RE.match(line.strip())
        if not m:
            continue
        hhmm, _asset, price_str, direction, conf_pct, regime, action = m.groups()

        # Map NO_TRADE → FLAT (AlphaForgeAI Direction enum)
        direction_mapped = "FLAT" if direction == "NO_TRADE" else direction
        confidence = round(float(conf_pct) / 100.0, 4)
        generated_at = f"{today}T{hhmm}:00Z"

        return {
            "symbol":       asset,
            "direction":    direction_mapped,
            "timeframe":    "15m",
            "confidence":   confidence,
            "regime":       regime,
            "thesis": (
                f"{direction} signal at {conf_pct}% confidence [{regime}]. "
                f"Price: ${price_str}. Action: {action}."
            ),
            "price":        float(price_str),
            "generated_at": generated_at,
        }
    return None


def _parse_model_info(asset: str) -> tuple[str, float | None]:
    """Return (model_file_stem, walk-forward accuracy) from the live log header."""
    lines = _read_tail(LOG_DIR / f"{asset}_live.log", n=60)
    model_file = f"xgboost-{asset.lower()}"
    accuracy   = None
    for line in lines:
        mf = _MODEL_FILE_RE.search(line)
        if mf:
            model_file = mf.group(1).replace(".pkl", "")
        ma = _MODEL_ACC_RE.search(line)
        if ma:
            accuracy = float(ma.group(1))
    return model_file, accuracy


# ── Snapshot builder ──────────────────────────────────────────────────────────

def build_snapshot(signals: list[dict]) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "schema_version": 1,
        "generated_at":   now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model_version":  "xgboost-live",
        "source":         "sentinel_push",
        "signal_count":   len(signals),
        "signals":        signals,
    }


# ── HTTP push ─────────────────────────────────────────────────────────────────

def push_snapshot(snapshot: dict) -> bool:
    if not API_KEY:
        log.error("ALPHAFORGEAI_INGEST_KEY not set — cannot push signals")
        return False
    try:
        r = requests.post(
            INGEST_URL,
            json=snapshot,
            headers={
                "Authorization":  f"Bearer {API_KEY}",
                "Content-Type":   "application/json",
            },
            timeout=20,
        )
        if r.status_code == 200:
            data = r.json()
            log.info(
                "event=push_ok signal_count=%d accepted=%s url=%s",
                snapshot["signal_count"], data.get("accepted"), INGEST_URL,
            )
            return True
        log.warning(
            "event=push_failed status=%d body=%s",
            r.status_code, r.text[:300],
        )
        return False
    except Exception as exc:
        log.error("event=push_error error=%s", exc)
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    now     = datetime.now(timezone.utc)
    today   = now.strftime("%Y-%m-%d")
    log.info("start generated_at=%s", now.strftime("%Y-%m-%dT%H:%M:%SZ"))

    signals: list[dict] = []
    missing: list[str]  = []

    for asset in ALL_ASSETS:
        sig = _parse_signal(asset, today)
        if sig:
            signals.append(sig)
        else:
            missing.append(asset)

    log.info(
        "collected %d/%d signals%s",
        len(signals), len(ALL_ASSETS),
        f" | missing: {', '.join(missing)}" if missing else "",
    )

    if not signals:
        log.warning("no signals collected — skipping push")
        return

    snapshot = build_snapshot(signals)
    push_snapshot(snapshot)


if __name__ == "__main__":
    main()
