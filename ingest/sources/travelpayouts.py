"""Travelpayouts / Aviasales Data API: regular-airline reference fares (display-only).

Official API (free affiliate token). `prices_for_dates` returns the cheapest prices Aviasales users
found in the last days for a route and month; one request per Segment, direct flights only.
Response: {"success": true, "currency": "pln", "data": [{departure_at, return_at, airline, price,
transfers, return_transfers, origin_airport, destination_airport, flight_number, link, ...}]}.
Times carry the airport's UTC offset, so .date() is the local departure date.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import parse_qs, urlsplit

from ingest.config import SourceConfig
from ingest.http_client import PoliteClient, RequestCapReached
from ingest.models import MarketFare, ParseError, Segment

SOURCE = "travelpayouts"
log = logging.getLogger(__name__)


def request_params(seg: Segment, limit: int) -> list[tuple[str, str]]:
    return [
        ("origin", seg.origin_iata), ("destination", seg.dest_iata),
        ("departure_at", seg.dep_month.strftime("%Y-%m")),
        ("one_way", "false"), ("direct", "true"), ("currency", "pln"),
        ("sorting", "price"), ("limit", str(limit)),
    ]


def crawl(client: PoliteClient, source: SourceConfig, segments: list[Segment]) -> dict[str, Any]:
    """Fetch one response per segment. Returns a bundle {"responses": [...], "truncated": bool}."""
    limit = int(source.payload.get("limit", 1000))
    bundle: dict[str, Any] = {"source": SOURCE, "responses": [], "truncated": False}
    for seg in segments:
        try:
            resp = client.fetch(source, None, params=request_params(seg, limit))
        except RequestCapReached:
            bundle["truncated"] = True
            break
        bundle["responses"].append({
            "origin": seg.origin_iata, "destination": seg.dest_iata,
            "month": seg.dep_month.strftime("%Y-%m"), "body": resp.json(),
        })
    return bundle


def parse(bundle: Any) -> dict[Segment, list[MarketFare]]:
    """Map a crawl bundle to fares per segment (segments with no fares map to []).

    Raises ParseError on any unexpected shape: nothing is written from a bundle that fails.
    """
    if not isinstance(bundle, dict) or not isinstance(bundle.get("responses"), list):
        raise ParseError("bundle: expected {'responses': [...]}")
    out: dict[Segment, list[MarketFare]] = {}
    for i, r in enumerate(bundle["responses"]):
        where = f"responses[{i}]"
        try:
            seg = Segment(r["origin"], r["destination"],
                          datetime.strptime(r["month"], "%Y-%m").date())
            body = r["body"]
        except (KeyError, TypeError, ValueError) as e:
            raise ParseError(f"{where}: bad segment header: {e!r}") from e
        if not isinstance(body, dict) or body.get("success") is not True:
            raise ParseError(f"{where}: success != true: {str(body)[:200]}")
        if body.get("currency") != "pln":
            raise ParseError(f"{where}: currency {body.get('currency')!r}, expected 'pln'")
        data = body.get("data")
        if not isinstance(data, list):
            raise ParseError(f"{where}: 'data' is not a list")
        best: dict[tuple[str, str, str, date, date, str], MarketFare] = {}
        for j, item in enumerate(data):
            fare = _fare(seg, item, f"{where}.data[{j}]")
            if fare is None:
                continue
            cur = best.get(fare.key)
            if cur is None or fare.price_pln < cur.price_pln:
                best[fare.key] = fare
        out[seg] = sorted(best.values(), key=lambda f: (f.price_pln, f.outbound_date))
    return out


def _fare(seg: Segment, item: Any, where: str) -> MarketFare | None:
    if not isinstance(item, dict):
        raise ParseError(f"{where}: expected an object")
    try:
        outbound = datetime.fromisoformat(item["departure_at"]).date()
        ret = datetime.fromisoformat(item["return_at"]).date()
        price = item["price"]
        transfers, return_transfers = item["transfers"], item["return_transfers"]
        airline = item["airline"]
    except (KeyError, TypeError, ValueError) as e:
        raise ParseError(f"{where}: missing/invalid field: {e!r}") from e
    if isinstance(price, bool) or not isinstance(price, int | float) or price <= 0:
        raise ParseError(f"{where}: bad price {price!r}")
    if not all(isinstance(t, int) and t >= 0 for t in (transfers, return_transfers)):
        raise ParseError(f"{where}: bad transfers {transfers!r}/{return_transfers!r}")
    if not isinstance(airline, str) or len(airline) != 2:
        raise ParseError(f"{where}: bad airline {airline!r}")
    if ret < outbound:
        raise ParseError(f"{where}: return {ret} before departure {outbound}")
    if outbound.replace(day=1) != seg.dep_month:
        # Valid record, just not for this segment (e.g. timezone edge); skip, don't fail the run.
        log.warning("%s: departure %s outside requested month %s, skipped",
                    where, outbound, seg.dep_month)
        return None
    link = item.get("link") if isinstance(item.get("link"), str) else None
    flight_no = item.get("flight_number")
    return MarketFare(
        source=SOURCE,
        origin_iata=seg.origin_iata,
        dest_iata=seg.dest_iata,
        outbound_date=outbound,
        return_date=ret,
        airline=airline.upper(),
        transfers=transfers,
        return_transfers=return_transfers,
        price_pln=Decimal(str(price)).quantize(Decimal("0.01")),
        origin_airport=_iata(item.get("origin_airport")),
        dest_airport=_iata(item.get("destination_airport")),
        flight_no=str(flight_no) if flight_no not in (None, "") else None,
        found_date=_search_date(link),
        link=link,
    )


def _iata(v: Any) -> str | None:
    return v.upper() if isinstance(v, str) and len(v) == 3 else None


def _search_date(link: str | None) -> date | None:
    """`search_date=DDMMYYYY` in the link = when the price was found. Optional, best effort."""
    if not link:
        return None
    raw = parse_qs(urlsplit(link).query).get("search_date", [""])[0]
    try:
        return datetime.strptime(raw, "%d%m%Y").date()
    except ValueError:
        return None
