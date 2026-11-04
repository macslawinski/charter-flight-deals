"""Postgres persistence: raw_fetches, flights, price_snapshots, market reference fares."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timedelta
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from ingest.models import FlightOffer, MarketFare, Segment


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


def unknown_destinations(conn: psycopg.Connection[Any], operator: str) -> list[str]:
    """Destinations of `operator`'s flights missing from `destinations`.

    They silently fall back to default_min_stay_days, which can let a too-short long-haul trip
    through the sensible-stay filter; the run logs them so they get seeded.
    """
    rows = conn.execute(
        """select distinct f.dest_iata from flights f
           where f.operator = %s
             and not exists (select 1 from destinations d where d.iata = f.dest_iata)
           order by 1""",
        (operator,),
    ).fetchall()
    return [r[0] for r in rows]


def refresh_deals(conn: psycopg.Connection[Any], as_of: date) -> int:
    """Recompute the `deals` rows for `as_of` (SQL in 004_transform.sql). Returns deal count."""
    row = conn.execute("select refresh_deals(%s)", (as_of,)).fetchone()
    assert row is not None
    return int(row[0])


_MARKET_SEGMENTS = """
with seg as (
    select distinct e.origin_iata::text as origin_iata, e.dest_iata::text as dest_iata, e.dep_month
    from eligible_flights e
    where e.return_date is not null
      and e.outbound_date > %(as_of)s and e.outbound_date <= %(as_of)s + %(horizon)s
),
deal_seg as (
    select distinct f.origin_iata::text as origin_iata, f.dest_iata::text as dest_iata,
           date_trunc('month', f.outbound_date)::date as dep_month
    from deals d
    join flights f on f.flight_key = d.flight_key
    where d.as_of = %(as_of)s and f.return_date is not null
),
last_fetch as (
    select origin_iata::text as origin_iata, dest_iata::text as dest_iata, dep_month,
           max(fetched_date) as last_date, max(fetched_at) as last_at
    from market_fetches
    where source = %(source)s
    group by 1, 2, 3
)
select s.origin_iata, s.dest_iata, s.dep_month
from (select * from seg union select * from deal_seg) s
left join deal_seg ds using (origin_iata, dest_iata, dep_month)
left join last_fetch lf using (origin_iata, dest_iata, dep_month)
where lf.last_date is distinct from %(as_of)s   -- at most one fetch per segment per day
order by (ds.origin_iata is null), lf.last_at nulls first, s.dep_month, s.origin_iata, s.dest_iata
limit %(limit)s
"""


def market_segments(conn: psycopg.Connection[Any], source: str, as_of: date, horizon_days: int,
                    limit: int) -> list[Segment]:
    """Segments to fetch reference fares for: segments with deals on `as_of` first, then upcoming
    segments (within `horizon_days`) never or least recently fetched. Skips ones fetched today."""
    rows = conn.execute(_MARKET_SEGMENTS, {"as_of": as_of, "horizon": horizon_days,
                                           "source": source, "limit": limit}).fetchall()
    return [Segment(o, d, m) for o, d, m in rows]


def save_market(conn: psycopg.Connection[Any], parsed: dict[Segment, list[MarketFare]],
                source: str, fetched_at: datetime, fetched_date: date) -> int:
    """Store one fetch per segment (also empty ones) and its fares; a same-day refetch replaces
    the day's rows. Runs inside the caller's transaction. Returns the number of fares written."""
    n = 0
    for seg, fares in parsed.items():
        next_month = (seg.dep_month + timedelta(days=32)).replace(day=1)
        conn.execute(
            """insert into market_fetches (source, origin_iata, dest_iata, dep_month, fetched_date,
                                           fetched_at, n_fares)
               values (%s, %s, %s, %s, %s, %s, %s)
               on conflict (source, origin_iata, dest_iata, dep_month, fetched_date) do update
                   set fetched_at = excluded.fetched_at, n_fares = excluded.n_fares""",
            (source, seg.origin_iata, seg.dest_iata, seg.dep_month, fetched_date, fetched_at,
             len(fares)),
        )
        conn.execute(
            """delete from market_fares
               where source = %s and origin_iata = %s and dest_iata = %s and fetched_date = %s
                 and outbound_date >= %s and outbound_date < %s""",
            (source, seg.origin_iata, seg.dest_iata, fetched_date, seg.dep_month, next_month),
        )
        if not fares:
            continue
        with conn.cursor() as cur:
            cur.executemany(
                """insert into market_fares (source, origin_iata, dest_iata, outbound_date,
                       return_date, airline, origin_airport, dest_airport, flight_no, transfers,
                       return_transfers, price_pln, found_date, link, fetched_date, fetched_at)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                [(f.source, f.origin_iata, f.dest_iata, f.outbound_date, f.return_date, f.airline,
                  f.origin_airport, f.dest_airport, f.flight_no, f.transfers, f.return_transfers,
                  f.price_pln, f.found_date, f.link, fetched_date, fetched_at) for f in fares],
            )
        n += len(fares)
    return n


def prune_market(conn: psycopg.Connection[Any], today: date, keep_days: int = 30) -> int:
    """Delete reference fares/fetch log older than `keep_days`. Returns fare rows deleted."""
    cutoff = today - timedelta(days=keep_days)
    conn.execute("delete from market_fetches where fetched_date < %s", (cutoff,))
    return conn.execute("delete from market_fares where fetched_date < %s", (cutoff,)).rowcount


def prune_raw_fetches(conn: psycopg.Connection[Any], now: datetime, keep_days: int = 14) -> int:
    """Delete raw responses older than `keep_days`. Returns rows deleted."""
    cur = conn.execute("delete from raw_fetches where fetched_at < %s",
                       (now - timedelta(days=keep_days),))
    return cur.rowcount
