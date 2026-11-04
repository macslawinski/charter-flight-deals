"""r.pl (Rainbow Tours) charter flights: crawling the JSON API and mapping it to FlightOffers.

The API is undocumented (discovered 2026-11-04 from https://r.pl/bilety-czarterowe). One run:

1. ``wyszukiwanie/v4.1/wyszukaj`` lists destinations (``Destynacje[].Klucz`` = IATA).
2. ``destynacja/v4.1/wyszukaj-wylot`` per destination lists outbound legs from all Polish origins,
   grouped by date. Each ticket lists ``Pakiety``: ids of outbound+return combinations.
3. ``destynacja/v4.1/wyszukaj-przylot`` for a batch of pakiet ids lists the matching return legs.
   ``Bilety[].BindId`` points back to the outbound pakiet and ``CenaRazem`` is the round-trip
   total for all passengers. (Leg ``Cena`` values are not additive and must not be used.)

A run's responses are combined into one *bundle* (see ``crawl``), saved raw and parsed by
``parse``. The bundle is the unit for raw storage, fixtures and ``--from-file``.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from ingest.config import SourceConfig
from ingest.http_client import Fetcher, RequestCapReached
from ingest.models import FlightOffer, ParseError

OPERATOR = "r_pl"
BUNDLE_VERSION = 1

PATH_DESTINATIONS = "wyszukiwanie/v4.1/wyszukaj"
PATH_OUTBOUND = "destynacja/v4.1/wyszukaj-wylot"
PATH_INBOUND = "destynacja/v4.1/wyszukaj-przylot"

log = logging.getLogger(__name__)


# --------------------------------------------------------------------------- crawling


def _birth_params(source: SourceConfig) -> list[tuple[str, str]]:
    births = source.payload.get("birth_dates") or []
    if not births:
        raise ValueError("sources.r_pl.payload.birth_dates must list at least one passenger")
    return [("dataUrodzenia", str(b)) for b in births]


def _batched(items: list[str], size: int) -> Iterator[list[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def crawl(client: Fetcher, source: SourceConfig, today: date) -> dict[str, Any]:
    """Fetch everything for one run and return the raw bundle (JSON-serializable)."""
    births = _birth_params(source)
    horizon = int(source.payload.get("horizon_days", 365))
    batch_size = int(source.payload.get("pakiet_batch_size", 200))
    dmin, dmax = today.isoformat(), (today + timedelta(days=horizon)).isoformat()

    destinations = client.fetch(
        source,
        path=PATH_DESTINATIONS,
        params=[("oneWay", "false"), *births, ("sortowanie", "cena")],
    ).json()
    iatas = [_req(d, "Klucz", f"$.Destynacje[{i}]") for i, d in
             enumerate(_req(destinations, "Destynacje", "$"))]

    outbound: dict[str, Any] = {}
    inbound: dict[str, list[Any]] = {}
    truncated = False
    try:
        for iata in iatas:
            _crawl_destination(client, source, iata, births, dmin, dmax, batch_size,
                               outbound, inbound)
    except RequestCapReached as e:
        # Keep what we have (complete destinations only) and flag the bundle; never retry past the cap.
        log.error("r_pl crawl truncated: %s (%d/%d destinations)", e, len(inbound), len(iatas))
        truncated = True
        for iata in set(outbound) - set(inbound):
            del outbound[iata]

    return {
        "bundle_version": BUNDLE_VERSION,
        "operator": OPERATOR,
        "passengers": len(births),
        "fetched_for": today.isoformat(),
        "truncated": truncated,
        "destinations": destinations,
        "outbound": outbound,
        "inbound": inbound,
    }


def _crawl_destination(
    client: Fetcher,
    source: SourceConfig,
    iata: str,
    births: list[tuple[str, str]],
    dmin: str,
    dmax: str,
    batch_size: int,
    outbound: dict[str, Any],
    inbound: dict[str, list[Any]],
) -> None:
    """Fetch outbound + all return legs for one destination; store only when complete."""
    out = client.fetch(
        source,
        path=PATH_OUTBOUND,
        params=[*births, ("iataDokad", iata), ("wybranaData", dmin), ("dataMin", dmin),
                ("dataMax", dmax), ("oneWay", "false")],
    ).json()
    _list(out, f"{PATH_OUTBOUND} response for {iata}")
    outbound[iata] = out
    pakiety = sorted({p for g in out for t in g.get("Bilety") or [] for p in t.get("Pakiety") or []})
    returns: list[Any] = []
    for batch in _batched(pakiety, batch_size):
        resp = client.fetch(
            source, path=PATH_INBOUND, params=[*[("pakietId", p) for p in batch], *births]
        )
        returns.extend(_list(resp.json(), f"{PATH_INBOUND} response for {iata}"))
    inbound[iata] = returns
    log.info("r_pl %s: %d outbound dates, %d pakiety", iata, len(out), len(pakiety))


# --------------------------------------------------------------------------- parsing


def _req(obj: Any, key: str, path: str) -> Any:
    if not isinstance(obj, dict) or key not in obj or obj[key] is None:
        raise ParseError(f"missing required field {path}.{key}")
    return obj[key]


def _list(obj: Any, path: str) -> list[Any]:
    if not isinstance(obj, list):
        raise ParseError(f"expected list at {path}, got {type(obj).__name__}")
    return obj


def _iata(obj: Any, path: str) -> str:
    code = _req(obj, "Iata", path)
    if not (isinstance(code, str) and len(code) == 3 and code.isalpha() and code.isupper()):
        raise ParseError(f"bad IATA code at {path}.Iata: {code!r}")
    return code


def _date(value: Any, path: str) -> date:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError as e:
        raise ParseError(f"bad date at {path}: {value!r}") from e


def parse(data: Any, observed_at: datetime) -> list[FlightOffer]:
    """Map one raw bundle to round-trip FlightOffers. Raise ParseError on unexpected shape."""
    if not isinstance(data, dict) or data.get("bundle_version") != BUNDLE_VERSION:
        got = list(data)[:8] if isinstance(data, dict) else type(data).__name__
        raise ParseError(f"not an r_pl bundle v{BUNDLE_VERSION} (got {got})")
    pax = _req(data, "passengers", "$")
    if not isinstance(pax, int) or pax < 1:
        raise ParseError(f"bad $.passengers: {pax!r}")
    outbound = _req(data, "outbound", "$")
    inbound = _req(data, "inbound", "$")

    offers: list[FlightOffer] = []
    for dest, out_groups in outbound.items():
        # pakiet id -> (outbound date, outbound ticket)
        by_pakiet: dict[str, tuple[date, dict[str, Any]]] = {}
        for gi, group in enumerate(_list(out_groups, f"$.outbound.{dest}")):
            gpath = f"$.outbound.{dest}[{gi}]"
            out_date = _date(_req(group, "Data", gpath), f"{gpath}.Data")
            for ticket in _list(_req(group, "Bilety", gpath), f"{gpath}.Bilety"):
                for p in ticket.get("Pakiety") or []:
                    by_pakiet[p] = (out_date, ticket)

        for gi, group in enumerate(_list(inbound.get(dest, []), f"$.inbound.{dest}")):
            gpath = f"$.inbound.{dest}[{gi}]"
            ret_date = _date(_req(group, "Data", gpath), f"{gpath}.Data")
            for ti, ret in enumerate(_list(_req(group, "Bilety", gpath), f"{gpath}.Bilety")):
                tpath = f"{gpath}.Bilety[{ti}]"
                bind = _req(ret, "BindId", tpath)
                if bind not in by_pakiet:
                    raise ParseError(f"{tpath}.BindId {bind!r} has no matching outbound pakiet")
                out_date, out = by_pakiet[bind]
                total = _req(ret, "CenaRazem", tpath)
                if not isinstance(total, int | float) or total <= 0:
                    raise ParseError(f"bad price at {tpath}.CenaRazem: {total!r}")
                origin = _iata(_req(out, "Wylot", "outbound ticket"), f"pakiet {bind} Wylot")
                dest_iata = _iata(_req(out, "Przylot", "outbound ticket"), f"pakiet {bind} Przylot")
                if dest_iata != dest:
                    raise ParseError(f"pakiet {bind}: outbound lands at {dest_iata}, expected {dest}")
                if ret_date < out_date:
                    raise ParseError(f"{tpath}: return {ret_date} before outbound {out_date}")
                out_no, ret_no = out.get("NumerLotu"), ret.get("NumerLotu")
                flight_no = f"{out_no}/{ret_no}" if out_no and ret_no else None
                offers.append(
                    FlightOffer(
                        operator=OPERATOR,
                        origin_iata=origin,
                        dest_iata=dest_iata,
                        outbound_date=out_date,
                        return_date=ret_date,
                        price_pln=(Decimal(str(total)) / pax).quantize(Decimal("0.01")),
                        observed_at=observed_at,
                        flight_no=flight_no,
                    )
                )
    return offers
