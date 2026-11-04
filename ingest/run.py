"""CLI entry point: python -m ingest.run [--source r_pl] [--dry-run] [--from-file path]."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ingest.config import load_settings
from ingest.http_client import PoliteClient
from ingest.sources import r_pl
from ingest.store import dedupe

PARSERS = {"r_pl": r_pl}

log = logging.getLogger("ingest")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ingest charter flight offers.")
    ap.add_argument("--source", default="r_pl", choices=sorted(PARSERS))
    ap.add_argument("--dry-run", action="store_true", help="parse and report, write nothing")
    ap.add_argument("--from-file", type=Path, help="parse a saved JSON response instead of fetching")
    ap.add_argument("--save-raw", type=Path, help="write the fetched raw bundle to this file")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = load_settings()
    source_mod = PARSERS[args.source]
    observed_at = datetime.now(UTC)

    if args.from_file:
        data = json.loads(args.from_file.read_text(encoding="utf-8"))
        offers = dedupe(source_mod.parse(data, observed_at))
        log.info("parsed %d offers from %s", len(offers), args.from_file)
        if args.dry_run:
            return 0
        raise NotImplementedError("DB write not implemented yet")

    source = settings.sources[args.source]
    if not source.enabled:
        log.error("source %s is disabled in config/sources.toml", args.source)
        return 2

    today = datetime.now(ZoneInfo("Europe/Warsaw")).date()
    with PoliteClient(settings) as client:
        try:
            bundle = source_mod.crawl(client, source, today)
        finally:
            log.info("%d requests sent", client.request_count)
    if args.save_raw:
        args.save_raw.parent.mkdir(parents=True, exist_ok=True)
        args.save_raw.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
        log.info("raw bundle saved to %s", args.save_raw)

    offers = dedupe(source_mod.parse(bundle, observed_at))
    log.info("parsed %d offers", len(offers))
    if bundle.get("truncated"):
        log.error("run hit max_requests_per_run; data is incomplete")
    if args.dry_run:
        return 3 if bundle.get("truncated") else 0
    raise NotImplementedError("DB write not implemented yet")


if __name__ == "__main__":
    sys.exit(main())
