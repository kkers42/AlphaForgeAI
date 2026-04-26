import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    app_name:     str = "AlphaForgeAI"
    app_version:  str = "0.4.0"
    environment:  str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    signal_source: str = field(default_factory=lambda: os.getenv("SIGNAL_SOURCE", "local_snapshot"))

    # ── Signal provider ──────────────────────────────────────────────────────
    # High-level provider selection.  "file" reads the persisted latest
    # snapshot by default.  "mock" serves hardcoded signals directly
    # (no file I/O).  The legacy
    # signal_source values (local_snapshot / sentinel_ssh) are used when
    # signal_provider is not set to mock or file.
    signal_provider:  str = field(default_factory=lambda: os.getenv("SIGNAL_PROVIDER", "file"))
    signal_file_path: str = field(
        default_factory=lambda: os.getenv("SIGNAL_FILE_PATH", "data/signals/latest.json")
    )

    # ── Sentinel SSH connection ──────────────────────────────────────────────
    # Required when signal_source == "sentinel_ssh".
    sentinel_ssh_host:         str = field(default_factory=lambda: os.getenv("SENTINEL_SSH_HOST", ""))
    sentinel_ssh_user:         str = field(default_factory=lambda: os.getenv("SENTINEL_SSH_USER", "kkers"))
    sentinel_ssh_key_path:     str = field(default_factory=lambda: os.getenv("SENTINEL_SSH_KEY_PATH", ""))
    sentinel_snapshot_command: str = field(
        default_factory=lambda: os.getenv(
            "SENTINEL_SNAPSHOT_COMMAND",
            "python3 /data/ai-trading-bot/snapshot.py",
        )
    )

    # ── Sentinel SSH operational settings ───────────────────────────────────
    # subprocess.run timeout (seconds).  ConnectTimeout is set to the same
    # value so SSH itself honours it independently of Python's timeout.
    sentinel_ssh_timeout_seconds: int = field(
        default_factory=lambda: int(os.getenv("SENTINEL_SSH_TIMEOUT", "18"))
    )

    # StrictHostKeyChecking: False (default) skips known-hosts verification,
    # which is safe for a trusted LAN host and avoids first-run key prompts.
    # Set SENTINEL_SSH_STRICT_HOST_KEY=true to enable strict checking.
    sentinel_ssh_strict_host_key_checking: bool = field(
        default_factory=lambda: os.getenv(
            "SENTINEL_SSH_STRICT_HOST_KEY", "false"
        ).strip().lower() in ("1", "true", "yes")
    )

    # ── Derived properties ───────────────────────────────────────────────────

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def debug(self) -> bool:
        return not self.is_production

    @property
    def allow_mock_fallback(self) -> bool:
        """
        Whether the service may fall back to hardcoded mock signals when the
        snapshot is empty or unavailable.

        Defaults to True in development, False in production.
        Override with the ALLOW_MOCK_FALLBACK environment variable.

        Examples
        --------
        ENVIRONMENT=production                            → False (no silent mock injection)
        ENVIRONMENT=production ALLOW_MOCK_FALLBACK=true   → True  (explicit override)
        ENVIRONMENT=development                           → True  (safe for local work)
        ENVIRONMENT=development ALLOW_MOCK_FALLBACK=false → False (test prod behaviour locally)
        """
        env_val = os.getenv("ALLOW_MOCK_FALLBACK")
        if env_val is not None:
            return env_val.strip().lower() in ("1", "true", "yes")
        return not self.is_production

    @property
    def sentinel_configured(self) -> bool:
        """True when SENTINEL_SSH_HOST is set (i.e. the SSH source can attempt a connection)."""
        return bool(self.sentinel_ssh_host)


# Single shared instance imported everywhere
settings = Settings()
