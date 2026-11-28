"""Read one stored call into a call record.

Makes the text a language model reads from a stored call: four labelled lines (the title, the
opening date, the deadline and the budget), then the call's words. For a call stored with its record,
the lines are written from the record's fields, and the words are the description, when the record
has one, and the conditions, with the page's tags stripped. For a call stored as its page alone, the
title is the one the list gave, the deadline is the one date tag on the page, the opening date and
the budget are not stated, and the words are all the page's text, without its scripts and styles.
Gives a later kind the text of a call it holds: the same text, or a page's words alone, since one closing
date is a call's rule.
Gives the topic check what it reads of a stored call: its title; the call title of a call stored with
its record; and its body, that record's description, read by the same rule as the words above.
Takes the topics the check made, and prepares the reading before any request: the text, the
instructions kept beside this file, and how an answer is used. Reads the one command line of an answer
and looks for each quoted sentence in the text. Builds the record from the four fields, the five facts
the model names and those topics, with the link, the call's identifier and the names of the model and
the instructions. Marks each sentence, and the funder's name, found or not found; a name not found is
never a reason to ask again. Gives the record with a note for each sentence and name not found, for
each empty field among the funder, who can apply and where, saying what the answer did, for an opening
date or a budget the source's page has no field for, and for a record with no description.
"""

import datetime as dt
import json
from dataclasses import dataclass
from typing import Any, cast, override

from pydantic import ValidationError

from field_monitoring_pipeline.data.fetch import JSON
from field_monitoring_pipeline.data.models import NOT_STATED, Call, Deadline, Named, Opening, Quoted, Topic
from field_monitoring_pipeline.data.reading import (
    AGAIN,
    MARKED_NOT_STATED,
    MODEL,
    NOT_MENTIONED,
    Answer,
    Prepared,
    Refused,
    Usable,
    Words,
    flags,
    found,
    line,
    miss,
    not_found,
    pair,
    plain,
    refusals,
    tidy,
)
from field_monitoring_pipeline.data.store import Saved
from field_monitoring_pipeline.data.tags import Parts, Subject

INSTRUCTIONS = "v3"
LABELS = ("Title", "Opening date", "Deadline", "Budget")
QUOTED = frozenset({"funder", "summary", "summary-quote", "eligibility", "eligibility-quote", "area", "area-quote"})
PLAIN = frozenset({"type"})
ALONE = frozenset({"funder-not-stated", "eligibility-not-stated", "area-not-stated"})
# The boxes our code copies from a field of the record; a call stored as its page alone has no such field.
COPIED = frozenset({"opening", "budget"})
# How a note names each box, in the record's own order.
NAMES = {
    "funder": "funder",
    "opening": "opening date",
    "deadline": "deadline",
    "budget": "budget",
    "summary": "summary",
    "eligibility": "who can apply",
    "area": "where",
}


@dataclass(frozen=True)
class _Stored:
    text: str
    words: str
    title: str
    opening: Opening | None
    deadline: Deadline
    budget: Quoted | None
    link: str
    identifier: str
    described: bool


class _EitiCallPage(Words):
    # A stored page's words, and the closing date of each <time> that carries one.
    def __init__(self) -> None:
        super().__init__()
        self.times: list[str] = []

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "time" and (when := dict(attrs).get("datetime")) is not None:
            self.times.append(when)
        super().handle_starttag(tag, attrs)


def _amount(number: int | str) -> str:
    return f"{int(number):,}".replace(",", " ") + " €"


def _metadata(record: JSON) -> dict[str, Any]:
    return cast("dict[str, Any]", record)["metadata"]


def _facts(metadata: dict[str, Any]) -> tuple[str, tuple[dt.date, str], tuple[dt.date, str], tuple[str, str]]:
    identifier = metadata["identifier"][0]
    groups = json.loads(metadata["budgetOverview"][0])["budgetTopicActionMap"].values()
    # The budget field holds a line for every call in the same programme; the call's own starts with its identifier.
    [(own, shared)] = [
        (line, len(group)) for group in groups for line in group if line["action"].startswith(identifier + " ")
    ]
    [(year, pot)] = own["budgetYearMap"].items()
    budget = _amount(pot)
    # Several lines in one group are one pot the portal's topics of this call share, and each line repeats the
    # whole amount.
    if shared > 1:
        budget += f" (shared by the {shared} topics of this call)"
    least, most = own["minContribution"], own["maxContribution"]
    # The portal writes 0 where it gives no amount, so an amount of 0 means the source gives nothing more.
    if most:
        if least == most:
            each = _amount(most)
        elif not least:
            each = f"up to {_amount(most)}"
        else:
            each = f"{_amount(least)} to {_amount(most)}"
        budget += f" (each winning project: {each})"
    budget_line = f"{LABELS[3]} {year}: {budget}"
    if own["expectedGrants"]:
        budget_line += f"; winning projects expected: {own['expectedGrants']}"
    opening = dt.date.fromisoformat(metadata["startDate"][0][:10])
    deadlines = sorted(dt.date.fromisoformat(date[:10]) for date in metadata["deadlineDate"])
    deadline_line = f"{LABELS[2]}: {deadlines[0]}"
    if len(deadlines) > 1:
        deadline_line += f" (two stages: {' and '.join(map(str, deadlines))})"
    return (
        metadata["title"][0],
        (opening, f"{LABELS[1]}: {opening}"),
        (deadlines[0], deadline_line),
        (budget, budget_line),
    )


def _description(metadata: dict[str, Any]) -> list[str]:
    # The description is a one-item list; the portal can give a call an empty one, which leaves no description.
    return [plain(text) for text in metadata["descriptionByte"][:1]]


def _stored(record: JSON) -> _Stored:
    metadata = _metadata(record)
    title, (opening, opening_line), (deadline, deadline_line), (budget, budget_line) = _facts(metadata)
    lines = [f"{LABELS[0]}: {tidy(title)}", opening_line, deadline_line, budget_line]
    # A call with no description is read from its conditions alone.
    description = _description(metadata)
    joined = "\n".join([*lines, *description, plain(metadata["topicConditions"][0])])
    words = tidy(joined)
    return _Stored(
        text=joined,
        words=words,
        title=title,
        opening=Opening(date=opening, quote=opening_line, found=found(opening_line, words)),
        deadline=Deadline(date=deadline, quote=deadline_line, found=found(deadline_line, words)),
        budget=Quoted(value=budget, quote=budget_line, found=found(budget_line, words)),
        link=metadata["url"][0],
        identifier=metadata["identifier"][0],
        described=bool(description),
    )


def _eiti_page(call: Saved, page: bytes) -> _Stored:
    parser = _EitiCallPage()
    parser.feed(page.decode("utf-8"))
    parser.close()
    if len(parser.times) != 1:
        raise ValueError(f"the page must hold exactly one closing date; it holds {len(parser.times)}")
    [when] = parser.times
    try:
        deadline = dt.date.fromisoformat(when[:10])
    except ValueError as error:
        raise ValueError(f"the page's closing date cannot be read: {when!r}") from error
    deadline_line = f"{LABELS[2]}: {deadline}"
    lines = [f"{LABELS[0]}: {tidy(call.title)}", f"{LABELS[1]}: {NOT_STATED}", deadline_line]
    joined = "\n".join([*lines, f"{LABELS[3]}: {NOT_STATED}", tidy("".join(parser.pieces))])
    words = tidy(joined)
    return _Stored(
        text=joined,
        words=words,
        title=call.title,
        opening=None,
        deadline=Deadline(date=deadline, quote=deadline_line, found=found(deadline_line, words)),
        budget=None,
        link=call.link,
        identifier=call.identifier,
        described=True,
    )


def text(record: JSON) -> str:
    return _stored(record).text


def held_text(kept: JSON | bytes) -> str:
    # A held call's text for a later kind's reading: its record's text, or its page's words without the
    # check of one closing date, which is a call's rule.
    return plain(kept.decode("utf-8")) if isinstance(kept, bytes) else text(kept)


def _funder(given: dict[str, object], words: str) -> dict[str, object] | None:
    name = given.get("funder")
    # Only text is tidied; any other value goes under the name, where the template finds it is not text.
    if name is None or (isinstance(name, str) and not tidy(name)):
        return None
    return {"name": name, "found": found(name, words)}


def _notes(call: Call, given: dict[str, object], *, described: bool) -> list[str]:
    notes: list[str] = []
    for name, label in NAMES.items():
        box = getattr(call, name)
        alone = f"{name}-not-stated"
        if isinstance(box, Opening | Deadline | Quoted) and not box.found:
            notes.append(not_found(label, "call", box.quote))
        elif isinstance(box, Named) and not box.found:
            notes.append(f"{label}: this name was not found in the call: {box.name}")
        elif box is None and alone in given:
            notes.append(f"{label}: {MARKED_NOT_STATED}")
        # Only the funder reaches this: a sentence field that is given is always built by pair,
        # so its box is never empty.
        elif box is None and name in given:
            notes.append(f"{label}: empty, because the model's answer gave no name")
        elif box is None and alone in ALONE and name not in given:
            notes.append(f"{label}: {NOT_MENTIONED}")
        elif box is None and name in COPIED:
            notes.append(f"{label}: empty, because this source's page has no field for it")
    if not described:
        notes.append("description: empty, because the source's record has none")
    return notes


def _build(stored: _Stored, found: tuple[Topic, ...], reply: str) -> tuple[Call, list[str]]:
    given = flags(line(reply), alone=ALONE, quoted=QUOTED, plain_words=PLAIN)
    call = Call.model_validate({
        "title": stored.title,
        "type": given.get("type"),
        "funder": _funder(given, stored.words),
        "opening": stored.opening,
        "deadline": stored.deadline,
        "budget": stored.budget,
        "summary": pair(given, "summary", stored.words),
        "eligibility": pair(given, "eligibility", stored.words),
        "area": pair(given, "area", stored.words),
        "topics": found,
        "link": stored.link,
        "identifier": stored.identifier,
        "model": MODEL,
        "instructions": INSTRUCTIONS,
    })
    return call, _notes(call, given, described=stored.described)


def build(record: JSON, found: tuple[Topic, ...], reply: str) -> tuple[Call, list[str]]:
    return _build(_stored(record), found, reply)


def _misses(call: Call) -> list[str]:
    # The sentences the model gave, each named by the flag it wrote.
    sentences = {"summary-quote": call.summary, "eligibility-quote": call.eligibility, "area-quote": call.area}
    return [miss(flag) for flag, fact in sentences.items() if fact is not None and not fact.found]


def _use(stored: _Stored, found: tuple[Topic, ...], reply: str) -> Answer[Call]:
    try:
        call, notes = _build(stored, found, reply)
    except ValidationError as error:
        return Refused(refusals(error))
    except ValueError as error:
        return Refused([str(error)])
    return Usable(record=call, notes=notes, misses=_misses(call))


CALL_PARTS = Parts(head="titles", body="description")


def subject(call: Saved, kept: JSON | bytes) -> Subject:
    # A page alone is EITI's, which gives no call title and no description; its call is checked on its list's title.
    if isinstance(kept, bytes):
        return Subject(title=call.title, other_titles=(), body="", parts=CALL_PARTS)
    metadata = _metadata(kept)
    # The call title is a one-item list, as the description is; an empty list leaves the title alone as the head.
    return Subject(
        title=metadata["title"][0],
        other_titles=tuple(metadata["callTitle"][:1]),
        body=" ".join(_description(metadata)),
        parts=CALL_PARTS,
    )


def prepare(call: Saved, kept: JSON | bytes, found: tuple[Topic, ...]) -> Prepared[Call]:
    # The text and the copied facts are made first, so a fault in what was stored stops the reading before any request.
    # A page alone is read by EITI's rule, the one source read from its page.
    stored = _eiti_page(call, kept) if isinstance(kept, bytes) else _stored(kept)
    return Prepared(
        text=stored.text, instructions=INSTRUCTIONS, again=AGAIN, use=lambda reply: _use(stored, found, reply)
    )
