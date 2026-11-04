"""CLI: fetch regular-airline reference fares (display-only).

    python -m ingest.market [--dry-run] [--from-file bundle.json] [--save-raw path]
                            [--max-segments N] [--database-url URL]

Run after `ingest.run` so today's deals get their segments fetched first. Never touches the deal
rule; the export joins the result via market_reference(as_of).
Exit codes: 0 ok, 1 fetch/parse failed, 2 configuration error, 3 request cap hit (incomplete).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import psycopg

from ingest import store
from ingest.config import load_settings
from ingest.http_client import BlockedError, PoliteClient
from ingest.models import ParseError
from ingest.sources import travelpayouts

WARSAW = ZoneInfo("Europe/Warsaw")
log = logging.getLogger("market")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fetch regular-airline reference fares.")
    ap.add_argument("--dry-run", action="store_true", help="fetch and parse, write nothing")
    ap.add_argument("--from-file", type=Path, help="parse a saved bundle instead of fetching")
    ap.add_argument("--save-raw", type=Path, help="write the fetched raw bundle to this file")
    ap.add_argument("--max-segments", type=int, help="override max_segments_per_run")
    ap.add_argument("--database-url", help="override DATABASE_URL (e.g. local Postgres)")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = load_settings()
    source = settings.sources[travelpayouts.SOURCE]
    fetched_at = datetime.now(UTC)
    today = fetched_at.astimezone(WARSAW).date()
    database_url = args.database_url or settings.database_url

    if args.from_file:
        bundle = json.loads(args.from_file.read_text(encoding="utf-8"))
    else:
        if not source.enabled:
            log.error("source %s is disabled in config/sources.toml", source.name)
            return 2
        if not source.token:
            log.error("%s is not set (.env locally, repository secret in CI)", source.token_env)
            return 2
        if not database_url:
            log.error("DATABASE_URL is not set: needed to pick the segments to fetch")
            return 2
        try:
            with store.connect(database_url) as conn:
                segments = store.market_segments(
                    conn, source.name, today,
                    int(source.payload.get("horizon_days", 120)),
                    args.max_segments or int(source.payload.get("max_segments_per_run", 40)))
        except psycopg.Error as e:
            log.error("cannot read segments from the database: %s", e)
            return 2
        log.info("%d segments to fetch", len(segments))
        if not segments:
            return 0
        with PoliteClient(settings) as client:
            try:
                bundle = travelpayouts.crawl(client, source, segments)
            except (BlockedError, httpx.HTTPError) as e:
                # 401/403 = bad or revoked token; don't retry, don't hammer.
                log.error("fetch failed after %d requests: %s", client.request_count, e)
                return 1
            log.info("%d requests sent", client.request_count)
        if args.save_raw:
            args.save_raw.parent.mkdir(parents=True, exist_ok=True)
            args.save_raw.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")

    truncated = bool(bundle.get("truncated")) if isinstance(bundle, dict) else False
    if truncated:
        log.error("run hit max_requests_per_run; some segments were not fetched")

    if args.dry_run:
        parsed = travelpayouts.parse(bundle)
        _report(parsed)
        return 3 if truncated else 0

    if not database_url:
        log.error("DATABASE_URL is not set (use .env, the env var, or --database-url)")
        return 2
    request_info: dict[str, Any] = {"source": source.name, "segments": len(bundle["responses"])}
    if args.from_file:
        request_info["from_file"] = args.from_file.name
    with store.connect(database_url) as conn:
        raw_id = store.save_raw_fetch(conn, source.name, request_info, bundle, 200, fetched_at)
        conn.commit()
        try:
            parsed = travelpayouts.parse(bundle)
        except ParseError as e:
            store.mark_parse_result(conn, raw_id, str(e))
            conn.commit()
            log.error("parse failed, raw_fetches.id=%d kept: %s", raw_id, e)
            return 1
        n = store.save_market(conn, parsed, source.name, fetched_at, today)
        store.mark_parse_result(conn, raw_id, None)
        pruned = store.prune_market(conn, today)
        unknown = conn.execute(
            """select coalesce(string_agg(distinct m.airline, ', '), '') from market_fares m
               where m.fetched_date = %s
                 and not exists (select 1 from airlines a where a.iata = m.airline)""",
            (today,),
        ).fetchone()
        conn.commit()
    _report(parsed)
    log.info("raw_fetches.id=%d: %d fares saved for %d segments, %d old fares pruned",
             raw_id, n, len(parsed), pruned)
    if unknown and unknown[0]:
        log.warning("airlines not in the `airlines` table (ignored as reference): %s", unknown[0])
    return 3 if truncated else 0


def _report(parsed: dict[Any, list[Any]]) -> None:
    with_fares = sum(1 for fares in parsed.values() if fares)
    log.info("%d/%d segments returned direct fares, %d fares total",
             with_fares, len(parsed), sum(len(f) for f in parsed.values()))


if __name__ == "__main__":
    sys.exit(main())
