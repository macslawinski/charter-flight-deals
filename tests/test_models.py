from datetime import UTC, date, datetime
from decimal import Decimal

from ingest.models import FlightOffer
from ingest.store import dedupe

T0 = datetime(2026, 11, 4, 8, 0, tzinfo=UTC)
T1 = datetime(2026, 11, 4, 9, 0, tzinfo=UTC)


def offer(price: str, observed_at: datetime = T0, return_date: date | None = date(2027, 1, 17),
          flight_no: str | None = None) -> FlightOffer:
    return FlightOffer(
        operator="r_pl",
        origin_iata="WAW",
        dest_iata="HRG",
        outbound_date=date(2027, 1, 10),
        return_date=return_date,
        price_pln=Decimal(price),
        observed_at=observed_at,
        flight_no=flight_no,
    )


def test_flight_key_round_trip():
    assert offer("1249").flight_key == "r_pl|WAW|HRG|2027-01-10|2027-01-17"


def test_flight_key_one_way_and_flight_no():
    assert offer("999", return_date=None, flight_no="ENT123").flight_key == (
        "r_pl|WAW|HRG|2027-01-10||ENT123"
    )


def test_stay_days():
    assert offer("1249").stay_days == 7
    assert offer("1249", return_date=None).stay_days is None


def test_dedupe_keeps_cheapest():
    result = dedupe([offer("1500"), offer("1249"), offer("1300")])
    assert [o.price_pln for o in result] == [Decimal(1249)]


def test_dedupe_tie_prefers_latest_observation():
    result = dedupe([offer("1249", T0), offer("1249", T1)])
    assert result[0].observed_at == T1
