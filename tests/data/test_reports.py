import datetime as dt
import io
import json
import re
import zipfile
from pathlib import Path

import docx
import openpyxl
import pytest

from field_monitoring_pipeline.data import reading
from field_monitoring_pipeline.data.fetch import JSON, NO_RECORD, Fetched, Posted
from field_monitoring_pipeline.data.models import Quoted, Report, Topic
from field_monitoring_pipeline.data.reading import MODEL, Refused, Usable
from field_monitoring_pipeline.data.reports import (
    ALONE,
    HELD,
    HELD_QUOTED,
    INSTRUCTIONS,
    QUOTED,
    file_text,
    prepare,
    prepare_held,
    subject,
    titled,
)
from field_monitoring_pipeline.data.store import Downloaded, Saved, file_type
from tests.samples import ARK_LINK, REPLIES, pdf

LINK = "https://example.org/reports/annual-2025.pdf"
TODAY = dt.date(2026, 11, 27)
UNTITLED = Fetched(LINK, LINK, None, NO_RECORD)


def word(title: str = "") -> bytes:
    document = docx.Document()
    document.core_properties.title = title
    document.add_paragraph("The programme reached 1 200 schools.")
    document.add_table(rows=1, cols=1).rows[0].cells[0].text = "Kenya and Uganda"
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def spreadsheet(title: str | None = None) -> bytes:
    book = openpyxl.Workbook()
    book.properties.title = title
    sheet = book.active
    assert sheet is not None
    sheet.append(["Résultats", 3, None])
    book.create_sheet("Second").append(["Indicateur"])
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def packed(*names: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as folder:
        for name in names:
            folder.writestr(name, "not what it should be")
    return buffer.getvalue()


def read(content: bytes) -> str:
    return file_text(Downloaded(file_type(content), content))


@pytest.mark.parametrize(
    ("content", "text"),
    [
        pytest.param(
            pdf("It reached 1 200 schools.", "In two countries."),
            "It reached 1 200 schools.\r\nIn two countries.",
            id="a PDF",
        ),
        pytest.param(
            word(), "The programme reached 1 200 schools.\nKenya and Uganda", id="a Word file, paragraphs then cells"
        ),
        pytest.param(spreadsheet(), "Résultats\n3\nIndicateur", id="a spreadsheet, every filled cell of every sheet"),
        pytest.param("<html><p>Café</p><script>x()</script></html>".encode(), "Café", id="a web page"),
    ],
)
def test_each_kind_of_file_is_read_by_its_reader(content: bytes, text: str) -> None:
    assert read(content) == text


def test_a_spreadsheet_gives_the_values_last_saved_not_its_formulas() -> None:
    book = openpyxl.Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.append([2, "=A1*2"])
    buffer = io.BytesIO()
    book.save(buffer)
    # The file was never opened in a spreadsheet program, so the formula has no saved value and gives nothing.
    assert read(buffer.getvalue()) == "2"


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        pytest.param(b"%PDF-1.4 cut short", "the PDF cannot be read: ", id="a damaged PDF"),
        pytest.param(pdf(), "no text: a scanned PDF", id="a PDF with no text"),
        pytest.param(packed("word/document.xml"), "the Word file cannot be read: ", id="a damaged Word file"),
        pytest.param(packed("xl/workbook.xml"), "the spreadsheet cannot be read: ", id="a damaged spreadsheet"),
        pytest.param(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "could not read: old Word or Excel format", id="an old file"),
        pytest.param(packed("other.xml"), "could not read: a packed file that", id="a packed file holding neither"),
        pytest.param(word()[:2000], "could not read: a packed file that", id="a Word file cut short"),
        pytest.param(b"<html>caf\xe9</html>", "'utf-8' codec can't decode", id="a page that is not UTF-8"),
    ],
)
def test_a_file_that_cannot_be_read_is_refused_with_its_reason(content: bytes, reason: str) -> None:
    with pytest.raises(ValueError) as raised:
        read(content)
    assert str(raised.value).startswith(reason)


@pytest.mark.parametrize(
    ("content", "title"),
    [
        pytest.param(
            b"<html><head><title> Annual\n report 2025 </title></head></html>", "Annual report 2025", id="a page"
        ),
        pytest.param(pdf("Text.", title="Annual report 2025"), "Annual report 2025", id="a PDF"),
        pytest.param(word("Annual report 2025"), "Annual report 2025", id="a Word file"),
        pytest.param(spreadsheet("Annual report 2025"), "Annual report 2025", id="a spreadsheet"),
    ],
)
def test_a_single_link_takes_the_title_its_file_holds(content: bytes, title: str) -> None:
    assert titled(UNTITLED, content).title == title


@pytest.mark.parametrize(
    "content",
    [
        pytest.param(b"<html><p>No title here.</p></html>", id="a page with no title"),
        pytest.param(b"<html><title>  </title></html>", id="a page with an empty title"),
        pytest.param(pdf("Text."), id="a PDF with no title of its own"),
        pytest.param(word(), id="a Word file with no title of its own"),
        pytest.param(spreadsheet(), id="a spreadsheet with no title of its own"),
        pytest.param(b"%PDF-1.4 cut short", id="a file that cannot be read"),
        pytest.param(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", id="an old file"),
    ],
)
def test_a_single_link_whose_file_gives_no_title_keeps_none_so_its_address_names_it(content: bytes) -> None:
    assert titled(UNTITLED, content) == UNTITLED


def test_an_item_with_a_title_keeps_it() -> None:
    item = Fetched(LINK, LINK, "From the list page", NO_RECORD)
    assert titled(item, pdf("Text.", title="Annual report 2025")) is item


STORIES = json.loads((REPLIES / "wordpress_stories_page_1.json").read_bytes())
ARK = Posted("wordpress", STORIES[0])
ARK_SAVED = Saved("data-org-stories", ARK_LINK, STORIES[0]["title"]["rendered"], ARK_LINK, TODAY)
FOUND = (Topic(name="open-data", mark="primary"),)
FARMERS = (
    "Ironically, smallholder farmers, who produce the country’s food supply, are trapped in a poverty cycle"
    " that prevents them from feeding their own families."
)
PHILIPPINES = "In the Philippines, food insecurity grips 37.8 million people, the worst in Southeast Asia."
NOT_STATED_REST = "--organisation-not-stated --methodology-not-stated --results-not-stated --duration-not-stated"


def answer(area_quote: str = PHILIPPINES, rest: str = NOT_STATED_REST) -> str:
    return (
        f'Reasoning first.\nfieldbook --type "research or case study" --audience "smallholder farmers"'
        f' --audience-quote {json.dumps(FARMERS, ensure_ascii=False)} --area "the Philippines"'
        f" --area-quote {json.dumps(area_quote)} {rest}"
    )


def test_a_report_s_text_is_its_title_then_its_own_words() -> None:
    reading = prepare(ARK_SAVED, ARK, FOUND)
    assert reading.instructions == "reports-v1"
    assert reading.text.startswith(f"Title: {ARK_SAVED.title}\nIn the Philippines, food insecurity grips")


def test_an_answer_whose_every_sentence_is_found_becomes_a_report() -> None:
    used = prepare(ARK_SAVED, ARK, FOUND).use(answer())
    assert isinstance(used, Usable)
    assert used.record == Report(
        title=ARK_SAVED.title,
        type="research or case study",
        organisation=None,
        audience=Quoted(value="smallholder farmers", quote=FARMERS, found=True),
        methodology=None,
        results=None,
        duration=None,
        area=Quoted(value="the Philippines", quote=PHILIPPINES, found=True),
        published=dt.date(2026, 9, 8),
        topics=FOUND,
        link=ARK_LINK,
        identifier=ARK_LINK,
        model=MODEL,
        instructions="reports-v1",
    )
    assert used.misses == []
    assert used.notes == [
        "organisation: empty, because the model marked it not stated",
        "method: empty, because the model marked it not stated",
        "results: empty, because the model marked it not stated",
        "how long it ran: empty, because the model marked it not stated",
    ]


def test_a_sentence_not_in_the_report_is_marked_and_asked_for_again() -> None:
    used = prepare(ARK_SAVED, ARK, FOUND).use(answer(area_quote="The Philippines has many farms."))
    assert isinstance(used, Usable)
    assert used.misses == ["--area-quote: the sentence must be in the text word for word"]
    assert "where: this sentence was not found in the report: The Philippines has many farms." in used.notes


@pytest.mark.parametrize("quote", ["", "  "], ids=["empty", "only spaces"])
def test_a_quote_with_no_words_is_not_found_and_is_asked_for_again(quote: str) -> None:
    used = prepare(ARK_SAVED, ARK, FOUND).use(answer(area_quote=quote))
    assert isinstance(used, Usable)
    assert used.record.area == Quoted(value="the Philippines", quote=quote, found=False)
    assert used.misses == ["--area-quote: the sentence must be in the text word for word"]


def test_a_fact_the_answer_does_not_mention_is_noted_so() -> None:
    used = prepare(ARK_SAVED, ARK, FOUND).use(answer(rest="--organisation-not-stated"))
    assert isinstance(used, Usable)
    assert "method: empty, because the model's answer did not mention it" in used.notes


@pytest.mark.parametrize(
    ("reply", "problem"),
    [
        pytest.param("fieldbook --area-not-stated", "type: ", id="no type"),
        pytest.param('fieldbook --type "audit"', "type: ", id="a type that is not one of the four"),
        pytest.param('fieldbook --type "evaluation" --budget "1"', "--budget is not a flag", id="a flag not offered"),
        pytest.param("no command line", "the answer must hold exactly one line", id="no command line"),
    ],
)
def test_an_answer_that_cannot_be_used_is_refused_with_its_problem(reply: str, problem: str) -> None:
    used = prepare(ARK_SAVED, ARK, FOUND).use(reply)
    assert isinstance(used, Refused)
    assert used.problems[0].startswith(problem)


def test_the_topic_check_reads_a_report_s_title_and_labels_as_its_head_and_its_text_as_its_body() -> None:
    checked = subject(ARK_SAVED, ARK)
    assert checked.head == (ARK_SAVED.title, "Capacity Accelerator Network (CAN)")
    assert checked.body.startswith("In the Philippines, food insecurity grips")
    # Khushi Baby's story, as data.org gives it, has no labels at all.
    khushi = STORIES[1]
    unlabelled = Saved("data-org-stories", khushi["link"], khushi["title"]["rendered"], khushi["link"], TODAY)
    assert subject(unlabelled, Posted("wordpress", khushi)).head == (unlabelled.title,)


def test_a_feed_entry_is_read_by_its_full_text_its_tags_and_its_date() -> None:
    entry: JSON = {
        "link": "https://example.org/reports/new/",
        "published_parsed": "2025-06-03T10:00:00+00:00",
        "tags": [{"term": "Open data", "scheme": None, "label": None}],
        "content": [{"value": "<p>It reached <a href='/schools'>1 200 schools</a>.</p>"}],
        "summary": "Short.",
    }
    item = Saved(
        "a-feed", "https://example.org/reports/new/", "A new report", "https://example.org/reports/new/", TODAY
    )
    kept = Posted("feed", entry)
    assert subject(item, kept).head == ("A new report", "Open data")
    assert prepare(item, kept, FOUND).text == "Title: A new report\nIt reached 1 200 schools."
    used = prepare(item, kept, FOUND).use('fieldbook --type "annual report"')
    assert isinstance(used, Usable)
    assert used.record.published == dt.date(2025, 6, 3)


def test_a_downloaded_report_has_no_date_and_says_why() -> None:
    item = Saved("links", LINK, "Annual report 2025", LINK, TODAY)
    used = prepare(item, Downloaded("pdf", pdf("It reached 1 200 schools.")), FOUND).use(
        'fieldbook --type "annual report"'
    )
    assert isinstance(used, Usable)
    assert used.record.published is None
    assert used.notes[-1] == "published: empty, because this source gives no date"


def test_a_file_that_cannot_be_read_fails_the_report_before_any_request() -> None:
    item = Saved("links", LINK, LINK, LINK, TODAY)
    with pytest.raises(ValueError, match="no text: a scanned PDF"):
        prepare(item, Downloaded("pdf", pdf()), FOUND)


@pytest.mark.parametrize(
    ("name", "offered"),
    [
        pytest.param(INSTRUCTIONS, QUOTED | ALONE, id="a report's own text"),
        pytest.param(HELD, HELD_QUOTED | ALONE | {"none"}, id="a document already held"),
    ],
)
def test_the_report_instructions_write_only_flags_the_code_offers_and_their_example_builds(
    name: str, offered: frozenset[str]
) -> None:
    text = (Path(reading.__file__).parent / "instructions" / f"{name}.md").read_text(encoding="utf-8")
    assert f"`{reading.BEGIN}`" in text
    assert f"`{reading.END}`" in text
    # Every flag the instructions write out is one the code offers, and each fact's own "not stated" flag is written.
    written = set(re.findall(r"`(?:fieldbook )?--([a-z-]+)`", text))
    assert ALONE <= written <= offered
    [example] = [line for line in text.splitlines() if line.startswith("fieldbook ")]
    prepared = prepare(ARK_SAVED, ARK, FOUND) if name == INSTRUCTIONS else prepare_held("Any text.", ())
    assert isinstance(prepared.use(example), Usable)
