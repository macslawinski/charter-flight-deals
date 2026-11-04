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


class ParseError(ValueError):
    """Raised when a source response does not match the expected shape. Never swallow silently."""
