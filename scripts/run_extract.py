"""Read one frozen fixture with the real model and print what it built.

This is the check a person does by eye: the record on one side, the funder's page
on the other, read down them together. It is the only thing in this project that
needs a model key, and it is run by hand.

It lives here rather than in the package for the same reason
`refresh_fixture.py` does. Both are harnesses a person runs, neither is part of
the scheduled run, and keeping them out of `src/` means the package holds only
what the run itself executes.

Usage:  uv run python scripts/run_extract.py [name ...]
"""

from __future__ import annotations

import hashlib
import io
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

from field_monitoring_pipeline.extract import (
    PROMPT_VERSION,
    Gemini,
    HeldAfterTwoTriesError,
    MissingKeyError,
    ModelUnreachableError,
    describe,
    extract,
    load_prompt,
    read_key,
)
from field_monitoring_pipeline.models import RawItem

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / "src" / "field_monitoring_pipeline" / "prompts"
FIXTURES = ROOT / "tests" / "fixtures"


MOST_OF_A_REPLY = 4_000
"""How much of one reply is printed before the rest is counted rather than shown.

Enough to read a model's reasoning and the command line it ends with, and short
enough that a reply running to the ceiling does not bury what came before it.
"""


def fixture_item(folder: Path, name: str) -> tuple[RawItem, str]:
    """One frozen fixture as an item, so the real path reads it like any other."""
    url = (folder / "source_url.txt").read_text(encoding="utf-8").strip()
    body = (folder / "input.txt").read_bytes()
    item = RawItem(
        source_id=name,
        source_item_id=None,
        url=url,
        canonical_url=url,
        fetched_at=datetime.now(UTC),
        raw_text=body.decode("utf-8", "replace"),
        raw_hash=hashlib.sha256(body).hexdigest(),
    )
    return item, url


def main() -> int:
    """Run the extraction against each named fixture, or the first one by default."""
    # The record carries a funder's own punctuation. When the screen is
    # redirected on Windows, Python encodes strictly in the machine's code
    # page, and one character it lacks stops the whole check. So the screen is
    # rewrapped to write UTF-8, and to replace rather than stop.
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    names = sys.argv[1:] or ["cipesa"]
    try:
        key = read_key(ROOT)
    except MissingKeyError as error:
        sys.stdout.write(f"{error}\n")
        return 1

    prompt = load_prompt(PROMPTS, PROMPT_VERSION)
    with httpx.Client() as client:
        model = Gemini(key=key, client=client)
        for name in names:
            folder = FIXTURES / name
            if not folder.exists():
                sys.stdout.write(f"there is no fixture called {name}\n")
                return 1
            item, url = fixture_item(folder, name)
            sys.stdout.write(f"\n{'=' * 78}\n{name}\n{url}\n{'=' * 78}\n")

            def show(attempt: int, reply: str) -> None:
                """What the model said, which is half of the check done by eye.

                Shown at length on purpose, because a person reading it beside the
                page is the whole point of this script. Bounded all the same: a
                reply may be sixty thousand characters, and a wall of them buries
                the command line underneath that the reader is here to look at.
                """
                said = reply.rstrip()
                if len(said) > MOST_OF_A_REPLY:
                    cut = len(said) - MOST_OF_A_REPLY
                    said = f"{said[:MOST_OF_A_REPLY]}\n[{cut} more characters, not shown]"
                sys.stdout.write(f"\n--- what the model wrote, attempt {attempt} ---\n")
                sys.stdout.write(said + "\n")
                sys.stdout.write("--- the record built from it ---\n")

            try:
                built = extract(item, model, prompt, model.model_id, watch=show)
            except (HeldAfterTwoTriesError, ModelUnreachableError) as error:
                sys.stdout.write(f"nothing built: {error}\n")
                continue
            sys.stdout.write(describe(built) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
