"""Store what the run collected and wrote, under the data folder.

Each saved call has its web page as downloaded in its source's folder and, when the source gives
one, the source's record of it. Both are named by a code made from the call's identifier. A saved
call is given back as its record, or as its page when it has no record. Each call read has a card in
one folder for all sources, named by the day it was saved, its title and the first ten characters of
its code. One log beside the folders has a row for each call the run tried, saved or failed; for
each answer the model gave while reading a call, first or second, with the answer as it came; and
for each call it read, card written or failed. It also has a row for each source, which says how the
run ended for it. What a step produced is written before the row that says the step is done. The
feed, built from the cards, sits beside them and is written again on every run that reaches its end.
A call counts as stored once it has a saved row, and as read once it has a card.
"""

import csv
import datetime as dt
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from field_monitoring_pipeline.fetch import JSON, FetchedCall, NoRecord

COLUMNS = ("code", "source", "identifier", "title", "link", "fetched", "status", "reason")
SHORT_TITLE = 60
SHORT_CODE = 10
type Status = Literal["saved", "failed"]
type Reading = Literal["card written", "failed"]
type AnswerWord = Literal["first answer", "second answer"]
type Outcome = Literal["successful", "failed", "nothing new"]
type Row = tuple[str, str, str, str, str, str, Status | Reading | AnswerWord | Outcome, str]


@dataclass(frozen=True)
class Saved:
    source: str
    identifier: str
    title: str
    link: str
    day: dt.date


def code(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _raw(data: Path) -> Path:
    return data / "raw"


def _log(data: Path) -> Path:
    return _raw(data) / "log.csv"


def _cards(data: Path) -> Path:
    return data / "calls"


def saved(data: Path) -> list[Saved]:
    log = _log(data)
    if not log.exists():
        return []
    with log.open(encoding="utf-8", newline="") as file:
        return [
            Saved(
                row["source"],
                row["identifier"],
                row["title"],
                row["link"],
                dt.datetime.fromisoformat(row["fetched"]).date(),
            )
            for row in csv.DictReader(file)
            if row["status"] == "saved"
        ]


def _add_row(data: Path, row: Row) -> None:
    _raw(data).mkdir(parents=True, exist_ok=True)
    with _log(data).open("a", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        if file.tell() == 0:
            writer.writerow(COLUMNS)
        writer.writerow(row)


def _add_call_row(
    data: Path,
    source: str,
    call: FetchedCall | Saved,
    fetched: dt.datetime,
    status: Status | Reading | AnswerWord,
    reason: str,
) -> None:
    name = code(call.identifier)
    _add_row(data, (name, source, call.identifier, call.title, call.link, fetched.isoformat(), status, reason))


def store(data: Path, source: str, call: FetchedCall, page: bytes, fetched: dt.datetime) -> None:
    folder = _raw(data) / source
    folder.mkdir(parents=True, exist_ok=True)
    name = code(call.identifier)
    (folder / f"{name}.html").write_bytes(page)
    if not isinstance(call.record, NoRecord):
        record = json.dumps(call.record, indent=1, ensure_ascii=False) + "\n"
        (folder / f"{name}.json").write_bytes(record.encode("utf-8"))
    _add_call_row(data, source, call, fetched, "saved", "")


def store_failure(data: Path, source: str, call: FetchedCall, fetched: dt.datetime, reason: str) -> None:
    _add_call_row(data, source, call, fetched, "failed", reason)


def store_run(data: Path, source: str, link: str, fetched: dt.datetime, outcome: Outcome, reason: str) -> None:
    _add_row(data, ("", source, "", "", link, fetched.isoformat(), outcome, reason))


def stored(data: Path, call: Saved) -> JSON | bytes:
    page = _raw(data) / call.source / f"{code(call.identifier)}.html"
    record = page.with_suffix(".json")
    return json.loads(record.read_bytes()) if record.exists() else page.read_bytes()


def _card_code(identifier: str) -> str:
    return code(identifier)[:SHORT_CODE]


def card_name(call: Saved) -> str:
    title = re.sub(r"[^a-z0-9]+", "-", call.title.lower()).strip("-")
    # A long title is cut at a hyphen, so a word is never cut in half.
    if len(title) > SHORT_TITLE:
        title = title[: SHORT_TITLE + 1].rsplit("-", 1)[0]
    return f"{call.day}-{title}-{_card_code(call.identifier)}.md"


def carded(data: Path, call: Saved) -> bool:
    return any(_cards(data).glob(f"*-{_card_code(call.identifier)}.md"))


def store_card(data: Path, call: Saved, card: str) -> None:
    _cards(data).mkdir(parents=True, exist_ok=True)
    (_cards(data) / card_name(call)).write_bytes(card.encode("utf-8"))


def cards(data: Path) -> list[tuple[str, str]]:
    return [
        (path.relative_to(data).as_posix(), path.read_bytes().decode("utf-8"))
        for path in sorted(_cards(data).glob("*.md"))
    ]


def store_feed(data: Path, feed: str) -> None:
    (data / "feed.xml").write_bytes(feed.encode("utf-8"))


def store_reading(data: Path, call: Saved, fetched: dt.datetime, status: Reading, reason: str) -> None:
    _add_call_row(data, call.source, call, fetched, status, reason)


def store_answer(data: Path, call: Saved, fetched: dt.datetime, word: AnswerWord, answer: str) -> None:
    _add_call_row(data, call.source, call, fetched, word, answer)
