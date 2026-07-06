import logging
import os
from dataclasses import dataclass, field

_log = logging.getLogger(__name__)


def _int_env(var: str, default: int) -> int:
    raw = os.getenv(var, str(default))
    try:
        return int(raw)
    except ValueError:
        _log.warning("Invalid value %r for %s; using default %d", raw, var, default)
        return default


@dataclass
class Settings:
    app_name:     str = "AlphaForgeAI"
    app_version:  str = "0.6.0"
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
    signal_freshness_warn_hours: int = field(
        default_factory=lambda: _int_env("SIGNAL_FRESHNESS_WARN_HOURS", 24)
    )
    signal_stale_after_hours: int = field(
        default_factory=lambda: _int_env("SIGNAL_STALE_AFTER_HOURS", 48)
    )
    signal_stale_action: str = field(
        default_factory=lambda: os.getenv("SIGNAL_STALE_ACTION", "mark").strip().lower()
    )

    # ── Ingest API ───────────────────────────────────────────────────────────
    # Bearer token required by POST /api/signals/ingest.
    # Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    signal_ingest_api_key: str = field(
        default_factory=lambda: os.getenv("SIGNAL_INGEST_API_KEY", "")
    )

    # ── GCS signal storage ───────────────────────────────────────────────────
    # Bucket that stores the live sentinel_push snapshot (latest.json).
    # The Cloud Run service account must have roles/storage.objectAdmin on it.
    gcs_signals_bucket: str = field(
        default_factory=lambda: os.getenv("GCS_SIGNALS_BUCKET", "alphaforgeai-signals")
    )

    # ── Explainer ingest API ─────────────────────────────────────────────────
    # Bearer token required by POST /api/explainers/ingest.
    # Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    explainer_ingest_api_key: str = field(
        default_factory=lambda: os.getenv("EXPLAINER_INGEST_API_KEY", "")
    )

    # ── GCS explainer storage ────────────────────────────────────────────────
    gcs_explainers_bucket: str = field(
        default_factory=lambda: os.getenv("GCS_EXPLAINERS_BUCKET", "alphaforgeai-explainers")
    )

    # ── News ingest API ──────────────────────────────────────────────────────
    # Bearer token required by POST /api/news/ingest.
    # Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    news_ingest_api_key: str = field(
        default_factory=lambda: os.getenv("NEWS_INGEST_API_KEY", "")
    )

    # ── GCS news storage ─────────────────────────────────────────────────────
    gcs_news_bucket: str = field(
        default_factory=lambda: os.getenv("GCS_NEWS_BUCKET", "alphaforgeai-news")
    )

    # ── Blog ingest API ──────────────────────────────────────────────────────
    # Bearer token required by POST /api/blog/ingest.
    # Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
    blog_ingest_api_key: str = field(
        default_factory=lambda: os.getenv("BLOG_INGEST_API_KEY", "")
    )

    # ── GCS blog storage ──────────────────────────────────────────────────────
    gcs_blog_bucket: str = field(
        default_factory=lambda: os.getenv("GCS_BLOG_BUCKET", "alphaforgeai-blog")
    )

    # ── Whale alert ingest API ───────────────────────────────────────────────
    whale_alerts_ingest_api_key: str = field(
        default_factory=lambda: os.getenv("WHALE_ALERTS_INGEST_API_KEY", "")
    )

    # ── GCS whale alert storage ──────────────────────────────────────────────
    gcs_whale_alerts_bucket: str = field(
        default_factory=lambda: os.getenv("GCS_WHALE_ALERTS_BUCKET", "alphaforgeai-whale-alerts")
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
        default_factory=lambda: _int_env("SENTINEL_SSH_TIMEOUT", 18)
    )

    # StrictHostKeyChecking: False (default) skips known-hosts verification,
    # which is safe for a trusted LAN host and avoids first-run key prompts.
    # Set SENTINEL_SSH_STRICT_HOST_KEY=true to enable strict checking.
    sentinel_ssh_strict_host_key_checking: bool = field(
        default_factory=lambda: os.getenv(
            "SENTINEL_SSH_STRICT_HOST_KEY", "false"
        ).strip().lower() in ("1", "true", "yes")
    )

    # ── Signal display limit ─────────────────────────────────────────────────
    # Max signals shown on /signals, ranked by confidence desc before limiting.
    # 0 = show all. Override with SIGNAL_DISPLAY_LIMIT env var or ?limit=all.
    signal_display_limit: int = field(
        default_factory=lambda: _int_env("SIGNAL_DISPLAY_LIMIT", 10)
    )

    # ── Confluence engine ────────────────────────────────────────────────────
    # SIGNAL_CONFLUENCE=true  → run the multi-TF confluence engine after load
    # SIGNAL_CONFLUENCE_FILTER=true → only return confluent signals (full/partial)
    signal_confluence: bool = field(
        default_factory=lambda: os.getenv("SIGNAL_CONFLUENCE", "false").strip().lower()
        in ("1", "true", "yes")
    )
    signal_confluence_filter: bool = field(
        default_factory=lambda: os.getenv("SIGNAL_CONFLUENCE_FILTER", "false").strip().lower()
        in ("1", "true", "yes")
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
