"""Open-data importers for the parents' service (Product B extension).

Each source module turns one raw download into an `ImportBatch`; `ingest.opendata.save` writes it
idempotently (upsert on source_id + external_id, vanished records retired, never deleted).
CLI: `python -m ingest.opendata --source <name>`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

SHORT_MAX = 80  # venue_facts.short_pl check constraint

# Rough bounding box of Poland: coordinates outside it are dropped, not stored.
PL_LAT = (49.0, 55.0)
PL_LON = (14.0, 24.2)


@dataclass(frozen=True)
class OpenFact:
    key: str                      # fact_keys.key
    value: dict[str, Any]
    short: str                    # one line on a card (<= SHORT_MAX)
    note: str | None = None


@dataclass(frozen=True)
class OpenRecord:
    external_id: str              # stable id within the source: the idempotency key
    name: str
    locality: str
    categories: tuple[str, ...]   # venue_categories.slug
    voivodeship: str | None = None
    address: str | None = None
    lat: float | None = None
    lon: float | None = None
    official_url: str | None = None
    facts: tuple[OpenFact, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ImportBatch:
    source_id: str                # data_sources.id
    data_url: str                 # the file the records came from (https), shown as the source
    data_as_of: date | None       # the source's own date, when it gives one
    records: tuple[OpenRecord, ...]
    skipped: int = 0              # rows deliberately left out (filler rows, non-public places...)


def short(text: str) -> str:
    """Trim a card line to SHORT_MAX characters."""
    text = " ".join(text.split())
    return text if len(text) <= SHORT_MAX else text[: SHORT_MAX - 1].rstrip() + "…"


def in_poland(lat: float | None, lon: float | None) -> bool:
    return (lat is not None and lon is not None
            and PL_LAT[0] <= lat <= PL_LAT[1] and PL_LON[0] <= lon <= PL_LON[1])
