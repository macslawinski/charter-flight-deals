"""Postgres persistence: raw_fetches, flights, price_snapshots."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timedelta
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

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


def connect(database_url: str) -> psycopg.Connection[Any]:
    # prepare_threshold=None: Supabase's transaction pooler does not support prepared statements.
    return psycopg.connect(database_url, prepare_threshold=None)


def save_raw_fetch(conn: psycopg.Connection[Any], operator: str, request: dict[str, Any],
                   response: Any, status: int, fetched_at: datetime) -> int:
    """Store one raw response (or run bundle). Returns the raw_fetches id."""
    row = conn.execute(
        """insert into raw_fetches (operator, fetched_at, http_status, request, response)
           values (%s, %s, %s, %s, %s) returning id""",
        (operator, fetched_at, status, Jsonb(request), Jsonb(response)),
    ).fetchone()
    assert row is not None
    return int(row[0])


def mark_parse_result(conn: psycopg.Connection[Any], raw_id: int, error: str | None) -> None:
    conn.execute(
        "update raw_fetches set parse_ok = %s, parse_error = %s where id = %s",
        (error is None, error, raw_id),
    )


_STAGE = """
create temp table stage_offers (
    flight_key text, operator text, origin_iata text, dest_iata text,
    outbound_date date, return_date date, flight_no text,
    price numeric(10, 2), seats_left integer, observed_at timestamptz
) on commit drop
"""

_UPSERT_FLIGHTS = """
insert into flights (flight_key, operator, origin_iata, dest_iata, outbound_date, return_date,
                     flight_no, first_seen_at, last_seen_at)
select flight_key, operator, origin_iata, dest_iata, outbound_date, return_date,
       flight_no, observed_at, observed_at
from stage_offers
on conflict (flight_key) do update
    set last_seen_at  = greatest(flights.last_seen_at, excluded.last_seen_at),
        first_seen_at = least(flights.first_seen_at, excluded.first_seen_at)
"""

_UPSERT_SNAPSHOTS = """
insert into price_snapshots as ps (flight_key, snapshot_date, price_last, price_min, seats_left,
                                   n_obs, first_observed_at, last_observed_at)
select flight_key, %(snapshot_date)s, price, price, seats_left, 1, observed_at, observed_at
from stage_offers
on conflict (flight_key, snapshot_date) do update
    set price_last = case when excluded.last_observed_at >= ps.last_observed_at
                          then excluded.price_last else ps.price_last end,
        seats_left = case when excluded.last_observed_at >= ps.last_observed_at
                          then excluded.seats_left else ps.seats_left end,
        price_min  = least(ps.price_min, excluded.price_min),
        n_obs      = ps.n_obs + 1,
        first_observed_at = least(ps.first_observed_at, excluded.first_observed_at),
        last_observed_at  = greatest(ps.last_observed_at, excluded.last_observed_at)
"""


def upsert_offers(conn: psycopg.Connection[Any], offers: list[FlightOffer],
                  snapshot_date: date) -> int:
    """Upsert flights and the day's price snapshot. `offers` must be deduped (one per key).

    Runs inside the caller's transaction. Returns the number of offers written.
    """
    keys = [o.flight_key for o in offers]
    if len(keys) != len(set(keys)):
        raise ValueError("upsert_offers needs deduped offers (one per flight_key)")
    if not offers:
        return 0
    conn.execute(_STAGE)
    with conn.cursor() as cur, cur.copy("copy stage_offers from stdin") as copy:
        for o in offers:
            copy.write_row((o.flight_key, o.operator, o.origin_iata, o.dest_iata,
                            o.outbound_date, o.return_date, o.flight_no,
                            o.price_pln, o.seats_left, o.observed_at))
    conn.execute(_UPSERT_FLIGHTS)
    conn.execute(_UPSERT_SNAPSHOTS, {"snapshot_date": snapshot_date})
    conn.execute("drop table stage_offers")  # allow several upserts in one transaction
    return len(offers)


def refresh_deals(conn: psycopg.Connection[Any], as_of: date) -> int:
    """Recompute the `deals` rows for `as_of` (SQL in 004_transform.sql). Returns deal count."""
    row = conn.execute("select refresh_deals(%s)", (as_of,)).fetchone()
    assert row is not None
    return int(row[0])


def prune_raw_fetches(conn: psycopg.Connection[Any], now: datetime, keep_days: int = 14) -> int:
    """Delete raw responses older than `keep_days`. Returns rows deleted."""
    cur = conn.execute("delete from raw_fetches where fetched_at < %s",
                       (now - timedelta(days=keep_days),))
    return cur.rowcount
