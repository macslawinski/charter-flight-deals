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

import json
import logging
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from ingest.config import SourceConfig
from ingest.http_client import Fetcher
from ingest.models import FlightOffer, ParseError

OPERATOR = "itaka"
BUNDLE_VERSION = 1

_LIST_LINE = re.compile(r'^[0-9a-f]+:(\{"flightsList":.*)$', re.MULTILINE)
_SPACES = r"\s\u00a0\u202f"  # regular, non-breaking, narrow no-break (pl-PL grouping)
_PRICE = re.compile(rf"^[{_SPACES}]*(\d{{1,3}}(?:[{_SPACES}]?\d{{3}})*(?:[.,]\d{{1,2}})?)"
                    rf"[{_SPACES}]*zł[{_SPACES}]*$")
_IATA = re.compile(r"^[A-Z]{3}$")
# Raw-bundle whitelist (see trim_offer).
_OFFER_KEYS = ("type", "currency", "pricePerPerson", "isApproximateSchedule")
_LEG_KEYS = ("flightNumber", "numberOfStops")
_POINT_KEYS = ("airportCode", "dateIso", "time")

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


def _trim_leg(leg: Any) -> Any:
    if not isinstance(leg, dict):
        return leg
    out: dict[str, Any] = {k: leg[k] for k in _LEG_KEYS if k in leg}
    for part in ("departure", "arrival"):
        p = leg.get(part)
        out[part] = {k: p[k] for k in _POINT_KEYS if k in p} if isinstance(p, dict) else p
    dep = leg.get("departure")
    info = dep.get("flightCarrierInfo") if isinstance(dep, dict) else None
    if isinstance(info, dict):  # later offers carry RSC "$ref" strings instead: not resolved
        out["carrier"] = info.get("name")
    luggage = leg.get("luggage")
    if isinstance(luggage, dict):
        out["luggage"] = luggage
    return out


def trim_offer(offer: Any) -> Any:
    """Keep only what parse() uses (+ carrier name and luggage for later analysis).

    A whitelist keeps the raw bundle small (~3k offers per run). Missing fields stay missing, so
    parse() still fails loudly on them.
    """
    if not isinstance(offer, dict):
        return offer
    out: dict[str, Any] = {k: offer[k] for k in _OFFER_KEYS if k in offer}
    for leg in ("departureFlight", "returnFlight"):
        if leg in offer:
            out[leg] = _trim_leg(offer[leg])
    return out


def crawl(client: Fetcher, source: SourceConfig, today: date) -> dict[str, Any]:
    """Fetch all listing pages for one run and return the raw bundle (JSON-serializable).

    - Unexpected payload shape: the error is recorded as a page and the crawl stops (no point
      fetching 150 pages of a changed layout); ``parse`` then fails loudly.
    - Fetch failure (request cap, 403, 4xx/5xx after retries, network): the crawl stops and the
      bundle is marked truncated, keeping every page fetched so far (saved raw and parsed).
    - The page count is re-read from every page: offers sell out during the ~15 min crawl.
    """
    max_pages = int(source.payload.get("max_pages", 220))
    pages: list[dict[str, Any]] = []
    pages_count: int | None = None
    rate_count: Any = None
    truncated = False
    fetch_error: str | None = None
    page = 1
    while True:
        try:
            resp = client.fetch(source, None, params=page_params(source, page))
        except (RuntimeError, httpx.HTTPError) as e:  # RequestCapReached, BlockedError, give-up
            log.error("itaka crawl stopped at page %d: %s", page, e)
            truncated, fetch_error = True, f"page {page}: {e}"
            break
        try:
            obj = extract_list(resp.text)
        except ParseError as e:
            pages.append({"page": page, "error": str(e)})
            log.error("itaka page %d: %s", page, e)
            break
        count = obj.get("pagesCount")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            pages.append({"page": page, "error": f"bad pagesCount {count!r}"})
            log.error("itaka page %d: bad pagesCount %r", page, count)
            break
        items = obj["flightsList"]
        pages.append({"page": page, "flightsList": [trim_offer(o) for o in items]})
        if pages_count is None:
            log.info("itaka: %s pages, %s offers", count, obj.get("rateCount"))
        elif count != pages_count:
            log.warning("itaka: pagesCount changed mid-crawl %s -> %s", pages_count, count)
        pages_count, rate_count = count, obj.get("rateCount")
        if not items or page >= count:
            break
        if page >= max_pages:
            log.error("itaka: max_pages=%d reached of %s pages", max_pages, count)
            truncated = True
            break
        page += 1

    return {
        "bundle_version": BUNDLE_VERSION,
        "operator": OPERATOR,
        "passengers": int(source.payload.get("adults", 1)),
        "fetched_for": today.isoformat(),
        "truncated": truncated,
        "fetch_error": fetch_error,
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
    digits = re.sub(f"[{_SPACES}]", "", m.group(1)).replace(",", ".")
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
    # Itaka dropped `currency` on 2026-11-26; the price regex still requires "zł".
    if o.get("currency", "PLN") != "PLN":
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
