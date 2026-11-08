"""Export published venues of one city (open data + curated) from the DB to family/src/data/map/<city>.json.

    python scripts/export_venues.py --city poznan [--database-url URL] [--out PATH]

The family site never reads the DB: its Vercel build reads this committed file. Every fact carries a
reference (source, exact URL, verified date) so the page can show where it comes from; references are
deduplicated into `refs` to keep the file small. Names, licences, attributions and the date of the
latest successful import of open-data sources come from `data_sources` / `import_runs` (`sources`);
curated venues (source 'curated') carry their references per fact. Only status 'published'.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

import psycopg

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ingest import store
from ingest.config import load_settings
from ingest.staleness import add_months

log = logging.getLogger("export_venues")

OUT_DIR = REPO_ROOT / "family" / "src" / "data" / "map"
# Site slug -> `venues.locality`. Add a city here when its data is ready.
CITIES = {"poznan": "Poznań"}
# Display order of facts on a place card; keys not listed go last, alphabetically.
FACT_ORDER = ["age_range", "toddler_zone", "infant_free", "toddler_classes", "family_programme", "opening_hours",
              "access", "price", "price_child", "price_adult", "equipment", "socks_required", "stroller_access",
              "birthday_parties", "cafe", "changing_table", "parking", "supervision", "service_mode", "phone",
              "notes", "managed_by"]


def _order(key: str) -> tuple[int, str]:
    return (FACT_ORDER.index(key) if key in FACT_ORDER else len(FACT_ORDER), key)


def build(conn: psycopg.Connection[Any], city: str) -> dict[str, Any]:
    locality = CITIES[city]
    venues = conn.execute(
        """select v.id, v.source_id, v.external_id, v.name, v.address, v.lat::float8, v.lon::float8,
                  v.official_url, v.location_source_url, v.location_verified_at,
                  array(select l.category from venue_category_links l
                        where l.venue_id = v.id order by l.category),
                  s.kind
           from venues v join data_sources s on s.id = v.source_id
           where v.status = 'published' and v.locality = %s
           order by v.source_id, v.external_id""",
        (locality,),
    ).fetchall()
    facts: dict[int, list[tuple[Any, ...]]] = {}
    for row in conn.execute(
        """select f.venue_id, f.fact_key, f.value, f.short_pl, f.note_pl, f.source_type::text,
                  f.source_url, f.verified_at, f.to_confirm
           from venue_facts f join venues v on v.id = f.venue_id
           where v.status = 'published' and v.locality = %s""",
        (locality,),
    ):
        facts.setdefault(row[0], []).append(row[1:])

    refs: list[dict[str, Any]] = []
    ref_ix: dict[tuple[Any, ...], int] = {}
    ref_months: list[int] = []
    # Staleness per category (DB param); a ref shared by several categories takes the shortest period.
    stale_months: dict[str, int] = dict(
        conn.execute("select slug, stale_after_months from venue_categories").fetchall())

    def ref(src: str | None, kind: str, url: str | None, verified: Any, months: int) -> int:
        key = (src, kind, url, verified.isoformat())
        if key not in ref_ix:
            ref_ix[key] = len(refs)
            refs.append({"src": src, "type": kind, "url": url, "verified_at": key[3], "_verified": verified})
            ref_months.append(months)
        i = ref_ix[key]
        ref_months[i] = min(ref_months[i], months)
        return i

    out_venues = []
    def loc_ref(src: str, kind: str, url: str, verified: Any, months: int) -> int:
        # Open data: the import itself. Curated: the OpenStreetMap object, else the venue's own page.
        if kind == "open_data":
            return ref(src, "open_data", url, verified, months)
        return ref(None, "osm" if url.startswith("https://www.openstreetmap.org/") else "venue_website",
                   url, verified, months)

    for (vid, src, ext, name, address, lat, lon, url, loc_url, loc_verified, cats, kind) in venues:
        vf = sorted(facts.get(vid, []), key=lambda f: (_order(f[0]), f[2] or ""))
        months = min((stale_months[c] for c in cats), default=6)
        out_venues.append({
            "id": f"{src}:{ext}", "source": src, "name": name, "address": address,
            "lat": lat, "lon": lon, "official_url": url, "categories": list(cats),
            "location_ref": (loc_ref(src, kind, loc_url, loc_verified, months)
                             if loc_url and loc_verified else None),
            "facts": [{"key": k, "value": v, "short": s, "note": n, "to_confirm": ask,
                       "ref": ref(src if t == "open_data" else None, t, u, d, months)}
                      for (k, v, s, n, t, u, d, ask) in vf],
        })
    for r, m in zip(refs, ref_months, strict=True):
        # After `due` the site shows "do ponownego sprawdzenia" next to the source line.
        r["due"] = add_months(r.pop("_verified"), m).isoformat()

    used_sources = sorted({v["source"] for v in out_venues})
    sources = {
        r[0]: {"name": r[1], "url": r[2], "licence": r[3], "attribution": r[4],
               "data_as_of": r[5].isoformat() if r[5] else None,
               "imported_at": r[6].isoformat() if r[6] else None}
        for r in conn.execute(
            """select s.id, s.name_pl, s.url, s.licence, s.attribution_pl, r.data_as_of,
                      (r.finished_at at time zone 'Europe/Warsaw')::date
               from data_sources s
               left join lateral (select data_as_of, finished_at from import_runs i
                                  where i.source_id = s.id and i.status = 'ok'
                                  order by i.finished_at desc limit 1) r on true
               where s.id = any(%s) and s.kind = 'open_data' order by s.id""",
            (used_sources,),
        )
    }
    used_cats = sorted({c for v in out_venues for c in v["categories"]})
    used_keys = sorted({f["key"] for v in out_venues for f in v["facts"]})
    return {
        "city": city,
        "locality": locality,
        "categories": dict(conn.execute(
            "select slug, label_pl from venue_categories where slug = any(%s) order by slug",
            (used_cats,)).fetchall()),
        "fact_labels": dict(conn.execute(
            "select key, label_pl from fact_keys where key = any(%s) order by key", (used_keys,)).fetchall()),
        "sources": sources,
        "refs": refs,
        "venues": out_venues,
    }


def render(doc: dict[str, Any]) -> str:
    """Stable JSON with one venue per line: small, and diffs stay readable."""
    head = {k: v for k, v in doc.items() if k != "venues"}
    lines = [json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for v in doc["venues"]]
    body = json.dumps(head, ensure_ascii=False, sort_keys=True, indent=1)[:-2]
    return body + ',\n "venues": [\n' + ",\n".join(lines) + "\n ]\n}\n"


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--city", choices=sorted(CITIES), required=True)
    ap.add_argument("--database-url", help="override DATABASE_URL (e.g. local Postgres)")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    url = args.database_url or load_settings().database_url
    if not url:
        log.error("DATABASE_URL is not set (use .env, the env var, or --database-url)")
        return 2
    with store.connect(url) as conn:
        doc = build(conn, args.city)
    if not doc["venues"]:
        log.error("no published venues for %s", args.city)
        return 1
    out: Path = args.out or OUT_DIR / f"{args.city}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(doc), encoding="utf-8", newline="\n")
    log.info("wrote %s: %d venues, %d refs", out, len(doc["venues"]), len(doc["refs"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
