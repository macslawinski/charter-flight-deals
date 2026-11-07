"""CLI: import one open-data source into venues.

    python -m ingest.opendata --source nfz_nisoz [--dry-run] [--from-file bundle.json]
                              [--save-raw bundle.json] [--database-url URL]

A run is all-or-nothing: the raw download is kept in raw_fetches, then the parsed batch is written in
one transaction. A batch smaller than the source's `min_records` fails before anything is written,
so a truncated file can never retire half of the records.
Exit codes: 0 ok, 1 fetch/parse failed, 2 configuration error.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from ingest import store
from ingest.config import SourceConfig, load_settings
from ingest.http_client import BlockedError, Fetcher, PoliteClient, RequestCapReached
from ingest.models import ParseError
from ingest.opendata import ImportBatch, nisoz, poznan_playgrounds
from ingest.opendata.save import log_run, save_batch

WARSAW = ZoneInfo("Europe/Warsaw")
log = logging.getLogger("opendata")


def fetch_nisoz(client: Fetcher, source: SourceConfig) -> dict[str, Any]:
    page = client.fetch(source, path=str(source.payload["page_path"]))
    data_url = nisoz.data_file_url(page.text)
    if not data_url.startswith(nisoz.BASE + "/"):
        raise ParseError(f"NiŚOZ data file on an unexpected host: {data_url}")
    resp = client.fetch(source, path=data_url[len(nisoz.BASE):])
    return {"data_url": data_url, "data": nisoz.loads(resp.text)}


def fetch_poznan_playgrounds(client: Fetcher, source: SourceConfig) -> dict[str, Any]:
    resp = client.fetch(source)
    try:
        data = resp.json()
    except json.JSONDecodeError as e:
        raise ParseError(f"Poznań playgrounds: response is not JSON: {e}") from e
    return {"data_url": source.url, "data": data}


Fetch = Callable[[Fetcher, SourceConfig], dict[str, Any]]
Parse = Callable[[dict[str, Any]], ImportBatch]
SOURCES: dict[str, tuple[Fetch, Parse]] = {
    nisoz.SOURCE_ID: (fetch_nisoz, nisoz.parse_bundle),
    poznan_playgrounds.SOURCE_ID: (fetch_poznan_playgrounds, poznan_playgrounds.parse_bundle),
}


def parse_checked(parse: Parse, bundle: dict[str, Any], min_records: int) -> ImportBatch:
    batch = parse(bundle)
    if len(batch.records) < min_records:
        raise ParseError(f"only {len(batch.records)} records (< min_records {min_records}): "
                         "truncated or changed source, nothing written")
    return batch


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Import an open-data source into venues.")
    ap.add_argument("--source", required=True, choices=sorted(SOURCES))
    ap.add_argument("--dry-run", action="store_true", help="fetch and parse, write nothing")
    ap.add_argument("--from-file", type=Path, help="use a saved bundle instead of fetching")
    ap.add_argument("--save-raw", type=Path, help="write the fetched bundle to this file")
    ap.add_argument("--database-url", help="override DATABASE_URL (e.g. local Postgres)")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = load_settings()
    source = settings.sources.get(args.source)
    if source is None:
        log.error("source %s missing in config/sources.toml", args.source)
        return 2
    fetch, parse = SOURCES[args.source]
    min_records = int(source.payload.get("min_records", 1))
    started_at = datetime.now(UTC)
    today = started_at.astimezone(WARSAW).date()

    if args.from_file:
        bundle = json.loads(args.from_file.read_text(encoding="utf-8"))
    else:
        if not source.enabled:
            log.error("source %s is disabled in config/sources.toml", source.name)
            return 2
        with PoliteClient(settings) as client:
            try:
                bundle = fetch(client, source)
            except (BlockedError, RequestCapReached, httpx.HTTPError, ParseError, RuntimeError) as e:
                log.error("fetch failed after %d requests: %s", client.request_count, e)
                return 1
            log.info("%d requests sent", client.request_count)
        if args.save_raw:
            args.save_raw.parent.mkdir(parents=True, exist_ok=True)
            args.save_raw.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")

    if args.dry_run:
        try:
            batch = parse_checked(parse, bundle, min_records)
        except ParseError as e:
            log.error("parse failed: %s", e)
            return 1
        _report(batch)
        return 0

    database_url = args.database_url or settings.database_url
    if not database_url:
        log.error("DATABASE_URL is not set (use .env, the env var, or --database-url)")
        return 2
    request_info: dict[str, Any] = {"source": source.name, "data_url": bundle.get("data_url")}
    if args.from_file:
        request_info["from_file"] = args.from_file.name
    with store.connect(database_url) as conn:
        raw_id = store.save_raw_fetch(conn, source.name, request_info, bundle, 200, started_at)
        conn.commit()
        try:
            batch = parse_checked(parse, bundle, min_records)
        except ParseError as e:
            store.mark_parse_result(conn, raw_id, str(e))
            log_run(conn, source.name, started_at, datetime.now(UTC), "failed",
                    data_url=bundle.get("data_url"), raw_fetch_id=raw_id, error=str(e))
            conn.commit()
            log.error("parse failed, raw_fetches.id=%d kept: %s", raw_id, e)
            return 1
        counts = save_batch(conn, batch, today)
        store.mark_parse_result(conn, raw_id, None)
        log_run(conn, source.name, started_at, datetime.now(UTC), "ok", data_url=batch.data_url,
                data_as_of=batch.data_as_of, raw_fetch_id=raw_id, counts=counts)
        conn.commit()
    _report(batch)
    log.info("raw_fetches.id=%d: %s", raw_id, counts)
    return 0


def _report(batch: ImportBatch) -> None:
    n_coords = sum(1 for r in batch.records if r.lat is not None)
    log.info("%s: %d records (%d with coordinates), %d rows skipped, data as of %s, from %s",
             batch.source_id, len(batch.records), n_coords, batch.skipped,
             batch.data_as_of or "n/a", batch.data_url)


if __name__ == "__main__":
    sys.exit(main())
