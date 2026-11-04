"""Loads config/sources.toml and environment variables."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO_ROOT / "config" / "sources.toml"


@dataclass(frozen=True)
class SourceConfig:
    name: str
    operator: str
    enabled: bool
    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)
    cookie_env: str | None = None
    token_env: str | None = None      # env var holding an API token (never in the toml)
    token_header: str | None = None   # header the token is sent in, e.g. X-Access-Token
    follow_redirects: bool = False
    max_requests_per_run: int | None = None  # overrides [defaults]; redirect hops count too
    # Override [defaults] delays, e.g. shorter for an official API with its own rate limits.
    min_delay_seconds: float | None = None
    max_delay_seconds: float | None = None

    @property
    def cookie(self) -> str | None:
        return os.environ.get(self.cookie_env) if self.cookie_env else None

    @property
    def token(self) -> str | None:
        if not self.token_env:
            return None
        return (os.environ.get(self.token_env) or "").strip() or None


@dataclass(frozen=True)
class Settings:
    min_delay_seconds: float
    max_delay_seconds: float
    max_requests_per_run: int
    max_retries: int
    timeout_seconds: float
    user_agent: str
    sources: dict[str, SourceConfig]
    database_url: str | None


def load_settings(path: Path = DEFAULT_CONFIG) -> Settings:
    load_dotenv(REPO_ROOT / ".env")
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    defaults = raw.get("defaults", {})
    sources = {
        name: SourceConfig(
            name=name,
            operator=cfg["operator"],
            enabled=cfg.get("enabled", False),
            method=cfg.get("method", "GET"),
            url=cfg["url"],
            headers=cfg.get("headers", {}),
            payload=cfg.get("payload", {}),
            cookie_env=cfg.get("cookie_env"),
            token_env=cfg.get("token_env"),
            token_header=cfg.get("token_header"),
            follow_redirects=bool(cfg.get("follow_redirects", False)),
            max_requests_per_run=cfg.get("max_requests_per_run"),
            min_delay_seconds=cfg.get("min_delay_seconds"),
            max_delay_seconds=cfg.get("max_delay_seconds"),
        )
        for name, cfg in raw.get("sources", {}).items()
    }
    return Settings(
        min_delay_seconds=defaults.get("min_delay_seconds", 3.0),
        max_delay_seconds=defaults.get("max_delay_seconds", 8.0),
        max_requests_per_run=defaults.get("max_requests_per_run", 50),
        max_retries=defaults.get("max_retries", 4),
        timeout_seconds=defaults.get("timeout_seconds", 30),
        user_agent=defaults.get("user_agent", "charter-flight-deals/0.1"),
        sources=sources,
        # strip(): secrets pasted into GitHub/Vercel UIs often carry a trailing newline.
        database_url=(os.environ.get("DATABASE_URL") or "").strip() or None,
    )
