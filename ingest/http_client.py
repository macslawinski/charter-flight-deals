"""Polite HTTP client: random delay, request cap, backoff on 429/5xx, hard stop on 403."""

from __future__ import annotations

import logging
import random
import time
from typing import Any, Protocol, Self

import httpx

from ingest.config import Settings, SourceConfig

log = logging.getLogger(__name__)


class BlockedError(RuntimeError):
    """403 received: we are likely blocked. The run must stop, not retry."""


class RequestCapReached(RuntimeError):
    """max_requests_per_run exhausted."""


class Fetcher(Protocol):
    """What source crawlers need from a client (PoliteClient, or a fake in tests)."""

    def fetch(
        self,
        source: SourceConfig,
        payload: dict[str, Any] | None = None,
        *,
        path: str = "",
        params: list[tuple[str, str]] | None = None,
    ) -> httpx.Response: ...


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

    @property
    def request_count(self) -> int:
        return self._count

    def fetch(
        self,
        source: SourceConfig,
        payload: dict[str, Any] | None = None,
        *,
        path: str = "",
        params: list[tuple[str, str]] | None = None,
    ) -> httpx.Response:
        """Send one request to `source.url` + `path`. `params` may repeat keys (list of pairs)."""
        headers = dict(source.headers)
        if source.cookie:
            headers["Cookie"] = source.cookie
        if source.token_header and source.token:
            headers[source.token_header] = source.token
        url = f"{source.url.rstrip('/')}/{path.lstrip('/')}" if path else source.url

        cap = source.max_requests_per_run or self._s.max_requests_per_run
        lo, hi = delay_range(self._s, source)
        for attempt in range(self._s.max_retries + 1):
            if self._count >= cap:
                raise RequestCapReached(f"cap of {cap} requests reached")
            if self._count > 0:
                time.sleep(random.uniform(lo, hi))
            self._count += 1

            try:
                resp = self._client.request(
                    source.method, url, headers=headers,
                    params=tuple(params) if params else None, json=payload,
                    follow_redirects=source.follow_redirects,
                )
            except httpx.TransportError as e:  # timeouts, TLS/connection resets: transient
                if attempt == self._s.max_retries:
                    raise
                wait = min(2**attempt * 5, 300)
                log.warning("%r, attempt %s, sleeping %ss", e, attempt + 1, wait)
                time.sleep(wait)
                continue
            # Every redirect hop is a real request to the site: count it against the cap.
            self._count += len(resp.history)

            if resp.status_code == 403:
                raise BlockedError(f"403 from {url}; stopping run")
            if resp.status_code == 429 or resp.status_code >= 500:
                wait = _retry_after(resp) or min(2**attempt * 5, 300)
                log.warning("HTTP %s, attempt %s, sleeping %ss", resp.status_code, attempt + 1, wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp

        raise RuntimeError(f"giving up on {url} after {self._s.max_retries + 1} attempts")


def delay_range(settings: Settings, source: SourceConfig) -> tuple[float, float]:
    """Random delay bounds between requests: the source's override, else [defaults]."""
    lo = settings.min_delay_seconds if source.min_delay_seconds is None else source.min_delay_seconds
    hi = settings.max_delay_seconds if source.max_delay_seconds is None else source.max_delay_seconds
    if not 0 <= lo <= hi:
        raise ValueError(f"source {source.name}: bad delay range {lo}..{hi}")
    return lo, hi


def _retry_after(resp: httpx.Response) -> float | None:
    value = resp.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None
