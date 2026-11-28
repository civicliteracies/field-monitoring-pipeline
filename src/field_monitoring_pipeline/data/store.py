"""Store what the run collected and wrote, under the data folder.

An item is a call or a report, and each kind has its own word. Each saved item has its web page as
downloaded in its source's folder and, when the source gives one, the source's record of it. Both are
named by a code made from the item's identifier. A call's page ends in `.html`; a report's download ends
in the kind of file its first bytes show, and a report's record in the form it came in.
A saved item's row holds its kind's saved word, so a
kind's run finds only its own items. A saved item is given back as its record, or as its page when it
has no record. Each item carded has a card in its kind's folder, one for all sources, named by the day
it was saved, its title and the first ten characters of the code of its card key, which is the item's
identifier. One log beside the folders has a row for each item the run tried, saved or failed; for
each answer the model gave while reading an item, first or second, with the answer as it came; and
for each item checked, set aside, card written or failed. A document already held, read once more for a
later kind, has the same rows, each naming that kind: its answers, then read or failed; an item found in
it has its document's identifier, the kind and its order, and its own rows, as an item does.
It also has a row for each source, which says how the run ended for it, and a row for each card the
feed could not read back, which was left out of the feed. What a step produced is written before the
row that says the step is done. The feed, built from the cards, sits beside them and is written again
on every run that reaches its end.
A card's record is written between two `---` lines, one field per line, each value in JSON, and a field
that holds parts with its parts indented under it; it is read back by the card's kind alone, into that
kind's record. A card's day is read back from its file name.
An item counts as stored once it has its kind's saved row, and as read once it has a card or a set
aside row.
"""

import csv
import datetime as dt
import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal, NewType, cast, get_args, overload

from pydantic import BaseModel, TypeAdapter

from field_monitoring_pipeline.data.fetch import JSON, Fetched, Form, NoRecord, Posted
from field_monitoring_pipeline.data.models import Call, Held, Kind, Report

FORMS: tuple[Form, ...] = get_args(Form.__value__)

# The line above and below a card's record.
FENCE = "---"
COLUMNS = ("code", "source", "identifier", "title", "link", "fetched", "status", "reason")
SHORT_TITLE = 60
SHORT_CODE = 10
# The word a saved item's row holds, one for each kind.
type SavedWord = Literal["saved", "report saved"]
type Status = SavedWord | Literal["failed"]
# The rows that say an item was read without a card.
type Finished = Literal["set aside"]
type Reading = Literal["card written", "failed"] | Finished
type AnswerWord = Literal["first answer", "second answer"]
type Outcome = Literal["successful", "failed", "nothing new"]
type LeftOut = Literal["left out of the feed"]
type HeldWord = Literal["read", "failed"]
# A held document's status: its word and the kind it was read for, written as "<word> for <kind>" by _for alone.
HeldStatus = NewType("HeldStatus", str)
type Row = tuple[str, str, str, str, str, str, Status | Reading | AnswerWord | Outcome | LeftOut | HeldStatus, str]


@dataclass(frozen=True)
class Saved:
    source: str
    identifier: str
    title: str
    link: str
    day: dt.date


@dataclass(frozen=True)
class Layout:
    """A kind's data: the word its saved items' rows hold, and the kinds whose documents its run reads once more."""

    saved: SavedWord
    holds: tuple[Held, ...]


def layout(kind: Kind) -> Layout:
    match kind:
        case "calls":
            return Layout("saved", ())
        case "reports":
            return Layout("report saved", ("calls",))


# The kind of file a download is, which its stored name ends with. An old Word or Excel file shares one
# opening, and every old file met on the real sources was a Word file; a packed file holding neither a Word
# document nor a workbook stays a packed file.
type FileType = Literal["html", "pdf", "docx", "xlsx", "doc", "zip"]
FILE_TYPES: tuple[FileType, ...] = get_args(FileType.__value__)


@dataclass(frozen=True)
class Downloaded:
    type: FileType
    content: bytes


def file_type(content: bytes) -> FileType:
    # Told by the file's first bytes, never by its address or its label, which can name the wrong format.
    if content.startswith(b"%PDF"):
        return "pdf"
    if content.startswith(b"\xd0\xcf\x11\xe0"):
        return "doc"
    if not content.startswith(b"PK\x03\x04"):
        return "html"
    try:
        names = set(zipfile.ZipFile(io.BytesIO(content)).namelist())
    except zipfile.BadZipFile:
        return "zip"
    if "word/document.xml" in names:
        return "docx"
    if "xl/workbook.xml" in names:
        return "xlsx"
    return "zip"


def _download_type(kind: Kind, page: bytes) -> FileType:
    match kind:
        case "calls":
            return "html"
        case "reports":
            return file_type(page)


# The key a card is named and found by.
CardKey = NewType("CardKey", str)


def item_key(item: Saved) -> CardKey:
    return CardKey(item.identifier)


def code(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _raw(data: Path) -> Path:
    return data / "raw"


def _log(data: Path) -> Path:
    return _raw(data) / "log.csv"


def _cards(data: Path, kind: Kind) -> Path:
    # A kind's cards are in the folder its word names.
    return data / kind


def _rows(data: Path) -> list[dict[str, str]]:
    log = _log(data)
    if not log.exists():
        return []
    with log.open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def saved(data: Path, kind: Kind) -> list[Saved]:
    word = layout(kind).saved
    return [
        Saved(
            row["source"],
            row["identifier"],
            row["title"],
            row["link"],
            dt.datetime.fromisoformat(row["fetched"]).date(),
        )
        for row in _rows(data)
        if row["status"] == word
    ]


def unread(data: Path, kind: Kind) -> list[Saved]:
    # Saved, with no card and no row that says it was read without one, both under its card key, in a fixed order.
    finished = {CardKey(row["identifier"]) for row in _rows(data) if row["status"] in get_args(Finished.__value__)}
    return sorted(
        (
            item
            for item in saved(data, kind)
            if item_key(item) not in finished and not carded(data, kind, item_key(item))
        ),
        key=lambda item: (item.source, item.identifier),
    )


def _add_row(data: Path, row: Row) -> None:
    _raw(data).mkdir(parents=True, exist_ok=True)
    with _log(data).open("a", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        if file.tell() == 0:
            writer.writerow(COLUMNS)
        writer.writerow(row)


def _add_item_row(
    data: Path,
    source: str,
    item: Fetched | Saved,
    fetched: dt.datetime,
    status: Status | Reading | AnswerWord | HeldStatus,
    reason: str,
) -> None:
    name = code(item.identifier)
    # An item its file could not title is named by its address.
    title = item.link if item.title is None else item.title
    _add_row(data, (name, source, item.identifier, title, item.link, fetched.isoformat(), status, reason))


def _json(record: JSON) -> bytes:
    return (json.dumps(record, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def store(data: Path, kind: Kind, source: str, item: Fetched, page: bytes, fetched: dt.datetime) -> None:
    folder = _raw(data) / source
    folder.mkdir(parents=True, exist_ok=True)
    name = code(item.identifier)
    (folder / f"{name}.{_download_type(kind, page)}").write_bytes(page)
    match item.record:
        case NoRecord():
            pass
        # A report source's record is named by its form, so the reading knows which rule reads it.
        case Posted(form=form, body=body):
            (folder / f"{name}.{form}.json").write_bytes(_json(body))
        case record:
            (folder / f"{name}.json").write_bytes(_json(record))
    _add_item_row(data, source, item, fetched, layout(kind).saved, "")


def store_failure(data: Path, source: str, item: Fetched, fetched: dt.datetime, reason: str) -> None:
    _add_item_row(data, source, item, fetched, "failed", reason)


def store_run(data: Path, source: str, link: str, fetched: dt.datetime, outcome: Outcome, reason: str) -> None:
    _add_row(data, ("", source, "", "", link, fetched.isoformat(), outcome, reason))


@overload
def stored(data: Path, kind: Literal["calls"], item: Saved) -> JSON | bytes: ...
@overload
def stored(data: Path, kind: Literal["reports"], item: Saved) -> Posted | Downloaded: ...
def stored(data: Path, kind: Kind, item: Saved) -> JSON | Posted | Downloaded | bytes:
    folder = _raw(data) / item.source
    name = code(item.identifier)
    match kind:
        case "calls":
            record = folder / f"{name}.json"
            return json.loads(record.read_bytes()) if record.exists() else (folder / f"{name}.html").read_bytes()
        case "reports":
            for form in FORMS:
                if (record := folder / f"{name}.{form}.json").exists():
                    return Posted(form, json.loads(record.read_bytes()))
            found: list[FileType] = [kept for kept in FILE_TYPES if (folder / f"{name}.{kept}").exists()]
            [kept] = found
            return Downloaded(kept, (folder / f"{name}.{kept}").read_bytes())


def _card_code(key: CardKey) -> str:
    return code(key)[:SHORT_CODE]


def card_name(day: dt.date, title: str, key: CardKey) -> str:
    title = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    # A long title is cut at a hyphen, so a word is never cut in half.
    if len(title) > SHORT_TITLE:
        title = title[: SHORT_TITLE + 1].rsplit("-", 1)[0]
    return f"{day}-{title}-{_card_code(key)}.md"


def carded(data: Path, kind: Kind, key: CardKey) -> bool:
    return any(_cards(data, kind).glob(f"*-{_card_code(key)}.md"))


def store_card(data: Path, kind: Kind, item: Saved, key: CardKey, card: str) -> None:
    _cards(data, kind).mkdir(parents=True, exist_ok=True)
    (_cards(data, kind) / card_name(item.day, item.title, key)).write_bytes(card.encode("utf-8"))


def card_day(path: str) -> dt.date:
    # The day card_name wrote at the start of a card's file name.
    return dt.date.fromisoformat(PurePosixPath(path).name[:10])


def cards(data: Path, kind: Kind) -> list[tuple[str, str]]:
    return [
        (path.relative_to(data).as_posix(), path.read_bytes().decode("utf-8"))
        for path in sorted(_cards(data, kind).glob("*.md"))
    ]


def record_block(record: BaseModel) -> list[str]:
    lines = [FENCE]
    for name, value in record.model_dump(mode="json").items():
        if isinstance(value, dict):
            lines.append(f"{name}:")
            lines += [f"  {part}: {json.dumps(inner)}" for part, inner in cast("dict[str, object]", value).items()]
        else:
            lines.append(f"{name}: {json.dumps(value)}")
    return [*lines, FENCE]


def _fields(text: str) -> dict[str, object]:
    lines = text.split("\n")
    fields: dict[str, object] = {}
    parts: dict[str, object] = {}
    for line in lines[1 : lines.index(FENCE, 1)]:
        name, _, value = line.strip().partition(":")
        if line.startswith("  "):
            parts[name] = json.loads(value)
        elif value:
            fields[name] = json.loads(value)
        else:
            fields[name] = parts = {}
    return fields


# One reader per kind, each declared with its record type.
_CALL: TypeAdapter[Call] = TypeAdapter(Call)
_REPORT: TypeAdapter[Report] = TypeAdapter(Report)


@overload
def read_card(kind: Literal["calls"], text: str) -> Call: ...
@overload
def read_card(kind: Literal["reports"], text: str) -> Report: ...
def read_card(kind: Kind, text: str) -> Call | Report:
    fields = _fields(text)
    match kind:
        case "calls":
            return _CALL.validate_python(fields)
        case "reports":
            return _REPORT.validate_python(fields)


def store_feed(data: Path, feed: str) -> None:
    (data / "feed.xml").write_bytes(feed.encode("utf-8"))


def store_left_out(data: Path, link: str, fetched: dt.datetime, reason: str) -> None:
    # A card left out has no code, source, identifier or title to copy; only its web address is written.
    _add_row(data, ("", "", "", "", link, fetched.isoformat(), "left out of the feed", reason))


def store_reading(data: Path, item: Saved, fetched: dt.datetime, status: Reading, reason: str) -> None:
    _add_item_row(data, item.source, item, fetched, status, reason)


def store_answer(data: Path, item: Saved, fetched: dt.datetime, word: AnswerWord, answer: str) -> None:
    _add_item_row(data, item.source, item, fetched, word, answer)


def _for(word: AnswerWord | HeldWord, kind: Kind) -> HeldStatus:
    return HeldStatus(f"{word} for {kind}")


def store_held_answer(
    data: Path, kind: Kind, document: Saved, fetched: dt.datetime, word: AnswerWord, answer: str
) -> None:
    _add_item_row(data, document.source, document, fetched, _for(word, kind), answer)


def store_held(data: Path, kind: Kind, document: Saved, fetched: dt.datetime, word: HeldWord, reason: str) -> None:
    _add_item_row(data, document.source, document, fetched, _for(word, kind), reason)


def held_read(data: Path, kind: Kind) -> set[tuple[str, str]]:
    read = _for("read", kind)
    return {(row["source"], row["identifier"]) for row in _rows(data) if row["status"] == read}


def earlier(data: Path, kind: Kind, document: Saved) -> tuple[str, ...]:
    # The answers a stopped reading left: those after the document's last failed row for this kind.
    first, second, failed = _for("first answer", kind), _for("second answer", kind), _for("failed", kind)
    answers: list[str] = []
    for row in _rows(data):
        if (row["source"], row["identifier"]) != (document.source, document.identifier):
            continue
        if row["status"] == failed:
            answers = []
        elif row["status"] == first:
            answers = [row["reason"]]
        elif row["status"] == second:
            answers.append(row["reason"])
    return tuple(answers)


def found_item(document: Saved, kind: Kind, order: int, title: str, day: dt.date) -> Saved:
    # An item found in a held document has no saved row; its identifier carries its document's.
    return Saved(document.source, f"{document.identifier}#{kind}-{order}", title, document.link, day)


def ended(data: Path) -> set[str]:
    # The identifiers whose rows say their reading ended: a card written, or read without one.
    words = {"card written", *get_args(Finished.__value__)}
    return {row["identifier"] for row in _rows(data) if row["status"] in words}
