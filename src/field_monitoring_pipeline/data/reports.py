"""Read one stored report into a report record, and title an item its source gives no title from its file.

Gives the topic check what it reads of a stored report: its title and its labels by name as its head, and
its own text as its body. A WordPress item's text is its content, and a feed entry's its full text, else its
description; their labels are the item's terms and the entry's tags, and none when the item has none. The
text the model reads is a labelled title line, then that text. The record takes the type and the six facts
the model names, each fact a value with its sentence, the day the item or entry was posted, and the
topics the check made, with the link, the identifier and the names of the model and the instructions. Each
sentence is marked found or not found, and a note names each one not found, each fact left empty and why,
and a report with no date.

A document of another kind already held is read once more for the reports it names, with instructions of
its own: one command line per report, or the one line that says none. Each line gives a report its title,
its type and its six facts, each sentence searched for in that document; a report found so is checked on
its line's title and the sentences its line quotes, and has no date. Its notes speak of the document it
was found in.

An item its source gives no title, as a single link always is, takes one when it is downloaded: its page's
title, or the PDF's, Word file's or spreadsheet's own, and with none of these it is named by its address.

A report's download is read by the kind of file its stored name gives: a web page by its words, a PDF page
by page, a Word file by its paragraphs and then its table cells, and a spreadsheet by every filled cell of
every sheet, as the values last saved in it. A page's bytes must be UTF-8. A file its library cannot read,
an old Word or Excel file, a packed file that cannot be opened or holds neither a Word document nor a
workbook, and a PDF with no text, which is how a scanned one reads, are each refused with the reason, so
the report gets a failed row and the run carries on.
"""

import datetime as dt
import io
from dataclasses import dataclass, replace
from functools import partial
from html.parser import HTMLParser
from typing import Any, cast, override

import docx
import openpyxl
import pypdfium2 as pdfium
from pydantic import TypeAdapter, ValidationError

from field_monitoring_pipeline.data.fetch import Fetched, Form, Posted, posted_day
from field_monitoring_pipeline.data.models import Quoted, Report, ReportType, Topic
from field_monitoring_pipeline.data.reading import (
    AGAIN,
    AGAIN_LINES,
    MARKED_NOT_STATED,
    MODEL,
    NOT_MENTIONED,
    Answer,
    Found,
    Prepared,
    Refused,
    Usable,
    flags,
    line,
    miss,
    not_found,
    pair,
    plain,
    refusals,
    several,
    tidy,
)
from field_monitoring_pipeline.data.store import Downloaded, Saved, file_type
from field_monitoring_pipeline.data.tags import Parts, Subject

# Each library is given a file from outside and raises its own errors on a damaged one, of several kinds
# (a damaged PDF, a cut packed file, a missing part); any of them refuses that one file, never the run.


def _pdf(content: bytes) -> str:
    try:
        document = pdfium.PdfDocument(content)
        pages = [page.get_textpage().get_text_bounded() for page in document]
        document.close()
    except Exception as error:
        raise ValueError(f"the PDF cannot be read: {error!r}") from error
    words = "\n".join(pages)
    if not words.strip():
        raise ValueError("no text: a scanned PDF")
    return words


def _word(content: bytes) -> str:
    try:
        document = docx.Document(io.BytesIO(content))
        paragraphs = [paragraph.text for paragraph in document.paragraphs]
        cells = [cell.text for table in document.tables for row in table.rows for cell in row.cells]
    except Exception as error:
        raise ValueError(f"the Word file cannot be read: {error!r}") from error
    return "\n".join(paragraphs + cells)


def _spreadsheet(content: bytes) -> str:
    try:
        book = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        values = [
            str(value)
            for sheet in book.worksheets
            for row in sheet.iter_rows(values_only=True)
            for value in row
            if value is not None
        ]
        book.close()
    except Exception as error:
        raise ValueError(f"the spreadsheet cannot be read: {error!r}") from error
    return "\n".join(values)


class _PageTitle(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.inside = False
        self.titles: list[str] = []

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self.inside = True
            self.titles.append("")

    @override
    def handle_endtag(self, tag: str) -> None:
        self.inside = self.inside and tag != "title"

    @override
    def handle_data(self, data: str) -> None:
        if self.inside:
            self.titles[-1] += data


def _own_title(file: Downloaded) -> str | None:
    try:
        return _library_title(file)
    except Exception as error:
        raise ValueError(f"the file's own title cannot be read: {error!r}") from error


def _library_title(file: Downloaded) -> str | None:
    match file.type:
        case "html":
            parser = _PageTitle()
            parser.feed(file.content.decode("utf-8"))
            parser.close()
            return parser.titles[0] if parser.titles else None
        case "pdf":
            document = pdfium.PdfDocument(file.content)
            title = document.get_metadata_dict()["Title"]
            document.close()
            return title
        case "docx":
            return docx.Document(io.BytesIO(file.content)).core_properties.title
        case "xlsx":
            book = openpyxl.load_workbook(io.BytesIO(file.content), read_only=True)
            title = book.properties.title
            book.close()
            return title
        case "doc" | "zip":
            return None


def titled(item: Fetched, page: bytes) -> Fetched:
    """Give an item with no title the one its file holds: a page's title, or a PDF's, Word file's or spreadsheet's
    own; with none, the store names it by its address."""
    if item.title is not None:
        return item
    try:
        title = _own_title(Downloaded(file_type(page), page))
    except ValueError:
        # A file that cannot be read is still saved, named by its address; its reading gives the reason.
        title = None
    # An empty title, as a file with none set gives, is no title.
    return replace(item, title=tidy(title or "") or None)


def file_text(file: Downloaded) -> str:
    match file.type:
        case "html":
            return plain(file.content.decode("utf-8"))
        case "pdf":
            return _pdf(file.content)
        case "docx":
            return _word(file.content)
        case "xlsx":
            return _spreadsheet(file.content)
        case "doc":
            raise ValueError("could not read: old Word or Excel format")
        case "zip":
            raise ValueError(
                "could not read: a packed file that cannot be opened or holds neither a Word document nor a workbook"
            )


INSTRUCTIONS = "reports-v1"
# The facts the model names, each a value with its sentence, in the record's own order.
FACTS = ("organisation", "audience", "methodology", "results", "duration", "area")
QUOTED = frozenset({"type", *FACTS, *(f"{fact}-quote" for fact in FACTS)})
ALONE = frozenset(f"{fact}-not-stated" for fact in FACTS)
# How a note names each fact.
NAMES = {
    "organisation": "organisation",
    "audience": "who it was for",
    "methodology": "method",
    "results": "results",
    "duration": "how long it ran",
    "area": "where",
}


@dataclass(frozen=True)
class _Stored:
    title: str
    labels: tuple[str, ...]
    body: str
    published: dt.date | None
    link: str
    identifier: str

    @property
    def text(self) -> str:
        return f"Title: {tidy(self.title)}\n{self.body}"

    @property
    def words(self) -> str:
        return tidy(self.text)


def _labels(body: dict[str, Any], form: Form) -> tuple[str, ...]:
    # An item or entry with no labels has no labels key at all.
    match form:
        case "wordpress":
            groups: list[list[dict[str, Any]]] = body["_embedded"]["wp:term"] if "_embedded" in body else []
            return tuple(term["name"] for group in groups for term in group)
        case "feed":
            return tuple(tag["term"] for tag in body.get("tags", []))


def _posted_text(body: dict[str, Any], form: Form) -> str:
    match form:
        case "wordpress":
            return plain(body["content"]["rendered"])
        # A feed entry's full text, else its description, which feedparser names its summary.
        case "feed":
            return plain(body["content"][0]["value"] if "content" in body else body.get("summary", ""))


def _stored(item: Saved, kept: Posted | Downloaded) -> _Stored:
    match kept:
        case Posted(form=form, body=body):
            fields = cast("dict[str, Any]", body)
            labels, text, published = _labels(fields, form), _posted_text(fields, form), posted_day(kept)
        case Downloaded():
            labels, text, published = (), file_text(kept), None
    return _Stored(item.title, labels, text, published, item.link, item.identifier)


REPORT_PARTS = Parts(head="title or labels", body="text")
FOUND_PARTS = Parts(head="title", body="quoted sentences")
NO_DATE = "published: empty, because this source gives no date"
FOUND_NO_DATE = "published: empty, because the document it was found in gives no date for it"


def _notes(facts: dict[str, Quoted | None], given: dict[str, object], noun: str) -> list[str]:
    # The noun names the text that was searched: the report, or the document a report was found in.
    notes: list[str] = []
    for name, label in NAMES.items():
        box = facts[name]
        if box is not None and not box.found:
            notes.append(not_found(label, noun, box.quote))
        elif box is None and f"{name}-not-stated" in given:
            notes.append(f"{label}: {MARKED_NOT_STATED}")
        elif box is None:
            notes.append(f"{label}: {NOT_MENTIONED}")
    return notes


def _facts(report: Report) -> dict[str, Quoted | None]:
    return {name: getattr(report, name) for name in FACTS}


def _build(stored: _Stored, found: tuple[Topic, ...], reply: str) -> tuple[Report, list[str]]:
    given = flags(line(reply), alone=ALONE, quoted=QUOTED, plain_words=frozenset())
    report = Report.model_validate({
        "title": stored.title,
        "type": given.get("type"),
        **{fact: pair(given, fact, stored.words) for fact in FACTS},
        "published": stored.published,
        "topics": found,
        "link": stored.link,
        "identifier": stored.identifier,
        "model": MODEL,
        "instructions": INSTRUCTIONS,
    })
    undated = [NO_DATE] if report.published is None else []
    return report, _notes(_facts(report), given, "report") + undated


def _use(stored: _Stored, found: tuple[Topic, ...], reply: str) -> Answer[Report]:
    try:
        report, notes = _build(stored, found, reply)
    except ValidationError as error:
        return Refused(refusals(error))
    except ValueError as error:
        return Refused([str(error)])
    misses = [miss(f"{fact}-quote") for fact in FACTS if (box := getattr(report, fact)) is not None and not box.found]
    return Usable(record=report, notes=notes, misses=misses)


def subject(item: Saved, kept: Posted | Downloaded) -> Subject:
    # The head is the title and the labels by name; the body is the report's own text.
    stored = _stored(item, kept)
    return Subject(title=stored.title, other_titles=stored.labels, body=stored.body, parts=REPORT_PARTS)


def prepare(item: Saved, kept: Posted | Downloaded, found: tuple[Topic, ...]) -> Prepared[Report]:
    # The text is made first, so a file that cannot be read fails the report before any request.
    stored = _stored(item, kept)
    return Prepared(
        text=stored.text, instructions=INSTRUCTIONS, again=AGAIN, use=lambda reply: _use(stored, found, reply)
    )


HELD = "reports-held-v1"
# A found report's title is the model's, so only a held document's line gives one.
HELD_QUOTED = QUOTED | {"title"}
# What one line gives of a report is checked by the record's own types before the topic check, each by its name.
_TYPE: TypeAdapter[dict[str, ReportType]] = TypeAdapter(dict[str, ReportType])
_FACTS: TypeAdapter[dict[str, Quoted | None]] = TypeAdapter(dict[str, Quoted | None])


def _found(document: str, order: int, command: str) -> tuple[Found[Report], list[str]]:
    given = flags(command, alone=ALONE, quoted=HELD_QUOTED, plain_words=frozenset())
    title = given.get("title")
    if not isinstance(title, str) or not tidy(title):
        raise ValueError("--title must give the report's title")
    kind = _TYPE.validate_python({"type": given.get("type")})["type"]
    facts = _FACTS.validate_python({fact: pair(given, fact, document) for fact in FACTS})

    def record(item: Saved, found: tuple[Topic, ...]) -> Report:
        return Report.model_validate({
            "title": tidy(title),
            "type": kind,
            **facts,
            "published": None,
            "topics": found,
            "link": item.link,
            "identifier": item.identifier,
            "model": MODEL,
            "instructions": HELD,
        })

    quoted = " ".join(box.quote for box in facts.values() if box is not None)
    item = Found(
        order=order,
        # A found report is checked on its line's title, and on the sentences its line quotes as its body.
        subject=Subject(title=tidy(title), other_titles=(), body=quoted, parts=FOUND_PARTS),
        record=record,
        notes=[*_notes(facts, given, "document it was found in"), FOUND_NO_DATE],
    )
    return item, [miss(f"{fact}-quote") for fact, box in facts.items() if box is not None and not box.found]


def prepare_held(text: str, earlier: tuple[str, ...]) -> Prepared[list[Found[Report]]]:
    # The reports a document of another kind names, one per command line of the answer.
    return Prepared(
        text=text,
        instructions=HELD,
        again=AGAIN_LINES,
        use=partial(several, partial(_found, tidy(text))),
        earlier=earlier,
    )
