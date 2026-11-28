"""A reports run: its own reports, then each call already held, read once for the reports it names.

Recorded pages and scripted model answers only. The stand-in serves the reports' addresses it is given and the
model's address, and raises on any other, so a run that fetched a call source would fail. It answers the model's
address only for the key the tests hand to the run, and only for a text a test scripted.
"""

import json
from collections.abc import Callable, Mapping
from pathlib import Path

import httpx2
import pytest

from field_monitoring_pipeline.calls import run
from field_monitoring_pipeline.data.fetch import NO_RECORD, Fetched
from field_monitoring_pipeline.data.reading import ADDRESS
from field_monitoring_pipeline.data.store import (
    Saved,
    cards,
    earlier,
    found_item,
    item_key,
    read_card,
    saved,
    store,
    store_card,
    store_held_answer,
    store_reading,
)
from field_monitoring_pipeline.presentation.write import report_card
from tests.samples import (
    BOARD,
    EU,
    FETCHED,
    FOUND_ACCOUNTS,
    FOUND_NOTES,
    FOUND_STUDY,
    JOURNALISM,
    KEY,
    LOG,
    MISQUOTED,
    MISS_1,
    NO_LINE,
    NONE,
    NOTHING_READ,
    OFFER,
    REPLIES,
    REPORT,
    TOPIC_LIST,
    VIEWS,
    WATCH_LIST,
    files,
    log,
    pdf,
    stored,
)

SITE = "https://example.org/"
EXAMPLE, TRUST = VIEWS, "https://eiti.org/call-for-proposals/trust"
EU_CALL = EU.identifier
JOURNALISM_PAGE, ROADS_PAGE = SITE + "reports/journalism", SITE + "reports/roads"
TRAINED = "The Example Trust trained 40 reporters in data journalism."
WORKED = "It worked in the example country for two years."
PUBLISHED = "The Example Trust published its evaluation of journalism training."
# A sentence of the recorded EU call's own text, which names no report.
NEWS = "Key data gaps affecting the news media sectors at European level are addressed"
PAGES = {
    JOURNALISM_PAGE: (
        f"<html><head><title>Data journalism training</title></head><body><p>{TRAINED}</p><p>{WORKED}</p></body></html>"
    ).encode(),
    ROADS_PAGE: b"<html><head><title>Roads</title></head><body><p>The Example Trust repaired roads.</p></body></html>",
}
REPORTS = f"""
[source.field-reports]
name = "Example reports"
url = "{SITE}reports"
how = "report-links"
kind = "reports"
links = ["{JOURNALISM_PAGE}", "{ROADS_PAGE}"]
"""
# As the model answers: its reasoning first, then the one command line.
OWN_REPORT = (
    "In the proposal pass, the page names one organisation and one place.\n"
    f'fieldbook --type "research or case study" --organisation "The Example Trust" --organisation-quote "{TRAINED}" '
    "--audience-not-stated --methodology-not-stated --results-not-stated "
    f'--duration "two years" --duration-quote "{WORKED}" --area "the example country" --area-quote "{WORKED}"'
)
ONE = FOUND_STUDY.replace(
    "A study of journalism in the example country", "An evaluation of journalism training"
).replace(BOARD, PUBLISHED)
OWN_NOTES = [
    "who it was for: empty, because the model marked it not stated",
    "method: empty, because the model marked it not stated",
    "results: empty, because the model marked it not stated",
    "published: empty, because this source gives no date",
]
OWN_SET_ASIDE = "no phrase of the topic list in the title or labels; in the text, no two different phrases that are not weak within ten words of each other"
FOUND_SET_ASIDE = "no phrase of the topic list in the title; in the quoted sentences, no two different phrases that are not weak within ten words of each other"


def answer(content: str) -> str:
    # The model's scripted answer, by the instructions the request opens with and the text it holds.
    if content.startswith("You read one report"):
        assert TRAINED in content
        return OWN_REPORT
    assert content.startswith("You read one document")
    if "Example 2027 EITI Validation" in content:
        return f"{FOUND_STUDY}\n{FOUND_ACCOUNTS}"
    if PUBLISHED in content:
        return ONE
    # The EU call's record names no report; any other text is one no test scripted.
    assert NEWS in content
    return NONE


def service(
    asked: list[str],
    answers: Callable[[str], str] = answer,
    fetched: list[str] | None = None,
    pages: Mapping[str, bytes] = PAGES,
) -> httpx2.Client:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if str(request.url) != ADDRESS:
            if fetched is not None:
                fetched.append(str(request.url))
            return httpx2.Response(200, content=pages[str(request.url)])
        # The model service answers only the key the tests hand to the run.
        if request.headers["Authorization"] != f"Bearer {KEY}":
            return httpx2.Response(401)
        asked.append(json.loads(request.read())["messages"][0]["content"])
        return httpx2.Response(200, json={"choices": [{"message": {"content": answers(asked[-1])}}]})

    return httpx2.Client(transport=httpx2.MockTransport(handler))


@pytest.fixture
def lists(tmp_path: Path) -> tuple[Path, Path]:
    # The calls' source beside a reports' source: a reports run asks only the second.
    watch_list, topic_list = tmp_path / "sources.toml", tmp_path / "tags.toml"
    watch_list.write_text(WATCH_LIST + REPORTS, encoding="utf-8")
    topic_list.write_text(TOPIC_LIST, encoding="utf-8")
    return watch_list, topic_list


@pytest.fixture
def data(tmp_path: Path) -> Path:
    # Three calls already held: an EITI page naming two reports, a page naming one, and an EU record naming none.
    folder = tmp_path / "data"
    store(folder, "calls", "eiti", Fetched(EXAMPLE, EXAMPLE, "A call for views", NO_RECORD), OFFER, FETCHED)
    page = f"<html><body><p>{PUBLISHED}</p></body></html>".encode()
    store(folder, "calls", "eiti", Fetched(TRUST, TRUST, "A second call", NO_RECORD), page, FETCHED)
    store(folder, "calls", "eu", Fetched(EU_CALL, SITE + "eu", "A grant", stored()), b"<html></html>", FETCHED)
    return folder


def rows(folder: Path, start: int = 4) -> list[tuple[str, str, str]]:
    return [(row[2], row[6], row[7]) for row in log(folder)[start:]]


def kept(folder: Path) -> dict[str, bytes]:
    # Every file but the log, which each run adds its rows to.
    return {name: content for name, content in files(folder).items() if name != LOG}


def test_a_reports_run_reads_its_own_reports_and_each_held_call_once(
    data: Path, lists: tuple[Path, Path], capsys: pytest.CaptureFixture[str]
) -> None:
    asked: list[str] = []
    found_notes = "; ".join(FOUND_NOTES)
    with service(asked) as client:
        assert run("reports", data, *lists, client, FETCHED, KEY) == 0
    assert rows(data) == [
        (JOURNALISM_PAGE, "report saved", ""),
        (ROADS_PAGE, "report saved", ""),
        ("", "successful", "2 reports, 2 new, 0 failed"),
        # An own report is checked before its reading: the off-topic one costs no request.
        (JOURNALISM_PAGE, "first answer", OWN_REPORT),
        (JOURNALISM_PAGE, "card written", "; ".join(OWN_NOTES)),
        (ROADS_PAGE, "set aside", OWN_SET_ASIDE),
        # A held call's found reports are checked after its reading, each on its line's title and sentences.
        (EXAMPLE, "first answer for reports", f"{FOUND_STUDY}\n{FOUND_ACCOUNTS}"),
        (f"{EXAMPLE}#reports-1", "card written", found_notes),
        (f"{EXAMPLE}#reports-2", "set aside", FOUND_SET_ASIDE),
        (EXAMPLE, "read for reports", "2 found"),
        (TRUST, "first answer for reports", ONE),
        (f"{TRUST}#reports-1", "card written", found_notes),
        (TRUST, "read for reports", "1 found"),
        (EU_CALL, "first answer for reports", NONE),
        (EU_CALL, "read for reports", "0 found"),
    ]
    assert len(asked) == 4
    # The EU call is read from its record's text, which the model is sent whole.
    assert NEWS in asked[-1]
    assert capsys.readouterr().out == (
        "Example reports: 2 reports, 2 new, 0 failed\n"
        "Read: 2 reports, 1 cards written, 1 set aside, 0 failed\n"
        "Held documents: 3 read, 2 cards written, 0 failed\n"
    )
    made = [read_card("reports", text) for _, text in cards(data, "reports")]
    assert sorted((report.identifier, report.instructions) for report in made) == [
        (f"{EXAMPLE}#reports-1", "reports-held-v1"),
        (f"{TRUST}#reports-1", "reports-held-v1"),
        (JOURNALISM_PAGE, "reports-v1"),
    ]
    assert all(JOURNALISM in report.topics for report in made)
    assert not (data / "calls").exists()
    assert not (data / "feed.xml").exists()
    # Run again: nothing is fetched, read or asked a second time; only the source's row is added.
    before, held = len(log(data)), kept(data)
    fetched: list[str] = []
    with service(asked, fetched=fetched) as client:
        assert run("reports", data, *lists, client, FETCHED, KEY) == 0
    assert rows(data, before) == [("", "nothing new", "2 reports, 0 new, 0 failed")]
    assert (len(asked), fetched) == (4, [])
    assert kept(data) == held


def test_a_reports_run_hands_the_model_the_key_it_was_given(data: Path, lists: tuple[Path, Path]) -> None:
    asked: list[str] = []
    with service(asked) as client:
        # The own report with a topic and the three held calls each fail; nothing is answered.
        assert run("reports", data, *lists, client, FETCHED, "another key") == 4
    assert asked == []
    assert [row[1] for row in rows(data) if row[0] in (JOURNALISM_PAGE, EU_CALL)][-2:] == [
        "failed",
        "failed for reports",
    ]


def test_a_reply_with_no_text_leaves_its_empty_answer_row_before_a_reports_run_stops(
    data: Path, lists: tuple[Path, Path]
) -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if str(request.url) != ADDRESS:
            return httpx2.Response(200, content=PAGES[str(request.url)])
        return httpx2.Response(200, json={"choices": [{"message": {"content": None}}]})

    # A reply with no text cannot be judged, so the run stops there, as a calls run does; its empty answer row is written.
    with httpx2.Client(transport=httpx2.MockTransport(handler)) as client, pytest.raises(AttributeError):
        run("reports", data, *lists, client, FETCHED, KEY)
    assert rows(data)[-1] == (JOURNALISM_PAGE, "first answer", "")


def test_a_held_reading_that_stopped_takes_its_items_from_the_answers_the_log_keeps(
    data: Path, lists: tuple[Path, Path]
) -> None:
    document = saved(data, "calls")[0]
    assert document.identifier == EXAMPLE
    store_held_answer(data, "reports", document, FETCHED, "first answer", f"{FOUND_STUDY}\n{FOUND_ACCOUNTS}")
    # The run stopped after the first item's card, before its row.
    first = found_item(document, "reports", 1, "A study of journalism in the example country", FETCHED.date())
    store_card(data, "reports", first, item_key(first), report_card(REPORT))
    before = len(log(data))
    asked: list[str] = []
    with service(asked) as client:
        assert run("reports", data, *lists, client, FETCHED, KEY) == 0
    assert not any("Example 2027 EITI Validation" in content for content in asked)
    assert [row for row in rows(data, before) if row[0].startswith(EXAMPLE)] == [
        (f"{EXAMPLE}#reports-1", "card written", "; ".join(FOUND_NOTES)),
        (f"{EXAMPLE}#reports-2", "set aside", FOUND_SET_ASIDE),
        (EXAMPLE, "read for reports", "2 found"),
    ]
    # The first item keeps its one card: with the other call's and the own report's, three in all.
    assert len(cards(data, "reports")) == 3


def test_an_item_already_given_its_row_gets_nothing_more(data: Path, lists: tuple[Path, Path]) -> None:
    document = saved(data, "calls")[0]
    store_held_answer(data, "reports", document, FETCHED, "first answer", f"{FOUND_STUDY}\n{FOUND_ACCOUNTS}")
    second = found_item(document, "reports", 2, "Annual accounts", FETCHED.date())
    store_reading(data, second, FETCHED, "set aside", FOUND_SET_ASIDE)
    before = len(log(data))
    with service([]) as client:
        assert run("reports", data, *lists, client, FETCHED, KEY) == 0
    assert [row[:2] for row in rows(data, before) if row[0].startswith(EXAMPLE)] == [
        (f"{EXAMPLE}#reports-1", "card written"),
        (EXAMPLE, "read for reports"),
    ]


def test_a_held_reading_that_fails_has_its_failed_row_and_is_read_afresh_next_run(
    data: Path, lists: tuple[Path, Path]
) -> None:
    def unusable(content: str) -> str:
        return NO_LINE if "Example 2027 EITI Validation" in content else answer(content)

    asked: list[str] = []
    with service(asked, unusable) as client:
        assert run("reports", data, *lists, client, FETCHED, KEY) == 1
    document = Saved("eiti", EXAMPLE, "A call for views", EXAMPLE, FETCHED.date())
    assert [row[1:] for row in rows(data) if row[0] == EXAMPLE] == [
        ("first answer for reports", NO_LINE),
        ("second answer for reports", NO_LINE),
        ("failed for reports", f"ValueError: first answer: {NOTHING_READ}; second answer: {NOTHING_READ}"),
    ]
    # A failed reading leaves no earlier answer; a stopped one leaves those after the last failed row.
    assert earlier(data, "reports", document) == ()
    store_held_answer(data, "reports", document, FETCHED, "first answer", MISQUOTED)
    with service(asked) as client:
        assert run("reports", data, *lists, client, FETCHED, KEY) == 0
    assert [row for row in rows(data) if row[0].startswith(EXAMPLE)][-4:] == [
        (EXAMPLE, "second answer for reports", f"{FOUND_STUDY}\n{FOUND_ACCOUNTS}"),
        (f"{EXAMPLE}#reports-1", "card written", "; ".join(FOUND_NOTES)),
        (f"{EXAMPLE}#reports-2", "set aside", FOUND_SET_ASIDE),
        (EXAMPLE, "read for reports", f"2 found; first answer: {MISS_1}"),
    ]


def test_a_held_page_with_two_dates_is_still_read_for_reports(tmp_path: Path, lists: tuple[Path, Path]) -> None:
    # Two closing dates fail a call's own reading; for a later kind the page is only its words.
    folder = tmp_path / "data"
    times = '<time datetime="2027-01-01">1 January</time><time datetime="2027-02-01">1 February</time>'
    page = f"<html><body>{times}<p>{PUBLISHED}</p></body></html>".encode()
    store(folder, "calls", "eiti", Fetched(TRUST, TRUST, "A call with two dates", NO_RECORD), page, FETCHED)
    with service([]) as client:
        assert run("reports", folder, *lists, client, FETCHED, KEY) == 0
    assert [row[:2] for row in rows(folder, 1) if row[0].startswith(TRUST)][-2:] == [
        (f"{TRUST}#reports-1", "card written"),
        (TRUST, "read for reports"),
    ]


STORIES = "https://data.org/wp-json/wp/v2/story"
TRAINING = SITE + "files/training.pdf"
WIDER = f"""
[source.data-org-stories]
name = "data.org stories"
url = "{STORIES}"
how = "report-wordpress"
kind = "reports"
since = 2024-08-05

[source.field-files]
name = "Example files"
url = "{SITE}files"
how = "report-links"
kind = "reports"
links = ["{TRAINING}"]
"""


def test_a_reports_run_reads_a_wordpress_source_and_a_pdf_and_asks_only_the_source_again(tmp_path: Path) -> None:
    watch_list, topic_list, data = tmp_path / "sources.toml", tmp_path / "tags.toml", tmp_path / "data"
    watch_list.write_text(WATCH_LIST + WIDER, encoding="utf-8")
    topic_list.write_text(TOPIC_LIST, encoding="utf-8")
    asked: list[str] = []
    fetched: list[httpx2.URL] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        if str(request.url) == ADDRESS:
            assert request.headers["Authorization"] == f"Bearer {KEY}"
            asked.append(json.loads(request.read())["messages"][0]["content"])
            return httpx2.Response(200, json={"choices": [{"message": {"content": OWN_REPORT}}]})
        fetched.append(request.url)
        if request.url.path == "/wp-json/wp/v2/story":
            # data.org's recorded answer, three stories over two pages, with the page count WordPress sends.
            content = (REPLIES / f"wordpress_stories_page_{request.url.params['page']}.json").read_bytes()
            return httpx2.Response(200, content=content, headers={"X-WP-TotalPages": "2"})
        if str(request.url) == TRAINING:
            return httpx2.Response(200, content=pdf(TRAINED, WORKED, title="Data journalism training"))
        # Each story's own page, which is stored beside its record.
        assert request.url.path.startswith("/stories/")
        return httpx2.Response(200, content=b"<html><body>A story.</body></html>")

    with httpx2.Client(transport=httpx2.MockTransport(handler)) as client:
        assert run("reports", data, watch_list, topic_list, client, FETCHED, KEY) == 0
        # Both pages of the WordPress answer, each story's page, then the one file.
        assert [url.path for url in fetched] == [
            "/wp-json/wp/v2/story",
            "/wp-json/wp/v2/story",
            "/stories/ark-solves/",
            "/stories/khushi-baby/",
            "/stories/artpark/",
            "/files/training.pdf",
        ]
        assert [(row[1], row[2]) for row in rows(data, 1) if row[1] in ("successful", "failed", "nothing new")] == [
            ("successful", "3 reports, 3 new, 0 failed"),
            ("successful", "1 reports, 1 new, 0 failed"),
        ]
        # The tests' topic list holds none of the three stories; the PDF is titled by its file and read by its pages.
        assert [row[1] for row in rows(data, 1) if row[1] in ("set aside", "first answer", "card written")] == [
            "set aside",
            "set aside",
            "set aside",
            "first answer",
            "card written",
        ]
        assert len(asked) == 1
        assert asked[0].count(f"Title: Data journalism training\n{TRAINED}") == 1
        [(_, text)] = cards(data, "reports")
        made = read_card("reports", text)
        assert (made.title, made.identifier, made.published) == ("Data journalism training", TRAINING, None)
        names = sorted(
            name.rsplit(".", 2)[-2] + "." + name.rsplit(".", 1)[-1] for name in files(data) if "/raw/" in "/" + name
        )
        assert sum(name.endswith("wordpress.json") for name in names) == 3
        assert sum(name.endswith(".pdf") for name in names) == 1
        # Run again: the source is asked again, both pages; no page, no file and no reading a second time.
        before, held = len(log(data)), kept(data)
        fetched.clear()
        assert run("reports", data, watch_list, topic_list, client, FETCHED, KEY) == 0
    assert [url.path for url in fetched] == ["/wp-json/wp/v2/story", "/wp-json/wp/v2/story"]
    assert rows(data, before) == [
        ("", "nothing new", "3 reports, 0 new, 0 failed"),
        ("", "nothing new", "1 reports, 0 new, 0 failed"),
    ]
    assert (len(asked), kept(data)) == (1, held)


def test_a_list_page_with_a_link_that_cannot_be_read_is_the_source_s_failed_run(tmp_path: Path) -> None:
    watch_list, topic_list, data = tmp_path / "sources.toml", tmp_path / "tags.toml", tmp_path / "data"
    listing = f"""
[source.field-list]
name = "Example list"
url = "{SITE}reports/"
how = "report-page"
kind = "reports"
path = "/reports/"
"""
    watch_list.write_text(WATCH_LIST + listing + REPORTS, encoding="utf-8")
    topic_list.write_text(TOPIC_LIST, encoding="utf-8")
    pages = PAGES | {SITE + "reports/": b'<html><a href="http://example.org:port/reports/a">A report</a></html>'}
    with service([], pages=pages) as client:
        # The list's source fails, and the next source is still searched and read.
        assert run("reports", data, watch_list, topic_list, client, FETCHED, KEY) == 1
    first = rows(data, 1)[0]
    assert (first[1], first[2].split(":")[0]) == ("failed", "httpx2.InvalidURL")
    assert (JOURNALISM_PAGE, "card written", "; ".join(OWN_NOTES)) in rows(data, 1)
