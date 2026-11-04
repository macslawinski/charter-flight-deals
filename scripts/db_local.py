"""Recreate a local scratch database and apply all db/migrations/*.sql in order.

    python scripts/db_local.py                 # recreate `cfd_local`, apply all migrations
    python scripts/db_local.py --db cfd_test --keep   # apply to existing DB without dropping

Requires a running local Postgres and `psql` on PATH (scoop install postgresql; pg_ctl start).
Connection uses PGHOST/PGPORT/PGUSER env vars, defaulting to localhost:5432 as postgres.
Never point this at the Supabase project: it drops the target database.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = ROOT / "db" / "migrations"


def psql(*args: str, db: str = "postgres") -> None:
    env = {"PGHOST": "localhost", "PGUSER": "postgres", **os.environ}
    if "supabase" in env.get("PGHOST", ""):
        sys.exit("refusing to run against a Supabase host")
    subprocess.run(
        ["psql", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-d", db, *args], check=True, env=env
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="cfd_local")
    ap.add_argument("--keep", action="store_true", help="don't drop/recreate the database")
    args = ap.parse_args()

    if not args.keep:
        psql("-c", f'drop database if exists "{args.db}" with (force)')
        psql("-c", f'create database "{args.db}"')

    files = sorted(MIGRATIONS.glob("*.sql"))
    for f in files:
        print(f"applying {f.name}")
        psql("-f", str(f), db=args.db)
    print(f"ok: {len(files)} migrations applied to {args.db}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
