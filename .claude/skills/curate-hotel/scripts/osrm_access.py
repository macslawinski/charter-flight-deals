"""Car access times from the six origin cities to a hotel, as TOML [[access]] blocks.

Usage (from the repo root):
    .venv/Scripts/python.exe .claude/skills/curate-hotel/scripts/osrm_access.py 54.1653895 15.5045583

Router: FOSSGIS OSRM (OpenStreetMap data, the "OSRM car" engine on openstreetmap.org), city centre ->
hotel, free-flow time rounded to 5 min, distance rounded to 10 km. The url in each block opens the same
route on openstreetmap.org, so a reader can check it. Same method as Saltic (2026-11-05).
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import date

import httpx

# City centres used for every hotel (keep in sync with ACCESS_CITIES in ingest/curated.py).
CITIES = {
    "Gdańsk": (54.3520, 18.6466),
    "Poznań": (52.4064, 16.9252),
    "Wrocław": (51.1079, 17.0385),
    "Warszawa": (52.2297, 21.0122),
    "Katowice": (50.2649, 19.0238),
    "Kraków": (50.0614, 19.9366),
}
ROUTER = "https://routing.openstreetmap.de/routed-car/route/v1/driving/{a},{b};{c},{d}?overview=false"
UA = "charter-flight-deals-poc/0.1 (hotel access times)"


def route(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[float, float]:
    url = ROUTER.format(a=lon1, b=lat1, c=lon2, d=lat2)
    last = ""
    for attempt in range(3):
        r = httpx.get(url, headers={"User-Agent": UA}, timeout=30)
        if r.status_code == 200 and r.json().get("code") == "Ok":
            leg = r.json()["routes"][0]
            return leg["duration"] / 60, leg["distance"] / 1000
        last = f"{r.status_code} {r.text[:200]}"
        time.sleep(5 * (attempt + 1))
    raise SystemExit(f"OSRM failed: {last}")


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    ap = argparse.ArgumentParser()
    ap.add_argument("lat", type=float)
    ap.add_argument("lon", type=float)
    ap.add_argument("--station", nargs=2, type=float, metavar=("LAT", "LON"),
                    help="also print station -> hotel distance/time for the header comment")
    a = ap.parse_args()
    if a.station:
        minutes, km = route(a.station[0], a.station[1], a.lat, a.lon)
        print(f"# Station -> hotel: ~{km:.0f} km, ~{round(minutes / 5) * 5 or 5} min by car (OSRM free flow).")
    rows = []
    for city, (clat, clon) in CITIES.items():
        minutes, km = route(clat, clon, a.lat, a.lon)
        rows.append((round(minutes / 5) * 5, round(km / 10) * 10, city, clat, clon))
        time.sleep(1)  # public server: be gentle
    today = date.today().isoformat()
    print("# --- Access: car (OSRM, free flow) " + "-" * 61)
    for minutes, km, city, clat, clon in sorted(rows):
        print(f"""[[access]]
from_kind = "city"
from = "{city}"
mode = "car"
minutes = {minutes}
note = "{km} km"
url = "https://www.openstreetmap.org/directions?engine=fossgis_osrm_car&route={clat:.4f}%2C{clon:.4f}%3B{a.lat:.4f}%2C{a.lon:.4f}"
verified_at = {today}
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
