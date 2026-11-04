"""Export current deals from Postgres to web/public/deals.json (consumed by the static site)."""

from __future__ import annotations

import sys


def main() -> int:
    raise NotImplementedError("export not implemented yet; needs the transform (003_transform.sql)")


if __name__ == "__main__":
    sys.exit(main())
