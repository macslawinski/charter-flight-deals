"""export_deals.build_payload on a planted synthetic deal (local Postgres, rolled back)."""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import export_deals
from test_transform import D, db, flight, history, price  # noqa: F401  (db is a fixture)

from ingest import store


def test_payload_contains_deal_with_proof_fields(db):  # noqa: F811
    keys = [flight(db, i) for i in range(6)]
    for k in keys:
        history(db, k, 1600)
        price(db, k, D, 1600)
    db.execute("update price_snapshots set price_last = 1249 where flight_key = %s and "
               "snapshot_date = %s", (keys[0], D))
    db.execute("select refresh_deals(%s)", (D,))

    payload = export_deals.build_payload(db, datetime(2027, 1, 15, 12, tzinfo=UTC))
    json.dumps(payload)  # must be serializable as-is

    assert payload["as_of"] == D.isoformat()
    deals = [d for d in payload["deals"] if d["flight_key"].startswith("test|")]
    assert len(deals) == 1
    d = deals[0]
    assert d["current_price"] == 1249.0
    assert d["baseline_avg"] == 1600.0 and d["threshold_price"] == 1360.0
    assert d["discount_pct"] == 21.94
    assert (d["baseline_flights"], d["baseline_obs"]) == (6, 60)
    assert d["dest_name"] == "Test long" and d["origin_name"] == "XXO"
    assert d["stay_days"] == 7 and d["outbound_date"] == "2027-03-10"
    assert payload["status"]["segments_with_baseline"] >= 1
    assert payload["params"]["discount_threshold"] == 0.15


def test_status_is_reported_per_operator(db):  # noqa: F811
    k = flight(db, 0)
    price(db, k, D, 1600)
    t_ok, t_market = datetime(2027, 1, 15, 6, tzinfo=UTC), datetime(2027, 1, 15, 9, tzinfo=UTC)
    store.save_raw_fetch(db, "test", {}, {}, 200, t_ok)
    db.execute("update raw_fetches set parse_ok = true where operator = 'test'")
    # A later successful reference-price fetch must not count as an operator check.
    store.save_raw_fetch(db, "travelpayouts", {}, {}, 200, t_market)
    db.execute("update raw_fetches set parse_ok = true where operator = 'travelpayouts' "
               "and fetched_at = %s", (t_market,))

    payload = export_deals.build_payload(db, datetime(2027, 1, 15, 12, tzinfo=UTC))
    [op] = [o for o in payload["status"]["operators"] if o["operator"] == "test"]
    assert op["last_successful_fetch"] == "2027-01-15T06:00:00Z"
    assert op["last_snapshot_date"] == D.isoformat() and op["last_failed_parse"] is None
    assert "travelpayouts" not in {o["operator"] for o in payload["status"]["operators"]}
