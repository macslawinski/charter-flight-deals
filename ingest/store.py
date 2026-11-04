"""Postgres persistence: raw_fetches, flights, price_snapshots."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from ingest.models import FlightOffer


def dedupe(offers: Iterable[FlightOffer]) -> list[FlightOffer]:
    """Keep one offer per flight_key within a run: the cheapest, latest observation on ties."""
    best: dict[str, FlightOffer] = {}
    for o in offers:
        cur = best.get(o.flight_key)
        if cur is None or (o.price_pln, -o.observed_at.timestamp()) < (
            cur.price_pln,
            -cur.observed_at.timestamp(),
        ):
            best[o.flight_key] = o
    return list(best.values())


def save_raw_fetch(conn: Any, operator: str, request: dict[str, Any], body: str,
                   status: int, fetched_at: datetime) -> int:
    raise NotImplementedError


def upsert_offers(conn: Any, offers: list[FlightOffer]) -> int:
    raise NotImplementedError
