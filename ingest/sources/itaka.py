"""Itaka charter flights (flight-only): crawling the listing pages and mapping to FlightOffers.

There is no JSON API (discovered 2026-11-04 on https://www.itaka.pl/bilety-lotnicze/). The listing
is a Next.js page; requested with header ``RSC: 1`` it returns a React Server Components payload:
one record per line, ``<hex id>:<data>``. One of those lines is plain JSON::

    3a:{"flightsList": [ ...20 offers... ], "pagesCount": 150, "rateCount": 2987}

Each offer has ``departureFlight`` / ``returnFlight`` legs (``departure.airportCode``,
``departure.dateIso``, ``flightNumber``, ``numberOfStops``, ``luggage``), ``pricePerPerson`` as a
formatted string ("1 050 zł", with non-breaking spaces) and ``currency``.

One run = all pages, sorted by departure date. Only the trimmed ``flightsList`` of each page goes
into the bundle (the full payload is ~700 KB of page layout per page).
"""

from __future__ import annotations

import copy
import json
import logging
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from ingest.config import SourceConfig
from ingest.http_client import RequestCapReached
from ingest.models import FlightOffer, ParseError
from ingest.sources.r_pl import Fetcher

OPERATOR = "itaka"
BUNDLE_VERSION = 1

_LIST_LINE = re.compile(r'^[0-9a-f]+:(\{"flightsList":.*)$', re.MULTILINE)
_PRICE = re.compile(r"^\s*(\d{1,3}(?:[\s  ]?\d{3})*(?:[.,]\d{1,2})?)\s*zł\s*$")
_IATA = re.compile(r"^[A-Z]{3}$")
_DROP = {"url", "badges"}

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- crawling


def page_params(source: SourceConfig, page: int) -> list[tuple[str, str]]:
    adults = int(source.payload.get("adults", 1))
    return [("flightType", "returnTicket"), ("participants[0][adults]", str(adults)),
            ("sortBy", "dateFromAsc"), ("page", str(page))]


def extract_list(text: str) -> dict[str, Any]:
    """Find the ``{"flightsList": ...}`` line in an RSC payload. Raises ParseError."""
    m = _LIST_LINE.search(text)
    if not m:
        raise ParseError(f"no flightsList line in RSC payload (starts {text[:120]!r})")
    try:
        obj = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        raise ParseError(f"flightsList line is not valid JSON: {e}") from e
    if not isinstance(obj, dict) or not isinstance(obj.get("flightsList"), list):
        raise ParseError("flightsList line: expected an object with a list")
    return obj


def trim_offer(offer: Any) -> Any:
    """Drop page-only fields; carrier info -> {"name": ...} (RSC "$ref" strings -> None)."""
    if not isinstance(offer, dict):
        return offer
    o = copy.deepcopy(offer)
    for k in _DROP:
        o.pop(k, None)
    for leg_key in ("departureFlight", "returnFlight"):
        leg = o.get(leg_key)
        if not isinstance(leg, dict):
            continue
        for part in (leg, leg.get("departure"), leg.get("arrival")):
            if isinstance(part, dict) and "flightCarrierInfo" in part:
                info = part["flightCarrierInfo"]
                part["flightCarrierInfo"] = {"name": info.get("name")} if isinstance(info, dict) \
                    else None
    return o


def crawl(client: Fetcher, source: SourceConfig, today: date) -> dict[str, Any]:
    """Fetch all listing pages for one run and return the raw bundle (JSON-serializable).

    If a page's payload has an unexpected shape, the error is recorded in the bundle and the
    crawl stops (no point fetching 150 pages of a changed layout); ``parse`` then fails loudly.
    """
    max_pages = int(source.payload.get("max_pages", 220))
    pages: list[dict[str, Any]] = []
    pages_count: int | None = None
    rate_count: int | None = None
    truncated = False
    page = 1
    while True:
        try:
            resp = client.fetch(source, None, params=page_params(source, page))
        except RequestCapReached as e:
            log.error("itaka crawl truncated at page %d: %s", page, e)
            truncated = True
            break
        try:
            obj = extract_list(resp.text)
        except ParseError as e:
            pages.append({"page": page, "error": str(e)})
            log.error("itaka page %d: %s", page, e)
            break
        pages.append({"page": page, "flightsList": [trim_offer(o) for o in obj["flightsList"]]})
        if pages_count is None:
            pages_count, rate_count = obj.get("pagesCount"), obj.get("rateCount")
            log.info("itaka: %s pages, %s offers", pages_count, rate_count)
        elif obj.get("pagesCount") != pages_count:
            log.warning("itaka: pagesCount changed mid-crawl %s -> %s", pages_count,
                        obj.get("pagesCount"))
        if not isinstance(pages_count, int) or page >= pages_count:
            break
        if page >= max_pages:
            log.error("itaka: max_pages=%d reached of %s pages", max_pages, pages_count)
            truncated = True
            break
        page += 1

    return {
        "bundle_version": BUNDLE_VERSION,
        "operator": OPERATOR,
        "passengers": int(source.payload.get("adults", 1)),
        "fetched_for": today.isoformat(),
        "truncated": truncated,
        "pages_count": pages_count,
        "rate_count": rate_count,
        "pages": pages,
    }


# --------------------------------------------------------------------------- parsing


def _req(obj: Any, key: str, path: str) -> Any:
    if not isinstance(obj, dict) or key not in obj or obj[key] is None:
        raise ParseError(f"missing required field {path}.{key}")
    return obj[key]


def _iata(obj: Any, path: str) -> str:
    code = _req(obj, "airportCode", path)
    if not isinstance(code, str) or not _IATA.match(code):
        raise ParseError(f"bad IATA code at {path}.airportCode: {code!r}")
    return code


def _date(obj: Any, path: str) -> date:
    value = _req(obj, "dateIso", path)
    try:
        return date.fromisoformat(str(value))
    except ValueError as e:
        raise ParseError(f"bad date at {path}.dateIso: {value!r}") from e


def parse_price(value: Any, path: str) -> Decimal:
    """'1 050 zł' (any space kind) -> Decimal('1050.00'). Anything else -> ParseError."""
    m = _PRICE.match(value) if isinstance(value, str) else None
    if not m:
        raise ParseError(f"bad price at {path}: {value!r}")
    digits = re.sub(r"[\s  ]", "", m.group(1)).replace(",", ".")
    try:
        price = Decimal(digits).quantize(Decimal("0.01"))
    except InvalidOperation as e:
        raise ParseError(f"bad price at {path}: {value!r}") from e
    if price <= 0:
        raise ParseError(f"non-positive price at {path}: {value!r}")
    return price


def parse(data: Any, observed_at: datetime) -> list[FlightOffer]:
    """Map one raw bundle to round-trip FlightOffers. Raise ParseError on unexpected shape."""
    if not isinstance(data, dict) or data.get("bundle_version") != BUNDLE_VERSION \
            or data.get("operator") != OPERATOR:
        got = list(data)[:8] if isinstance(data, dict) else type(data).__name__
        raise ParseError(f"not an itaka bundle v{BUNDLE_VERSION} (got {got})")
    if data.get("passengers") != 1:
        raise ParseError(f"expected a 1-adult crawl, got passengers={data.get('passengers')!r}")
    pages = _req(data, "pages", "$")
    if not isinstance(pages, list) or not pages:
        raise ParseError("$.pages: expected a non-empty list")

    offers: list[FlightOffer] = []
    open_jaw = 0
    for pi, page in enumerate(pages):
        ppath = f"$.pages[{pi}]"
        if not isinstance(page, dict):
            raise ParseError(f"{ppath}: expected an object")
        if "error" in page:
            raise ParseError(f"{ppath} (page {page.get('page')}): {page['error']}")
        items = _req(page, "flightsList", ppath)
        if not isinstance(items, list):
            raise ParseError(f"{ppath}.flightsList: expected a list")
        for oi, o in enumerate(items):
            offer = _offer(o, f"{ppath}.flightsList[{oi}]", observed_at)
            if offer is None:
                open_jaw += 1
            else:
                offers.append(offer)
    if open_jaw:
        log.info("itaka: %d open-jaw offers skipped", open_jaw)

    expected = data.get("rate_count")
    if isinstance(expected, int) and not data.get("truncated") and expected > 0:
        keys = {o.flight_key for o in offers}
        if abs(len(keys) + open_jaw - expected) > max(20, expected // 20):
            log.warning("itaka: %d distinct offers parsed, site reported %d", len(keys), expected)
    return offers


def _offer(o: Any, path: str, observed_at: datetime) -> FlightOffer | None:
    """One offer -> FlightOffer; None for an open-jaw itinerary (skipped, counted by caller)."""
    if not isinstance(o, dict):
        raise ParseError(f"{path}: expected an object")
    if o.get("type") != "returnTicket":
        raise ParseError(f"{path}.type: expected 'returnTicket', got {o.get('type')!r}")
    if o.get("currency") != "PLN":
        raise ParseError(f"{path}.currency: expected 'PLN', got {o.get('currency')!r}")
    out_leg = _req(o, "departureFlight", path)
    ret_leg = _req(o, "returnFlight", path)
    op, rp = f"{path}.departureFlight", f"{path}.returnFlight"
    origin = _iata(_req(out_leg, "departure", op), f"{op}.departure")
    dest = _iata(_req(out_leg, "arrival", op), f"{op}.arrival")
    ret_from = _iata(_req(ret_leg, "departure", rp), f"{rp}.departure")
    out_date = _date(_req(out_leg, "departure", op), f"{op}.departure")
    ret_date = _date(_req(ret_leg, "departure", rp), f"{rp}.departure")
    ret_to = _iata(_req(ret_leg, "arrival", rp), f"{rp}.arrival")
    if ret_from != dest or ret_to != origin:
        # Open-jaw: valid offer, but it doesn't fit one origin/destination segment. Skip it.
        return None
    if ret_date < out_date:
        raise ParseError(f"{path}: return {ret_date} before outbound {out_date}")
    price = parse_price(_req(o, "pricePerPerson", path), f"{path}.pricePerPerson")
    out_no, ret_no = out_leg.get("flightNumber"), ret_leg.get("flightNumber")
    return FlightOffer(
        operator=OPERATOR,
        origin_iata=origin,
        dest_iata=dest,
        outbound_date=out_date,
        return_date=ret_date,
        price_pln=price,
        observed_at=observed_at,
        flight_no=f"{out_no}/{ret_no}" if out_no and ret_no else None,
    )
