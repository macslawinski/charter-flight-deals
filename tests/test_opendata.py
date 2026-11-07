"""Open-data importers: parsing (saved samples) and idempotent writes (local Postgres, rolled back)."""

import json
import os
from collections.abc import Iterator
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
import pytest

from ingest import store
from ingest.models import ParseError
from ingest.opendata import ImportBatch, OpenFact, OpenRecord, nisoz, poznan_playgrounds
from ingest.opendata.__main__ import parse_checked
from ingest.opendata.save import save_batch

FIXTURES = Path(__file__).parent / "fixtures"
DSN = os.environ.get("TEST_DATABASE_URL", "postgresql://postgres@localhost:5432/cfd_local")


def bundle(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


# --- NiŚOZ ------------------------------------------------------------------------------------

def test_nisoz_data_file_url_from_page_html() -> None:
    html = ('..."markers":[]},"map_points_file":"\\/sites\\/pacjent\\/files\\/dane\\/'
            'Mapa-Nocna-i-swiateczna-pomoc-05.10.2026.json","points_url":null...')
    url = nisoz.data_file_url(html)
    assert url == "https://pacjent.gov.pl/sites/pacjent/files/dane/Mapa-Nocna-i-swiateczna-pomoc-05.10.2026.json"
    assert nisoz.file_date(url) == date(2026, 10, 5)


def test_nisoz_page_without_data_file_fails_loudly() -> None:
    with pytest.raises(ParseError):
        nisoz.data_file_url("<html>new layout</html>")


def test_nisoz_parse_sample() -> None:
    batch = nisoz.parse_bundle(bundle("nisoz_sample.json"))
    assert batch.source_id == "nfz_nisoz"
    assert batch.data_as_of == date(2026, 10, 5)
    assert len(batch.records) == 6 and batch.skipped == 1     # one empty filler row
    by_name = {r.name: r for r in batch.records}

    wczd = by_name["WIELKOPOLSKIE CENTRUM ZDROWIA DZIECKA"]
    assert wczd.locality == "Poznań" and wczd.categories == ("nisoz",)
    assert wczd.address == "ADAMA WRZOSKA 1, 60-663 POZNAŃ"
    assert wczd.lat == pytest.approx(52.437787)
    assert [f.key for f in wczd.facts] == ["phone"]

    # Old district names collapse to the city so filters match; the address keeps the original.
    assert {r.locality for r in batch.records if "POZNA" in (r.address or "")} == {"Poznań"}

    gorzow = next(r for r in batch.records if r.locality == "Gorzów Wielkopolski")
    keys = {f.key: f for f in gorzow.facts}
    assert keys["phone"].value == {"numbers": ["95 733 18 95", "95 733 18 97"]}
    assert "opening_hours" in keys and "notes" in keys
    assert all(len(f.short) <= 80 for r in batch.records for f in r.facts)

    # "lat" holding a "lat, lon" pair that disagrees with "lng": no coordinates rather than wrong ones.
    gdansk = next(r for r in batch.records if r.locality == "Gdańsk")
    assert gdansk.lat is None and gdansk.lon is None and gdansk.address


def test_nisoz_external_id_is_stable() -> None:
    a = nisoz.parse_bundle(bundle("nisoz_sample.json"))
    b = nisoz.parse_bundle(bundle("nisoz_sample.json"))
    assert [r.external_id for r in a.records] == [r.external_id for r in b.records]
    assert len({r.external_id for r in a.records}) == len(a.records)


def test_nisoz_shape_change_fails_loudly() -> None:
    b = bundle("nisoz_sample.json")
    for row in b["data"]:
        row.pop("adr_lok_miejsc")
    with pytest.raises(ParseError, match="missing keys"):
        nisoz.parse_bundle(b)


def test_nisoz_real_row_without_locality_fails() -> None:
    b = bundle("nisoz_sample.json")
    b["data"][0]["adr_lok_miejsc"] = ""
    with pytest.raises(ParseError, match="locality missing"):
        nisoz.parse_bundle(b)


def test_min_records_guard() -> None:
    with pytest.raises(ParseError, match="min_records"):
        parse_checked(nisoz.parse_bundle, bundle("nisoz_sample.json"), min_records=400)


# --- Poznań playgrounds -------------------------------------------------------------------------

def test_playgrounds_keep_only_public_open_playgrounds() -> None:
    batch = poznan_playgrounds.parse_bundle(bundle("poznan_playgrounds_sample.json"))
    # 7 features: closed ('nieczynny'), no public access and a sports pitch are skipped.
    assert len(batch.records) == 4 and batch.skipped == 3
    assert {r.external_id for r in batch.records} == {"1", "3", "39", "25"}
    assert all(r.locality == "Poznań" and r.categories == ("plac_zabaw",) for r in batch.records)
    assert all(r.lat is not None and 52 < r.lat < 53 for r in batch.records)


def test_playground_facts() -> None:
    recs = {r.external_id: r for r in
            poznan_playgrounds.parse_bundle(bundle("poznan_playgrounds_sample.json")).records}
    f1 = {f.key: f for f in recs["1"].facts}
    assert f1["access"].value == {"text": "bez ograniczeń", "unrestricted": True}
    assert f1["price"].value == {"free": True} and f1["price"].short == "Bezpłatny"
    assert f1["managed_by"].value == {"name": "Wspólnota Mieszkaniowa 5G-K"}
    assert {f.key for f in recs["3"].facts} >= {"equipment"}
    assert recs["3"].facts[-1].value["zipline"] is True
    hours = {f.key: f for f in recs["39"].facts}["opening_hours"]
    assert hours.value == {"text": "8-21"} and hours.short == "Otwarte 8–21"
    assert recs["25"].name != "Plac zabaw"   # a named playground keeps its name


def test_playgrounds_closed_in_either_gender_is_skipped() -> None:
    b = bundle("poznan_playgrounds_sample.json")
    one = next(f for f in b["data"]["features"] if str(f["id"]) == "1")
    one["properties"]["dostep"] = "nieczynne"
    assert "1" not in {r.external_id for r in poznan_playgrounds.parse_bundle(b).records}


@pytest.mark.parametrize(("name", "kept"), [
    ("stół do ping ponga", False), ("stół do gry w szachy", False), ("piłkarzyki", False),
    ("stół do ping ponga i piłkarzyki", False), ("stół do ping ponga, stół do gry w szachy", False),
    ("piaskownica", True), ("Plac zabaw", True), ("Plac zabaw ze stołem do ping ponga", True),
])
def test_playgrounds_skip_game_tables(name: str, kept: bool) -> None:
    b = bundle("poznan_playgrounds_sample.json")
    one = next(f for f in b["data"]["features"] if str(f["id"]) == "1")
    one["properties"]["nazwa"] = name
    assert ("1" in {r.external_id for r in poznan_playgrounds.parse_bundle(b).records}) is kept


def test_playground_long_access_keeps_full_text_in_note() -> None:
    b = bundle("poznan_playgrounds_sample.json")
    one = next(f for f in b["data"]["features"] if str(f["id"]) == "1")
    text = "7 dni w tyg. w okresie letnim w godz. 9-22 , w okresie zimowym w godz. 9-18 (ogrodzony)"
    one["properties"]["dostep"] = text
    rec = next(r for r in poznan_playgrounds.parse_bundle(b).records if r.external_id == "1")
    access = {f.key: f for f in rec.facts}["access"]
    assert len(access.short) <= 80 and access.short.endswith("…")
    assert access.note == f"Dostęp: {text}"
    assert {f.key: f for f in rec.facts}["price"].note is None


def test_playgrounds_projection_change_fails() -> None:
    b = bundle("poznan_playgrounds_sample.json")
    b["data"]["features"][0]["geometry"]["coordinates"] = [357000.0, 506000.0]   # metres, not degrees
    with pytest.raises(ParseError, match="outside Poland"):
        poznan_playgrounds.parse_bundle(b)


# --- idempotent save (local Postgres) -----------------------------------------------------------

@pytest.fixture
def conn() -> Iterator[psycopg.Connection[Any]]:
    try:
        c = store.connect(DSN)
    except psycopg.OperationalError:
        pytest.skip("local Postgres not available (run scripts/db_local.py)")
    try:
        if c.execute("select to_regclass('venues')").fetchone() == (None,):
            pytest.skip("cfd_local has no venues table (re-run scripts/db_local.py)")
        # Real rows may have been imported into cfd_local; work on a clean slate inside the transaction.
        c.execute("delete from venues where source_id = 'poznan_place_zabaw'")
        yield c
    finally:
        c.rollback()
        c.close()


def _batch(*records: OpenRecord) -> ImportBatch:
    return ImportBatch("poznan_place_zabaw", "https://example.test/data.json", None, records)


def _rec(ext: str, name: str = "Plac zabaw") -> OpenRecord:
    return OpenRecord(ext, name, "Poznań", ("plac_zabaw",), lat=52.4, lon=16.9,
                      facts=(OpenFact("price", {"free": True}, "Bezpłatny"),))


def _venues(conn: psycopg.Connection[Any]) -> dict[str, tuple[str, str]]:
    rows = conn.execute("select external_id, name, status from venues "
                        "where source_id = 'poznan_place_zabaw'").fetchall()
    return {r[0]: (r[1], r[2]) for r in rows}


def test_save_is_idempotent(conn: psycopg.Connection[Any]) -> None:
    d1, d2 = date(2026, 11, 7), date(2026, 11, 8)
    first = save_batch(conn, _batch(_rec("a"), _rec("b")), d1)
    assert first["inserted"] == 2 and first["retired"] == 0
    again = save_batch(conn, _batch(_rec("a"), _rec("b")), d2)
    assert again == {"seen": 2, "inserted": 0, "updated": 2, "retired": 0, "skipped": 0}
    assert conn.execute(
        """select count(*) from venue_facts f join venues v on v.id = f.venue_id
           where v.source_id = 'poznan_place_zabaw'""").fetchone() == (2,)
    assert conn.execute("select min(first_seen_at), max(last_seen_at) from venues "
                        "where source_id = 'poznan_place_zabaw'").fetchone() == (d1, d2)
    assert set(_venues(conn).values()) == {("Plac zabaw", "published")}   # source auto-publishes


def test_vanished_record_is_retired_and_comes_back(conn: psycopg.Connection[Any]) -> None:
    save_batch(conn, _batch(_rec("a"), _rec("b")), date(2026, 11, 7))
    res = save_batch(conn, _batch(_rec("a")), date(2026, 11, 8))
    assert res["retired"] == 1
    assert _venues(conn)["b"][1] == "retired"        # kept, not deleted
    save_batch(conn, _batch(_rec("a"), _rec("b", "Plac zabaw Sołacz")), date(2026, 11, 9))
    assert _venues(conn)["b"] == ("Plac zabaw Sołacz", "published")


def test_manual_status_survives_reimport(conn: psycopg.Connection[Any]) -> None:
    save_batch(conn, _batch(_rec("a")), date(2026, 11, 7))
    conn.execute("update venues set status = 'draft' where source_id = 'poznan_place_zabaw'")
    save_batch(conn, _batch(replace(_rec("a"), name="Nowa nazwa")), date(2026, 11, 8))
    assert _venues(conn)["a"] == ("Nowa nazwa", "draft")
