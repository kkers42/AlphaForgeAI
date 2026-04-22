"""
Signal repository — local JSON snapshot source.

Loads signal records from a local JSON file and validates each record
into the Signal domain model.

Swap guide (SSH/Sentinel source)
---------------------------------
Replace ``_load_snapshot()`` with a function that fetches the JSON over SSH:

    import subprocess, json

    def _load_snapshot() -> list[dict]:
        result = subprocess.run(
            ["ssh", "-i", KEY_PATH, f"{USER}@{HOST}",
             "python3 /data/ai-trading-bot/snapshot.py"],
            capture_output=True, text=True, timeout=18,
        )
        return json.loads(result.stdout).get("signals", [])

Everything above that function — validation, error handling, get_signals() —
stays exactly the same.
"""

import json
import logging
from pathlib import Path

from pydantic import ValidationError

from app.domain.signals import Signal

log = logging.getLogger(__name__)

# Path is relative to the project root (one level above app/).
_SNAPSHOT_PATH = Path(__file__).resolve().parents[2] / "data" / "signals_snapshot.json"


def _load_snapshot() -> list[dict]:
    """Read raw records from the local JSON snapshot file."""
    with open(_SNAPSHOT_PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array in {_SNAPSHOT_PATH}, got {type(data).__name__}")
    return data


def get_signals() -> list[Signal]:
    """
    Load and validate signals from the local snapshot file.

    Returns an empty list if the file is missing, empty, or malformed,
    so the route always gets a safe value.
    """
    try:
        records = _load_snapshot()
    except FileNotFoundError:
        log.warning("signals_snapshot.json not found at %s — returning empty list", _SNAPSHOT_PATH)
        return []
    except (json.JSONDecodeError, ValueError) as exc:
        log.warning("Could not parse signals snapshot: %s — returning empty list", exc)
        return []

    signals: list[Signal] = []
    for i, record in enumerate(records):
        try:
            signals.append(Signal.model_validate(record))
        except ValidationError as exc:
            log.warning("Skipping record %d — validation failed: %s", i, exc)

    return signals
