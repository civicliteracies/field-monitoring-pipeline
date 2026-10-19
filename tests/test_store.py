import csv
import datetime as dt
import json
from pathlib import Path

import pytest

from field_monitoring_pipeline.fetch import JSON, FetchedCall
from field_monitoring_pipeline.store import (
    COLUMNS,
    Saved,
    card_name,
    carded,
    code,
    saved,
    store,
    store_card,
    store_failure,
    store_reading,
    store_run,
    stored_record,
)

SOURCE = "eu-funding-tenders"
FETCHED = dt.datetime(2026, 9, 27, 6, 0, tzinfo=dt.UTC)
STAMP = "2026-09-27T06:00:00+00:00"
PAGE = b"<html>caf\xe9\r\n\x00</html>"
IDENTIFIER = "HORIZON-CL2-2027-01-HERITAGE-06"
RECORD: JSON = {"summary": "Tourism “for all”", "metadata": {"identifier": [IDENTIFIER]}, "weight": 1.5}
STORED_RECORD = (json.dumps(RECORD, indent=1, ensure_ascii=False) + "\n").encode()
CALL = FetchedCall(IDENTIFIER, "https://example.org/calls/one", "Tourism “for all”", RECORD)
OTHER = FetchedCall("EuropeAid/187605/DD/ACT/ID", "https://example.org/calls/two", "Two", {})
SAVED = Saved(SOURCE, IDENTIFIER, CALL.title, CALL.link, dt.date(2026, 9, 27))
OTHER_SAVED = Saved(SOURCE, OTHER.identifier, OTHER.title, OTHER.link, dt.date(2026, 9, 28))


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
    assert saved(tmp_path) == [SAVED]


def test_a_record_that_cannot_be_written_stops_the_store(tmp_path: Path) -> None:
    unwritable = FetchedCall("X", "https://example.org/calls/x", "X", {"title": "\udc80"})
    with pytest.raises(UnicodeEncodeError):
        store(tmp_path, SOURCE, unwritable, PAGE, FETCHED)
    assert saved(tmp_path) == []


def test_saved_holds_each_stored_call_with_the_day_it_was_saved(tmp_path: Path) -> None:
    assert saved(tmp_path) == []
    store(tmp_path, SOURCE, CALL, PAGE, FETCHED)
    assert saved(tmp_path) == [SAVED]
    store(tmp_path, SOURCE, OTHER, PAGE, FETCHED + dt.timedelta(days=1))
    assert saved(tmp_path) == [SAVED, OTHER_SAVED]


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
    assert saved(tmp_path) == []
    store(tmp_path, SOURCE, CALL, PAGE, FETCHED)
    assert saved(tmp_path) == [SAVED]


def test_the_runs_row_names_no_call_and_is_not_a_saved_call(tmp_path: Path) -> None:
    link = "https://example.org/search"
    store_run(tmp_path, SOURCE, link, FETCHED, "successful", "4 calls, 4 new, 0 failed")
    store_run(tmp_path, SOURCE, link, FETCHED, "failed", "4 calls, 3 new, 1 failed")
    store_run(tmp_path, SOURCE, link, FETCHED, "nothing new", "4 calls, 0 new, 0 failed")
    assert log(tmp_path) == [
        list(COLUMNS),
        ["", SOURCE, "", "", link, STAMP, "successful", "4 calls, 4 new, 0 failed"],
        ["", SOURCE, "", "", link, STAMP, "failed", "4 calls, 3 new, 1 failed"],
        ["", SOURCE, "", "", link, STAMP, "nothing new", "4 calls, 0 new, 0 failed"],
    ]
    assert saved(tmp_path) == []


@pytest.mark.parametrize(
    ("title", "name"),
    [
        pytest.param("Tourism “for all”", "2026-09-27-tourism-for-all-b710c74df0.md", id="quotation marks"),
        pytest.param(
            "Strengthening Europe’s resilience through improved capacity of farmers in coping with risks and crises",
            "2026-09-27-strengthening-europe-s-resilience-through-improved-capacity-b710c74df0.md",
            id="long title with an apostrophe",
        ),
        pytest.param(
            "Support for independent news media and journalists in Europe",
            "2026-09-27-support-for-independent-news-media-and-journalists-in-europe-b710c74df0.md",
            id="title of 60 characters",
        ),
        pytest.param(
            "Support for independent news media and journalists in Europe today",
            "2026-09-27-support-for-independent-news-media-and-journalists-in-europe-b710c74df0.md",
            id="cut where the 61st character is a hyphen",
        ),
    ],
)
def test_a_card_s_name_is_the_day_saved_a_short_title_and_the_code(title: str, name: str) -> None:
    assert card_name(Saved(SOURCE, IDENTIFIER, title, CALL.link, dt.date(2026, 9, 27))) == name


def test_a_card_is_written_and_found_by_its_code(tmp_path: Path) -> None:
    text = '---\ntitle: "Tourism \\u201cfor all\\u201d"\n---\n\n# Tourism “for all”\n'
    assert not carded(tmp_path, SAVED)
    store_card(tmp_path, SAVED, text)
    card = tmp_path / "calls" / "2026-09-27-tourism-for-all-b710c74df0.md"
    assert card.read_bytes() == text.encode()
    assert b"\r" not in card.read_bytes()
    assert carded(tmp_path, SAVED)
    assert not carded(tmp_path, OTHER_SAVED)


def test_a_stored_record_is_read_back(tmp_path: Path) -> None:
    store(tmp_path, SOURCE, CALL, PAGE, FETCHED)
    assert stored_record(tmp_path, SAVED) == RECORD


def test_the_reading_s_row_names_the_call_and_what_the_reading_met(tmp_path: Path) -> None:
    store_reading(tmp_path, SAVED, FETCHED, "card written", "funder: empty, because the model marked it not stated")
    store_reading(tmp_path, SAVED, FETCHED, "failed", "ValueError: no budget line")
    row = [code(IDENTIFIER), SOURCE, IDENTIFIER, CALL.title, CALL.link, STAMP]
    assert log(tmp_path)[1:] == [
        [*row, "card written", "funder: empty, because the model marked it not stated"],
        [*row, "failed", "ValueError: no budget line"],
    ]
    assert saved(tmp_path) == []
