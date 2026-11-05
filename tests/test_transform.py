"""Transform SQL (004_transform.sql) on synthetic data in local Postgres; rolled back per test.

Synthetic airports XXO (origin), XXL (long zone, min stay 7) and XXS (short zone, min stay 3)
keep segments disjoint from any real data loaded into cfd_local.
"""

import os
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import psycopg
import pytest

from ingest import store

DSN = os.environ.get("TEST_DATABASE_URL", "postgresql://postgres@localhost:5432/cfd_local")
D = date(2027, 1, 15)          # as_of
DEP = date(2027, 3, 10)        # departure in segment month 2027-03


@pytest.fixture
def db() -> Iterator[psycopg.Connection[Any]]:
    try:
        c = store.connect(DSN)
    except psycopg.OperationalError:
        pytest.skip("local Postgres not available (run scripts/db_local.py)")
    if c.execute("select to_regproc('compute_deals')").fetchone() == (None,):
        c.close()
        pytest.skip("transform not applied locally (run scripts/db_local.py)")
    c.execute("""update pipeline_params set window_days = 30, discount_threshold = 0.15,
                 min_baseline_flights = 5, min_history_days = 7, baseline_stat = 'avg',
                 default_min_stay_days = 3, include_one_way = false""")
    c.execute("""insert into destinations (iata, name, country, zone) values
                 ('XXL', 'Test long', 'Test', 'long'), ('XXS', 'Test short', 'Test', 'short')""")
    try:
        yield c
    finally:
        c.rollback()
        c.close()


def flight(db, n: int, dest: str = "XXL", stay: int = 7, dep: date = DEP) -> str:
    key = f"test|XXO|{dest}|{dep}|{n}"
    db.execute(
        """insert into flights (flight_key, operator, origin_iata, dest_iata, outbound_date,
                                return_date, flight_no) values (%s, 'test', 'XXO', %s, %s, %s, %s)""",
        (key, dest, dep, dep + timedelta(days=stay), str(n)),
    )
    return key


def price(db, key: str, day: date, value: float, n_obs: int = 1) -> None:
    t = datetime(day.year, day.month, day.day, 12, tzinfo=UTC)
    db.execute(
        """insert into price_snapshots (flight_key, snapshot_date, price_last, price_min, n_obs,
                                        first_observed_at, last_observed_at)
           values (%s, %s, %s, %s, %s, %s, %s)""",
        (key, day, value, value, n_obs, t, t),
    )


def history(db, key: str, value: float, days: int = 10) -> None:
    for i in range(1, days + 1):
        price(db, key, D - timedelta(days=i), value)


def deals(db, as_of: date = D) -> dict[str, dict[str, Any]]:
    cur = db.execute("select * from compute_deals(%s) where flight_key like 'test|%%'", (as_of,))
    assert cur.description is not None
    cols = [c.name for c in cur.description]
    return {r[1]: dict(zip(cols, r, strict=True)) for r in cur.fetchall()}


def segment(db, n_flights: int, dest: str = "XXL", base: float = 1600) -> list[str]:
    keys = [flight(db, i, dest) for i in range(n_flights)]
    for k in keys:
        history(db, k, base)
        price(db, k, D, base)
    return keys


def test_planted_deal_is_found_with_full_proof(db):
    keys = segment(db, 6)
    db.execute("update price_snapshots set price_last = 1249 where flight_key = %s and "
               "snapshot_date = %s", (keys[0], D))
    result = deals(db)
    assert list(result) == [keys[0]]
    d = result[keys[0]]
    assert d["current_price"] == Decimal("1249.00")
    assert d["baseline_avg"] == d["baseline_median"] == d["baseline_used"] == Decimal("1600.00")
    assert d["threshold_price"] == Decimal("1360.00")
    assert d["discount_pct"] == Decimal("21.94")
    assert (d["baseline_flights"], d["baseline_obs"]) == (6, 60)
    assert (d["window_start"], d["window_end"]) == (D - timedelta(days=30), D - timedelta(days=1))


def test_ten_percent_drop_is_not_flagged(db):
    keys = segment(db, 6)
    db.execute("update price_snapshots set price_last = 1440 where flight_key = %s and "
               "snapshot_date = %s", (keys[0], D))
    assert deals(db) == {}


def test_exactly_at_threshold_is_a_deal(db):
    keys = segment(db, 6)
    db.execute("update price_snapshots set price_last = 1360 where flight_key = %s and "
               "snapshot_date = %s", (keys[0], D))
    assert list(deals(db)) == [keys[0]]


def test_three_day_long_haul_is_dropped_and_not_in_baseline(db):
    keys = segment(db, 5)
    short_stay = flight(db, 99, stay=3)
    history(db, short_stay, 100)   # would drag the baseline down if counted
    price(db, short_stay, D, 50)   # would be a huge "deal" if not filtered
    db.execute("update price_snapshots set price_last = 1249 where flight_key = %s and "
               "snapshot_date = %s", (keys[0], D))
    result = deals(db)
    assert short_stay not in result
    assert result[keys[0]]["baseline_flights"] == 5
    assert result[keys[0]]["baseline_avg"] == Decimal("1600.00")


def test_three_day_stay_is_fine_for_short_zone(db):
    keys = [flight(db, i, "XXS", stay=3) for i in range(5)]
    for k in keys:
        history(db, k, 800)
        price(db, k, D, 800)
    db.execute("update price_snapshots set price_last = 500 where flight_key = %s and "
               "snapshot_date = %s", (keys[0], D))
    assert list(deals(db)) == [keys[0]]


def test_segment_with_too_few_flights_yields_no_deal(db):
    keys = segment(db, 4)
    db.execute("update price_snapshots set price_last = 400 where flight_key = %s and "
               "snapshot_date = %s", (keys[0], D))
    assert deals(db) == {}


def test_segment_with_too_little_history_yields_no_deal(db):
    # 010: 6 flights but only 6 days of history (< min_history_days 7): no deal yet ...
    keys = [flight(db, i) for i in range(6)]
    for k in keys:
        history(db, k, 1600, days=6)
        price(db, k, D, 1600)
    db.execute("update price_snapshots set price_last = 1000 where flight_key = %s and "
               "snapshot_date = %s", (keys[0], D))
    assert deals(db) == {}
    # ... one more day, even from a single flight in the segment, and the deal shows up.
    price(db, keys[1], D - timedelta(days=7), 1600)
    assert list(deals(db)) == [keys[0]]


def test_history_outside_window_does_not_count(db):
    keys = [flight(db, i) for i in range(6)]
    for k in keys:
        history(db, k, 1600, days=6)
        price(db, k, D - timedelta(days=31), 1600)  # old day: outside the 30-day window
        price(db, k, D, 1600)
    db.execute("update price_snapshots set price_last = 1000 where flight_key = %s and "
               "snapshot_date = %s", (keys[0], D))
    assert deals(db) == {}


def test_one_vote_per_flight(db):
    # One flight seen 10x at 1000, four seen once at 2000: per-flight baseline = 1800,
    # an observation-weighted average would be ~1286 and miss this deal.
    heavy = flight(db, 0)
    history(db, heavy, 1000, days=10)
    light = [flight(db, i) for i in range(1, 5)]
    for k in light:
        price(db, k, D - timedelta(days=3), 2000)
    target = light[0]
    price(db, target, D, 1500)
    d = deals(db)[target]
    assert d["baseline_avg"] == Decimal("1800.00")
    assert d["baseline_median"] == Decimal("2000.00")
    assert (d["baseline_flights"], d["baseline_obs"]) == (5, 14)


def test_todays_prices_do_not_pull_baseline_down(db):
    keys = segment(db, 6)
    for k in keys:  # everyone drops today: baseline must still be yesterday's 1600
        db.execute("update price_snapshots set price_last = 1200 where flight_key = %s and "
                   "snapshot_date = %s", (k, D))
    result = deals(db)
    assert len(result) == 6
    assert {d["baseline_avg"] for d in result.values()} == {Decimal("1600.00")}


def test_snapshots_outside_window_are_ignored(db):
    keys = segment(db, 6)
    for k in keys:  # very old high prices must not inflate the baseline
        price(db, k, D - timedelta(days=31), 9999)
    db.execute("update price_snapshots set price_last = 1440 where flight_key = %s and "
               "snapshot_date = %s", (keys[0], D))
    assert deals(db) == {}


def test_departed_flight_is_not_a_deal(db):
    keys = [flight(db, i, dep=D) for i in range(6)]  # departs on as_of itself
    for k in keys:
        history(db, k, 1600)
        price(db, k, D, 1000)
    assert deals(db) == {}


def test_median_baseline_stat(db):
    keys = [flight(db, i) for i in range(5)]
    for k, base in zip(keys, [1000, 1000, 1600, 1600, 1600], strict=True):
        history(db, k, base)
        price(db, k, D, base)
    db.execute("update pipeline_params set baseline_stat = 'median'")
    db.execute("update price_snapshots set price_last = 1300 where flight_key = %s and "
               "snapshot_date = %s", (keys[2], D))
    d = deals(db)[keys[2]]  # avg 1360 -> threshold 1156 (no deal); median 1600 -> 1360 (deal)
    assert d["baseline_used"] == Decimal("1600.00")
    assert d["baseline_avg"] == Decimal("1360.00")


def other_operator_flight(db, n: int, base: float) -> str:
    """Same route and month as flight(), sold by another operator ('test2')."""
    key = f"test2|XXO|XXL|{DEP}|{n}"
    db.execute(
        """insert into flights (flight_key, operator, origin_iata, dest_iata, outbound_date,
                                return_date, flight_no) values (%s, 'test2', 'XXO', 'XXL', %s, %s, %s)""",
        (key, DEP, DEP + timedelta(days=7), str(n)),
    )
    history(db, key, base)
    price(db, key, D, base)
    return key


def test_baseline_is_per_operator(db):
    # 6 flights of another operator at 1000 on the same route/month must neither pull this
    # operator's baseline down (1600 -> deal at 1249 stays a deal) ...
    for i in range(6):
        other_operator_flight(db, i, 1000)
    keys = segment(db, 6)
    db.execute("update price_snapshots set price_last = 1249 where flight_key = %s and "
               "snapshot_date = %s", (keys[0], D))
    d = deals(db)[keys[0]]
    assert (d["baseline_avg"], d["baseline_flights"]) == (Decimal("1600.00"), 6)


def test_other_operator_flights_do_not_fill_a_thin_segment(db):
    # ... nor make up the min_baseline_flights for a segment this operator barely sells.
    for i in range(6):
        other_operator_flight(db, i, 1600)
    keys = segment(db, 2)
    db.execute("update price_snapshots set price_last = 900 where flight_key = %s and "
               "snapshot_date = %s", (keys[0], D))
    assert deals(db) == {}


def test_itaka_destinations_are_seeded_with_their_zone(db):
    # 007: without the seed FUE fell back to default_min_stay_days (3) and a 3-day trip passed.
    short = "test|XXO|FUE|2027-03-10|3d"
    week = "test|XXO|FUE|2027-03-10|7d"
    for key, stay in ((short, 3), (week, 7)):
        db.execute(
            """insert into flights (flight_key, operator, origin_iata, dest_iata, outbound_date,
                                    return_date) values (%s, 'test', 'XXO', 'FUE', %s, %s)""",
            (key, DEP, DEP + timedelta(days=stay)),
        )
    eligible = {r[0] for r in db.execute(
        "select flight_key from eligible_flights where dest_iata = 'FUE' and operator = 'test'")}
    assert eligible == {week}


def test_turkish_aegean_destinations_match_antalya(db):
    # 008: same zone as AYT, not the default min stay.
    rows = db.execute("select iata, zone from destinations "
                      "where iata in ('AYT', 'ADB', 'BJV', 'DLM')").fetchall()
    assert dict(rows) == dict.fromkeys(("AYT", "ADB", "BJV", "DLM"), "medium")


def test_unknown_destinations_are_reported(db):
    flight(db, 1)  # XXL is seeded by the fixture
    db.execute(
        """insert into flights (flight_key, operator, origin_iata, dest_iata, outbound_date,
                                return_date) values ('test|XXO|QQQ|x', 'test', 'XXO', 'QQQ', %s, %s)""",
        (DEP, DEP + timedelta(days=7)),
    )
    assert store.unknown_destinations(db, "test") == ["QQQ"]


def test_refresh_deals_is_idempotent(db):
    keys = segment(db, 6)
    db.execute("update price_snapshots set price_last = 1249 where flight_key = %s and "
               "snapshot_date = %s", (keys[0], D))
    assert db.execute("select refresh_deals(%s)", (D,)).fetchone() == (1,)
    assert db.execute("select refresh_deals(%s)", (D,)).fetchone() == (1,)
    n = db.execute("select count(*) from deals where as_of = %s and flight_key like 'test|%%'",
                   (D,)).fetchone()
    assert n == (1,)
