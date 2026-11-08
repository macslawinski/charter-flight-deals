"""Export the curated Product B data to family/src/data/family.json for the static site build.

    python scripts/export_family.py           # write the file
    python scripts/export_family.py --check   # exit 1 if the committed file is stale (CI / tests)

Reads data/curated/*.toml through the same strict loader as `python -m ingest.curated`, so the site
never shows a fact the DB loader would reject. No database needed: the build runs on Vercel.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ingest import curated

OUT = REPO_ROOT / "family" / "src" / "data" / "family.json"


def _plain(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    if isinstance(obj, date):
        return obj.isoformat()
    return obj


def build(data: curated.Curated) -> dict[str, Any]:
    return _plain({
        # Vocabularies let the site list what a hotel's page does *not* state.
        "feature_keys": sorted(curated.FEATURE_KEYS),
        "rule_keys": sorted(curated.RULE_KEYS),
        "places": [asdict(p) for p in data.places],
        "hotels": [asdict(h) for h in data.hotels],
        "carriers": [asdict(c) for c in sorted(data.carriers, key=lambda c: c.carrier_iata)],
        # The bawialnie pages read indoor playgrounds only; pools and rinks reach the map via the DB
        # (python -m ingest.curated, then scripts/export_venues.py).
        "venue_keys": sorted(curated.VENUE_KEYS_BY_CATEGORY["sala_zabaw"]),
        "venue_cities": curated.VENUE_CITIES,
        "venues": [asdict(v) for v in sorted(data.venues, key=lambda v: (v.city, v.name))
                   if v.category == "sala_zabaw"],
        "essentials": {e.topic: asdict(e) for e in data.essentials},
    })


def render(data: curated.Curated) -> str:
    return json.dumps(build(data), ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--check", action="store_true", help="fail if the committed file is stale")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    try:
        text = render(curated.load())
    except curated.CuratedError as e:
        print(f"curated data invalid: {e}", file=sys.stderr)
        return 2
    if args.check:
        current = args.out.read_text(encoding="utf-8") if args.out.exists() else ""
        if current != text:
            print(f"{args.out} is stale: run python scripts/export_family.py", file=sys.stderr)
            return 1
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {args.out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
