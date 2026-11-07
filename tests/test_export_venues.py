"""scripts/export_venues.py: DB -> map JSON (local Postgres, rolled back) and the committed file's shape."""

import json
import os
import sys
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import psycopg
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import export_venues

from ingest.opendata import ImportBatch, OpenFact, OpenRecord
from ingest.opendata.save import log_run, save_batch

DSN = os.environ.get("TEST_DATABASE_URL", "postgresql://postgres@localhost:5432/cfd_local")
COMMITTED = export_venues.OUT_DIR / "poznan.json"


@pytest.fixture
def conn() -> Iterator[psycopg.Connection[Any]]:
    try:
        c = psycopg.connect(DSN)
    except psycopg.OperationalError:
        pytest.skip("local Postgres not available (run scripts/db_local.py)")
    try:
        if c.execute("select to_regclass('venues')").fetchone() == (None,):
            pytest.skip("cfd_local has no venues table (re-run scripts/db_local.py)")
        c.execute("delete from venues")
        yield c
    finally:
        c.rollback()
        c.close()


def _rec(ext: str, locality: str = "Poznań", *facts: OpenFact) -> OpenRecord:
    return OpenRecord(ext, f"Plac {ext}", locality, ("plac_zabaw",), lat=52.4, lon=16.9, facts=facts)


def test_build_exports_published_city_venues_with_refs(conn: psycopg.Connection[Any]) -> None:
    url = "https://example.test/place.json"
    free = OpenFact("price", {"free": True}, "Bezpłatny")
    hours = OpenFact("opening_hours", {"text": "8-21"}, "Otwarte 8–21")
    batch = ImportBatch("poznan_place_zabaw", url, None,
                        (_rec("a", "Poznań", free, hours), _rec("b", "Poznań", free),
                         _rec("c", "Swarzędz", free), _rec("d", "Poznań", free)))
    save_batch(conn, batch, date(2026, 11, 7))
    conn.execute("update venues set status = 'draft' where external_id = 'd'")
    t = datetime(2026, 11, 7, 12, tzinfo=UTC)
    log_run(conn, "poznan_place_zabaw", t, t, "ok", data_url=url)

    doc = export_venues.build(conn, "poznan")
    assert [v["id"] for v in doc["venues"]] == ["poznan_place_zabaw:a", "poznan_place_zabaw:b"]
    a = doc["venues"][0]
    assert [f["key"] for f in a["facts"]] == ["opening_hours", "price"]      # display order
    # One shared reference for every fact and location from the same import.
    assert doc["refs"] == [{"src": "poznan_place_zabaw", "type": "open_data", "url": url,
                            "verified_at": "2026-11-07"}]
    assert a["location_ref"] == 0 and {f["ref"] for f in a["facts"]} == {0}
    assert doc["categories"] == {"plac_zabaw": "Place zabaw"}
    assert set(doc["fact_labels"]) == {"opening_hours", "price"}
    src = doc["sources"]["poznan_place_zabaw"]
    assert src["attribution"].startswith("Źródło: Miasto Poznań") and src["imported_at"] == "2026-11-07"
    assert json.loads(export_venues.render(doc)) == doc


def test_build_includes_curated_venues_with_their_own_refs(conn: psycopg.Connection[Any]) -> None:
    from ingest import curated

    data = curated.load()
    curated.save_venues(conn, data.venues, today=date(2026, 11, 7))
    doc = export_venues.build(conn, "poznan")
    mlecz = next(v for v in doc["venues"] if v["id"] == "curated:mlecz")
    assert mlecz["categories"] == ["sala_zabaw"] and mlecz["facts"][0]["key"] == "age_range"
    loc = doc["refs"][mlecz["location_ref"]]
    assert loc == {"src": None, "type": "osm", "url": "https://www.openstreetmap.org/node/12492719739",
                   "verified_at": "2026-11-04"}
    assert {doc["refs"][f["ref"]]["type"] for f in mlecz["facts"]} == {"venue_website"}
    assert "curated" not in doc["sources"]                 # the site lists open-data sources only
    assert {"infant_free", "price_child", "socks_required"} <= set(doc["fact_labels"])


def _committed() -> dict[str, Any]:
    if not COMMITTED.exists():
        pytest.skip("no committed map export yet")
    return json.loads(COMMITTED.read_text(encoding="utf-8"))


def test_committed_export_is_consistent() -> None:
    # The site trusts this file blindly: every reference, label and source it points to must exist.
    doc = _committed()
    assert doc["city"] == "poznan" and doc["venues"]
    n_refs = len(doc["refs"])
    for r in doc["refs"]:
        assert r["url"].startswith("https://") and date.fromisoformat(r["verified_at"])
    ids = [v["id"] for v in doc["venues"]]
    assert len(ids) == len(set(ids))
    for v in doc["venues"]:
        assert v["source"] in doc["sources"] or v["source"] == "curated"
        assert v["categories"] and set(v["categories"]) <= set(doc["categories"])
        assert v["lat"] is None or 52.2 < v["lat"] < 52.6
        for f in v["facts"]:
            assert f["key"] in doc["fact_labels"] and 0 <= f["ref"] < n_refs
            assert 1 <= len(f["short"]) <= 80
    for s in doc["sources"].values():
        assert s["url"].startswith("https://") and s["attribution"]
