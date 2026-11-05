"""Export current deals from Postgres to web/public/deals.json (consumed by the static site).

    python scripts/export_deals.py [--out web/public/deals.json] [--database-url URL]

The page never talks to the database; this file is the whole public interface. It also carries a
small `status` block so the page can explain the cold start honestly instead of showing nothing.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ingest import store
from ingest.config import load_settings

DEFAULT_OUT = REPO_ROOT / "web" / "public" / "deals.json"
SCHEMA_VERSION = 1

# Display names of Polish departure airports (r.pl's "Wylot.Przystanek"); unknown codes show as IATA.
ORIGINS = {
    "BZG": "Bydgoszcz", "GDN": "Gdańsk", "KRK": "Kraków", "KTW": "Katowice", "LCJ": "Łódź",
    "LUZ": "Lublin", "POZ": "Poznań", "RZE": "Rzeszów", "SZZ": "Szczecin", "WAW": "Warszawa",
    "WMI": "Warszawa-Modlin", "WRO": "Wrocław", "OSZ": "Koszalin", "SZY": "Olsztyn-Mazury",
}

log = logging.getLogger("export")

_DEALS = """
select d.as_of, d.flight_key, f.operator, f.origin_iata, f.dest_iata,
       dest.name as dest_name, dest.country as dest_country,
       f.outbound_date, f.return_date, f.stay_days, f.flight_no,
       d.current_price, d.baseline_avg, d.baseline_median, d.baseline_used, d.threshold_price,
       d.discount_pct, d.baseline_flights, d.baseline_obs, d.window_start, d.window_end
from deals d
join flights f using (flight_key)
left join destinations dest on dest.iata = f.dest_iata
where d.as_of = %(as_of)s
order by d.discount_pct desc, d.current_price
"""

_STATUS = """
select (select max(snapshot_date) from price_snapshots)            as last_snapshot_date,
       (select min(snapshot_date) from price_snapshots)            as first_snapshot_date,
       (select count(distinct snapshot_date) from price_snapshots) as history_days,
       (select max(fetched_at) from raw_fetches
         where parse_ok and operator in (select distinct operator from flights))
                                                                   as last_successful_fetch,
       (select count(*) from price_snapshots
         where snapshot_date = (select max(snapshot_date) from price_snapshots)) as flights_priced
"""

# Per-operator freshness: one operator's outage must not hide behind the other's fresh data.
_OPERATORS = """
with last_day as (select max(snapshot_date) as d from price_snapshots)
select f.operator,
       max(s.snapshot_date)                                         as last_snapshot_date,
       count(*) filter (where s.snapshot_date = (select d from last_day)) as flights_priced,
       (select max(r.fetched_at) from raw_fetches r
         where r.operator = f.operator and r.parse_ok)               as last_successful_fetch,
       (select max(r.fetched_at) from raw_fetches r
         where r.operator = f.operator and r.parse_ok is false)      as last_failed_parse
from price_snapshots s
join flights f on f.flight_key = s.flight_key
group by f.operator
order by f.operator
"""

# Upcoming segments (operator + origin + destination + departure month) and how many already have
# a baseline.
_SEGMENTS = """
with p as (select * from pipeline_params),
seg as (
    select e.operator, e.origin_iata, e.dest_iata, e.dep_month,
           count(distinct s.flight_key) filter (
               where s.snapshot_date between %(as_of)s - p.window_days and %(as_of)s - 1
           ) as baseline_flights,
           count(distinct s.snapshot_date) filter (
               where s.snapshot_date between %(as_of)s - p.window_days and %(as_of)s - 1
           ) as baseline_days
    from eligible_flights e
    cross join p
    left join price_snapshots s on s.flight_key = e.flight_key
    where e.outbound_date > %(as_of)s
    group by e.operator, e.origin_iata, e.dest_iata, e.dep_month
)
select count(*) as segments,
       count(*) filter (where baseline_flights >= (select min_baseline_flights from p)
                          and baseline_days >= (select min_history_days from p)) as ready
from seg
"""


# Regular-airline reference per deal (display-only; 005_market_fares.sql).
_MARKET = "select * from market_reference(%(as_of)s)"
AVIASALES = "https://www.aviasales.com"


def _market(r: dict[str, Any] | None) -> dict[str, Any] | None:
    """None = segment not checked recently; price None = checked, no direct regular fare."""
    if r is None:
        return None
    m = _row(r)
    m.pop("flight_key", None)
    link = m.pop("link", None)
    m["url"] = f"{AVIASALES}{link}" if isinstance(link, str) and link.startswith("/") else None
    if m.get("origin_airport"):
        m["origin_airport_name"] = ORIGINS.get(m["origin_airport"], m["origin_airport"])
    m["airline_name"] = m.get("airline_name") or m.get("airline")
    return m


def _jsonable(v: Any) -> Any:
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, datetime):
        return v.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(v, date):
        return v.isoformat()
    return v


def _row(r: dict[str, Any]) -> dict[str, Any]:
    return {k: _jsonable(v) for k, v in r.items()}


def build_payload(conn: psycopg.Connection[Any], generated_at: datetime) -> dict[str, Any]:
    with conn.cursor(row_factory=dict_row) as cur:
        status = cur.execute(_STATUS).fetchone() or {}
        operators = [_row(r) for r in cur.execute(_OPERATORS).fetchall()]
        params = cur.execute(
            """select window_days, discount_threshold, min_baseline_flights, min_history_days,
                      baseline_stat,
                      default_min_stay_days, include_one_way, market_stay_tolerance_days,
                      market_max_age_days from pipeline_params"""
        ).fetchone() or {}
        as_of = status.get("last_snapshot_date")
        deals: list[dict[str, Any]] = []
        market: dict[str, dict[str, Any]] = {}
        segments: dict[str, Any] = {"segments": 0, "ready": 0}
        if as_of is not None:
            deals = [_row(r) for r in cur.execute(_DEALS, {"as_of": as_of}).fetchall()]
            segments = cur.execute(_SEGMENTS, {"as_of": as_of}).fetchone() or segments
            market = {r["flight_key"]: r for r in cur.execute(_MARKET, {"as_of": as_of}).fetchall()}
        zones = cur.execute(
            "select zone, min_sensible_stay_days from zones order by min_sensible_stay_days"
        ).fetchall()

    for d in deals:
        d["origin_name"] = ORIGINS.get(d["origin_iata"], d["origin_iata"])
        d["dest_name"] = d["dest_name"] or d["dest_iata"]
        d["market"] = _market(market.get(d["flight_key"]))
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _jsonable(generated_at),
        "as_of": _jsonable(as_of),
        "status": {
            **_row(status),
            "segments_upcoming": segments["segments"],
            "segments_with_baseline": segments["ready"],
            "operators": operators,
        },
        "params": _row(params),
        "zones": [_row(z) for z in zones],
        "deals": deals,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Export current deals to deals.json.")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--database-url", help="override DATABASE_URL")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    url = args.database_url or load_settings().database_url
    if not url:
        log.error("DATABASE_URL is not set")
        return 2
    with store.connect(url) as conn:
        payload = build_payload(conn, datetime.now(UTC))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    s = payload["status"]
    log.info("wrote %s: %d deals as of %s (%s history days, %s/%s segments with baseline)",
             args.out, len(payload["deals"]), payload["as_of"], s.get("history_days"),
             s["segments_with_baseline"], s["segments_upcoming"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
