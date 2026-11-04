"""Print the structure of a JSON file without its bulk: keys, types, list lengths, sample scalars.

Use this instead of reading large API responses into context.

    python scripts/json_shape.py data/r_pl_raw.json [--depth 6] [--items 2]
    python scripts/json_shape.py old.json --diff new.json     # compare two shapes
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def shape(node: Any, depth: int, items: int, path: str = "$") -> list[str]:
    lines: list[str] = []
    if isinstance(node, dict):
        lines.append(f"{path}: object({len(node)})")
        if depth > 0:
            for k, v in node.items():
                lines += shape(v, depth - 1, items, f"{path}.{k}")
    elif isinstance(node, list):
        lines.append(f"{path}: array[{len(node)}]")
        if depth > 0:
            for i, v in enumerate(node[:items]):
                lines += shape(v, depth - 1, items, f"{path}[{i}]")
    else:
        sample = json.dumps(node, ensure_ascii=False)
        if len(sample) > 60:
            sample = sample[:57] + "..."
        lines.append(f"{path}: {type(node).__name__} = {sample}")
    return lines


def paths(node: Any, path: str = "$") -> set[str]:
    """Type signature per path, with list indices collapsed to [*]."""
    out = set()
    if isinstance(node, dict):
        out.add(f"{path}: object")
        for k, v in node.items():
            out |= paths(v, f"{path}.{k}")
    elif isinstance(node, list):
        out.add(f"{path}: array")
        for v in node:
            out |= paths(v, f"{path}[*]")
    else:
        out.add(f"{path}: {type(node).__name__}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file", type=Path)
    ap.add_argument("--depth", type=int, default=6)
    ap.add_argument("--items", type=int, default=1, help="list items to expand")
    ap.add_argument("--diff", type=Path, help="second file: print paths added/removed")
    args = ap.parse_args()

    data = json.loads(args.file.read_text(encoding="utf-8-sig"))
    if args.diff:
        other = json.loads(args.diff.read_text(encoding="utf-8-sig"))
        a, b = paths(data), paths(other)
        for line in sorted(a - b):
            print(f"- {line}")
        for line in sorted(b - a):
            print(f"+ {line}")
        return 0 if a == b else 1

    print("\n".join(shape(data, args.depth, args.items)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
