"""Freeze a funder's page into a test fixture, through the real fetch function.

A golden fixture is only worth anything if anyone can regenerate it and get the
same thing. This script is how. It reaches a page the way the scheduled run
reaches a source, with the same address checks, the same size cap and the same
timeouts, and writes exactly what the server sent into the tests folder.

It writes nothing into `data/`. That directory belongs to the run, and a
scheduled run could rewrite a file there and move a test underneath it.

A regenerated fixture will differ from the old one even when the funder has
changed nothing. Both test pages carry values that change on every request: a
session identifier on one, and on the other an email address the site re-encodes
each time it is served. Measured on both: 168 and 226 characters differ between
two fetches a moment apart, out of 246,286 and 157,373. So a difference here is
not evidence that the page changed. Read the words, not the diff.

Usage:  uv run python scripts/refresh_fixture.py [name ...]
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import httpx

from field_monitoring_pipeline.fetch import Fetched, fetch
from field_monitoring_pipeline.models import Source

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
USER_AGENT = "fieldbook (+https://github.com/civicliteracies/field-monitoring-pipeline)"

PAGES = {
    "cipesa": "https://cipesa.org/2024/01/introducing-the-tech-accountability-fund-and-a-call-for-proposals/",
    "pulitzer": "https://pulitzercenter.org/blog/open-call-proposals-pulitzer-centers-ai-accountability-fellowships-2026-2027",
}


def freeze(name: str, url: str, client: httpx.Client) -> int:
    """Fetch one page and write it into its fixture folder. Returns bytes written."""
    source = Source.model_validate({
        "id": name,
        "name": name,
        "kind": "call",
        "how": "feed",
        "url": url,
        "since": date(2020, 1, 1),
    })
    outcome = fetch(source, None, client)
    if not isinstance(outcome, Fetched):
        msg = f"{name}: the page did not answer, {outcome}"
        raise SystemExit(msg)
    folder = FIXTURES / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "input.txt").write_bytes(outcome.body)
    (folder / "source_url.txt").write_text(url + "\n", encoding="utf-8")
    return len(outcome.body)


def main() -> int:
    """Freeze every named fixture, or all of them when none is named."""
    wanted = sys.argv[1:] or list(PAGES)
    unknown = [name for name in wanted if name not in PAGES]
    if unknown:
        sys.stdout.write(f"unknown fixture: {', '.join(unknown)}\n")
        return 1
    with httpx.Client(follow_redirects=False, headers={"user-agent": USER_AGENT}) as client:
        for name in wanted:
            written = freeze(name, PAGES[name], client)
            sys.stdout.write(f"{name}: {written} bytes frozen\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
