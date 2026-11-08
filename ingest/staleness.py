"""Staleness rule for curated facts (PLAN.md §3): when a fact is due for re-verification.

One place for the rule, used by scripts/stale_facts.py (the re-check list) and by the site exports
(each fact carries its `due` date; the site shows "do ponownego sprawdzenia" once it has passed).

A fact expires 12 months after `verified_at`, or 6 months when it carries a fee or price (a value key or
fact key with fee/fare/price/pln/eur/amount), for every venue fact (prices and hours change often) and for
airport facilities. Map venues from the DB use their category's `venue_categories.stale_after_months`.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

_MONEY_KEY = re.compile(r"fee|fare|price|pln|eur|amount", re.IGNORECASE)


def add_months(d: date, months: int) -> date:
    y, m = divmod(d.month - 1 + months, 12)
    year, month = d.year + y, m + 1
    for day in (d.day, 30, 29, 28):  # 31 Aug + 6 months -> 28/29 Feb
        try:
            return date(year, month, day)
        except ValueError:
            continue
    raise AssertionError("unreachable")


def _has_money(key: str, value: dict[str, Any] | None) -> bool:
    return bool(_MONEY_KEY.search(key)) or any(_MONEY_KEY.search(k) for k in (value or {}))


def months_valid(kind: str, key: str, value: dict[str, Any] | None = None) -> int:
    """kind: carrier | hotel | venue | airport | essential."""
    if kind in ("venue", "airport"):
        return 6
    if kind == "essential":
        return 12
    return 6 if _has_money(key, value) else 12


def due_date(kind: str, key: str, verified: date, value: dict[str, Any] | None = None) -> date:
    return add_months(verified, months_valid(kind, key, value))
