"""PostToolUse hook: after Claude edits a .py file, run `ruff check --fix` on it.

Remaining lint errors are reported back to Claude (exit 2 + stderr) so it fixes them right away.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def ruff_cmd() -> list[str] | None:
    for py in (ROOT / ".venv" / "Scripts" / "python.exe", ROOT / ".venv" / "bin" / "python"):
        if py.exists():
            return [str(py), "-m", "ruff"]
    exe = shutil.which("ruff")
    return [exe] if exe else None


def main() -> int:
    event = json.loads(sys.stdin.buffer.read().decode("utf-8-sig") or "{}")
    file_path = (event.get("tool_input") or {}).get("file_path", "")
    if not file_path.endswith(".py"):
        return 0
    cmd = ruff_cmd()
    if cmd is None:
        return 0  # ruff not installed: don't block work
    result = subprocess.run(
        [*cmd, "check", "--fix", "--quiet", file_path],
        check=False, cwd=ROOT, capture_output=True, text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(f"ruff found issues in {file_path}:\n{result.stdout}{result.stderr}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
