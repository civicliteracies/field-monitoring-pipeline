import datetime as dt
import io
import json
import zipfile
from pathlib import Path
from typing import get_args

import pytest

from field_monitoring_pipeline.data.fetch import JSON, NO_RECORD, Fetched, Posted
from field_monitoring_pipeline.data.models import Kind, Quoted, Report, Topic
from field_monitoring_pipeline.data.store import (
    COLUMNS,
    Downloaded,
    FileType,
    Layout,
    Saved,
    card_day,
    card_name,
    carded,
    cards,
    code,
    item_key,
    layout,
    read_card,
    record_block,
    saved,
    store,
    store_answer,
    store_card,
    store_failure,
    store_feed,
    store_left_out,
    store_reading,
    store_run,
    stored,
    unread,
)
from field_monitoring_pipeline.presentation.publish import CARDS
from tests.samples import FETCHED, IDENTIFIER, NO_MATCH, SOURCE, STAMP, log

PAGE = b"<html>caf\xe9\r\n\x00</html>"
RECORD: JSON = {"summary": "Tourism “for all”", "metadata": {"identifier": [IDENTIFIER]}, "weight": 1.5}
STORED_RECORD = (json.dumps(RECORD, indent=1, ensure_ascii=False) + "\n").encode()
CALL = Fetched(IDENTIFIER, "https://example.org/calls/one", "Tourism “for all”", RECORD)
OTHER = Fetched("EuropeAid/187605/DD/ACT/ID", "https://example.org/calls/two", "Two", {})
SAVED = Saved(SOURCE, IDENTIFIER, "Tourism “for all”", CALL.link, dt.date(2026, 9, 27))
OTHER_SAVED = Saved(SOURCE, OTHER.identifier, "Two", OTHER.link, dt.date(2026, 9, 28))


def test_code_is_the_sha256_of_the_identifier() -> None:
    assert code(IDENTIFIER) == "b710c74df0c35d264045756f5cb89193914419912ed41939c80b9a8fb155d25f"
    assert code("é") == "4a99557e4033c3539de2eb65472017cad5f9557f7a0625a09f1c3f6e2ba69c4c"
    name = code(OTHER.identifier)
    assert len(name) == 64
    assert set(name) <= set("0123456789abcdef")


def test_store_writes_the_page_the_record_and_a_saved_row(tmp_path: Path) -> None:
    store(tmp_path, "calls", SOURCE, CALL, PAGE, FETCHED)
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
        store(tmp_path, "calls", SOURCE, CALL, PAGE, FETCHED)
    assert page.read_bytes() == PAGE
    assert not (tmp_path / "raw" / "log.csv").exists()
    record.rmdir()
    record.write_bytes(b"cut short")
    page.write_bytes(b"cut short")
    store(tmp_path, "calls", SOURCE, CALL, PAGE, FETCHED)
    assert (page.read_bytes(), record.read_bytes()) == (PAGE, STORED_RECORD)
    assert saved(tmp_path, "calls") == [SAVED]


def test_a_record_that_cannot_be_written_stops_the_store(tmp_path: Path) -> None:
    unwritable = Fetched("X", "https://example.org/calls/x", "X", {"title": "\udc80"})
    with pytest.raises(UnicodeEncodeError):
        store(tmp_path, "calls", SOURCE, unwritable, PAGE, FETCHED)
    assert saved(tmp_path, "calls") == []


def test_saved_holds_each_stored_call_with_the_day_it_was_saved(tmp_path: Path) -> None:
    assert saved(tmp_path, "calls") == []
    store(tmp_path, "calls", SOURCE, CALL, PAGE, FETCHED)
    assert saved(tmp_path, "calls") == [SAVED]
    store(tmp_path, "calls", SOURCE, OTHER, PAGE, FETCHED + dt.timedelta(days=1))
    assert saved(tmp_path, "calls") == [SAVED, OTHER_SAVED]


def test_each_kind_has_its_saved_word_and_the_kinds_its_run_reads_once_more() -> None:
    assert {kind: layout(kind) for kind in get_args(Kind.__value__)} == {
        "calls": Layout("saved", ()),
        "reports": Layout("report saved", ("calls",)),
    }


def packed(*names: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as folder:
        for name in names:
            folder.writestr(name, "<x/>")
    return buffer.getvalue()


@pytest.mark.parametrize(
    ("content", "kind"),
    [
        pytest.param(b"%PDF-1.7\n", "pdf", id="a PDF"),
        pytest.param(packed("[Content_Types].xml", "word/document.xml"), "docx", id="a Word file"),
        pytest.param(packed("[Content_Types].xml", "xl/workbook.xml"), "xlsx", id="a spreadsheet"),
        pytest.param(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "doc", id="an old Word or Excel file"),
        pytest.param(packed("other.xml"), "zip", id="a packed file holding neither part"),
        pytest.param(b"PK\x03\x04 cut short", "zip", id="a packed file that cannot be opened"),
        pytest.param(PAGE, "html", id="anything else"),
    ],
)
def test_a_report_s_download_is_named_by_the_kind_its_first_bytes_show(
    tmp_path: Path, content: bytes, kind: FileType
) -> None:
    link = "https://example.org/report.doc"
    store(tmp_path, "reports", "links", Fetched(link, link, link, NO_RECORD), content, FETCHED)
    assert [path.name for path in (tmp_path / "raw" / "links").iterdir()] == [f"{code(link)}.{kind}"]
    assert stored(tmp_path, "reports", Saved("links", link, link, link, FETCHED.date())) == Downloaded(kind, content)


def test_a_saved_report_is_never_a_saved_call_and_its_card_is_in_its_own_folder(tmp_path: Path) -> None:
    store(tmp_path, "reports", SOURCE, CALL, PAGE, FETCHED)
    assert saved(tmp_path, "calls") == []
    assert unread(tmp_path, "calls") == []
    assert saved(tmp_path, "reports") == [SAVED]
    assert log(tmp_path)[1][6] == "report saved"
    store_card(tmp_path, "reports", SAVED, item_key(SAVED), "one")
    assert carded(tmp_path, "reports", item_key(SAVED))
    assert not carded(tmp_path, "calls", item_key(SAVED))
    assert [path for path, _ in cards(tmp_path, "reports")] == [
        f"reports/{card_name(SAVED.day, SAVED.title, item_key(SAVED))}"
    ]


def test_a_card_s_day_is_the_day_its_name_was_written_with(tmp_path: Path) -> None:
    store_card(tmp_path, "calls", SAVED, item_key(SAVED), "one")
    [(path, _)] = cards(tmp_path, "calls")
    assert card_day(path) == SAVED.day


def test_a_report_s_record_written_on_a_card_is_read_back_the_same() -> None:
    report = Report(
        title="ARK Solves",
        type="research or case study",
        organisation=Quoted(value="ARK", quote="ARK runs the programme.", found=True),
        audience=None,
        methodology=None,
        results=Quoted(value="1 200 schools", quote="It reached 1 200 schools.", found=False),
        duration=None,
        area=Quoted(value="Kenya", quote="in Kenya", found=True),
        published=dt.date(2025, 3, 4),
        topics=(Topic(name="open-data", mark="primary"),),
        link="https://data.org/stories/ark-solves/",
        identifier="https://data.org/stories/ark-solves/",
        model="gemini",
        instructions="reports-v1",
    )
    text = "\n".join(record_block(report)) + "\n\nfor people\n"
    assert read_card("reports", text) == report
    with pytest.raises(ValueError, match="deadline\n  Field required"):
        read_card("calls", text)


def test_the_log_has_one_header_and_no_windows_line_ending(tmp_path: Path) -> None:
    store(tmp_path, "calls", SOURCE, CALL, PAGE, FETCHED)
    store(tmp_path, "calls", SOURCE, OTHER, PAGE, FETCHED)
    rows = log(tmp_path)
    assert len(rows) == 3
    assert rows[0] == ["code", "source", "identifier", "title", "link", "fetched", "status", "reason"]
    assert b"\r" not in (tmp_path / "raw" / "log.csv").read_bytes()


def test_an_empty_log_gets_its_header(tmp_path: Path) -> None:
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / "log.csv").write_bytes(b"")
    store(tmp_path, "calls", SOURCE, CALL, PAGE, FETCHED)
    assert log(tmp_path)[0] == list(COLUMNS)


def test_a_failed_call_has_a_failed_row_and_no_file_until_it_is_stored(tmp_path: Path) -> None:
    reason = "httpx2.HTTPStatusError: Redirect response '301 Moved Permanently'\nRedirect location: 'x'"
    store_failure(tmp_path, SOURCE, CALL, FETCHED, reason)
    row = [code(IDENTIFIER), SOURCE, IDENTIFIER, CALL.title, CALL.link, STAMP, "failed", reason]
    assert log(tmp_path) == [list(COLUMNS), row]
    assert [path.name for path in tmp_path.rglob("*") if path.is_file()] == ["log.csv"]
    assert saved(tmp_path, "calls") == []
    store(tmp_path, "calls", SOURCE, CALL, PAGE, FETCHED)
    assert saved(tmp_path, "calls") == [SAVED]


def test_a_card_left_out_of_the_feed_has_a_row_naming_the_card_and_is_not_a_saved_call(tmp_path: Path) -> None:
    link = CARDS + "calls/2026-09-27-two-b710c74df0.md"
    store_left_out(tmp_path, link, FETCHED, "ValueError: no record")
    assert log(tmp_path) == [
        list(COLUMNS),
        ["", "", "", "", link, STAMP, "left out of the feed", "ValueError: no record"],
    ]
    assert saved(tmp_path, "calls") == []


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
    assert saved(tmp_path, "calls") == []


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
    assert card_name(dt.date(2026, 9, 27), title, item_key(SAVED)) == name


def test_an_item_s_card_key_is_its_identifier() -> None:
    assert item_key(SAVED) == IDENTIFIER


def test_a_card_is_written_and_found_by_its_card_key(tmp_path: Path) -> None:
    text = '---\ntitle: "Tourism \\u201cfor all\\u201d"\n---\n\n# Tourism “for all”\n'
    assert not carded(tmp_path, "calls", item_key(SAVED))
    store_card(tmp_path, "calls", SAVED, item_key(SAVED), text)
    card = tmp_path / "calls" / "2026-09-27-tourism-for-all-b710c74df0.md"
    assert card.read_bytes() == text.encode()
    assert b"\r" not in card.read_bytes()
    assert carded(tmp_path, "calls", item_key(SAVED))
    assert not carded(tmp_path, "calls", item_key(OTHER_SAVED))


def test_the_cards_are_listed_with_their_paths_in_the_order_of_their_names(tmp_path: Path) -> None:
    assert cards(tmp_path, "calls") == []
    store_card(tmp_path, "calls", OTHER_SAVED, item_key(OTHER_SAVED), "two “x”")
    store_card(tmp_path, "calls", SAVED, item_key(SAVED), "one €")
    assert cards(tmp_path, "calls") == [
        ("calls/2026-09-27-tourism-for-all-b710c74df0.md", "one €"),
        (f"calls/2026-09-28-two-{code(OTHER.identifier)[:10]}.md", "two “x”"),
    ]


def test_the_feed_is_written_as_utf_8_with_line_feeds(tmp_path: Path) -> None:
    text = "<title>Tourism “for all” €</title>\n<link />\n"
    store_feed(tmp_path, text)
    assert (tmp_path / "feed.xml").read_bytes() == text.encode("utf-8")


def test_a_stored_record_is_read_back(tmp_path: Path) -> None:
    store(tmp_path, "calls", SOURCE, CALL, PAGE, FETCHED)
    assert stored(tmp_path, "calls", SAVED) == RECORD


def test_a_call_with_no_record_is_stored_as_its_page_alone_and_read_back_as_it(tmp_path: Path) -> None:
    link = "https://eiti.org/call-for-proposals/example-consultancy"
    store(tmp_path, "calls", "eiti", Fetched(link, link, "An example study", NO_RECORD), PAGE, FETCHED)
    assert [path.name for path in (tmp_path / "raw" / "eiti").iterdir()] == [f"{code(link)}.html"]
    assert stored(tmp_path, "calls", Saved("eiti", link, "An example study", link, dt.date(2026, 9, 27))) == PAGE
    assert log(tmp_path)[1] == [code(link), "eiti", link, "An example study", link, STAMP, "saved", ""]


def test_a_report_is_stored_by_the_form_of_its_record_beside_its_page(tmp_path: Path) -> None:
    post: JSON = {"link": "https://data.org/stories/one/", "content": {"rendered": "<p>Text</p>"}}
    link = "https://data.org/stories/one/"
    for form in ("wordpress", "feed"):
        store(tmp_path, "reports", form, Fetched(link, link, "One", Posted(form, post)), PAGE, FETCHED)
        saved_item = Saved(form, link, "One", link, FETCHED.date())
        assert {path.name for path in (tmp_path / "raw" / form).iterdir()} == {
            f"{code(link)}.html",
            f"{code(link)}.{form}.json",
        }
        assert stored(tmp_path, "reports", saved_item) == Posted(form, post)


def test_the_reading_s_row_names_the_call_and_what_the_reading_met(tmp_path: Path) -> None:
    store_reading(tmp_path, SAVED, FETCHED, "card written", "funder: empty, because the model marked it not stated")
    store_reading(tmp_path, SAVED, FETCHED, "failed", "ValueError: no budget line")
    store_reading(tmp_path, SAVED, FETCHED, "set aside", NO_MATCH)
    row = [code(IDENTIFIER), SOURCE, IDENTIFIER, CALL.title, CALL.link, STAMP]
    assert log(tmp_path)[1:] == [
        [*row, "card written", "funder: empty, because the model marked it not stated"],
        [*row, "failed", "ValueError: no budget line"],
        [*row, "set aside", NO_MATCH],
    ]
    assert saved(tmp_path, "calls") == []


def test_a_saved_call_is_unread_until_it_has_a_card_or_a_set_aside_row(tmp_path: Path) -> None:
    third = Fetched("A-THIRD", "https://example.org/calls/three", "Three", {})
    for call in (OTHER, CALL, third):
        store(tmp_path, "calls", SOURCE, call, PAGE, FETCHED)
    first, second, last = (Saved(SOURCE, c.identifier, c.title or "", c.link, SAVED.day) for c in (third, OTHER, CALL))
    assert unread(tmp_path, "calls") == [first, second, last]
    # A failed reading leaves a call unread; a card or a set aside row reads it.
    store_reading(tmp_path, first, FETCHED, "failed", "ValueError: no budget line")
    store_card(tmp_path, "calls", last, item_key(last), "one")
    store_reading(tmp_path, second, FETCHED, "set aside", NO_MATCH)
    assert unread(tmp_path, "calls") == [first]


def test_an_answer_row_holds_its_word_and_the_answer_whole(tmp_path: Path) -> None:
    answer = 'First, the call funds "news media", in Europe.\r\nThen,\ralone:\n\nfieldbook --type grant\n'
    store_answer(tmp_path, SAVED, FETCHED, "first answer", answer)
    store_answer(tmp_path, SAVED, FETCHED, "second answer", "")
    row = [code(IDENTIFIER), SOURCE, IDENTIFIER, CALL.title, CALL.link, STAMP]
    assert log(tmp_path)[1:] == [[*row, "first answer", answer], [*row, "second answer", ""]]
    assert saved(tmp_path, "calls") == []


def test_an_item_with_no_title_is_named_by_its_address_in_its_rows(tmp_path: Path) -> None:
    link = "https://example.org/reports/annual-2025.pdf"
    untitled = Fetched(link, link, None, NO_RECORD)
    store_failure(tmp_path, "links", untitled, FETCHED, "httpx2.ConnectError: no connection")
    store(tmp_path, "reports", "links", untitled, b"%PDF-1.7", FETCHED)
    assert [row[3] for row in log(tmp_path)[1:]] == [link, link]
    assert saved(tmp_path, "reports") == [Saved("links", link, link, link, FETCHED.date())]
