"""Regular-airline reference (005_market_fares.sql) + store.save_market/market_segments on
synthetic data in local Postgres; rolled back per test. Display-only: deals must not change."""

import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import export_deals
from test_transform import DEP, D, db, flight, history, price  # noqa: F401  (db is a fixture)

from ingest import store
from ingest.models import MarketFare, Segment

SEG = Segment("XXO", "XXL", DEP.replace(day=1))
T = datetime(D.year, D.month, D.day, 10, tzinfo=UTC)


def planted_deal(db) -> str:  # noqa: F811
    """Six flights at 1600 in the window, one of them at 1249 today -> one deal (stay 7)."""
    keys = [flight(db, i) for i in range(6)]
    for k in keys:
        history(db, k, 1600)
        price(db, k, D, 1600)
    db.execute("update price_snapshots set price_last = 1249 where flight_key = %s and "
               "snapshot_date = %s", (keys[0], D))
    assert db.execute("select refresh_deals(%s)", (D,)).fetchone() == (1,)
    return keys[0]


def fare(out: date, stay: int, airline: str, p: float, transfers: int = 0) -> MarketFare:
    return MarketFare("travelpayouts", "XXO", "XXL", out, out + timedelta(days=stay), airline,
                      transfers, 0, Decimal(str(p)), origin_airport="XXO", dest_airport="XXL",
                      link="/search/x")


def save(db, fares: list[MarketFare], day: date = D) -> None:  # noqa: F811
    t = datetime(day.year, day.month, day.day, 10, tzinfo=UTC)
    store.save_market(db, {SEG: fares}, "travelpayouts", t, day)


def ref(db, as_of: date = D) -> list[dict]:  # noqa: F811
    cur = db.execute("select * from market_reference(%s) where flight_key like 'test|%%'", (as_of,))
    cols = [c.name for c in cur.description or []]
    return [dict(zip(cols, r, strict=True)) for r in cur.fetchall()]


def test_cheapest_direct_regular_fare_with_similar_stay(db):  # noqa: F811
    key = planted_deal(db)
    save(db, [
        fare(DEP, 7, "W6", 900),                       # candidate (same dates)
        fare(DEP + timedelta(days=5), 9, "FR", 850),   # stay 9 vs 7: within ±2 -> cheapest valid
        fare(DEP, 7, "E4", 500),                       # charter: ignored
        fare(DEP, 7, "ZZ", 400),                       # unknown airline: ignored
        fare(DEP, 7, "LO", 300, transfers=1),          # not direct: ignored
        fare(DEP, 3, "W6", 200),                       # stay 3 vs 7: ignored
        fare(DEP.replace(day=1) + timedelta(days=31), 7, "W6", 100),  # next month: other segment
    ])
    [r] = ref(db)
    assert r["flight_key"] == key
    assert (r["price"], r["airline"], r["airline_name"]) == (Decimal("850.00"), "FR", "Ryanair")
    assert r["same_dates"] is False and r["outbound_date"] == DEP + timedelta(days=5)


def test_same_dates_flagged_and_preferred_on_price_tie(db):  # noqa: F811
    planted_deal(db)
    save(db, [fare(DEP + timedelta(days=1), 7, "FR", 900), fare(DEP, 7, "W6", 900)])
    [r] = ref(db)
    assert (r["airline"], r["same_dates"]) == ("W6", True)


def test_checked_without_match_returns_null_price(db):  # noqa: F811
    planted_deal(db)
    save(db, [])
    [r] = ref(db)
    assert r["price"] is None and r["checked_at"] is not None


def test_latest_fetch_wins_and_stale_fetch_is_ignored(db):  # noqa: F811
    planted_deal(db)
    save(db, [fare(DEP, 7, "W6", 500)], day=D - timedelta(days=2))
    save(db, [fare(DEP, 7, "W6", 950)], day=D - timedelta(days=1))
    assert ref(db)[0]["price"] == Decimal("950.00")      # newer fetch, even if pricier

    for t in ("market_fetches", "market_fares"):
        db.execute(f"delete from {t} where fetched_date = %s", (D - timedelta(days=1),))
    db.execute("update market_fetches set fetched_date = %s", (D - timedelta(days=4),))
    db.execute("update market_fares set fetched_date = %s", (D - timedelta(days=4),))
    assert ref(db) == []                                  # older than market_max_age_days (3)


def test_reference_does_not_change_deals(db):  # noqa: F811
    planted_deal(db)
    before = db.execute("select * from compute_deals(%s) where flight_key like 'test|%%'",
                        (D,)).fetchall()
    save(db, [fare(DEP, 7, "W6", 300)])
    after = db.execute("select * from compute_deals(%s) where flight_key like 'test|%%'",
                       (D,)).fetchall()
    assert before == after


def test_same_day_refetch_replaces_fares(db):  # noqa: F811
    save(db, [fare(DEP, 7, "W6", 900), fare(DEP, 8, "FR", 800)])
    save(db, [fare(DEP, 7, "W6", 950)])
    rows = db.execute("select airline, price_pln from market_fares where origin_iata = 'XXO'"
                      ).fetchall()
    assert rows == [("W6", Decimal("950.00"))]
    assert db.execute("select n_fares from market_fetches where origin_iata = 'XXO'"
                      ).fetchall() == [(1,)]


def test_segments_deals_first_then_never_fetched_skip_today(db):  # noqa: F811
    planted_deal(db)                                      # segment XXO-XXL 2027-03 has a deal
    flight(db, 50, dest="XXS", stay=4, dep=DEP)           # XXO-XXS 2027-03, no deal
    flight(db, 51, dest="XXS", stay=4, dep=D + timedelta(days=400))  # beyond horizon
    segs = [s for s in store.market_segments(db, "travelpayouts", D, 120, 1000)
            if s.origin_iata == "XXO"]
    assert segs == [SEG, Segment("XXO", "XXS", SEG.dep_month)]

    save(db, [])                                          # deal segment fetched today
    segs = [s for s in store.market_segments(db, "travelpayouts", D, 120, 1000)
            if s.origin_iata == "XXO"]
    assert segs == [Segment("XXO", "XXS", SEG.dep_month)]


def test_export_attaches_market_reference(db):  # noqa: F811
    key = planted_deal(db)
    save(db, [fare(DEP, 7, "W6", 900)])
    payload = export_deals.build_payload(db, T)
    [d] = [x for x in payload["deals"] if x["flight_key"] == key]
    m = d["market"]
    assert m["price"] == 900.0 and m["airline_name"] == "Wizz Air" and m["same_dates"] is True
    assert m["url"] == "https://www.aviasales.com/search/x"
    assert m["origin_airport_name"] == "XXO" and m["checked_at"].endswith("Z")
    assert payload["params"]["market_stay_tolerance_days"] == 2
