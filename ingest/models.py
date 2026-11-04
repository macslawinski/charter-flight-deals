"""Normalized domain objects shared by all sources."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class FlightOffer:
    """One flight-only offer as observed at `observed_at`. Price is per person, in PLN."""

    operator: str
    origin_iata: str
    dest_iata: str
    outbound_date: date
    return_date: date | None
    price_pln: Decimal
    observed_at: datetime
    flight_no: str | None = None
    seats_left: int | None = None

    @property
    def stay_days(self) -> int | None:
        if self.return_date is None:
            return None
        return (self.return_date - self.outbound_date).days

    @property
    def flight_key(self) -> str:
        parts = [
            self.operator,
            self.origin_iata,
            self.dest_iata,
            self.outbound_date.isoformat(),
            self.return_date.isoformat() if self.return_date else "",
        ]
        if self.flight_no:
            parts.append(self.flight_no)
        return "|".join(parts)


@dataclass(frozen=True, slots=True, order=True)
class Segment:
    """Origin + destination + departure month (first day of the month)."""

    origin_iata: str
    dest_iata: str
    dep_month: date


@dataclass(frozen=True, slots=True)
class MarketFare:
    """A regular-airline round-trip reference fare (display-only). Per person, PLN, no bag.

    origin_iata/dest_iata are the codes we asked for; *_airport are the actual airports.
    """

    source: str
    origin_iata: str
    dest_iata: str
    outbound_date: date
    return_date: date
    airline: str
    transfers: int
    return_transfers: int
    price_pln: Decimal
    origin_airport: str | None = None
    dest_airport: str | None = None
    flight_no: str | None = None
    found_date: date | None = None
    link: str | None = None

    @property
    def key(self) -> tuple[str, str, str, date, date, str]:
        return (self.source, self.origin_iata, self.dest_iata, self.outbound_date,
                self.return_date, self.airline)


class ParseError(ValueError):
    """Raised when a source response does not match the expected shape. Never swallow silently."""
