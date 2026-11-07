"""Idempotent write of an ImportBatch into venues / venue_category_links / venue_facts.

- Upsert on (source_id, external_id); a re-run with the same data changes nothing but dates.
- New records start 'published' when the source has auto_publish, else 'draft'. An existing record keeps
  a status a human set, except 'retired', which is lifted when the record comes back.
- Records of this source that are not in the batch become 'retired' (never deleted).
- The batch's facts replace the stored facts of each record (imported records only hold imported facts).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from ingest.opendata import ImportBatch


def save_batch(conn: psycopg.Connection[Any], batch: ImportBatch, today: date) -> dict[str, int]:
    """Write `batch` inside the caller's transaction. Returns counts."""
    src = conn.execute("select auto_publish from data_sources where id = %s",
                       (batch.source_id,)).fetchone()
    if src is None:
        raise ValueError(f"unknown data source {batch.source_id!r} (missing seed in data_sources?)")
    new_status = "published" if src[0] else "draft"

    inserted = updated = 0
    for r in batch.records:
        row = conn.execute(
            """insert into venues (source_id, external_id, name, locality, voivodeship, address, lat, lon,
                   official_url, location_source_url, location_verified_at, first_seen_at, last_seen_at,
                   status)
               values (%(src)s, %(ext)s, %(name)s, %(loc)s, %(voi)s, %(addr)s, %(lat)s, %(lon)s, %(url)s,
                       %(data_url)s, %(today)s, %(today)s, %(today)s, %(status)s)
               on conflict (source_id, external_id) do update set
                   name = excluded.name, locality = excluded.locality,
                   voivodeship = excluded.voivodeship, address = excluded.address,
                   lat = excluded.lat, lon = excluded.lon, official_url = excluded.official_url,
                   location_source_url = excluded.location_source_url,
                   location_verified_at = excluded.location_verified_at,
                   last_seen_at = excluded.last_seen_at,
                   status = case when venues.status = 'retired' then excluded.status
                                 else venues.status end
               returning id, (xmax = 0) as inserted""",
            {"src": batch.source_id, "ext": r.external_id, "name": r.name, "loc": r.locality,
             "voi": r.voivodeship, "addr": r.address, "lat": r.lat, "lon": r.lon,
             "url": r.official_url, "data_url": batch.data_url, "today": today, "status": new_status},
        ).fetchone()
        assert row is not None
        venue_id, was_inserted = int(row[0]), bool(row[1])
        inserted += was_inserted
        updated += not was_inserted

        conn.execute("delete from venue_category_links where venue_id = %s", (venue_id,))
        for cat in r.categories:
            conn.execute("insert into venue_category_links (venue_id, category) values (%s, %s)",
                         (venue_id, cat))
        conn.execute("delete from venue_facts where venue_id = %s", (venue_id,))
        for f in r.facts:
            conn.execute(
                """insert into venue_facts (venue_id, fact_key, value, short_pl, note_pl, source_type,
                       source_url, verified_at)
                   values (%s, %s, %s, %s, %s, 'open_data', %s, %s)""",
                (venue_id, f.key, Jsonb(f.value), f.short, f.note, batch.data_url, today),
            )

    seen = [r.external_id for r in batch.records]
    retired = conn.execute(
        """update venues set status = 'retired'
           where source_id = %s and status <> 'retired' and not (external_id = any(%s))""",
        (batch.source_id, seen),
    ).rowcount
    return {"seen": len(seen), "inserted": inserted, "updated": updated, "retired": retired,
            "skipped": batch.skipped}


def log_run(conn: psycopg.Connection[Any], source_id: str, started_at: datetime, finished_at: datetime,
            status: str, *, data_url: str | None = None, data_as_of: date | None = None,
            raw_fetch_id: int | None = None, counts: dict[str, int] | None = None,
            error: str | None = None) -> None:
    c = counts or {}
    conn.execute(
        """insert into import_runs (source_id, started_at, finished_at, status, data_url, data_as_of,
               raw_fetch_id, n_seen, n_inserted, n_updated, n_retired, error)
           values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (source_id, started_at, finished_at, status, data_url, data_as_of, raw_fetch_id,
         c.get("seen"), c.get("inserted"), c.get("updated"), c.get("retired"), error),
    )
