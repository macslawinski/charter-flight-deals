import copy
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest

from ingest.config import SourceConfig
from ingest.http_client import RequestCapReached
from ingest.models import ParseError
from ingest.sources import r_pl

FIXTURE = Path(__file__).parent / "fixtures" / "r_pl_sample.json"
T0 = datetime(2026, 11, 4, 8, 0, tzinfo=UTC)


@pytest.fixture
def bundle() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_parse_maps_round_trip_offers(bundle):
    offers = r_pl.parse(bundle, T0)
    assert len(offers) == 6
    first = next(o for o in offers if o.return_date == date(2026, 11, 21))
    assert first.operator == "r_pl"
    assert (first.origin_iata, first.dest_iata) == ("WAW", "AYT")
    assert first.outbound_date == date(2026, 11, 14)
    assert first.stay_days == 7
    assert first.flight_no == "ENT4001/ENT4002"
    assert first.observed_at == T0
    assert first.flight_key == "r_pl|WAW|AYT|2026-11-14|2026-11-21|ENT4001/ENT4002"


def test_price_is_round_trip_total_per_person(bundle):
    # CenaRazem 1998 for 2 passengers -> 999 per person (verified against a 1-passenger query).
    offers = {o.return_date: o for o in r_pl.parse(bundle, T0) if o.origin_iata == "WAW"}
    assert offers[date(2026, 11, 21)].price_pln == Decimal("999.00")
    bundle["passengers"] = 1
    offers = {o.return_date: o for o in r_pl.parse(bundle, T0) if o.origin_iata == "WAW"}
    assert offers[date(2026, 11, 21)].price_pln == Decimal("1998.00")


def test_multiple_origins_are_kept_apart(bundle):
    origins = {o.origin_iata for o in r_pl.parse(bundle, T0)}
    assert origins == {"WAW", "KTW"}


def test_flight_keys_unique_within_fixture(bundle):
    keys = [o.flight_key for o in r_pl.parse(bundle, T0)]
    assert len(keys) == len(set(keys))


def test_destination_without_inbound_yields_nothing(bundle):
    bundle["inbound"] = {}
    assert r_pl.parse(bundle, T0) == []


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda b: b.pop("bundle_version"), "not an r_pl bundle"),
        (lambda b: b["inbound"]["AYT"][0]["Bilety"][0].pop("CenaRazem"), "CenaRazem"),
        (lambda b: b["inbound"]["AYT"][0]["Bilety"][0].update(CenaRazem=0), "bad price"),
        (lambda b: b["inbound"]["AYT"][0]["Bilety"][0].update(BindId="1_2"), "no matching outbound"),
        (lambda b: b["inbound"]["AYT"][0].update(Data="21.11.2026"), "bad date"),
        (lambda b: b["outbound"]["AYT"][0]["Bilety"][0]["Wylot"].update(Iata="Warszawa"), "bad IATA"),
        (lambda b: b["outbound"]["AYT"][0]["Bilety"][0]["Przylot"].update(Iata="HRG"), "expected AYT"),
        (lambda b: b["outbound"].update(AYT={"Data": []}), "expected list"),
    ],
)
def test_malformed_input_raises_parse_error(bundle, mutate, message):
    broken = copy.deepcopy(bundle)
    mutate(broken)
    with pytest.raises(ParseError, match=message):
        r_pl.parse(broken, T0)


class FakeClient:
    """Serves the fixture's responses and records requests."""

    def __init__(self, bundle: dict[str, Any]) -> None:
        self.b = bundle
        self.calls: list[tuple[str, list[tuple[str, str]]]] = []

    def fetch(self, source, payload=None, *, path="", params=None):
        params = params or []
        self.calls.append((path, params))
        p = dict(params)
        if path == r_pl.PATH_DESTINATIONS:
            body: Any = {"Destynacje": [{"Klucz": "AYT"}]}
        elif path == r_pl.PATH_OUTBOUND:
            body = self.b["outbound"][p["iataDokad"]]
        else:
            ids = {v for k, v in params if k == "pakietId"}
            body = [
                dict(g, Bilety=[t for t in g["Bilety"] if t["BindId"] in ids])
                for g in self.b["inbound"]["AYT"]
            ]
            body = [g for g in body if g["Bilety"]]
        return httpx.Response(200, json=body)


def test_crawl_builds_parseable_bundle_in_batches(bundle):
    source = SourceConfig(
        name="r_pl", operator="r_pl", enabled=True, method="GET", url="https://example.test",
        payload={"birth_dates": ["1990-01-01", "1990-01-01"], "horizon_days": 30,
                 "pakiet_batch_size": 4},
    )
    client = FakeClient(bundle)
    crawled = r_pl.crawl(client, source, date(2026, 11, 4))

    paths = [c[0] for c in client.calls]
    n_pakiety = len({p for g in bundle["outbound"]["AYT"] for t in g["Bilety"] for p in t["Pakiety"]})
    assert paths.count(r_pl.PATH_OUTBOUND) == 1
    assert paths.count(r_pl.PATH_INBOUND) == -(-n_pakiety // 4)
    outbound_params = dict(client.calls[1][1])
    assert outbound_params["dataMax"] == "2026-12-04"
    assert crawled["passengers"] == 2
    assert crawled["truncated"] is False
    assert len(r_pl.parse(crawled, T0)) == len(r_pl.parse(bundle, T0))


def test_crawl_stops_at_request_cap_and_drops_incomplete_destination(bundle):
    source = SourceConfig(
        name="r_pl", operator="r_pl", enabled=True, method="GET", url="https://example.test",
        payload={"birth_dates": ["1990-01-01"], "pakiet_batch_size": 1},
    )

    class CappedClient(FakeClient):
        def fetch(self, source, payload=None, *, path="", params=None):
            if len(self.calls) >= 3:  # destinations + outbound + 1 inbound batch, then cap
                raise RequestCapReached("cap")
            return super().fetch(source, payload, path=path, params=params)

    crawled = r_pl.crawl(CappedClient(bundle), source, date(2026, 11, 4))
    assert crawled["truncated"] is True
    assert crawled["outbound"] == {} and crawled["inbound"] == {}
    assert r_pl.parse(crawled, T0) == []
