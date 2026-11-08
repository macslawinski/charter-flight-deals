"""scripts/stale_facts.py: which curated facts are due for re-verification."""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import stale_facts as sf

from ingest import curated


def _fact(key: str, verified: date, value: dict | None = None) -> curated.Fact:
    return curated.Fact(key, None, value or {}, None, "carrier_official", "https://x.example/r", verified, False)


def test_fees_expire_after_6_months_other_rules_after_12():
    assert sf.months_valid("carrier", "infant_fee") == 6
    assert sf.months_valid("hotel", "cot", {"fee_pln": 30}) == 6
    assert sf.months_valid("hotel", "cot", {"available": True}) == 12
    assert sf.months_valid("venue", "toddler_zone") == 6
    assert sf.months_valid("airport", "play_area") == 6
    assert sf.months_valid("essential", "passport-fee") == 12


def test_month_arithmetic_clamps_to_month_end():
    assert sf._add_months(date(2026, 8, 31), 6) == date(2027, 2, 28)
    assert sf._add_months(date(2026, 11, 8), 12) == date(2027, 11, 8)


def test_due_by_filters_and_groups_by_file():
    data = curated.Curated(places=(), hotels=(), carriers=(
        curated.CarrierRules("FR", (_fact("infant_fee", date(2026, 1, 10)), _fact("stroller", date(2026, 1, 10)))),
        curated.CarrierRules("W6", (_fact("stroller", date(2025, 6, 1)),)),
    ))
    hits = sf.due_by(sf.collect(data), date(2026, 8, 1), within_days=0)
    # FR fee: due 2026-07-10 (expired); FR stroller: due 2027-01-10 (not yet); W6 stroller: due 2026-06-01.
    assert [(d.item, d.key) for d in hits] == [("W6", "stroller"), ("FR", "infant_fee")]
    assert hits[0].file == "child_rules/w6.toml"
    assert sf.due_by(sf.collect(data), date(2026, 8, 1), within_days=200, kind="carrier")[-1].key == "stroller"
    assert "EXPIRED" in sf.render(hits, date(2026, 8, 1))


def test_runs_on_the_real_data():
    items = sf.collect(curated.load())
    assert {d.kind for d in items} >= {"carrier", "hotel", "venue", "airport", "essential"}
    assert sf.main(["--as-of", "2026-11-08", "--within-days", "0"]) == 0
