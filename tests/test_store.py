"""DB tests against local Postgres (scripts/db_local.py). Skipped when it is not reachable.

Each test runs in a transaction that is rolled back, so cfd_local stays clean.
"""

import os
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import psycopg
import pytest

from ingest import store
from ingest.models import FlightOffer

DSN = os.environ.get("TEST_DATABASE_URL", "postgresql://postgres@localhost:5432/cfd_local")
T0 = datetime(2026, 11, 4, 8, 0, tzinfo=UTC)
T1 = datetime(2026, 11, 4, 14, 0, tzinfo=UTC)
D = date(2026, 11, 4)


@pytest.fixture
def conn() -> Iterator[psycopg.Connection[Any]]:
    try:
        c = store.connect(DSN)
    except psycopg.OperationalError:
        pytest.skip("local Postgres not available (run scripts/db_local.py)")
    try:
        yield c
    finally:
        c.rollback()
        c.close()


def offer(price: str, observed_at: datetime = T0, dest: str = "AYT") -> FlightOffer:
    return FlightOffer(operator="r_pl", origin_iata="WAW", dest_iata=dest,
                       outbound_date=date(2026, 12, 5), return_date=date(2026, 12, 12),
                       price_pln=Decimal(price), observed_at=observed_at,
                       flight_no="ENT4001/ENT4002")


def snapshot(conn, key: str, d: date = D) -> tuple[Any, ...]:
    row = conn.execute(
        """select price_last, price_min, n_obs, first_observed_at, last_observed_at
           from price_snapshots where flight_key = %s and snapshot_date = %s""", (key, d),
    ).fetchone()
    assert row is not None
    return row


def test_upsert_creates_flight_and_snapshot(conn):
    o = offer("1099")
    assert store.upsert_offers(conn, [o], D) == 1
    f = conn.execute("select origin_iata, dest_iata, stay_days, flight_no from flights "
                     "where flight_key = %s", (o.flight_key,)).fetchone()
    assert f == ("WAW", "AYT", 7, "ENT4001/ENT4002")
    assert snapshot(conn, o.flight_key) == (Decimal("1099.00"), Decimal("1099.00"), 1, T0, T0)


def test_second_run_same_day_updates_last_and_min(conn):
    store.upsert_offers(conn, [offer("1099", T0)], D)
    store.upsert_offers(conn, [offer("1199", T1)], D)
    assert snapshot(conn, offer("1").flight_key) == (
        Decimal("1199.00"), Decimal("1099.00"), 2, T0, T1)


def test_late_reparse_of_older_observation_does_not_override_last_price(conn):
    store.upsert_offers(conn, [offer("1199", T1)], D)
    store.upsert_offers(conn, [offer("999", T0)], D)  # e.g. reparse of an earlier raw fetch
    last, low, n, first, last_at = snapshot(conn, offer("1").flight_key)
    assert (last, low, n, first, last_at) == (Decimal("1199.00"), Decimal("999.00"), 2, T0, T1)


def test_next_day_gets_its_own_snapshot(conn):
    store.upsert_offers(conn, [offer("1099", T0)], D)
    store.upsert_offers(conn, [offer("899", T0 + timedelta(days=1))], D + timedelta(days=1))
    n = conn.execute("select count(*) from price_snapshots where flight_key = %s",
                     (offer("1").flight_key,)).fetchone()
    assert n == (2,)
    seen = conn.execute("select first_seen_at, last_seen_at from flights where flight_key = %s",
                        (offer("1").flight_key,)).fetchone()
    assert seen == (T0, T0 + timedelta(days=1))


def test_upsert_rejects_duplicates_within_batch(conn):
    with pytest.raises(ValueError, match="deduped"):
        store.upsert_offers(conn, [offer("1099"), offer("999")], D)


def test_raw_fetch_roundtrip_and_parse_flag(conn):
    raw_id = store.save_raw_fetch(conn, "r_pl", {"source": "r_pl"}, {"bundle_version": 1},
                                  200, T0)
    store.mark_parse_result(conn, raw_id, "missing required field $.x")
    row = conn.execute("select http_status, response->>'bundle_version', parse_ok, parse_error "
                       "from raw_fetches where id = %s", (raw_id,)).fetchone()
    assert row == (200, "1", False, "missing required field $.x")


def test_prune_keeps_recent_raw_fetches(conn):
    old = store.save_raw_fetch(conn, "r_pl", {}, {}, 200, T0 - timedelta(days=15))
    new = store.save_raw_fetch(conn, "r_pl", {}, {}, 200, T0 - timedelta(days=13))
    store.prune_raw_fetches(conn, T0, keep_days=14)
    ids = {r[0] for r in conn.execute("select id from raw_fetches where id in (%s, %s)",
                                      (old, new)).fetchall()}
    assert ids == {new}
