"""List indoor playgrounds in a city from OpenStreetMap (one Overpass query) and mark the ones we have.

Usage (from the repo root):
    .venv/Scripts/python.exe .claude/skills/find-playgrounds/scripts/osm_playgrounds.py poznan
    ... osm_playgrounds.py wroclaw --names "Hulakula|Fikołki"     # also match these names
    ... osm_playgrounds.py lodz --bbox 51.68,19.33,51.86,19.64     # city without a preset

Output: one line per OSM object: status (KNOWN = osm id already in data/curated/venues/<city>/),
osm id, name, website, address, lat/lon, opening_hours. Discovery only: facts still come from the
venue's own website. Data © OpenStreetMap contributors, ODbL.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[4]
VENUES = REPO / "data" / "curated" / "venues"

# south,west,north,east. A bbox (not an Overpass "area") because area queries by name time out on
# the public server; a bbox can spill into neighbouring towns, so check addresses.
BBOX = {
    "poznan": "52.29,16.73,52.51,17.07",
    "warszawa": "52.09,20.85,52.37,21.28",
    "krakow": "49.97,19.79,50.13,20.22",
    "wroclaw": "51.04,16.80,51.21,17.18",
    "gdansk": "54.27,18.43,54.45,18.95",
    "katowice": "50.13,18.89,50.30,19.13",
}
ENDPOINTS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]
HEADERS = {"User-Agent": "charter-flight-deals-poc/0.1 (indoor playground list)"}


def query(bbox: str, names: str | None) -> str:
    extra = f'\n nwr["name"~"{names}",i]({bbox});' if names else ""
    return f"""[out:json][timeout:50];
(nwr["leisure"="indoor_play"]({bbox});
 nwr["leisure"="playground"]["indoor"="yes"]({bbox});{extra}
);
out center tags;"""


def fetch(q: str) -> list[dict]:
    last: Exception | None = None
    for url in ENDPOINTS:
        for attempt in range(2):
            try:
                r = httpx.post(url, data={"data": q}, headers=HEADERS, timeout=90)
                if r.status_code in (429, 504):
                    raise httpx.HTTPStatusError(str(r.status_code), request=r.request, response=r)
                r.raise_for_status()
                return r.json()["elements"]
            except (httpx.HTTPError, ValueError) as e:
                last = e
                time.sleep(10 * (attempt + 1))
    raise SystemExit(f"Overpass failed on all endpoints: {last}")


def known_osm_ids(city: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in (VENUES / city).glob("*.toml"):
        m = re.search(r'^osm\s*=\s*"([^"]+)"', p.read_text(encoding="utf-8"), re.MULTILINE)
        if m:
            out[m.group(1)] = p.stem
    return out


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    ap = argparse.ArgumentParser()
    ap.add_argument("city", help="city slug as in VENUE_CITIES, e.g. poznan")
    ap.add_argument("--bbox", help="south,west,north,east (required for cities without a preset)")
    ap.add_argument("--names", help="regex of venue names to match too (e.g. from the roadmap)")
    a = ap.parse_args()
    bbox = a.bbox or BBOX.get(a.city)
    if not bbox:
        ap.error(f"no preset bbox for {a.city!r}; pass --bbox")
    known = known_osm_ids(a.city)
    elements = fetch(query(bbox, a.names))
    rows: list[tuple[bool, str, str]] = []
    seen: set[str] = set()
    for e in elements:
        t = e.get("tags", {})
        osm = f"{e['type']}/{e['id']}"
        lat = e.get("lat") or e.get("center", {}).get("lat")
        lon = e.get("lon") or e.get("center", {}).get("lon")
        addr = " ".join(x for x in (t.get("addr:street"), t.get("addr:housenumber"),
                                    t.get("addr:postcode"), t.get("addr:city")) if x)
        status = f"KNOWN({known[osm]})" if osm in known else "new"
        if osm in known:
            seen.add(osm)
        web = t.get("website") or t.get("contact:website")
        line = (f"{status} | {osm} | {t.get('name')} | web={web} | {addr or '-'} | "
                f"{lat},{lon} | hours={t.get('opening_hours')}")
        rows.append((osm in known, t.get("name") or "", line))
    for _, _, line in sorted(rows):
        print(line)
    gone = sorted(known[o] for o in set(known) - seen)
    print(f"-- {len(rows)} objects, {len(seen)} already curated; curated but no longer in OSM: {gone or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
