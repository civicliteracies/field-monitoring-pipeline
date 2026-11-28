"""Write a call record or a report record as a card.

A card is one Markdown file. On top sits the record, written by the data layer, which also reads it
back. Below is the half for people: the title, then each fact on its own line. For a call, the
publisher's own sentence sits under the summary, who can apply and where, and the source's own line under
the dates and the budget. For a report, the sentence sits under each of its six facts, after its type and
the day it was posted. A sentence or a funder's name not found has a warning under it, naming the call or
the report, and an empty field says "not stated". The link and the model and instructions that read the
item come last.
"""

import datetime as dt

from field_monitoring_pipeline.data.models import NOT_STATED, Call, Deadline, Named, Opening, Quoted, Report
from field_monitoring_pipeline.data.store import record_block

NAME_WARNING = "This name was not found in the call."
STAYS_OPEN = "stays open"


def day(date: dt.date) -> str:
    return f"{date.day} {date:%B %Y}"


def _under(fact: Opening | Deadline | Quoted, noun: str) -> list[str]:
    return [f"> {fact.quote}"] if fact.found else [f"> {fact.quote}", f"This sentence was not found in the {noun}."]


def _sentences(facts: tuple[tuple[str, Quoted | None], ...], noun: str) -> list[str]:
    paragraphs: list[str] = []
    for label, fact in facts:
        paragraphs += [f"{label}: {NOT_STATED}"] if fact is None else [f"{label}: {fact.value}", *_under(fact, noun)]
    return paragraphs


def _funder(funder: Named | None) -> list[str]:
    if funder is None:
        return [f"Funder: {NOT_STATED}"]
    return [f"Funder: {funder.name}"] if funder.found else [f"Funder: {funder.name}", NAME_WARNING]


def _call_facts(call: Call) -> list[str]:
    opening, deadline = call.opening, call.deadline
    return [
        f"# {call.title}",
        f"Type: {call.type}",
        *_funder(call.funder),
        *([f"Opens: {NOT_STATED}"] if opening is None else [f"Opens: {day(opening.date)}", *_under(opening, "call")]),
        f"Deadline: {STAYS_OPEN if deadline.date is None else day(deadline.date)}",
        *_under(deadline, "call"),
        *_sentences(
            (
                ("Budget", call.budget),
                ("Summary", call.summary),
                ("Who can apply", call.eligibility),
                ("Where", call.area),
            ),
            "call",
        ),
    ]


def _report_facts(report: Report) -> list[str]:
    published = NOT_STATED if report.published is None else day(report.published)
    return [
        f"# {report.title}",
        f"Type: {report.type}",
        f"Published: {published}",
        *_sentences(
            (
                ("Organisation", report.organisation),
                ("Who it was for", report.audience),
                ("Method", report.methodology),
                ("Results", report.results),
                ("How long it ran", report.duration),
                ("Where", report.area),
            ),
            "report",
        ),
    ]


def _card(record: Call | Report, facts: list[str]) -> str:
    # Each paragraph stands apart, because github.com joins lines that touch and takes a line after a quote into it.
    paragraphs = [
        *facts,
        f"Link: {record.link}",
        f"Read by {record.model}, with the instructions {record.instructions}",
    ]
    return "\n".join(record_block(record)) + "\n\n" + "\n\n".join(paragraphs) + "\n"


def card(call: Call) -> str:
    return _card(call, _call_facts(call))


def report_card(report: Report) -> str:
    return _card(report, _report_facts(report))
