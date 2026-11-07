"""List hotels in a Polish voivodeship from OpenStreetMap and (optionally) probe their own websites
for an offer for children 0-3.

Usage (from the repo root):
    .venv/Scripts/python.exe .claude/skills/find-hotels/scripts/osm_hotels.py zachodniopomorskie --out <scratchpad>/zp.json
    ... osm_hotels.py pomorskie --out <f> --bbox 54.57,18.40,54.85,18.82        # a sub-region by coordinates
    ... osm_hotels.py pomorskie --out <f> --towns "Jastarnia|Jurata"           # or by addr:city / addr:place
    ... osm_hotels.py malopolskie --out <f> --probe --top 60

The whole voivodeship is always fetched once and cached in --out (JSON); --bbox / --towns only filter
what is shown and probed, so a sub-region run never shrinks the cache. --refresh re-queries OSM and
re-probes sites.

Without --probe: one line per OSM object (tourism=hotel, leisure=resort), grouped by town.
With --probe: for every hotel with a website, read robots.txt, the home page and up to four
"for children" pages linked from it (8 sites in parallel, one request at a time per site), score
signals of a 0-3 offer, subtract negated ones ("nie mamy brodzika", "brak łóżeczek"), and flag sites
that are probably not the hotel's own (portal/agency domain, hotel name absent, domain for sale).

Discovery only: a probe hit is a lead, not a fact. Facts still come from reading the hotel's pages.
Data (c) OpenStreetMap contributors, ODbL.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import tomllib
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

REPO = Path(__file__).resolve().parents[4]
CURATED = REPO / "data" / "curated"

VOIVODESHIPS = {
    "dolnoslaskie": "dolnośląskie",
    "kujawsko-pomorskie": "kujawsko-pomorskie",
    "lubelskie": "lubelskie",
    "lubuskie": "lubuskie",
    "lodzkie": "łódzkie",
    "malopolskie": "małopolskie",
    "mazowieckie": "mazowieckie",
    "opolskie": "opolskie",
    "podkarpackie": "podkarpackie",
    "podlaskie": "podlaskie",
    "pomorskie": "pomorskie",
    "slaskie": "śląskie",
    "swietokrzyskie": "świętokrzyskie",
    "warminsko-mazurskie": "warmińsko-mazurskie",
    "wielkopolskie": "wielkopolskie",
    "zachodniopomorskie": "zachodniopomorskie",
}
# Area by name works; area by ISO3166-2 code returned 0 objects (checked 2026-11-05).
ENDPOINTS = ["https://overpass-api.de/api/interpreter", "https://overpass.private.coffee/api/interpreter",
             "https://overpass.kumi.systems/api/interpreter"]
UA = "charter-flight-deals-poc/0.1 (family hotel list; robots.txt respected)"

# Signals on the hotel's own pages. "baby" = things only a 0-3 offer has (weight 2); "kids" = a
# general children's offer (weight 1). Stems, matched case-insensitively on page text.
BABY = {
    "łóżeczko": r"łóżecz",
    "wanienka": r"wanienk",
    "podgrzewacz": r"podgrzewacz",
    "przewijak": r"przewijak",
    "nocnik": r"nocnik",
    "krzesełko": r"krzesełk",
    "brodzik": r"brodzik",
    "niemowlę": r"niemowl",
    "maluch": r"malusz|maluch|maluszk|bobas",
    "do 3 lat": r"(?:do|poniżej|0\s*[-–]\s*)\s*3\s*(?:lat|r\.\s*ż)",
    "elektroniczna niania": r"elektroniczn\w* nian",
}
KIDS = {
    "sala zabaw": r"sal\w* zabaw|kącik\w* (?:zabaw|dla dzieci)|pokój zabaw|bawialni",
    "kids club": r"kids\s*club|mini\s*club|klub\w* (?:dla )?dzie|klub\w* malucha",
    "plac zabaw": r"plac\w* zabaw",
    "animacje": r"animacj\w*|animator",
    "basen dla dzieci": r"basen\w* dla dzieci|zjeżdżal|aquapark|park wodny",
    "menu dziecięce": r"menu dzieci|menu dla dzieci|kids menu",
}
# "nie mamy brodzika", "brak łóżeczek", "nie posiadamy sali zabaw": a negation up to 4 words before.
NEGATION = re.compile(r"\b(?:nie\s+(?:mamy|posiadamy|oferujemy|zapewniamy|ma|posiada|dysponujemy)|brak)\b"
                      r"(?:\W+\w+){0,4}?\W+(łóżecz\w*|wanienk\w*|brodzik\w*|przewijak\w*|sal\w* zabaw|"
                      r"basen\w*|animac\w*|krzesełk\w*)", re.IGNORECASE)
KIDS_LINK = re.compile(r"dzieci|dziecka|dla-dzieci|rodzin|family|kids|maluch|najm(?:ł|l)odsz|"
                       r"udogodnienia|atrakcje|faq|pytania|cennik|regulamin", re.IGNORECASE)
# Legal pages that mention children but say nothing about the offer (since 2024 Polish hotels must
# publish "standardy ochrony małoletnich"), plus privacy/cookie pages.
NOT_KIDS_PAGE = re.compile(r"ochron\w*|standard\w*|polityk\w*|małoletn|maloletn|rodo|cookie|prywatno",
                           re.IGNORECASE)
BLOCK_MARKERS = ("cf-chl", "Just a moment...", "challenge-platform", "Access denied")
PARKED = re.compile(r"domena (?:jest )?na sprzeda|domain (?:is )?for sale|this domain may be for sale|"
                    r"kup tę domenę|parked free", re.IGNORECASE)
# Portals / agencies / booking sites that OSM sometimes lists as a hotel's website. Not a source.
PORTALS = re.compile(r"(^|\.)(booking\.com|tripadvisor\.|nocowanie\.pl|noclegi\.pl|e-turysta\.pl|"
                     r"meteor-turystyka\.pl|travelist\.pl|wakacje\.pl|urlop\.pl|triverna\.pl|"
                     r"facebook\.com|instagram\.com|google\.|itaka\.pl|r\.pl|hotels\.com|expedia\.|"
                     r"trivago\.|agoda\.|slowhop\.com|turystyka\.|nocleg\w*\.)", re.IGNORECASE)
NAME_STOP = {"hotel", "resort", "spa", "wellness", "apartamenty", "apartments", "villa", "willa",
             "pensjonat", "dom", "wczasowy", "osrodek", "ośrodek", "and", "the", "conference", "sport",
             "park", "restauracja", "family", "club", "medical", "mazury", "baltic", "&"}


# --- Overpass ---------------------------------------------------------------------------------

def overpass(voiv_name: str) -> list[dict]:
    q = f"""[out:json][timeout:120];
area["name"="województwo {voiv_name}"]["admin_level"="4"]->.a;
(nwr["tourism"="hotel"](area.a);
 nwr["leisure"="resort"](area.a););
out center tags;"""
    last = ""
    for url in ENDPOINTS:
        for attempt in range(3):
            try:
                r = httpx.post(url, data={"data": q}, headers={"User-Agent": UA}, timeout=180)
                if r.status_code == 200:
                    data = r.json()
                    # An overloaded server can answer 200 with no elements and a runtime-error remark.
                    # A whole voivodeship always has hotels, so an empty answer is a failure.
                    if data.get("elements"):
                        return data["elements"]
                    last = f"{url}: 200 but empty ({data.get('remark', 'no remark')[:120]})"
                else:
                    last = f"{url}: HTTP {r.status_code}"
            except (httpx.HTTPError, ValueError) as e:
                last = f"{url}: {e}"
            print(f"-- Overpass retry ({last})", file=sys.stderr, flush=True)
            time.sleep(15 * (attempt + 1))  # "at capacity": back off, then the next endpoint
    raise SystemExit(f"Overpass failed on all endpoints; last error: {last}")


def host(url: str | None) -> str | None:
    if not url:
        return None
    if not re.match(r"https?://", url):
        url = "https://" + url
    h = urlparse(url).hostname or ""
    return h.removeprefix("www.").lower() or None


def fold(s: str) -> str:
    """Lowercase ASCII fold (ł→l, ó→o...) for name matching."""
    s = s.lower().replace("ł", "l")
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def known_hosts() -> dict[str, str]:
    """Website host -> 'curated:<slug>' or 'lead:<voivodeship>:<status>'."""
    out: dict[str, str] = {}
    for p in (CURATED / "hotel_leads").glob("*.toml"):
        for lead in tomllib.loads(p.read_text(encoding="utf-8")).get("lead", []):
            if h := host(lead.get("official_url")):
                out[h] = f"lead:{p.stem}:{lead.get('status', '?')}"
    for p in (CURATED / "hotels").glob("*/*.toml"):
        m = re.search(r'^official_url\s*=\s*"([^"]+)"', p.read_text(encoding="utf-8"), re.MULTILINE)
        if m and (h := host(m.group(1))):
            out[h] = f"curated:{p.stem}"
    return out


def rows_from(elements: list[dict]) -> list[dict]:
    rows = []
    for e in elements:
        t = e.get("tags", {})
        if not t.get("name"):
            continue
        web = t.get("website") or t.get("contact:website") or t.get("url")
        if web and not re.match(r"https?://", web):
            web = "https://" + web
        rows.append({
            "osm": f"{e['type']}/{e['id']}",
            "name": t["name"],
            "kind": t.get("tourism") or t.get("leisure"),
            "town": t.get("addr:city") or t.get("addr:place") or "?",
            "address": " ".join(x for x in (t.get("addr:street") or t.get("addr:place"),
                                            t.get("addr:housenumber"), t.get("addr:postcode"),
                                            t.get("addr:city")) if x),
            "lat": e.get("lat") or e.get("center", {}).get("lat"),
            "lon": e.get("lon") or e.get("center", {}).get("lon"),
            "website": web,
            "stars": t.get("stars"),
            "rooms": t.get("rooms"),
        })
    return rows


def in_filter(r: dict, towns: re.Pattern | None, bbox: tuple[float, ...] | None) -> bool:
    """Selected if the town/address matches --towns OR the point lies in --bbox (rows often lack a town)."""
    by_town = bool(towns and (towns.fullmatch(r["town"]) or towns.search(r["address"] or "")))
    in_box = False
    if bbox and r["lat"] is not None:
        s, w, n, e = bbox
        in_box = s <= r["lat"] <= n and w <= r["lon"] <= e
    return by_town or in_box


# --- probing a hotel's own site -----------------------------------------------------------------

def page_text(raw: str) -> str:
    raw = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"(?s)<[^>]+>", " ", raw)))


def signals(text: str) -> tuple[list[str], list[str], list[str]]:
    t = text.lower()
    negated = sorted({m.group(0)[:60] for m in NEGATION.finditer(t)})
    return ([k for k, rx in BABY.items() if re.search(rx, t)],
            [k for k, rx in KIDS.items() if re.search(rx, t)], negated)


def kids_links(raw: str, base: str) -> list[str]:
    base_host = host(base)
    found: list[tuple[int, str]] = []
    for m in re.finditer(r'(?is)<a\b[^>]*href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', raw):
        href, label = m.group(1), page_text(m.group(2))
        if href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        url = urljoin(base, href)
        if host(url) != base_host or not (KIDS_LINK.search(href) or KIDS_LINK.search(label)):
            continue
        if NOT_KIDS_PAGE.search(href) or NOT_KIDS_PAGE.search(label):
            continue
        both = href + " " + label
        rank = (0 if re.search(r"dzieci|dziecka|kids|maluch|najm", both, re.IGNORECASE)
                else 1 if re.search(r"rodzin|family", both, re.IGNORECASE) else 2)
        found.append((rank, url.split("#")[0]))
    seen: list[str] = []
    for _, u in sorted(found):
        if u not in seen and u.rstrip("/") != base.rstrip("/") and not u.lower().endswith(".pdf"):
            seen.append(u)
    return seen[:4]


def name_on_site(name: str, text: str) -> bool:
    tokens = [w for w in re.findall(r"\w{3,}", fold(name)) if w not in NAME_STOP]
    return not tokens or any(w in fold(text) for w in tokens)


def probe(row: dict) -> dict:
    url = row["website"]
    res: dict = {"status": "ok", "baby": [], "kids": [], "negated": [], "flags": [], "kids_url": None,
                 "pages": []}
    if PORTALS.search(host(url) or ""):
        return {**res, "status": "portal", "flags": ["portal_domain"]}
    try:
        with httpx.Client(headers={"User-Agent": UA}, timeout=15, follow_redirects=True) as c:
            rp = RobotFileParser()
            try:
                r = c.get(urljoin(url, "/robots.txt"))
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
            except httpx.HTTPError:
                rp.parse([])
            if not rp.can_fetch(UA, url):
                return {**res, "status": "robots_disallow"}
            r = c.get(url)
            if r.status_code in (401, 403, 429, 503) or any(m in r.text[:5000] for m in BLOCK_MARKERS):
                return {**res, "status": f"blocked_{r.status_code}"}
            if r.status_code >= 400:
                return {**res, "status": f"http_{r.status_code}"}
            final = str(r.url)
            res["final_url"] = final
            home = page_text(r.text[:2_000_000])
            texts = [home]
            res["pages"].append(final)
            if PARKED.search(home[:3000]):
                return {**res, "status": "parked_domain"}
            if host(final) != host(url):
                res["flags"].append(f"redirect_to:{host(final)}")
                if PORTALS.search(host(final) or ""):
                    return {**res, "status": "portal", "flags": res["flags"] + ["portal_domain"]}
            if len(home) < 300:
                res["status"] = "little_text"  # JS-rendered site: check in a browser
            links = kids_links(r.text, final)
            for link in links:
                if not rp.can_fetch(UA, link):
                    continue
                time.sleep(1.0)
                try:
                    k = c.get(link)
                except httpx.HTTPError:
                    continue
                if k.status_code == 200 and "html" in k.headers.get("content-type", "html"):
                    texts.append(page_text(k.text[:2_000_000]))
                    res["pages"].append(str(k.url))
            alltext = " ".join(texts)
            res["baby"], res["kids"], res["negated"] = signals(alltext)
            if not name_on_site(row["name"], alltext[:200_000]):
                res["flags"].append("name_not_on_site")  # portal, other property or a renamed hotel
            if links:
                res["kids_url"] = links[0]
    except httpx.HTTPError as e:
        res["status"] = f"error_{type(e).__name__}"
    return res


def score(p: dict) -> int:
    return 2 * len(p.get("baby", [])) + len(p.get("kids", [])) - 2 * len(p.get("negated", []))


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    ap = argparse.ArgumentParser()
    ap.add_argument("voivodeship", choices=sorted(VOIVODESHIPS))
    ap.add_argument("--out", type=Path, required=True,
                    help="JSON cache of OSM rows + probes (put it in the session scratchpad)")
    ap.add_argument("--towns", help="regex of towns (addr:city / addr:place), e.g. 'Jastarnia|Jurata'")
    ap.add_argument("--bbox", help="south,west,north,east: only objects inside (catches rows with no town)")
    ap.add_argument("--probe", action="store_true", help="probe hotel websites for a 0-3 offer")
    ap.add_argument("--refresh", action="store_true", help="re-query OSM and re-probe cached sites")
    ap.add_argument("--max-probe", type=int, default=400, help="cap of sites probed in one run")
    ap.add_argument("--top", type=int, default=50, help="with --probe: print this many best-scored")
    a = ap.parse_args()
    towns = re.compile(a.towns, re.IGNORECASE) if a.towns else None
    bbox = tuple(float(x) for x in a.bbox.split(",")) if a.bbox else None
    if bbox and len(bbox) != 4:
        ap.error("--bbox needs south,west,north,east")

    cache: dict = json.loads(a.out.read_text(encoding="utf-8")) if a.out.exists() else {}
    if cache.get("rows") and not a.refresh:
        rows = cache["rows"]
        print(f"-- cached OSM rows from {a.out} ({len(rows)}); --refresh to query again", flush=True)
    else:
        rows = rows_from(overpass(VOIVODESHIPS[a.voivodeship]))
        cache["rows"] = rows
        a.out.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    known = known_hosts()
    for r in rows:
        r["known"] = known.get(host(r["website"]) or "", "")
    sel = [r for r in rows if in_filter(r, towns, bbox)] if (towns or bbox) else rows

    with_web = [r for r in sel if r["website"]]
    print(f"-- {len(sel)} named hotels/resorts selected ({len(rows)} in {VOIVODESHIPS[a.voivodeship]}), "
          f"{len(with_web)} with a website, {sum(bool(r['known']) for r in sel)} already known; "
          f"{sum(r['town'] == '?' for r in sel)} have no town tag", flush=True)

    if not a.probe:
        for r in sorted(sel, key=lambda r: (r["town"], r["name"])):
            print(f"{r['known'] or 'new'} | {r['town']} | {r['name']} | web={r['website']} | "
                  f"stars={r['stars']} rooms={r['rooms']} | {r['osm']} | {r['lat']},{r['lon']}")
        return 0

    probes: dict = cache.get("probes", {})
    by_host: dict[str, dict] = {}
    for r in with_web:
        h = host(r["website"])
        if h and h not in by_host:  # one probe per site (chains share a domain: check the location)
            by_host[h] = r
    todo = [r for h, r in by_host.items() if a.refresh or h not in probes][: a.max_probe]
    print(f"-- probing {len(todo)} sites ({len(by_host) - len(todo)} cached or over the cap)", flush=True)
    with ThreadPoolExecutor(max_workers=8) as ex:
        for i, (r, p) in enumerate(zip(todo, ex.map(probe, todo)), 1):
            probes[host(r["website"]) or r["website"]] = p
            if i % 25 == 0:
                print(f"   ... {i}/{len(todo)}", flush=True)
    cache["probes"] = probes
    a.out.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")

    scored = [(score(p), r, p) for h, r in by_host.items() if (p := probes.get(h))]
    scored.sort(key=lambda x: (-x[0], x[1]["town"], x[1]["name"]))
    print("score | known | town | name | site | kids page | baby | kids | NEGATED | flags | status")
    for s, r, p in scored[: a.top]:
        print(f"{s} | {r['known'] or 'new'} | {r['town']} | {r['name']} | {p.get('final_url') or r['website']} | "
              f"{p.get('kids_url') or '-'} | {','.join(p['baby']) or '-'} | {','.join(p['kids']) or '-'} | "
              f"{'; '.join(p.get('negated', [])) or '-'} | {','.join(p.get('flags', [])) or '-'} | {p['status']}")
    unread = [(r, p) for _, r, p in scored if p["status"] != "ok"]
    print(f"-- {len(unread)} sites not usable by the probe (blocked / JS-only / robots / portal / parked / errors):")
    for r, p in unread[:50]:
        print(f"   {p['status']} | {r['town']} | {r['name']} | {r['website']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
