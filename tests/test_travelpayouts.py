"""Travelpayouts response -> MarketFare mapping, on a saved real response (trimmed)."""

import copy
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ingest.models import ParseError, Segment
from ingest.sources import travelpayouts

SAMPLE = json.loads(
    (Path(__file__).parent / "fixtures" / "travelpayouts_sample.json").read_text(encoding="utf-8")
)
TFS = Segment("WAW", "TFS", date(2026, 12, 1))
HRG = Segment("WAW", "HRG", date(2026, 12, 1))
NBE = Segment("WAW", "NBE", date(2027, 5, 1))


def test_maps_sample_per_segment():
    parsed = travelpayouts.parse(SAMPLE)
    assert set(parsed) == {TFS, HRG, NBE}
    assert parsed[NBE] == []  # checked, nothing found: still reported
    assert [f.price_pln for f in parsed[TFS]] == [Decimal("646.00"), Decimal("649.00"),
                                                  Decimal("659.00"), Decimal("684.00")]
    f = parsed[TFS][0]
    assert (f.origin_iata, f.dest_iata) == ("WAW", "TFS")       # what we asked for
    assert (f.origin_airport, f.dest_airport) == ("WMI", "TFS")  # where it really flies
    assert (f.outbound_date, f.return_date) == (date(2026, 12, 4), date(2026, 12, 15))
    assert (f.airline, f.transfers, f.return_transfers) == ("FR", 0, 0)
    assert f.found_date == date(2026, 11, 4)
    assert f.link is not None and f.link.startswith("/search/")


def test_local_dates_follow_airport_offset():
    # 22:05 +02:00 in Hurghada is still 15 Dec locally (20:05 UTC).
    hrg = travelpayouts.parse(SAMPLE)[HRG]
    assert (hrg[0].outbound_date, hrg[0].return_date) == (date(2026, 12, 10), date(2026, 12, 15))


def test_duplicate_fare_keeps_cheapest():
    b = copy.deepcopy(SAMPLE)
    data = b["responses"][0]["body"]["data"]
    dup = dict(data[0], price=600, origin_airport="WAW")
    data.append(dup)
    tfs = travelpayouts.parse(b)[TFS]
    assert len(tfs) == 4
    assert tfs[0].price_pln == Decimal("600.00") and tfs[0].origin_airport == "WAW"


def test_fare_outside_requested_month_is_skipped():
    b = copy.deepcopy(SAMPLE)
    b["responses"][0]["body"]["data"][0]["departure_at"] = "2027-01-02T10:00:00+01:00"
    b["responses"][0]["body"]["data"][0]["return_at"] = "2027-01-09T10:00:00Z"
    assert len(travelpayouts.parse(b)[TFS]) == 3


@pytest.mark.parametrize("mutate, msg", [
    (lambda b: b["responses"][0]["body"].update(currency="rub"), "currency"),
    (lambda b: b["responses"][0]["body"].update(success=False), "success"),
    (lambda b: b["responses"][0]["body"].update(data={"x": 1}), "not a list"),
    (lambda b: b["responses"][0]["body"]["data"][0].pop("price"), "price"),
    (lambda b: b["responses"][0]["body"]["data"][0].update(price="646"), "bad price"),
    (lambda b: b["responses"][0]["body"]["data"][0].update(return_at=None), "invalid field"),
    (lambda b: b["responses"][0]["body"]["data"][0].update(transfers=-1), "transfers"),
    (lambda b: b["responses"][0].pop("month"), "segment header"),
])
def test_unexpected_shape_fails_loudly(mutate, msg):
    b = copy.deepcopy(SAMPLE)
    mutate(b)
    with pytest.raises(ParseError, match=msg):
        travelpayouts.parse(b)


def test_request_params_ask_for_direct_round_trips_in_pln():
    p = dict(travelpayouts.request_params(TFS, 1000))
    assert p == {"origin": "WAW", "destination": "TFS", "departure_at": "2026-12",
                 "one_way": "false", "direct": "true", "currency": "pln", "sorting": "price",
                 "limit": "1000"}
