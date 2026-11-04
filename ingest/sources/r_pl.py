"""r.pl (Rainbow Tours): request building and JSON -> FlightOffer mapping.

The endpoint is undocumented; fill this in after discovering it in the browser network tab.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ingest.config import SourceConfig
from ingest.models import FlightOffer

OPERATOR = "r_pl"


def build_requests(source: SourceConfig) -> list[dict[str, Any]]:
    """Return the request payloads to send in one run (e.g. one per origin airport / month)."""
    raise NotImplementedError("r.pl endpoint not discovered yet")


def parse(data: Any, observed_at: datetime) -> list[FlightOffer]:
    """Map one raw JSON response to FlightOffers. Raise ParseError on unexpected shape."""
    raise NotImplementedError("r.pl response mapping not written yet")
