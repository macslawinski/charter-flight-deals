"""Append car (OSRM) and train [[access]] blocks to one or more hotel TOMLs, in place.

Usage (from the repo root):
    .venv/Scripts/python.exe .claude/skills/curate-hotel/scripts/add_access.py <hotel.toml>... \
        [--station LAT LON] \
        [--train-from <hotel near the same station.toml>] \
        [--train "<Station>" "Warszawa|238|1 przesiadka; Gdańsk|78|bezpośredni; ..." --train-date 2026-11-12]

- lat/lon are read from each hotel file; car blocks come from osrm_access.py (same method).
- --station: computes station -> hotel by car; if the header contains "Station -> hotel: TBD" the TBD
  is replaced with "~N km, ~M min by car or taxi (OSRM)", otherwise the line is only printed.
- Train: either copy the train section of a hotel already curated near the same station
  (--train-from, preferred: train times belong to the station), or build it from rozklad-pkp.pl
  results (--train, six cities, "City|minutes|note" separated by ";"). Without either: car only
  (say "no sensible train" in the header).
- Refuses a file that already has [[access]] blocks, so a rerun can't duplicate them.
"""

from __future__ import annotations

import argparse
import sys
import tomllib
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from osrm_access import CITIES, car_section, station_desc

TRAIN_MARK = "# --- Access: train"


def train_section(station: str, results: str, train_date: str, today: str) -> str:
    items = []
    for part in results.split(";"):
        city, minutes, note = (x.strip() for x in part.split("|"))
        if city not in CITIES:
            raise SystemExit(f"unknown city in --train: {city!r} (expected one of {', '.join(CITIES)})")
        items.append((int(minutes), city, note))
    out = [f"{TRAIN_MARK} to {station} station (rozklad-pkp.pl, {train_date}) " + "-" * 20]
    for minutes, city, note in sorted(items):
        out.append(
            f'[[access]]\nfrom_kind = "city"\nfrom = "{city}"\nmode = "train"\nminutes = {minutes}\n'
            f'note = "{note}"\nurl = "https://rozklad-pkp.pl/"\nverified_at = {today}\n'
        )
    return "\n".join(out)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    ap = argparse.ArgumentParser()
    ap.add_argument("hotels", nargs="+", type=Path)
    ap.add_argument("--station", nargs=2, type=float, metavar=("LAT", "LON"))
    ap.add_argument("--train-from", type=Path, help="hotel TOML whose train section to copy")
    ap.add_argument("--train", nargs=2, metavar=("STATION", "RESULTS"))
    ap.add_argument("--train-date", help="the weekday date queried on rozklad-pkp.pl (with --train)")
    a = ap.parse_args()
    if a.train and a.train_from:
        ap.error("use --train or --train-from, not both")
    if a.train and not a.train_date:
        ap.error("--train needs --train-date")

    today = date.today().isoformat()
    train = ""
    if a.train_from:
        donor = a.train_from.read_text(encoding="utf-8")
        if TRAIN_MARK not in donor:
            raise SystemExit(f"{a.train_from} has no train section")
        train = donor[donor.index(TRAIN_MARK):].rstrip() + "\n"
    elif a.train:
        train = train_section(a.train[0], a.train[1], a.train_date, today)

    for path in a.hotels:
        text = path.read_text(encoding="utf-8")
        if "[[access]]" in text:
            raise SystemExit(f"{path} already has [[access]] blocks; remove them first")
        data = tomllib.loads(text)
        lat, lon = float(data["lat"]), float(data["lon"])
        if a.station:
            desc = station_desc(a.station[0], a.station[1], lat, lon)
            if "Station -> hotel: TBD" in text:
                text = text.replace("Station -> hotel: TBD", f"Station -> hotel: {desc}", 1)
            else:
                print(f"{path}: station -> hotel {desc} (header has no 'Station -> hotel: TBD')")
        parts = [text.rstrip() + "\n", car_section(lat, lon)]
        if train:
            parts.append(train.rstrip() + "\n")
        path.write_bytes("\n".join(parts).encode("utf-8"))
        print(f"{path}: {''.join(parts).count('[[access]]')} access blocks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
