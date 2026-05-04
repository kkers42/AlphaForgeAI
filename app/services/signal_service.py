"""
Signal service — provider dispatcher and mock-fallback logic.

Selects the configured provider, delegates to it, and applies the
mock-fallback policy when the provider returns no signals.

Provider selection (SIGNAL_PROVIDER env var)
--------------------------------------------
"mock"         → app.providers.mock_provider   (no I/O)
"file"         → app.providers.file_provider   (SIGNAL_FILE_PATH)
"sentinel_ssh" → app.providers.sentinel_provider (SSH)
other / unset  → app.providers.local_provider  (data/signals_snapshot.json)

Fallback policy (ALLOW_MOCK_FALLBACK env var)
----------------------------------------------
development (default) → True   — UI is never blank during local work
production  (default) → False  — empty snapshot surfaces as empty feed
"""

import logging
from dataclasses import replace

from app.core.config import settings
from app.domain.signals import Signal
from app.repositories.signal_repository import SignalSnapshot

log = logging.getLogger(__name__)


def get_signals() -> SignalSnapshot:
    """Dispatch to the configured provider and apply fallback if needed."""
    from app.providers import (
        file_provider,
        local_provider,
        mock_provider,
        sentinel_provider,
    )

    provider = settings.signal_provider

    _PROVIDERS = {
        "mock":         mock_provider.get_signals,
        "file":         file_provider.get_signals,
        "sentinel_ssh": sentinel_provider.get_signals,
    }

    load = _PROVIDERS.get(provider, local_provider.get_signals)
    snapshot = load()

    if not snapshot.signals:
        if settings.allow_mock_fallback:
            log.info(
                "event=mock_fallback_activated provider=%s status=%s environment=%s",
                provider,
                snapshot.status,
                settings.environment,
            )
            return replace(
                snapshot,
                signals=get_mock_signals(),
                source="mock_fallback",
                used_mock_fallback=True,
                status="fallback",
            )
        log.info(
            "event=empty_feed_returned provider=%s status=%s environment=%s",
            provider,
            snapshot.status,
            settings.environment,
        )

    return snapshot


def get_mock_signals() -> list[Signal]:
    """Return the hardcoded mock signal list (used for fallback only)."""
    from app.providers.mock_provider import _build_signals
    return _build_signals()
