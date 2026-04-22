import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    app_name:     str = "AlphaForgeAI"
    app_version:  str = "0.3.0"
    environment:  str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    signal_source: str = field(default_factory=lambda: os.getenv("SIGNAL_SOURCE", "local_snapshot"))

    # Sentinel SSH connection settings (used when signal_source == "sentinel_ssh")
    sentinel_ssh_host:         str = field(default_factory=lambda: os.getenv("SENTINEL_SSH_HOST", ""))
    sentinel_ssh_user:         str = field(default_factory=lambda: os.getenv("SENTINEL_SSH_USER", "kkers"))
    sentinel_ssh_key_path:     str = field(default_factory=lambda: os.getenv("SENTINEL_SSH_KEY_PATH", ""))
    sentinel_snapshot_command: str = field(
        default_factory=lambda: os.getenv(
            "SENTINEL_SNAPSHOT_COMMAND",
            "python3 /data/ai-trading-bot/snapshot.py",
        )
    )

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
        ENVIRONMENT=production                          → False (no silent mock injection)
        ENVIRONMENT=production ALLOW_MOCK_FALLBACK=true → True  (explicit override)
        ENVIRONMENT=development                         → True  (safe for local work)
        ENVIRONMENT=development ALLOW_MOCK_FALLBACK=false → False (test prod behaviour locally)
        """
        env_val = os.getenv("ALLOW_MOCK_FALLBACK")
        if env_val is not None:
            return env_val.strip().lower() in ("1", "true", "yes")
        return not self.is_production


# Single shared instance imported everywhere
settings = Settings()
