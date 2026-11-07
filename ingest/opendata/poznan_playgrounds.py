"""Poznań public playgrounds from the city map service (GeoJSON, layer "Place zabaw i gier").

The layer mixes playgrounds and sports pitches, public and closed ones. We keep only
`rodzaj == "plac gier i zabaw"`, `typ == "ogólnodostępne"` and not closed (`dostep` "nieczynny"/"nieczynne"),
minus points that are only game tables (ping-pong, chess, table football).
Points only: the data has no street addresses.
"""

from __future__ import annotations

import re
from typing import Any

from ingest.models import ParseError
from ingest.opendata import ImportBatch, OpenFact, OpenRecord, in_poland, short

SOURCE_ID = "poznan_place_zabaw"
CATEGORY = "plac_zabaw"
REQUIRED = ("rodzaj", "typ", "dostep", "platnosc", "nazwa", "opiekun")
UNKNOWN = {"", "brak danych"}
# Equipment flags worth a parent's attention ('tak' / 'nie' in the source).
EQUIPMENT = {"tyrolka": ("zipline", "tyrolka"), "park_linowy": ("rope_course", "elementy linowe"),
             "naturalne": ("natural", "plac naturalny"), "pumptrack": ("pumptrack", "pumptrack")}
_HOURS = re.compile(r"^\d{1,2}(:\d{2})?\s*-\s*\d{1,2}(:\d{2})?$")


def _s(p: dict[str, Any], key: str) -> str:
    v = p.get(key)
    return "" if v is None else " ".join(str(v).split())


def _closed(p: dict[str, Any]) -> bool:
    # The source writes both 'nieczynny' and 'nieczynne'.
    return _s(p, "dostep").casefold().startswith("nieczynn")


# Points named only after a game table ("stół do ping ponga", "stół do gry w szachy", "piłkarzyki")
# are in the layer too; they are not playgrounds for children 0-6. Sandboxes etc. stay.
_GAME_TABLE = re.compile(r"^(stół do (ping ponga|gry w szachy)|piłkarzyki)([ ,]+(i |stół do )?"
                         r"(ping ponga|gry w szachy|piłkarzyki))*$")


def _game_table(p: dict[str, Any]) -> bool:
    return bool(_GAME_TABLE.match(_s(p, "nazwa").casefold()))


def _fact(key: str, value: dict[str, Any], text: str) -> OpenFact:
    """A fact whose one-liner may be cut at 80 chars: the full text then goes into the note."""
    cut = short(text)
    return OpenFact(key, value, cut, text if cut != text else None)


def _facts(p: dict[str, Any]) -> tuple[OpenFact, ...]:
    facts: list[OpenFact] = []
    access = _s(p, "dostep")
    if access not in UNKNOWN:
        if _HOURS.match(access):
            hours = access.replace(" ", "").replace("-", "–")
            facts.append(OpenFact("opening_hours", {"text": access}, short(f"Otwarte {hours}")))
        else:
            facts.append(_fact("access", {"text": access, "unrestricted": access == "bez ograniczeń"},
                               f"Dostęp: {access}"))
    paid = _s(p, "platnosc")
    if paid in {"tak", "nie"}:
        facts.append(OpenFact("price", {"free": paid == "nie"}, "Bezpłatny" if paid == "nie" else "Płatny"))
    manager = _s(p, "opiekun")
    if manager not in UNKNOWN:
        facts.append(_fact("managed_by", {"name": manager}, f"Zarządca: {manager}"))
    equipment = {key: True for src, (key, _) in EQUIPMENT.items() if _s(p, src) == "tak"}
    if equipment:
        labels = [label for src, (_, label) in EQUIPMENT.items() if _s(p, src) == "tak"]
        facts.append(OpenFact("equipment", equipment, short(", ".join(labels).capitalize())))
    return tuple(facts)


def parse(geojson: Any, data_url: str) -> ImportBatch:
    if not isinstance(geojson, dict) or geojson.get("type") != "FeatureCollection":
        raise ParseError("Poznań playgrounds: expected a GeoJSON FeatureCollection")
    features = geojson.get("features")
    if not isinstance(features, list) or not features:
        raise ParseError("Poznań playgrounds: no features")
    first = features[0].get("properties") if isinstance(features[0], dict) else None
    if not isinstance(first, dict) or any(k not in first for k in REQUIRED):
        raise ParseError(f"Poznań playgrounds: property shape changed (need {list(REQUIRED)})")

    records: dict[str, OpenRecord] = {}
    skipped = 0
    for i, f in enumerate(features):
        p = f.get("properties") if isinstance(f, dict) else None
        geom = f.get("geometry") if isinstance(f, dict) else None
        if not isinstance(p, dict) or not isinstance(geom, dict):
            raise ParseError(f"Poznań playgrounds feature {i}: missing properties or geometry")
        if (_s(p, "rodzaj") != "plac gier i zabaw" or _s(p, "typ") != "ogólnodostępne"
                or _closed(p) or _game_table(p)):
            skipped += 1
            continue
        ext = str(f.get("id") or "").strip()
        if not ext:
            raise ParseError(f"Poznań playgrounds feature {i}: no id")
        coords = geom.get("coordinates")
        if geom.get("type") != "Point" or not isinstance(coords, list) or len(coords) < 2:
            raise ParseError(f"Poznań playgrounds feature {ext}: expected a Point")
        lon, lat = float(coords[0]), float(coords[1])
        if not in_poland(lat, lon):
            raise ParseError(f"Poznań playgrounds feature {ext}: coordinates {coords} outside Poland "
                             "(projection changed?)")
        if ext in records:
            raise ParseError(f"Poznań playgrounds: duplicate id {ext}")
        name = _s(p, "nazwa")
        records[ext] = OpenRecord(
            external_id=ext, name=name or "Plac zabaw", locality="Poznań", categories=(CATEGORY,),
            voivodeship="Wielkopolskie", address=_s(p, "lokalizacja") or None, lat=lat, lon=lon,
            facts=_facts(p),
        )
    return ImportBatch(SOURCE_ID, data_url, None, tuple(records.values()), skipped)


def parse_bundle(bundle: dict[str, Any]) -> ImportBatch:
    try:
        return parse(bundle["data"], bundle["data_url"])
    except KeyError as e:
        raise ParseError(f"Poznań playgrounds bundle: missing {e}") from e
