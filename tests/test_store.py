import csv
import datetime as dt
import json
from pathlib import Path

import pytest

from field_monitoring_pipeline.fetch import JSON, FetchedCall
from field_monitoring_pipeline.store import COLUMNS, code, saved, store, store_failure

SOURCE = "eu-funding-tenders"
FETCHED = dt.datetime(2026, 9, 27, 6, 0, tzinfo=dt.UTC)
STAMP = "2026-09-27T06:00:00+00:00"
PAGE = b"<html>caf\xe9\r\n\x00</html>"
IDENTIFIER = "HORIZON-CL2-2027-01-HERITAGE-06"
RECORD: JSON = {"summary": "Tourism “for all”", "metadata": {"identifier": [IDENTIFIER]}, "weight": 1.5}
STORED_RECORD = (json.dumps(RECORD, indent=1, ensure_ascii=False) + "\n").encode()
CALL = FetchedCall(IDENTIFIER, "https://example.org/calls/one", "Tourism “for all”", RECORD)
OTHER = FetchedCall("EuropeAid/187605/DD/ACT/ID", "https://example.org/calls/two", "Two", {})


def log(data: Path) -> list[list[str]]:
    with (data / "raw" / "log.csv").open(encoding="utf-8", newline="") as file:
        return list(csv.reader(file))


def test_code_is_the_sha256_of_the_identifier() -> None:
    assert code(IDENTIFIER) == "b710c74df0c35d264045756f5cb89193914419912ed41939c80b9a8fb155d25f"
    assert code("é") == "4a99557e4033c3539de2eb65472017cad5f9557f7a0625a09f1c3f6e2ba69c4c"
    name = code(OTHER.identifier)
    assert len(name) == 64
    assert set(name) <= set("0123456789abcdef")


def test_store_writes_the_page_the_record_and_a_saved_row(tmp_path: Path) -> None:
    store(tmp_path, SOURCE, CALL, PAGE, FETCHED)
    folder = tmp_path / "raw" / SOURCE
    name = code(IDENTIFIER)
    assert (folder / f"{name}.html").read_bytes() == PAGE
    assert (folder / f"{name}.json").read_bytes() == STORED_RECORD
    row = [name, SOURCE, IDENTIFIER, CALL.title, CALL.link, STAMP, "saved", ""]
    assert log(tmp_path) == [list(COLUMNS), row]


def test_the_row_is_written_last_and_a_cut_call_is_stored_again(tmp_path: Path) -> None:
    record = tmp_path / "raw" / SOURCE / f"{code(IDENTIFIER)}.json"
    page = record.with_suffix(".html")
    record.mkdir(parents=True)
    with pytest.raises(OSError):
        store(tmp_path, SOURCE, CALL, PAGE, FETCHED)
    assert page.read_bytes() == PAGE
    assert not (tmp_path / "raw" / "log.csv").exists()
    record.rmdir()
    record.write_bytes(b"cut short")
    page.write_bytes(b"cut short")
    store(tmp_path, SOURCE, CALL, PAGE, FETCHED)
    assert (page.read_bytes(), record.read_bytes()) == (PAGE, STORED_RECORD)
    assert saved(tmp_path) == {(SOURCE, IDENTIFIER)}


def test_a_record_that_cannot_be_written_stops_the_store(tmp_path: Path) -> None:
    unwritable = FetchedCall("X", "https://example.org/calls/x", "X", {"title": "\udc80"})
    with pytest.raises(UnicodeEncodeError):
        store(tmp_path, SOURCE, unwritable, PAGE, FETCHED)
    assert saved(tmp_path) == set()


def test_saved_holds_each_stored_call(tmp_path: Path) -> None:
    assert saved(tmp_path) == set()
    store(tmp_path, SOURCE, CALL, PAGE, FETCHED)
    assert saved(tmp_path) == {(SOURCE, IDENTIFIER)}


def test_the_log_has_one_header_and_no_windows_line_ending(tmp_path: Path) -> None:
    store(tmp_path, SOURCE, CALL, PAGE, FETCHED)
    store(tmp_path, SOURCE, OTHER, PAGE, FETCHED)
    rows = log(tmp_path)
    assert len(rows) == 3
    assert rows[0] == ["code", "source", "identifier", "title", "link", "fetched", "status", "reason"]
    assert b"\r" not in (tmp_path / "raw" / "log.csv").read_bytes()


def test_an_empty_log_gets_its_header(tmp_path: Path) -> None:
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / "log.csv").write_bytes(b"")
    store(tmp_path, SOURCE, CALL, PAGE, FETCHED)
    assert log(tmp_path)[0] == list(COLUMNS)


def test_a_failed_call_has_a_failed_row_and_no_file_until_it_is_stored(tmp_path: Path) -> None:
    reason = "httpx2.HTTPStatusError: Redirect response '301 Moved Permanently'\nRedirect location: 'x'"
    store_failure(tmp_path, SOURCE, CALL, FETCHED, reason)
    row = [code(IDENTIFIER), SOURCE, IDENTIFIER, CALL.title, CALL.link, STAMP, "failed", reason]
    assert log(tmp_path) == [list(COLUMNS), row]
    assert [path.name for path in tmp_path.rglob("*") if path.is_file()] == ["log.csv"]
    assert saved(tmp_path) == set()
    store(tmp_path, SOURCE, CALL, PAGE, FETCHED)
    assert saved(tmp_path) == {(SOURCE, IDENTIFIER)}
