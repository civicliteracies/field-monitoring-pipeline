"""Store what the run collected, under the data folder.

Each saved call has two files in its source's folder: its web page as downloaded and the source's
record of it. Both are named by a code made from the call's identifier. One log beside the folders
has a row for each call the run tried, saved or failed, and for a search that failed. The files are
written first and the row last, and a call counts as stored once it has a saved row.
"""

import csv
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Literal

from field_monitoring_pipeline.fetch import FetchedCall

COLUMNS = ("code", "source", "identifier", "title", "link", "fetched", "status", "reason")
type Status = Literal["saved", "failed"]
type Row = tuple[str, str, str, str, str, str, Status, str]


def code(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _raw(data: Path) -> Path:
    return data / "raw"


def _log(data: Path) -> Path:
    return _raw(data) / "log.csv"


def saved(data: Path) -> set[tuple[str, str]]:
    log = _log(data)
    if not log.exists():
        return set()
    with log.open(encoding="utf-8", newline="") as file:
        return {(row["source"], row["identifier"]) for row in csv.DictReader(file) if row["status"] == "saved"}


def _add_row(data: Path, row: Row) -> None:
    _raw(data).mkdir(parents=True, exist_ok=True)
    with _log(data).open("a", encoding="utf-8", newline="") as file:
        writer = csv.writer(file, lineterminator="\n")
        if file.tell() == 0:
            writer.writerow(COLUMNS)
        writer.writerow(row)


def _add_call_row(
    data: Path, source: str, call: FetchedCall, fetched: dt.datetime, status: Status, reason: str
) -> None:
    name = code(call.identifier)
    _add_row(data, (name, source, call.identifier, call.title, call.link, fetched.isoformat(), status, reason))


def store(data: Path, source: str, call: FetchedCall, page: bytes, fetched: dt.datetime) -> None:
    folder = _raw(data) / source
    folder.mkdir(parents=True, exist_ok=True)
    name = code(call.identifier)
    (folder / f"{name}.html").write_bytes(page)
    record = json.dumps(call.record, indent=1, ensure_ascii=False) + "\n"
    (folder / f"{name}.json").write_bytes(record.encode("utf-8"))
    _add_call_row(data, source, call, fetched, "saved", "")


def store_failure(data: Path, source: str, call: FetchedCall, fetched: dt.datetime, reason: str) -> None:
    _add_call_row(data, source, call, fetched, "failed", reason)


def store_search_failure(data: Path, source: str, link: str, fetched: dt.datetime, reason: str) -> None:
    _add_row(data, ("", source, "", "", link, fetched.isoformat(), "failed", reason))
