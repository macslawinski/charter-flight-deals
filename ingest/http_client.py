"""Polite HTTP client: random delay, request cap, backoff on 429/5xx, hard stop on 403."""

from __future__ import annotations

import logging
import random
import time
from typing import Any, Self

import httpx

from ingest.config import Settings, SourceConfig

log = logging.getLogger(__name__)


class BlockedError(RuntimeError):
    """403 received: we are likely blocked. The run must stop, not retry."""


class RequestCapReached(RuntimeError):
    """max_requests_per_run exhausted."""


class PoliteClient:
    def __init__(self, settings: Settings) -> None:
        self._s = settings
        self._count = 0
        self._client = httpx.Client(
            timeout=settings.timeout_seconds,
            headers={"User-Agent": settings.user_agent},
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self._client.close()

    def fetch(self, source: SourceConfig, payload: dict[str, Any] | None = None) -> httpx.Response:
        headers = dict(source.headers)
        if source.cookie:
            headers["Cookie"] = source.cookie

        for attempt in range(self._s.max_retries + 1):
            if self._count >= self._s.max_requests_per_run:
                raise RequestCapReached(f"cap of {self._s.max_requests_per_run} requests reached")
            if self._count > 0:
                time.sleep(random.uniform(self._s.min_delay_seconds, self._s.max_delay_seconds))
            self._count += 1

            resp = self._client.request(source.method, source.url, headers=headers, json=payload)

            if resp.status_code == 403:
                raise BlockedError(f"403 from {source.url}; stopping run")
            if resp.status_code == 429 or resp.status_code >= 500:
                wait = _retry_after(resp) or min(2**attempt * 5, 300)
                log.warning("HTTP %s, attempt %s, sleeping %ss", resp.status_code, attempt + 1, wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp

        raise RuntimeError(f"giving up on {source.url} after {self._s.max_retries + 1} attempts")


def _retry_after(resp: httpx.Response) -> float | None:
    value = resp.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None
