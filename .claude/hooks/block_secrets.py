"""PreToolUse hook: block `git commit` when staged changes contain secrets.

Checks staged file names (.env) and added lines for DB URLs with real passwords, JWTs
(Supabase keys), Supabase/Anthropic/GitHub tokens and cookie values. Exit 2 blocks the tool call
and shows the reason to Claude.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PATTERNS = {
    "Postgres URL with password": re.compile(r"postgres(?:ql)?://[^:\s/]+:(?!<password>)[^@\s]+@"),
    "JWT / Supabase key": re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+"),
    "Supabase access token": re.compile(r"\bsbp_[A-Za-z0-9]{20,}"),
    "Anthropic/OpenAI-style key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"),
    "Cookie value": re.compile(r"(?i)\b(?:cookie|set-cookie|RPL_COOKIE)\b\s*[=:]\s*['\"]?[^\s'\"]{20,}"),
}
ALLOWED_ENV_FILES = {".env.example"}


def git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], check=False, cwd=ROOT, capture_output=True, text=True
    ).stdout


def main() -> int:
    event = json.loads(sys.stdin.buffer.read().decode("utf-8-sig") or "{}")
    command = (event.get("tool_input") or {}).get("command", "")
    if not re.search(r"\bgit\b[^;|&]*\bcommit\b", command):
        return 0

    commit_all = re.search(r"\bcommit\b[^;|&]*\s-(?:[a-zA-Z]*a[a-zA-Z]*)\b|--all\b", command)
    names = git("diff", "--cached", "--name-only").split()
    diff = git("diff", "--cached", "-U0")
    if commit_all:
        names += git("diff", "--name-only").split()
        diff += git("diff", "-U0")

    problems = []
    for name in names:
        base = Path(name).name
        if base.startswith(".env") and base not in ALLOWED_ENV_FILES:
            problems.append(f"{name}: env file must not be committed")

    current = "?"
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else line[4:]
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        for label, rx in PATTERNS.items():
            if rx.search(line):
                problems.append(f"{current}: {label}")

    if problems:
        sys.stderr.write(
            "Commit blocked: possible secrets in staged changes:\n  "
            + "\n  ".join(sorted(set(problems)))
            + "\nMove the value to .env / CI secrets, unstage it, then commit again. "
            "If it is a false positive, tell the user and let them decide.\n"
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
