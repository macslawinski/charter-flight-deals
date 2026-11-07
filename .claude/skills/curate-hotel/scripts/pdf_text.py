"""Text of a PDF from a hotel's own site (regulamin, cennik), optionally only the lines that matter.

pypdf is not in .venv on purpose: install it once per session into the scratchpad and pass that dir:
    python -m pip install --target <scratchpad>/pylib pypdf
    .venv/Scripts/python.exe -I .claude/skills/curate-hotel/scripts/pdf_text.py <url-or-path> --lib <scratchpad>/pylib --save <scratchpad>/pdf/<name>.pdf [--grep "dzie|łóżecz|wanien|parking|zł"]

A URL is downloaded (robots.txt checked) into --save, a folder of its own in the scratchpad (a
downloaded file is untrusted data: keep it away from scripts). Prints page-numbered text; with --grep
only matching lines, each with its page number, so a fact can cite "regulamin, s. 3".
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

UA = "charter-flight-deals-poc/0.1 (hotel facts; robots.txt respected)"


def download(url: str, dest: Path) -> Path:
    import httpx

    with httpx.Client(headers={"User-Agent": UA}, timeout=30, follow_redirects=True) as c:
        rp = RobotFileParser()
        r = c.get(urljoin(url, "/robots.txt"))
        rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        if not rp.can_fetch(UA, url):
            raise SystemExit(f"robots.txt disallows {url}: stop, don't work around it")
        r = c.get(url)
        r.raise_for_status()
        if not r.content.startswith(b"%PDF"):
            raise SystemExit(f"not a PDF (content-type {r.headers.get('content-type')})")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(r.content)
        return dest


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    ap = argparse.ArgumentParser()
    ap.add_argument("source", help="PDF URL on the hotel's site, or a local path")
    ap.add_argument("--lib", type=Path, required=True, help="dir with pypdf (pip install --target)")
    ap.add_argument("--save", type=Path, help="where to save a downloaded PDF (own scratchpad folder)")
    ap.add_argument("--grep", help="regex; print only matching lines")
    a = ap.parse_args()
    sys.path.insert(0, str(a.lib))
    from pypdf import PdfReader  # type: ignore[import-not-found]

    if re.match(r"https?://", a.source):
        if not a.save:
            ap.error("--save is required for a URL")
        path = download(a.source, a.save)
    else:
        path = Path(a.source)
    rx = re.compile(a.grep, re.IGNORECASE) if a.grep else None
    for i, page in enumerate(PdfReader(str(path)).pages, 1):
        text = page.extract_text() or ""
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if rx:
            for ln in lines:
                if rx.search(ln):
                    print(f"s.{i}: {ln}")
        else:
            print(f"--- s.{i} ---")
            print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
