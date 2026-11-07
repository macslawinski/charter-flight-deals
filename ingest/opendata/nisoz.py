"""NFZ night and holiday care points (NiŚOZ) from the pacjent.gov.pl map.

The map page embeds the path of its data file in the HTML (Drupal settings, "map_points_file"). The
file is a JSON array of rows with the operator, the point's address, phone, coordinates and optional
hours. About a third of the rows are empty filler; those are skipped. A real row without a locality
fails the parse: the shape changed and nothing should be written.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from typing import Any

from ingest.models import ParseError
from ingest.opendata import ImportBatch, OpenFact, OpenRecord, in_poland, short

SOURCE_ID = "nfz_nisoz"
BASE = "https://pacjent.gov.pl"
CATEGORY = "nisoz"

_FILE = re.compile(r'"map_points_file"\s*:\s*"(?P<path>\\?/sites\\?/pacjent\\?/files\\?/dane\\?/[^"]+?\.json)"')
_FILE_DATE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})\.json$")
REQUIRED = ("nazwa_swd", "adr_lok_miejsc", "adr_lok_ulica", "adr_lok_nr_domu", "adr_lok_kod_poczt",
            "telefon_rej", "lat", "lng", "Województwo")
DISTRICT_CITIES = {"Poznań", "Kraków", "Łódź", "Wrocław", "Warszawa"}
DAYS = (("harm_pon", "pn."), ("harm_wt", "wt."), ("harm_sr", "śr."), ("harm_czw", "czw."),
        ("harm_pt", "pt."), ("harm_sob", "sob."), ("harm_niedz", "niedz."))


def data_file_url(page_html: str) -> str:
    """Absolute URL of the map's data file, read from the page HTML."""
    m = _FILE.search(page_html)
    if not m:
        raise ParseError("map_points_file not found on the NiŚOZ page (page layout changed?)")
    return BASE + m.group("path").replace("\\/", "/")


def file_date(url: str) -> date | None:
    """The data date carried in the file name (…-05.10.2026.json), if any."""
    m = _FILE_DATE.search(url)
    if not m:
        return None
    d, mth, y = (int(x) for x in m.groups())
    try:
        return date(y, mth, d)
    except ValueError:
        return None


def _s(row: dict[str, Any], key: str) -> str:
    v = row.get(key)
    return "" if v is None else " ".join(str(v).split())


def _coord(v: Any) -> float | None:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    if isinstance(v, str) and v.strip():
        try:
            return float(v.strip().replace(",", "."))
        except ValueError:
            return None
    return None


def _locality(raw: str) -> str:
    """'POZNAŃ' -> 'Poznań'; 'Poznań-Jeżyce' (old district names) -> 'Poznań', so filters match.

    The full original stays in the address line.
    """
    loc = raw.title() if raw.isupper() else raw
    head = loc.split("-", 1)[0].strip()
    return head if "-" in loc and head in DISTRICT_CITIES else loc


def _external_id(name: str, locality: str, street: str, number: str) -> str:
    key = "|".join(x.casefold() for x in (name, locality, street, number))
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def _address(row: dict[str, Any]) -> str:
    street = _s(row, "adr_lok_ulica")
    number = _s(row, "adr_lok_nr_domu")
    flat = _s(row, "adr_lok_nr_lokalu")
    line1 = " ".join(x for x in (street, number + (f"/{flat}" if flat else "")) if x)
    line2 = " ".join(x for x in (_s(row, "adr_lok_kod_poczt"), _s(row, "adr_lok_miejsc")) if x)
    return ", ".join(x for x in (line1, line2) if x)


def _website(v: str) -> str | None:
    v = v.strip()
    if re.match(r"^https?://\S+$", v):
        return v
    return None  # bare 'www.x.pl' or free text: don't guess the scheme


def _facts(row: dict[str, Any]) -> tuple[OpenFact, ...]:
    facts: list[OpenFact] = []
    phone = _s(row, "telefon_rej")
    if phone:
        numbers = [p.strip() for p in re.split(r"[;,]", phone) if p.strip()]
        facts.append(OpenFact("phone", {"numbers": numbers}, short(f"Tel. {numbers[0]}"),
                              "; ".join(numbers) if len(numbers) > 1 else None))
    hours = {label: _s(row, key) for key, label in DAYS if _s(row, key)}
    if hours:
        weekday, sat, sun = _s(row, "harm_pon"), _s(row, "harm_sob"), _s(row, "harm_niedz")
        parts = [f"pn.–pt. {weekday}" if weekday else "", f"sob. {sat}" if sat else "",
                 f"niedz. {sun}" if sun else ""]
        facts.append(OpenFact("opening_hours", {"by_day": hours},
                              short("Godziny: " + "; ".join(p for p in parts if p)),
                              "; ".join(f"{d} {h}" for d, h in hours.items())))
    notes = _s(row, "uwagi")
    if notes:
        facts.append(OpenFact("notes", {"text": notes}, short(notes), notes))
    mode = _s(row, "zakreś świadczeń")
    if mode:
        facts.append(OpenFact("service_mode", {"text": mode}, short(mode.capitalize())))
    return tuple(facts)


def parse(rows: Any, data_url: str) -> ImportBatch:
    if not isinstance(rows, list) or not rows:
        raise ParseError("NiŚOZ file: expected a non-empty JSON array")
    if not isinstance(rows[0], dict) or any(k not in rows[0] for k in REQUIRED):
        missing = [k for k in REQUIRED if not isinstance(rows[0], dict) or k not in rows[0]]
        raise ParseError(f"NiŚOZ file: row shape changed, missing keys {missing}")

    records: dict[str, OpenRecord] = {}
    skipped = 0
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ParseError(f"NiŚOZ row {i}: expected an object")
        name, locality = _s(row, "nazwa_swd"), _s(row, "adr_lok_miejsc")
        if not name and not locality:
            skipped += 1  # empty filler row
            continue
        if not name or not locality:
            raise ParseError(f"NiŚOZ row {i}: operator name or locality missing ({name!r}, {locality!r})")
        locality = _locality(locality)
        lat, lon = _coord(row.get("lat")), _coord(row.get("lng"))
        if not in_poland(lat, lon):
            lat = lon = None  # no coordinates rather than wrong ones; address still shown
        ext = _external_id(name, locality, _s(row, "adr_lok_ulica"), _s(row, "adr_lok_nr_domu"))
        if ext in records:
            raise ParseError(f"NiŚOZ row {i}: duplicate point {name!r} at {_address(row)!r}")
        records[ext] = OpenRecord(
            external_id=ext, name=name, locality=locality, categories=(CATEGORY,),
            voivodeship=_s(row, "Województwo") or None, address=_address(row) or None,
            lat=lat, lon=lon, official_url=_website(_s(row, "strona_www_podmiotu")),
            facts=_facts(row),
        )
    return ImportBatch(SOURCE_ID, data_url, file_date(data_url), tuple(records.values()), skipped)


def parse_bundle(bundle: dict[str, Any]) -> ImportBatch:
    """Parse a saved run bundle {"data_url": ..., "data": [...]} (see ingest.opendata.__main__)."""
    try:
        return parse(bundle["data"], bundle["data_url"])
    except KeyError as e:
        raise ParseError(f"NiŚOZ bundle: missing {e}") from e


def loads(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ParseError(f"NiŚOZ file is not JSON: {e}") from e
