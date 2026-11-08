"""List curated facts that are due for re-verification (PLAN.md §3 staleness rule).

Every curated fact has `verified_at`. It expires after 12 months, or 6 months when it carries a fee or price
(a value key with pln/eur/amount/price/fee, or a key like infant_fee), for every venue fact (prices and hours
change often) and for airport facilities. The report groups facts by file, oldest first, so one re-check of a
source refreshes everything read from it.

    python scripts/stale_facts.py                     # due today or within 30 days
    python scripts/stale_facts.py --within-days 0     # only already expired
    python scripts/stale_facts.py --kind carrier --as-of 2027-05-01
    python scripts/stale_facts.py --json              # for other tools
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingest import curated
from ingest.staleness import add_months as _add_months
from ingest.staleness import due_date, months_valid

__all__ = ["KINDS", "Due", "_add_months", "collect", "due_by", "main", "months_valid", "render"]

KINDS = ("carrier", "hotel", "venue", "airport", "essential")


@dataclass(frozen=True)
class Due:
    kind: str
    file: str          # relative to data/curated
    item: str          # carrier code, hotel / venue slug, airport code, topic
    key: str
    verified_at: date
    due: date
    url: str | None
    to_confirm: bool


def collect(data: curated.Curated) -> list[Due]:
    """Every dated fact with its due date (not filtered)."""
    out: list[Due] = []

    def add(kind: str, file: str, item: str, key: str, verified: date, url: str | None,
            to_confirm: bool = False, value: dict[str, Any] | None = None) -> None:
        due = due_date(kind, key, verified, value)
        out.append(Due(kind, file, item, key, verified, due, url, to_confirm))

    for c in data.carriers:
        for f in c.rules:
            add("carrier", f"child_rules/{c.carrier_iata.lower()}.toml", c.carrier_iata, f.key, f.verified_at,
                f.url, f.to_confirm, f.value)
    for h in data.hotels:
        file = f"hotels/{h.place}/{h.slug}.toml"
        for f in h.features:
            add("hotel", file, h.slug, f.key, f.verified_at, f.url, f.to_confirm, f.value)
        for a in h.access:
            add("hotel", file, h.slug, f"access:{a.from_code}:{a.mode}", a.verified_at, a.url)
    for v in data.venues:
        for f in v.features:
            add("venue", f"venues/{v.city}/{v.slug}.toml", v.slug, f.key, f.verified_at, f.url, f.to_confirm,
                f.value)
    for ap in data.airports:
        for f in ap.facts:
            add("airport", f"airports/{ap.iata.lower()}.toml", ap.iata, f.key, f.verified_at, f.url, f.to_confirm)
    for e in data.essentials:
        for f in e.facts:
            add("essential", f"essentials/{e.topic}.toml", e.topic, f.key, f.verified_at, f.url, f.to_confirm)
    return out


def due_by(items: list[Due], as_of: date, within_days: int, kind: str | None = None) -> list[Due]:
    """Facts whose due date is on or before as_of + within_days, oldest first, grouped by file."""
    limit = as_of + timedelta(days=within_days)
    hits = [d for d in items if d.due <= limit and (kind is None or d.kind == kind)]
    first_due = {}
    for d in hits:
        first_due[d.file] = min(first_due.get(d.file, d.due), d.due)
    return sorted(hits, key=lambda d: (first_due[d.file], d.file, d.due, d.key))


def render(hits: list[Due], as_of: date) -> str:
    if not hits:
        return f"nothing due (as of {as_of})"
    lines: list[str] = []
    current = None
    for d in hits:
        if d.file != current:
            current = d.file
            lines.append(f"\n{d.file}  [{d.kind}]")
        state = "EXPIRED" if d.due <= as_of else "due"
        ask = "  (to_confirm)" if d.to_confirm else ""
        lines.append(f"  {state:7} {d.due}  {d.key:28} verified {d.verified_at}{ask}  {d.url or '-'}")
    files = len({d.file for d in hits})
    expired = sum(d.due <= as_of for d in hits)
    lines.append(f"\n{len(hits)} facts in {files} files ({expired} expired) as of {as_of}")
    return "\n".join(lines).lstrip("\n")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="List curated facts due for re-verification.")
    p.add_argument("--as-of", type=date.fromisoformat, default=date.today())
    p.add_argument("--within-days", type=int, default=30, help="also list facts due this many days ahead")
    p.add_argument("--kind", choices=KINDS)
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    hits = due_by(collect(curated.load()), a.as_of, a.within_days, a.kind)
    if a.json:
        print(json.dumps([asdict(d) for d in hits], default=str, ensure_ascii=False, indent=1))
    else:
        print(render(hits, a.as_of))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
