"""scripts/export_family.py: the committed family.json matches data/curated, and the shape the site reads."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import export_family

from ingest import curated


def test_committed_json_is_up_to_date():
    # Edit a TOML, forget the export -> the site would show stale facts. CI catches it here.
    assert export_family.main(["--check"]) == 0, "run: python scripts/export_family.py"


def test_export_shape():
    out = json.loads(export_family.render(curated.load()))
    assert set(out) == {"feature_keys", "rule_keys", "places", "hotels", "carriers"}
    assert "cot" in out["feature_keys"] and "infant_fee" in out["rule_keys"]
    fr = next(c for c in out["carriers"] if c["carrier_iata"] == "FR")
    fee = next(r for r in fr["rules"] if r["key"] == "infant_fee")
    assert fee["value"]["amount_eur"] == 25 and fee["verified_at"] == "2026-11-04"
    saltic = next(h for h in out["hotels"] if h["slug"] == "saltic-resort-spa-grzybowo")
    assert saltic["place"] == "grzybowo" and saltic["features"]


def test_check_fails_on_stale_file(tmp_path):
    stale = tmp_path / "family.json"
    stale.write_text("{}\n", encoding="utf-8")
    assert export_family.main(["--check", "--out", str(stale)]) == 1
