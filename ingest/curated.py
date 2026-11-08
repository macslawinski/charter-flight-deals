"""Load hand-curated Product B data (data/curated/*.toml) into Postgres.

    python -m ingest.curated --dry-run        # validate only
    python -m ingest.curated [--database-url URL]

The files are the source of truth: a run replaces places, hotels (with their features and access
times) and child rules with what the files say, and upserts venues (source 'curated') into
venues / venue_facts; a venue whose file is gone becomes 'retired'. Validation is strict and fails loudly, because a
wrong fee or a "verified" fact without a source is worse for a parent than a missing one.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import tomllib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from ingest import store
from ingest.config import REPO_ROOT, load_settings

CURATED = REPO_ROOT / "data" / "curated"
log = logging.getLogger("ingest.curated")

AGE_BANDS = {"0-1", "0-2", "1-2", "2-3", "0-3", "2+", "3+"}
SOURCES = {"hotel_written", "carrier_official", "hotel_website", "own_visit", "operator_page",
           "review_hint"}
# Closed vocabularies: a typo must fail the load, not create a new feature nobody renders.
FEATURE_KEYS = {
    "cot", "child_free_stay", "baby_bath", "bottle_warmer", "high_chair", "kids_menu",
    "toddler_food", "changing_table", "potty", "playroom", "playground", "kids_animation",
    "paddling_pool", "kids_pool", "shade", "lift", "step_free_access", "stroller_rental",
    "baby_monitor", "beach_walk_minutes", "parking", "transfer",
}
RULE_KEYS = {
    "infant_fee", "infant_min_age", "lap_infant", "infants_per_adult", "twins", "infant_seat",
    "stroller", "car_seat", "travel_cot", "bassinet", "baby_food", "priority_boarding",
    "infant_baggage", "child_baggage", "child_fare", "child_seating",
}
ACCESS_CITIES = {"Warszawa", "Poznań", "Gdańsk", "Wrocław", "Kraków", "Katowice"}
# Indoor playgrounds ("bawialnie"): loaded into venues / venue_facts (013) under source 'curated'.
VENUE_CITIES = {"poznan": "Poznań"}
VENUE_SOURCE_ID = "curated"
DEFAULT_VENUE_CATEGORY = "sala_zabaw"  # files without `category` are indoor playgrounds
# age_band -> (age_min_months, age_max_months) for venue_facts; None = open end.
BAND_MONTHS: dict[str, tuple[int | None, int | None]] = {
    "0-1": (0, 12), "0-2": (0, 24), "1-2": (12, 24), "2-3": (24, 36), "0-3": (0, 36),
    "2+": (24, None), "3+": (36, None),
}
CARD_SHORT_MAX = 80  # venue_facts.short_pl check
# Fact keys per curated category (DB: fact_keys, scope 'shared' or the category; 013, 014).
_VENUE_SHARED = {"age_range", "opening_hours", "parking", "changing_table", "supervision"}
VENUE_KEYS_BY_CATEGORY: dict[str, set[str]] = {
    "sala_zabaw": _VENUE_SHARED | {"toddler_zone", "infant_free", "price_child", "price_adult", "cafe",
                                   "socks_required", "toddler_classes"},
    "basen": _VENUE_SHARED | {"price", "pools", "paddling_pool", "swim_nappies", "baby_classes"},
    "lodowisko": _VENUE_SHARED | {"price", "season", "skate_rental", "skating_aid", "helmet"},
}
VENUE_KEYS = set().union(*VENUE_KEYS_BY_CATEGORY.values())
VENUE_SOURCES = {"venue_website", "osm", "own_visit"}
SHORT_MAX = 60  # one line on a phone card
# Legal and official topics ("Niezbędnik", travel documents): official sources only.
ESSENTIAL_TOPICS = {"travel_documents"}
ESSENTIAL_SHORT_MAX = 160
_OFFICIAL_URL = re.compile(r"^https://([a-z0-9-]+\.)*gov\.pl(/|$)")
_SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class CuratedError(ValueError):
    """A curated file is invalid; the message names the file and the offending field."""


@dataclass(frozen=True)
class Place:
    slug: str
    name: str
    country: str
    kind: str
    region: str | None = None
    dest_iata: str | None = None


@dataclass(frozen=True)
class Fact:
    key: str
    age_band: str | None
    value: dict[str, Any]
    note: str | None
    source: str
    url: str | None
    verified_at: date
    to_confirm: bool
    short: str | None = None  # card headline; site-only (not stored in the DB)


@dataclass(frozen=True)
class Access:
    from_kind: str
    from_code: str
    mode: str
    minutes: int
    note: str | None
    url: str | None
    verified_at: date


@dataclass(frozen=True)
class Hotel:
    slug: str
    place: str
    name: str
    status: str
    official_url: str | None = None
    address: str | None = None
    lat: float | None = None
    lon: float | None = None
    features: tuple[Fact, ...] = field(default_factory=tuple)
    access: tuple[Access, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CarrierRules:
    carrier_iata: str
    rules: tuple[Fact, ...]


@dataclass(frozen=True)
class Venue:
    slug: str
    city: str  # VENUE_CITIES key, e.g. 'poznan'
    name: str
    status: str
    official_url: str | None = None
    address: str | None = None
    lat: float | None = None
    lon: float | None = None
    osm: str | None = None  # 'node/123' or 'way/456': lets a monthly check spot closed venues
    features: tuple[Fact, ...] = field(default_factory=tuple)
    category: str = DEFAULT_VENUE_CATEGORY  # VENUE_KEYS_BY_CATEGORY key


@dataclass(frozen=True)
class Link:
    label: str
    url: str


@dataclass(frozen=True)
class EssentialFact:
    group: str
    key: str
    short: str       # the fact in one or two sentences, our own words
    publisher: str   # who says it, shown in the source line ("gov.pl", "NFZ", ...)
    url: str         # official page (*.gov.pl only)
    verified_at: date
    note: str | None = None
    to_confirm: bool = False
    also: tuple[Link, ...] = ()  # further official pages, e.g. a source that says otherwise


@dataclass(frozen=True)
class EssentialGroup:
    id: str
    title: str
    icon: str
    intro: str | None = None


@dataclass(frozen=True)
class Essential:
    """A topic of rules (documents, benefits, ...), not places: exported to the site, not to the DB."""
    topic: str
    title: str
    groups: tuple[EssentialGroup, ...]
    facts: tuple[EssentialFact, ...]


@dataclass(frozen=True)
class Curated:
    places: tuple[Place, ...]
    hotels: tuple[Hotel, ...]
    carriers: tuple[CarrierRules, ...]
    venues: tuple[Venue, ...] = ()
    essentials: tuple[Essential, ...] = ()


# --- validation helpers ---------------------------------------------------------------------

def _get(d: dict[str, Any], key: str, typ: type | tuple[type, ...], where: str, *,
         required: bool = True) -> Any:
    if key not in d:
        if required:
            raise CuratedError(f"{where}: missing '{key}'")
        return None
    v = d[key]
    if not isinstance(v, typ) or (typ is int and isinstance(v, bool)):
        raise CuratedError(f"{where}: '{key}' must be {typ}, got {v!r}")
    return v


def _no_extra(d: dict[str, Any], allowed: set[str], where: str) -> None:
    extra = set(d) - allowed
    if extra:
        raise CuratedError(f"{where}: unknown field(s) {sorted(extra)}")


def _url(v: str | None, where: str) -> str | None:
    if v is not None and not v.startswith("https://"):
        raise CuratedError(f"{where}: url must start with https://, got {v!r}")
    return v


def _slug(v: str, where: str) -> str:
    if not _SLUG.match(v):
        raise CuratedError(f"{where}: bad slug {v!r}")
    return v


def _fact(d: Any, where: str, keys: set[str], sources: set[str] = SOURCES) -> Fact:
    if not isinstance(d, dict):
        raise CuratedError(f"{where}: expected a table")
    _no_extra(d, {"key", "age_band", "value", "note", "short", "source", "url", "verified_at",
                  "to_confirm"}, where)
    key = _get(d, "key", str, where)
    if key not in keys:
        raise CuratedError(f"{where}: unknown key {key!r}")
    band = _get(d, "age_band", str, where, required=False)
    if band is not None and band not in AGE_BANDS:
        raise CuratedError(f"{where}: bad age_band {band!r}")
    source = _get(d, "source", str, where)
    if source not in sources:
        raise CuratedError(f"{where}: bad source {source!r}")
    url = _url(_get(d, "url", str, where, required=source not in {"own_visit", "hotel_written"}),
               where)
    short = _get(d, "short", str, where, required=False)
    if short is not None and len(short) > SHORT_MAX:
        raise CuratedError(f"{where}: 'short' longer than {SHORT_MAX} chars: {short!r}")
    verified = _get(d, "verified_at", date, where)
    if verified > date.today():
        raise CuratedError(f"{where}: verified_at {verified} is in the future")
    to_confirm = bool(_get(d, "to_confirm", bool, where, required=False))
    if source == "review_hint" and not to_confirm:
        raise CuratedError(f"{where}: a review_hint is never a verified fact (set to_confirm = true)")
    return Fact(key, band, _get(d, "value", dict, where), _get(d, "note", str, where, required=False),
                source, url, verified, to_confirm, short)


def card_short(f: Fact) -> str:
    """One-line headline: the curated `short`, else the note's first sentence (as family/src/lib/data.ts)."""
    if f.short:
        return f.short
    m = re.match(r"^.*?[.!?](\s|$)", f.note or "")
    return (m.group(0) if m else f.note or "").strip()


def _access(d: Any, where: str) -> Access:
    if not isinstance(d, dict):
        raise CuratedError(f"{where}: expected a table")
    _no_extra(d, {"from_kind", "from", "mode", "minutes", "note", "url", "verified_at"}, where)
    kind = _get(d, "from_kind", str, where)
    code = _get(d, "from", str, where)
    if kind == "city" and code not in ACCESS_CITIES:
        raise CuratedError(f"{where}: city {code!r} not in {sorted(ACCESS_CITIES)}")
    if kind == "airport" and not re.fullmatch(r"[A-Z]{3}", code):
        raise CuratedError(f"{where}: airport must be an IATA code, got {code!r}")
    if kind not in {"airport", "city"}:
        raise CuratedError(f"{where}: bad from_kind {kind!r}")
    mode = _get(d, "mode", str, where)
    if mode not in {"transfer", "car", "train", "bus"}:
        raise CuratedError(f"{where}: bad mode {mode!r}")
    minutes = _get(d, "minutes", int, where)
    if minutes <= 0:
        raise CuratedError(f"{where}: minutes must be > 0")
    return Access(kind, code, mode, minutes, _get(d, "note", str, where, required=False),
                  _url(_get(d, "url", str, where, required=False), where),
                  _get(d, "verified_at", date, where))


def _unique(items: list[Any], key: Any, where: str) -> None:
    seen: set[Any] = set()
    for it in items:
        k = key(it)
        if k in seen:
            raise CuratedError(f"{where}: duplicate {k!r}")
        seen.add(k)


# --- loading files ----------------------------------------------------------------------------

def _read(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise CuratedError(f"{path}: {e}") from e


def load(root: Path = CURATED) -> Curated:
    """Read and validate every curated file under `root`."""
    places: list[Place] = []
    pfile = root / "places.toml"
    for i, p in enumerate(_read(pfile).get("place", []) if pfile.exists() else []):
        where = f"{pfile.name} place[{i}]"
        _no_extra(p, {"slug", "name", "country", "region", "kind", "dest_iata"}, where)
        kind = _get(p, "kind", str, where)
        iata = _get(p, "dest_iata", str, where, required=False)
        if kind not in {"flight", "domestic"} or (kind == "flight") != (iata is not None):
            raise CuratedError(f"{where}: 'flight' places need dest_iata, 'domestic' ones must not")
        places.append(Place(_slug(_get(p, "slug", str, where), where), _get(p, "name", str, where),
                            _get(p, "country", str, where), kind,
                            _get(p, "region", str, where, required=False), iata))
    _unique(places, lambda p: p.slug, pfile.name)
    place_slugs = {p.slug for p in places}

    hotels: list[Hotel] = []
    for path in sorted((root / "hotels").glob("*/*.toml")):
        where = str(path.relative_to(root))
        h = _read(path)
        _no_extra(h, {"slug", "place", "name", "status", "official_url", "address", "lat", "lon",
                      "feature", "access"}, where)
        place = _get(h, "place", str, where)
        if place not in place_slugs:
            raise CuratedError(f"{where}: place {place!r} not in places.toml")
        if path.parent.name != place:
            raise CuratedError(f"{where}: file must live in hotels/{place}/")
        status = _get(h, "status", str, where)
        if status not in {"draft", "published", "retired"}:
            raise CuratedError(f"{where}: bad status {status!r}")
        feats = [_fact(f, f"{where} feature[{i}]", FEATURE_KEYS)
                 for i, f in enumerate(h.get("feature", []))]
        _unique(feats, lambda f: (f.key, f.age_band), where)
        access = [_access(a, f"{where} access[{i}]") for i, a in enumerate(h.get("access", []))]
        _unique(access, lambda a: (a.from_kind, a.from_code, a.mode), where)
        hotels.append(Hotel(
            slug=_slug(_get(h, "slug", str, where), where), place=place,
            name=_get(h, "name", str, where), status=status,
            official_url=_url(_get(h, "official_url", str, where, required=False), where),
            address=_get(h, "address", str, where, required=False),
            lat=_get(h, "lat", float, where, required=False),
            lon=_get(h, "lon", float, where, required=False),
            features=tuple(feats), access=tuple(access),
        ))
    _unique(hotels, lambda h: h.slug, "hotels")

    carriers: list[CarrierRules] = []
    for path in sorted((root / "child_rules").glob("*.toml")):
        where = str(path.relative_to(root))
        c = _read(path)
        _no_extra(c, {"carrier", "rule"}, where)
        iata = _get(c, "carrier", str, where)
        if path.stem != iata.lower():
            raise CuratedError(f"{where}: file name must be the carrier code ({iata.lower()}.toml)")
        rules = [_fact(r, f"{where} rule[{i}]", RULE_KEYS) for i, r in enumerate(c.get("rule", []))]
        _unique(rules, lambda r: (r.key, r.age_band), where)
        for r in rules:
            if r.note is None:
                raise CuratedError(f"{where} {r.key}: 'note' (the summary shown on the site) is required")
        carriers.append(CarrierRules(iata, tuple(rules)))

    venues: list[Venue] = []
    for path in sorted((root / "venues").glob("*/*.toml")):
        where = str(path.relative_to(root))
        v = _read(path)
        _no_extra(v, {"slug", "city", "name", "status", "official_url", "address", "lat", "lon",
                      "osm", "feature", "category"}, where)
        category = _get(v, "category", str, where, required=False) or DEFAULT_VENUE_CATEGORY
        if category not in VENUE_KEYS_BY_CATEGORY:
            raise CuratedError(f"{where}: category {category!r} not in {sorted(VENUE_KEYS_BY_CATEGORY)}")
        city = _get(v, "city", str, where)
        if city not in VENUE_CITIES:
            raise CuratedError(f"{where}: city {city!r} not in {sorted(VENUE_CITIES)}")
        if path.parent.name != city:
            raise CuratedError(f"{where}: file must live in venues/{city}/")
        status = _get(v, "status", str, where)
        if status not in {"draft", "published", "retired"}:
            raise CuratedError(f"{where}: bad status {status!r}")
        osm = _get(v, "osm", str, where, required=False)
        if osm is not None and not re.fullmatch(r"(node|way|relation)/\d+", osm):
            raise CuratedError(f"{where}: osm must look like 'node/123', got {osm!r}")
        feats = [_fact(f, f"{where} feature[{i}]", VENUE_KEYS_BY_CATEGORY[category], VENUE_SOURCES)
                 for i, f in enumerate(v.get("feature", []))]
        _unique(feats, lambda f: (f.key, f.age_band), where)
        if not feats:
            raise CuratedError(f"{where}: a venue needs at least one feature")
        for f in feats:  # venue_facts constraints, checked here so a bad file fails before any write
            if f.url is None:
                raise CuratedError(f"{where} {f.key}: venue facts need a url")
            if not 1 <= len(card_short(f)) <= CARD_SHORT_MAX:
                raise CuratedError(f"{where} {f.key}: needs 'short' or a 'note' with a first sentence "
                                   f"of 1-{CARD_SHORT_MAX} chars")
        if osm is None and _get(v, "official_url", str, where, required=False) is None:
            raise CuratedError(f"{where}: a venue needs 'osm' or 'official_url' (location source)")
        venues.append(Venue(
            slug=_slug(_get(v, "slug", str, where), where), city=city,
            name=_get(v, "name", str, where), status=status,
            official_url=_url(_get(v, "official_url", str, where, required=False), where),
            address=_get(v, "address", str, where, required=False),
            lat=_get(v, "lat", float, where, required=False),
            lon=_get(v, "lon", float, where, required=False),
            osm=osm, features=tuple(feats), category=category,
        ))
    _unique(venues, lambda v: v.slug, "venues")

    essentials = [_essential(path, root) for path in sorted((root / "essentials").glob("*.toml"))]
    return Curated(tuple(places), tuple(hotels), tuple(carriers), tuple(venues), tuple(essentials))


def _official(v: str, where: str) -> str:
    if not _OFFICIAL_URL.match(v):
        raise CuratedError(f"{where}: official topics need a *.gov.pl https url, got {v!r}")
    return v


def _essential(path: Path, root: Path) -> Essential:
    where = str(path.relative_to(root))
    e = _read(path)
    _no_extra(e, {"title", "group", "fact"}, where)
    if path.stem not in ESSENTIAL_TOPICS:
        raise CuratedError(f"{where}: unknown topic {path.stem!r}, expected one of {sorted(ESSENTIAL_TOPICS)}")
    groups: list[EssentialGroup] = []
    for i, g in enumerate(e.get("group", [])):
        w = f"{where} group[{i}]"
        _no_extra(g, {"id", "title", "icon", "intro"}, w)
        groups.append(EssentialGroup(_slug(_get(g, "id", str, w), w), _get(g, "title", str, w),
                                     _get(g, "icon", str, w), _get(g, "intro", str, w, required=False)))
    _unique(groups, lambda g: g.id, where)
    ids = {g.id for g in groups}

    facts: list[EssentialFact] = []
    for i, f in enumerate(e.get("fact", [])):
        w = f"{where} fact[{i}]"
        _no_extra(f, {"group", "key", "short", "note", "publisher", "url", "verified_at",
                      "to_confirm", "also"}, w)
        group = _get(f, "group", str, w)
        if group not in ids:
            raise CuratedError(f"{w}: group {group!r} not defined in this file")
        short = _get(f, "short", str, w)
        if not 1 <= len(short) <= ESSENTIAL_SHORT_MAX:
            raise CuratedError(f"{w}: 'short' must be 1-{ESSENTIAL_SHORT_MAX} chars")
        verified = _get(f, "verified_at", date, w)
        if verified > date.today():
            raise CuratedError(f"{w}: verified_at {verified} is in the future")
        also: list[Link] = []
        for j, a in enumerate(_get(f, "also", list, w, required=False) or []):
            wa = f"{w} also[{j}]"
            if not isinstance(a, dict):
                raise CuratedError(f"{wa}: expected a table")
            _no_extra(a, {"label", "url"}, wa)
            also.append(Link(_get(a, "label", str, wa), _official(_get(a, "url", str, wa), wa)))
        facts.append(EssentialFact(
            group=group, key=_slug(_get(f, "key", str, w), w), short=short,
            publisher=_get(f, "publisher", str, w), url=_official(_get(f, "url", str, w), w),
            verified_at=verified, note=_get(f, "note", str, w, required=False),
            to_confirm=bool(_get(f, "to_confirm", bool, w, required=False)), also=tuple(also),
        ))
    _unique(facts, lambda f: f.key, where)
    for g in groups:
        if not any(f.group == g.id for f in facts):
            raise CuratedError(f"{where}: group {g.id!r} has no facts")
    return Essential(path.stem, _get(e, "title", str, where), tuple(groups), tuple(facts))


# --- writing ---------------------------------------------------------------------------------

def save(conn: psycopg.Connection[Any], data: Curated) -> dict[str, int]:
    """Replace curated rows with `data` inside the caller's transaction. Returns row counts."""
    conn.execute("delete from hotels")          # cascades to features and access
    conn.execute("delete from places")
    conn.execute("delete from child_rules")
    for p in data.places:
        conn.execute("insert into places (slug, name, country, region, kind, dest_iata) "
                     "values (%s, %s, %s, %s, %s, %s)",
                     (p.slug, p.name, p.country, p.region, p.kind, p.dest_iata))
    n_feat = n_acc = 0
    for h in data.hotels:
        row = conn.execute(
            """insert into hotels (slug, place_slug, name, official_url, address, lat, lon, status)
               values (%s, %s, %s, %s, %s, %s, %s, %s) returning id""",
            (h.slug, h.place, h.name, h.official_url, h.address, h.lat, h.lon, h.status),
        ).fetchone()
        assert row is not None
        for f in h.features:
            conn.execute(
                """insert into hotel_child_features (hotel_id, feature_key, age_band, value, note_pl,
                       source_type, source_url, verified_at, to_confirm)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (row[0], f.key, f.age_band, Jsonb(f.value), f.note, f.source, f.url, f.verified_at,
                 f.to_confirm),
            )
        for a in h.access:
            conn.execute(
                """insert into hotel_access (hotel_id, from_kind, from_code, mode, minutes, note_pl,
                       source_url, verified_at) values (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (row[0], a.from_kind, a.from_code, a.mode, a.minutes, a.note, a.url, a.verified_at),
            )
        n_feat += len(h.features)
        n_acc += len(h.access)
    n_rules = 0
    for c in data.carriers:
        for r in c.rules:
            conn.execute(
                """insert into child_rules (carrier_iata, rule_key, age_band, value, summary_pl,
                       source_type, source_url, verified_at, to_confirm)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (c.carrier_iata, r.key, r.age_band, Jsonb(r.value), r.note, r.source, r.url,
                 r.verified_at, r.to_confirm),
            )
            n_rules += 1
    return {"places": len(data.places), "hotels": len(data.hotels), "features": n_feat,
            "access": n_acc, "child_rules": n_rules, **save_venues(conn, data.venues)}


def save_venues(conn: psycopg.Connection[Any], venues: tuple[Venue, ...],
                today: date | None = None) -> dict[str, int]:
    """Upsert curated venues on (source 'curated', slug) and replace their facts and category.

    Venues are keyed rows shared with open data (ids may be referenced later), so they are upserted,
    not deleted: a file that disappears turns its venue 'retired'. Status always comes from the file.
    """
    today = today or date.today()
    n_facts = 0
    for v in venues:
        loc_url = f"https://www.openstreetmap.org/{v.osm}" if v.osm else v.official_url
        row = conn.execute(
            """insert into venues (source_id, external_id, slug, name, locality, address, lat, lon,
                   official_url, location_source_url, location_verified_at, first_seen_at, last_seen_at,
                   status)
               values (%(src)s, %(slug)s, %(slug)s, %(name)s, %(loc)s, %(addr)s, %(lat)s, %(lon)s,
                       %(url)s, %(loc_url)s, %(loc_at)s, %(today)s, %(today)s, %(status)s)
               on conflict (source_id, external_id) do update set
                   slug = excluded.slug, name = excluded.name, locality = excluded.locality,
                   address = excluded.address, lat = excluded.lat, lon = excluded.lon,
                   official_url = excluded.official_url,
                   location_source_url = excluded.location_source_url,
                   location_verified_at = excluded.location_verified_at,
                   last_seen_at = excluded.last_seen_at, status = excluded.status
               returning id""",
            {"src": VENUE_SOURCE_ID, "slug": v.slug, "name": v.name, "loc": VENUE_CITIES[v.city],
             "addr": v.address, "lat": v.lat, "lon": v.lon, "url": v.official_url, "loc_url": loc_url,
             # the location was read when the venue was first curated: the oldest fact date
             "loc_at": min(f.verified_at for f in v.features), "today": today, "status": v.status},
        ).fetchone()
        assert row is not None
        vid = row[0]
        conn.execute("delete from venue_category_links where venue_id = %s", (vid,))
        conn.execute("insert into venue_category_links (venue_id, category) values (%s, %s)",
                     (vid, v.category))
        conn.execute("delete from venue_facts where venue_id = %s", (vid,))
        for f in v.features:
            age_min, age_max = BAND_MONTHS[f.age_band] if f.age_band else (None, None)
            conn.execute(
                """insert into venue_facts (venue_id, fact_key, age_min_months, age_max_months, value,
                       short_pl, note_pl, source_type, source_url, verified_at, to_confirm)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (vid, f.key, age_min, age_max, Jsonb(f.value), card_short(f), f.note, f.source, f.url,
                 f.verified_at, f.to_confirm),
            )
        n_facts += len(v.features)
    retired = conn.execute(
        """update venues set status = 'retired'
           where source_id = %s and status <> 'retired' and not (external_id = any(%s))""",
        (VENUE_SOURCE_ID, [v.slug for v in venues]),
    ).rowcount
    return {"venues": len(venues), "venue_facts": n_facts, "venues_retired": retired}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Load data/curated into Postgres.")
    ap.add_argument("--dry-run", action="store_true", help="validate only, write nothing")
    ap.add_argument("--database-url", help="override DATABASE_URL (e.g. local Postgres)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    try:
        data = load()
    except CuratedError as e:
        log.error("invalid curated data: %s", e)
        return 1
    log.info("valid: %d places, %d hotels, %d carriers with rules, %d venues, %d essential topics",
             len(data.places), len(data.hotels), len(data.carriers), len(data.venues),
             len(data.essentials))
    if args.dry_run:
        return 0
    url = args.database_url or load_settings().database_url
    if not url:
        log.error("DATABASE_URL is not set (use .env, the env var, or --database-url)")
        return 2
    try:
        with store.connect(url) as conn:
            counts = save(conn, data)
            conn.commit()
    except (psycopg.Error, CuratedError) as e:
        log.error("load failed, nothing written: %s", e)
        return 1
    log.info("written: %s", counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
