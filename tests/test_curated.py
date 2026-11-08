"""data/curated loader: strict validation, and a DB round-trip on local Postgres (rolled back)."""

import shutil
from pathlib import Path

import pytest
from test_transform import db  # noqa: F401  (fixture)

from ingest import curated
from ingest.curated import CuratedError


def test_repo_curated_data_is_valid():
    data = curated.load()
    assert {p.slug for p in data.places} >= {"rodos", "kreta-heraklion", "grzybowo"}
    saltic = next(h for h in data.hotels if h.slug == "saltic-resort-spa-grzybowo")
    cot = next(f for f in saltic.features if f.key == "cot")
    assert cot.value["fee_pln_per_night"] == 60 and cot.age_band == "0-3"
    assert all(f.url and f.url.startswith("https://www.hotelsaltic.pl/") for f in saltic.features)
    rules = {c.carrier_iata: {(r.key, r.age_band): r for r in c.rules} for c in data.carriers}
    assert set(rules) >= {"E4", "QS", "RR", "LO", "FR", "W6", "XC", "A3", "3E", "NO", "BJ", "2W", "SM"}
    assert rules["E4"][("infants_per_adult", "0-2")].value == {"max": 1}
    assert rules["LO"][("twins", "0-2")].value["one_adult_allowed"] is True
    # Every fee rule tells the parent where the price comes from: an amount or an explicit flag.
    for c in data.carriers:
        fee = next(r for r in c.rules if r.key == "infant_fee")
        assert fee.note and fee.url and fee.source == "carrier_official"


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    shutil.copytree(curated.CURATED, tmp_path / "curated")
    return tmp_path / "curated"


def _hotel_file(tree: Path) -> Path:
    return tree / "hotels" / "grzybowo" / "saltic-resort-spa-grzybowo.toml"


def _append(path: Path, text: str) -> None:
    path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")


FACT = """
[[feature]]
key = "{key}"
value = {{ available = true }}
source = "{source}"
url = "{url}"
verified_at = 2026-11-04
"""


@pytest.mark.parametrize(("key", "source", "url", "error"), [
    ("cott", "hotel_website", "https://x.pl/a", "unknown key 'cott'"),
    ("lift", "booking_com", "https://x.pl/a", "bad source"),
    ("lift", "hotel_website", "http://x.pl/a", "must start with https://"),
    ("lift", "review_hint", "https://x.pl/a", "never a verified fact"),
])
def test_bad_fact_is_rejected(tree, key, source, url, error):
    _append(_hotel_file(tree), FACT.format(key=key, source=source, url=url))
    with pytest.raises(CuratedError, match=error):
        curated.load(tree)


def test_duplicate_fact_is_rejected(tree):
    _append(_hotel_file(tree), FACT.format(key="cot", source="hotel_website", url="https://x.pl")
            .replace('key = "cot"', 'key = "cot"\nage_band = "0-3"'))
    with pytest.raises(CuratedError, match="duplicate"):
        curated.load(tree)


def test_unknown_field_is_rejected(tree):
    path = _hotel_file(tree)
    path.write_text(path.read_text(encoding="utf-8").replace('status = "published"',
                                                             'status = "published"\nstars = 5'),
                    encoding="utf-8")
    with pytest.raises(CuratedError, match="unknown field"):
        curated.load(tree)


def test_hotel_must_live_in_its_place_folder(tree):
    (tree / "hotels" / "rodos").mkdir(exist_ok=True)
    shutil.move(_hotel_file(tree), tree / "hotels" / "rodos" / "saltic.toml")
    with pytest.raises(CuratedError, match="must live in hotels/grzybowo/"):
        curated.load(tree)


def test_flight_place_needs_iata(tree):
    path = tree / "places.toml"
    path.write_text(path.read_text(encoding="utf-8").replace('dest_iata = "RHO"\n', ""),
                    encoding="utf-8")
    with pytest.raises(CuratedError, match="need dest_iata"):
        curated.load(tree)


def test_child_rule_needs_summary(tree):
    (tree / "child_rules").mkdir(exist_ok=True)
    (tree / "child_rules" / "fr.toml").write_text(
        'carrier = "FR"\n[[rule]]\nkey = "lap_infant"\nvalue = { allowed = true }\n'
        'source = "carrier_official"\nurl = "https://www.ryanair.com/x"\nverified_at = 2026-11-04\n',
        encoding="utf-8")
    with pytest.raises(CuratedError, match="'note'"):
        curated.load(tree)


def test_short_headline_is_capped(tree):
    path = tree / "child_rules" / "fr.toml"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace('short = "25 € za lot w jedną stronę"', 'short = "' + "x" * 61 + '"'),
                    encoding="utf-8")
    with pytest.raises(CuratedError, match="longer than 60"):
        curated.load(tree)


def test_venues_load_with_their_own_sources():
    data = curated.load()
    venues = {v.slug: v for v in data.venues}
    assert {"kraina-piratow", "mlecz", "fikolki-stary-browar"} <= set(venues)
    kp = venues["kraina-piratow"]
    assert kp.city == "poznan" and kp.osm == "node/1982842819"
    assert all(f.source == "venue_website" and f.url for f in kp.features)


def test_venue_rejects_hotel_source_and_bad_osm(tree):
    path = tree / "venues" / "poznan" / "madagaskar.toml"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace('source = "venue_website"', 'source = "hotel_website"', 1),
                    encoding="utf-8")
    with pytest.raises(CuratedError, match="bad source"):
        curated.load(tree)
    path.write_text(text.replace('osm = "way/165076478"', 'osm = "165076478"'), encoding="utf-8")
    with pytest.raises(CuratedError, match="osm must look like"):
        curated.load(tree)


def test_save_round_trip(db):  # noqa: F811
    data = curated.load()
    counts = curated.save(db, data)
    assert counts["places"] == len(data.places) and counts["hotels"] == len(data.hotels)
    row = db.execute(
        """select f.value->>'fee_pln_per_night', p.kind, p.dest_iata
           from hotel_child_features f join hotels h on h.id = f.hotel_id
           join places p on p.slug = h.place_slug
           where h.slug = 'saltic-resort-spa-grzybowo' and f.feature_key = 'cot'""").fetchone()
    assert row == ("60", "domestic", None)
    # Flight places join to Product A's destinations by IATA and share its slug.
    assert db.execute("""select d.slug from places p join destinations d on d.iata = p.dest_iata
                         where p.slug = 'kreta-heraklion'""").fetchone() == ("kreta-heraklion",)
    # Child rules reference carriers seeded in `airlines` (005); an unknown code fails the FK.
    assert counts["child_rules"] == sum(len(c.rules) for c in data.carriers) > 0
    assert db.execute("""select r.value->>'amount_eur' from child_rules r
                         where r.carrier_iata = 'FR' and r.rule_key = 'infant_fee'""").fetchone() == ("25",)
    assert curated.save(db, data) == counts  # idempotent: files are the source of truth


def test_venues_round_trip_and_retire(db):  # noqa: F811
    data = curated.load()
    counts = curated.save_venues(db, data.venues)
    assert counts == {"venues": len(data.venues), "venue_facts": sum(len(v.features) for v in data.venues),
                      "venues_retired": 0}
    row = db.execute(
        """select v.source_id, v.external_id, v.locality, v.status, v.location_source_url,
                  array(select category from venue_category_links where venue_id = v.id)
           from venues v where v.slug = 'mlecz'""").fetchone()
    assert row == ("curated", "mlecz", "Poznań", "published",
                   "https://www.openstreetmap.org/node/12492719739", ["sala_zabaw"])
    # age_band "0-1" lands in the numeric month columns; to_confirm and the source survive.
    assert db.execute(
        """select f.age_min_months, f.age_max_months, f.to_confirm, f.source_type::text, f.short_pl
           from venue_facts f join venues v on v.id = f.venue_id
           where v.slug = 'mlecz' and f.fact_key = 'infant_free'""").fetchone() == (
        0, 12, True, "venue_website", "Niemowlęta taniej: 6–12 mies. −50%")
    first_id = db.execute("select id from venues where slug = 'mlecz'").fetchone()
    # A removed file retires its venue (never deletes it); the others keep their ids.
    rest = tuple(v for v in data.venues if v.slug != "mlecz")
    assert curated.save_venues(db, rest)["venues_retired"] == 1
    assert db.execute("select id, status from venues where slug = 'mlecz'").fetchone() == (*first_id, "retired")
    curated.save_venues(db, data.venues)
    assert db.execute("select status from venues where slug = 'mlecz'").fetchone() == ("published",)
    # Pools and rinks link to their own category and use the keys of migration 014.
    cats = dict(db.execute(
        """select v.slug, l.category from venues v join venue_category_links l on l.venue_id = v.id
           where v.slug in ('termy-maltanskie', 'lodowisko-ligawa')""").fetchall())
    assert cats == {"termy-maltanskie": "basen", "lodowisko-ligawa": "lodowisko"}


def test_venue_category_limits_its_keys(tree):
    path = tree / "venues" / "poznan" / "lodowisko-ligawa.toml"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace('key = "skating_aid"', 'key = "socks_required"'), encoding="utf-8")
    with pytest.raises(CuratedError, match="unknown key 'socks_required'"):
        curated.load(tree)
    path.write_text(text.replace('category = "lodowisko"', 'category = "kino"'), encoding="utf-8")
    with pytest.raises(CuratedError, match="category 'kino'"):
        curated.load(tree)
    # A file without `category` stays an indoor playground.
    assert {v.slug: v.category for v in curated.load().venues}["mlecz"] == "sala_zabaw"


def test_card_short_falls_back_to_first_sentence():
    f = curated.Fact("cafe", None, {}, "Kawiarnia jest. Druga część.", "venue_website", "https://x.pl",
                     curated.date(2026, 11, 4), False)
    assert curated.card_short(f) == "Kawiarnia jest."


def test_venue_fact_without_url_is_rejected(tree):
    path = tree / "venues" / "poznan" / "mlecz.toml"
    _append(path, '\n[[feature]]\nkey = "parking"\nvalue = { available = true }\nshort = "Parking"\n'
                  'source = "own_visit"\nverified_at = 2026-11-04\n')
    with pytest.raises(CuratedError, match="need a url"):
        curated.load(tree)


# --- essentials (official topics, exported to the site only) ---------------------------------

def _docs(tree: Path) -> Path:
    return tree / "essentials" / "travel_documents.toml"


ESSENTIAL_FACT = """
[[fact]]
group = "{group}"
key = "extra-fact"
short = "Test."
publisher = "gov.pl"
url = "{url}"
verified_at = 2026-11-04
"""


def test_travel_documents_load_with_official_sources_only():
    [docs] = [e for e in curated.load().essentials if e.topic == "travel_documents"]
    assert {g.id for g in docs.groups} == {"dokument", "dowod", "paszport", "ekuz", "zgoda"}
    fee = next(f for f in docs.facts if f.key == "passport-fee")
    assert "30 zł" in fee.short and fee.url.startswith("https://www.gov.pl/")
    # Sources that disagree are shown as such, never as a plain fact.
    consent = next(f for f in docs.facts if f.key == "consent-holiday")
    assert consent.to_confirm and consent.also


@pytest.mark.parametrize("group, url, error", [
    ("paszport", "https://www.paszport-info.pl/x", "gov.pl https url"),
    ("paszport", "https://gov.pl.evil.com/x", "gov.pl https url"),
    ("nope", "https://www.gov.pl/x", "group 'nope' not defined"),
])
def test_bad_essential_fact_is_rejected(tree, group, url, error):
    _append(_docs(tree), ESSENTIAL_FACT.format(group=group, url=url))
    with pytest.raises(CuratedError, match=error):
        curated.load(tree)


def test_essential_unknown_topic_and_empty_group_are_rejected(tree):
    shutil.copy(_docs(tree), tree / "essentials" / "benefits.toml")
    with pytest.raises(CuratedError, match="unknown topic 'benefits'"):
        curated.load(tree)
    (tree / "essentials" / "benefits.toml").unlink()
    _append(_docs(tree), '\n[[group]]\nid = "pusta"\ntitle = "Pusta"\nicon = "info"\n')
    with pytest.raises(CuratedError, match="group 'pusta' has no facts"):
        curated.load(tree)


# --- airports (facts from the airport's own site, exported to the site only) ----------------

AIRPORT_FACT = """
[[fact]]
key = "{key}"
short = "Test."
url = "{url}"
verified_at = 2026-11-04
"""


def test_airports_load_from_their_own_sites():
    airports = {a.iata: a for a in curated.load().airports}
    assert set(airports) == set(curated.AIRPORT_DOMAINS)
    for a in airports.values():
        domain = curated.AIRPORT_DOMAINS[a.iata]
        assert all(domain in f.url for f in a.facts)
        assert [f.key for f in a.facts] == sorted((f.key for f in a.facts), key=curated.AIRPORT_KEYS.index)
    krk = {f.key: f for f in airports["KRK"].facts}
    assert "do 2 lat" in krk["family_security"].short


@pytest.mark.parametrize("key, url, error", [
    ("lounge", "https://www.airport.gdansk.pl/x", "unknown key 'lounge'"),
    ("stroller", "https://www.gdansk-lotnisko.info/x", "page on airport.gdansk.pl"),
    ("stroller", "https://airport.gdansk.pl.evil.com/x", "page on airport.gdansk.pl"),
    ("baby_food", "https://www.airport.gdansk.pl/x", "duplicate"),
])
def test_bad_airport_fact_is_rejected(tree, key, url, error):
    _append(tree / "airports" / "gdn.toml", AIRPORT_FACT.format(key=key, url=url))
    with pytest.raises(CuratedError, match=error):
        curated.load(tree)


def test_airport_file_name_must_match_code(tree):
    shutil.copy(tree / "airports" / "gdn.toml", tree / "airports" / "gda.toml")
    with pytest.raises(CuratedError, match="file name must be the airport code"):
        curated.load(tree)
