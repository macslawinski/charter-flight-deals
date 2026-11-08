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
    assert set(out) == {"feature_keys", "rule_keys", "places", "hotels", "carriers", "venue_keys",
                        "venue_cities", "essentials", "airport_keys", "airports"}
    assert out["airport_keys"][0] == "play_area" and len(out["airports"]) == 6
    assert out["airports"][0]["facts"][0]["verified_at"]
    docs = out["essentials"]["travel_documents"]
    assert docs["title"] and docs["groups"] and docs["facts"][0]["verified_at"]
    assert out["venue_cities"]["poznan"] == "Poznań" and "age_range" in out["venue_keys"]
    assert "cot" in out["feature_keys"] and "infant_fee" in out["rule_keys"]
    fr = next(c for c in out["carriers"] if c["carrier_iata"] == "FR")
    fee = next(r for r in fr["rules"] if r["key"] == "infant_fee")
    assert fee["value"]["amount_eur"] == 25 and fee["verified_at"] == "2026-11-04"
    saltic = next(h for h in out["hotels"] if h["slug"] == "saltic-resort-spa-grzybowo")
    assert saltic["place"] == "grzybowo" and saltic["features"]


def test_every_fact_carries_its_due_date():
    # The site flags "do ponownego sprawdzenia" from `due` (ingest/staleness.py, same rule as stale_facts).
    out = json.loads(export_family.render(curated.load()))
    fr = next(c for c in out["carriers"] if c["carrier_iata"] == "FR")
    fee = next(r for r in fr["rules"] if r["key"] == "infant_fee")
    assert fee["due"] == "2027-05-04"                              # money: 6 months
    facts = [f for c in out["carriers"] for f in c["rules"]]
    facts += [f for h in out["hotels"] for f in h["features"] + h["access"]]
    facts += [f for a in out["airports"] for f in a["facts"]]
    facts += [f for e in out["essentials"].values() for f in e["facts"]]
    assert facts and all(f["due"] > f["verified_at"] for f in facts)


def test_check_fails_on_stale_file(tmp_path):
    stale = tmp_path / "family.json"
    stale.write_text("{}\n", encoding="utf-8")
    assert export_family.main(["--check", "--out", str(stale)]) == 1
