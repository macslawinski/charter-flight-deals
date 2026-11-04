"""CLI entry point: python -m ingest.run [--source r_pl|itaka] [--dry-run] [--from-file path]."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import psycopg

from ingest import store
from ingest.config import load_settings
from ingest.http_client import PoliteClient
from ingest.models import ParseError
from ingest.sources import itaka, r_pl
from ingest.store import dedupe

PARSERS = {"r_pl": r_pl, "itaka": itaka}
WARSAW = ZoneInfo("Europe/Warsaw")

log = logging.getLogger("ingest")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ingest charter flight offers.")
    ap.add_argument("--source", default="r_pl", choices=sorted(PARSERS))
    ap.add_argument("--dry-run", action="store_true", help="parse and report, write nothing")
    ap.add_argument("--from-file", type=Path, help="parse a saved JSON response instead of fetching")
    ap.add_argument("--save-raw", type=Path, help="write the fetched raw bundle to this file")
    ap.add_argument("--database-url", help="override DATABASE_URL (e.g. local Postgres)")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = load_settings()
    source_mod = PARSERS[args.source]
    observed_at = datetime.now(UTC)
    database_url = args.database_url or settings.database_url
    if not args.dry_run and not database_url:
        log.error("DATABASE_URL is not set (use .env, the env var, or --database-url)")
        return 2
    if not args.dry_run:
        # Fail fast: a full crawl takes ~10 min, don't spend it only to find the DB unreachable.
        # (Reconnect after the crawl instead of holding an idle connection through the pooler.)
        assert database_url is not None
        try:
            with store.connect(database_url) as conn:
                conn.execute("select 1")
        except psycopg.Error as e:
            log.error("cannot connect to the database: %s", e)
            return 2

    request_info: dict[str, Any] = {"source": args.source}
    if args.from_file:
        bundle = json.loads(args.from_file.read_text(encoding="utf-8"))
        request_info["from_file"] = args.from_file.name
    else:
        source = settings.sources[args.source]
        if not source.enabled:
            log.error("source %s is disabled in config/sources.toml", args.source)
            return 2
        with PoliteClient(settings) as client:
            try:
                bundle = source_mod.crawl(client, source, observed_at.astimezone(WARSAW).date())
            finally:
                log.info("%d requests sent", client.request_count)
                request_info["requests"] = client.request_count
        if args.save_raw:
            args.save_raw.parent.mkdir(parents=True, exist_ok=True)
            args.save_raw.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
            log.info("raw bundle saved to %s", args.save_raw)

    truncated = bool(bundle.get("truncated")) if isinstance(bundle, dict) else False
    if truncated:
        log.error("run hit max_requests_per_run; data is incomplete")

    if args.dry_run:
        offers = dedupe(source_mod.parse(bundle, observed_at))
        log.info("parsed %d offers (dry run, nothing written)", len(offers))
        return 3 if truncated else 0

    assert database_url is not None
    with store.connect(database_url) as conn:
        # Raw first, committed on its own: if parsing fails the response is still kept for reparsing.
        raw_id = store.save_raw_fetch(conn, args.source, request_info, bundle, 200, observed_at)
        conn.commit()
        try:
            offers = dedupe(source_mod.parse(bundle, observed_at))
        except ParseError as e:
            store.mark_parse_result(conn, raw_id, str(e))
            conn.commit()
            log.error("parse failed, raw_fetches.id=%d kept: %s", raw_id, e)
            return 1
        snapshot_date = observed_at.astimezone(WARSAW).date()
        written = store.upsert_offers(conn, offers, snapshot_date)
        store.mark_parse_result(conn, raw_id, None)
        n_deals = store.refresh_deals(conn, snapshot_date)
        pruned = store.prune_raw_fetches(conn, observed_at)
        conn.commit()
    log.info("raw_fetches.id=%d: %d offers upserted, %d deals for %s, %d old raw rows pruned",
             raw_id, written, n_deals, snapshot_date, pruned)
    return 3 if truncated else 0


if __name__ == "__main__":
    sys.exit(main())
