"""Base adapter interface and adapter registry."""

from __future__ import annotations

import logging
import os
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import httpx
import yaml

from skill_gather.models import RawSkillEntry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# GitHub client helper (shared across adapters)
# ---------------------------------------------------------------------------

_GITHUB_API = "https://api.github.com"


def github_headers() -> dict[str, str]:
    """Build GitHub API request headers, using token if available."""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "skill-gather/0.1",
    }
    token = os.environ.get("GITHUB_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def github_client() -> httpx.Client:
    """Create a reusable httpx client for GitHub API calls."""
    return httpx.Client(
        base_url=_GITHUB_API,
        headers=github_headers(),
        timeout=30.0,
        follow_redirects=True,
    )


def github_get(client: httpx.Client, path: str, *, retries: int = 3) -> httpx.Response:
    """GET with retry and rate-limit logging for GitHub API."""
    last_resp: httpx.Response | None = None
    for attempt in range(retries):
        resp = client.get(path)
        last_resp = resp

        if resp.status_code not in (403, 429):
            return resp

        remaining = resp.headers.get("X-RateLimit-Remaining")
        if remaining == "0":
            reset = resp.headers.get("X-RateLimit-Reset", "?")
            logger.warning(
                "GitHub rate limit exceeded (reset epoch %s). "
                "Set GITHUB_TOKEN in .env for 5000 req/h.",
                reset,
            )
        elif not os.environ.get("GITHUB_TOKEN"):
            logger.warning(
                "GitHub API returned %d for %s — configure GITHUB_TOKEN to avoid limits.",
                resp.status_code,
                path,
            )

        if attempt + 1 >= retries:
            break

        retry_after = int(resp.headers.get("Retry-After", "2"))
        time.sleep(min(retry_after, 10))

    assert last_resp is not None
    return last_resp


# ---------------------------------------------------------------------------
# Source config model
# ---------------------------------------------------------------------------


class SourceConfig:
    """A single source entry parsed from adapters/config.yml."""

    def __init__(self, data: dict[str, Any]) -> None:
        self.id: str = data["id"]
        self.adapter: str = data["adapter"]
        self.enabled: bool = data.get("enabled", True)
        self.raw = data

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)

    def __repr__(self) -> str:
        return f"SourceConfig(id={self.id!r}, adapter={self.adapter!r}, enabled={self.enabled})"


# ---------------------------------------------------------------------------
# Base adapter
# ---------------------------------------------------------------------------


class BaseAdapter(ABC):
    """Abstract base class for all source adapters.

    Subclasses implement `discover()` which returns raw skill entries.
    The `sync()` method orchestrates the full flow.
    """

    def __init__(self, config: SourceConfig) -> None:
        self.config = config
        self.logger = logging.getLogger(f"adapter.{config.id}")

    @abstractmethod
    def discover(self) -> list[RawSkillEntry]:
        """Discover skills from the source. Returns raw entries."""
        ...

    def peek_fingerprint(self) -> str | None:
        """Return a cheap upstream fingerprint for incremental sync, or None."""
        return None

    def sync(self) -> list[RawSkillEntry]:
        """Full sync flow: discover + validate + return."""
        if not self.config.enabled:
            self.logger.info("Source %s is disabled, skipping", self.config.id)
            return []

        self.logger.info("Syncing source: %s", self.config.id)
        entries = self.discover()
        valid = [e for e in entries if self._validate(e)]
        self.logger.info("Discovered %d skills (%d valid)", len(entries), len(valid))
        return valid

    def _validate(self, entry: RawSkillEntry) -> bool:
        """Basic validation: must have name and source_url."""
        if not entry.name:
            self.logger.warning("Skipping entry with empty name from %s", self.config.id)
            return False
        if not entry.source_url:
            self.logger.warning("Skipping entry %s with empty source_url", entry.name)
            return False
        return True


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

_CONFIG_PATH = Path(__file__).parent / "config.yml"


def load_sources_config(path: Path | None = None) -> list[SourceConfig]:
    """Load all source configurations from the YAML config file."""
    config_path = path or _CONFIG_PATH
    if not config_path.exists():
        raise FileNotFoundError(f"Adapter config not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    sources_raw = data.get("sources", [])
    sources = [SourceConfig(s) for s in sources_raw]
    logger.info("Loaded %d source configs from %s", len(sources), config_path)
    return sources


# ---------------------------------------------------------------------------
# Adapter registry
# ---------------------------------------------------------------------------

_ADAPTER_REGISTRY: dict[str, type[BaseAdapter]] = {}


def register_adapter(name: str):
    """Decorator to register an adapter class by name."""

    def decorator(cls: type[BaseAdapter]):
        _ADAPTER_REGISTRY[name] = cls
        return cls

    return decorator


def create_adapter(config: SourceConfig) -> BaseAdapter:
    """Instantiate the appropriate adapter for a given source config."""
    adapter_cls = _ADAPTER_REGISTRY.get(config.adapter)
    if adapter_cls is None:
        raise ValueError(
            f"Unknown adapter type '{config.adapter}' for source '{config.id}'. "
            f"Available: {list(_ADAPTER_REGISTRY.keys())}"
        )
    return adapter_cls(config)


def get_all_adapters(sources: list[SourceConfig] | None = None) -> list[BaseAdapter]:
    """Load config and instantiate all enabled adapters."""
    if sources is None:
        sources = load_sources_config()
    return [create_adapter(s) for s in sources if s.enabled]
