"""Itaka RSC payload -> FlightOffer mapping, on saved real pages (trimmed), plus crawl paging."""

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
from ingest.sources import itaka

SAMPLE: dict[str, Any] = json.loads(
    (Path(__file__).parent / "fixtures" / "itaka_sample.json").read_text(encoding="utf-8")
)
NOW = datetime(2026, 11, 4, 12, tzinfo=UTC)
SOURCE = SourceConfig(name="itaka", operator="itaka", enabled=True, method="GET",
                      url="https://example.test/", payload={"adults": 1, "max_pages": 10})


def test_maps_sample_offers():
    offers = itaka.parse(SAMPLE, NOW)
    assert len(offers) == 7
    o = offers[0]
    assert (o.operator, o.origin_iata, o.dest_iata) == ("itaka", "KTW", "MBA")
    assert (o.outbound_date, o.return_date, o.stay_days) == (date(2026, 11, 5), date(2026, 11, 12), 7)
    assert o.price_pln == Decimal("2590.00")
    assert o.flight_no == "ENT5401/ENT5402"
    assert o.flight_key == "itaka|KTW|MBA|2026-11-05|2026-11-12|ENT5401/ENT5402"
    assert {x.origin_iata for x in offers} == {"KTW", "WAW"}


@pytest.mark.parametrize("text, value", [
    ("2 590 zł", "2590.00"), ("996 zł", "996.00"), ("1 249,50 zł", "1249.50"),
    ("1 050 zł", "1050.00"), ("12 345 zł", "12345.00"),
])
def test_parse_price(text, value):
    assert itaka.parse_price(text, "$") == Decimal(value)


@pytest.mark.parametrize("bad", ["1050 EUR", "", "zł", "0 zł", "1 05 zł", 1050, None, "od 999 zł"])
def test_parse_price_rejects(bad):
    with pytest.raises(ParseError):
        itaka.parse_price(bad, "$")


def rsc(obj: dict[str, Any]) -> str:
    return '0:["$","html"]\n1a:{"layout":true}\n3f:' + json.dumps(obj) + '\n40:"$Sreact"\n'


def test_extract_list_finds_the_json_line():
    obj = itaka.extract_list(rsc({"flightsList": [{"a": 1}], "pagesCount": 3, "rateCount": 50}))
    assert obj["pagesCount"] == 3 and obj["flightsList"] == [{"a": 1}]


@pytest.mark.parametrize("text", ['0:["$","html"]\n', '3f:{"flightsList":[{"a":1]\n',
                                  '3f:{"flightsList":{"a":1}}\n'])
def test_extract_list_fails_loudly(text):
    with pytest.raises(ParseError):
        itaka.extract_list(text)


def test_trim_offer_drops_page_fields_and_carrier_details():
    o = {"url": "/x?y", "badges": [1], "pricePerPerson": "1 zł",
         "departureFlight": {"flightCarrierInfo": "$52:ref",
                             "departure": {"flightCarrierInfo": {"name": "Enter Air", "phone": "1"}},
                             "arrival": {"flightCarrierInfo": "$52:ref"}}}
    t = itaka.trim_offer(o)
    assert "url" not in t and "badges" not in t and t["pricePerPerson"] == "1 zł"
    leg = t["departureFlight"]
    assert leg["flightCarrierInfo"] is None and leg["arrival"]["flightCarrierInfo"] is None
    assert leg["departure"]["flightCarrierInfo"] == {"name": "Enter Air"}
    assert o["departureFlight"]["departure"]["flightCarrierInfo"]["phone"] == "1"  # not mutated


def test_open_jaw_offer_is_skipped():
    b = copy.deepcopy(SAMPLE)
    b["pages"][0]["flightsList"][0]["returnFlight"]["arrival"]["airportCode"] = "WAW"
    assert len(itaka.parse(b, NOW)) == 6


def first(b: dict[str, Any]) -> dict[str, Any]:
    return b["pages"][0]["flightsList"][0]


@pytest.mark.parametrize("mutate, msg", [
    (lambda b: first(b).update(currency="EUR"), "currency"),
    (lambda b: first(b).update(type="oneWayTicket"), "type"),
    (lambda b: first(b).pop("returnFlight"), "returnFlight"),
    (lambda b: first(b).update(pricePerPerson="?"), "bad price"),
    (lambda b: first(b)["departureFlight"]["departure"].update(airportCode="Katowice"), "IATA"),
    (lambda b: first(b)["departureFlight"]["departure"].update(dateIso="5 lis"), "bad date"),
    (lambda b: first(b)["returnFlight"]["departure"].update(dateIso="2026-11-01"), "before"),
    (lambda b: b["pages"].append({"page": 3, "error": "no flightsList line"}), "page 3"),
    (lambda b: b.update(passengers=2), "1-adult"),
    (lambda b: b.update(bundle_version=99), "not an itaka bundle"),
])
def test_unexpected_shape_fails_loudly(mutate, msg):
    b = copy.deepcopy(SAMPLE)
    mutate(b)
    with pytest.raises(ParseError, match=msg):
        itaka.parse(b, NOW)


class FakeClient:
    """Serves `pages` RSC payloads (a page is a list of offers or a raw string)."""

    def __init__(self, pages: list[Any], cap: int = 100) -> None:
        self.pages, self.cap = pages, cap
        self.calls: list[dict[str, str]] = []

    def fetch(self, source, payload=None, *, path="", params=None):
        if len(self.calls) >= self.cap:
            raise RequestCapReached("cap")
        p = dict(params or [])
        self.calls.append(p)
        page = self.pages[int(p["page"]) - 1]
        if isinstance(page, str):
            return httpx.Response(200, text=page)
        obj = {"flightsList": page, "pagesCount": len(self.pages), "rateCount": 7}
        return httpx.Response(200, text=rsc(obj))


def sample_pages() -> list[list[Any]]:
    return [p["flightsList"] for p in SAMPLE["pages"]]


def test_crawl_fetches_all_pages_sorted_by_date():
    client = FakeClient(sample_pages())
    bundle = itaka.crawl(client, SOURCE, date(2026, 11, 4))
    assert [c["page"] for c in client.calls] == ["1", "2"]
    assert all(c["sortBy"] == "dateFromAsc" and c["participants[0][adults]"] == "1"
               for c in client.calls)
    assert bundle["truncated"] is False and bundle["pages_count"] == 2
    assert len(itaka.parse(bundle, NOW)) == 7


def test_crawl_stops_on_changed_layout_and_parse_fails():
    client = FakeClient([sample_pages()[0], "0:[\"$\",\"html\"]\n", sample_pages()[1]])
    bundle = itaka.crawl(client, SOURCE, date(2026, 11, 4))
    assert len(client.calls) == 2  # did not continue to page 3
    with pytest.raises(ParseError, match="page 2"):
        itaka.parse(bundle, NOW)


def test_crawl_marks_truncation_at_request_cap():
    bundle = itaka.crawl(FakeClient(sample_pages(), cap=1), SOURCE, date(2026, 11, 4))
    assert bundle["truncated"] is True and len(bundle["pages"]) == 1
    assert len(itaka.parse(bundle, NOW)) == 5
