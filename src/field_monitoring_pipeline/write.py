"""Write a call record as a card, and read a card back into the same record.

A card is one Markdown file. On top, between two `---` lines, sits the record, one field per line,
each value written in JSON. A field that holds a sentence is written over several lines, its parts
indented under it. Below is the half for people: the title, then each fact on its own line. The
funder's own sentence sits under the summary, who can apply and where, and the source's own line
under the dates and the budget. A sentence not found has a warning under it, and an empty field says
"not stated". The link and the model and instructions that read the call come last.
"""

import datetime as dt
import json
from typing import cast

from field_monitoring_pipeline.models import Call, Deadline, Opening, Quoted

FENCE = "---"
NOT_STATED = "not stated"
WARNING = "This sentence was not found in the call."
STAYS_OPEN = "stays open"


def day(date: dt.date) -> str:
    return f"{date.day} {date:%B %Y}"


def _block(call: Call) -> list[str]:
    lines = [FENCE]
    for name, value in call.model_dump(mode="json").items():
        if isinstance(value, dict):
            lines.append(f"{name}:")
            lines += [f"  {part}: {json.dumps(inner)}" for part, inner in cast("dict[str, object]", value).items()]
        else:
            lines.append(f"{name}: {json.dumps(value)}")
    return [*lines, FENCE]


def _under(fact: Opening | Deadline | Quoted) -> list[str]:
    return [f"> {fact.quote}"] if fact.found else [f"> {fact.quote}", WARNING]


def _facts(call: Call) -> list[str]:
    opening, deadline = call.opening, call.deadline
    paragraphs = [
        f"# {call.title}",
        f"Type: {call.type}",
        f"Funder: {NOT_STATED if call.funder is None else call.funder}",
        *([f"Opens: {NOT_STATED}"] if opening is None else [f"Opens: {day(opening.date)}", *_under(opening)]),
        f"Deadline: {STAYS_OPEN if deadline.date is None else day(deadline.date)}",
        *_under(deadline),
    ]
    for label, fact in (
        ("Budget", call.budget),
        ("Summary", call.summary),
        ("Who can apply", call.eligibility),
        ("Where", call.area),
    ):
        paragraphs += [f"{label}: {NOT_STATED}"] if fact is None else [f"{label}: {fact.value}", *_under(fact)]
    return [*paragraphs, f"Link: {call.link}", f"Read by {call.model}, with the instructions {call.instructions}"]


def card(call: Call) -> str:
    # Each paragraph stands apart, because github.com joins lines that touch and takes a line after a quote into it.
    return "\n".join(_block(call)) + "\n\n" + "\n\n".join(_facts(call)) + "\n"


def read_card(text: str) -> Call:
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
    return Call.model_validate(fields)
