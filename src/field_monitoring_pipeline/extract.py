"""Read one stored call into a call record.

Makes the text a language model reads from a stored call: four labelled lines written from the
record's fields (the title, the opening date, the deadline and the budget), then the description and
the conditions with the page's tags stripped. Asks the model under the instructions kept beside this
file, reads the one command line of its answer, and looks for each quoted sentence in the text. When
the answer cannot be used or a sentence is not found, asks once more, in the same conversation,
naming each problem. Builds the record from the four fields and the five facts the model names, with
the link, the call's identifier and the names of the model and the instructions. Marks each sentence
found or not found, and returns the record with a note for each problem, each sentence not found and
each empty field.
"""

import datetime as dt
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Literal, TypedDict, cast, override

import httpx2
from pydantic import ValidationError

from field_monitoring_pipeline.fetch import JSON
from field_monitoring_pipeline.models import Call, Deadline, Opening, Quoted

MODEL = "gemini-3.5-flash-lite"
ADDRESS = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
INSTRUCTIONS = "v3"
COMMAND = "fieldbook"
BEGIN = "-----BEGIN SOURCE TEXT-----"
END = "-----END SOURCE TEXT-----"
LABELS = ("Title", "Opening date", "Deadline", "Budget")
# A space only where a block begins or ends, so a link or a bold word inside a sentence leaves no space before its stop.
BLOCKS = frozenset({"p", "div", "h4", "li", "ul", "ol", "br"})
QUOTED = frozenset({"funder", "summary", "summary-quote", "eligibility", "eligibility-quote", "area", "area-quote"})
PLAIN = frozenset({"type"})
ALONE = frozenset({"funder-not-stated", "eligibility-not-stated", "area-not-stated"})
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
AGAIN = "This answer cannot be used as it is. Write the one command line again, with each problem below put right:"
_FLAG = re.compile(r"\s*--([a-z-]+)\s*")
_WORD = re.compile(r"[^\s\"]+")


class Message(TypedDict):
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class _Stored:
    text: str
    words: str
    title: str
    opening: Opening
    deadline: Deadline
    budget: Quoted
    link: str
    identifier: str


@dataclass(frozen=True)
class _Answer:
    call: Call | None
    notes: list[str]
    problems: list[str]


class _Words(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.pieces: list[str] = []

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in BLOCKS:
            self.pieces.append(" ")

    @override
    def handle_endtag(self, tag: str) -> None:
        if tag in BLOCKS:
            self.pieces.append(" ")

    @override
    def handle_data(self, data: str) -> None:
        self.pieces.append(data)


def _tidy(words: str) -> str:
    return " ".join(words.split())


def _plain(markup: str) -> str:
    parser = _Words()
    parser.feed(markup)
    parser.close()
    return _tidy("".join(parser.pieces))


def _amount(number: int | str) -> str:
    return f"{int(number):,}".replace(",", " ") + " €"


def _metadata(record: JSON) -> dict[str, Any]:
    return cast("dict[str, Any]", record)["metadata"]


def _facts(metadata: dict[str, Any]) -> tuple[str, tuple[dt.date, str], tuple[dt.date, str], tuple[str, str]]:
    identifier = metadata["identifier"][0]
    groups = json.loads(metadata["budgetOverview"][0])["budgetTopicActionMap"].values()
    # The budget field holds a line for every call in the same programme; the call's own starts with its identifier.
    [(own, topics)] = [
        (line, len(group)) for group in groups for line in group if line["action"].startswith(identifier + " ")
    ]
    [(year, pot)] = own["budgetYearMap"].items()
    budget = _amount(pot)
    # Several lines in one group are one pot the call's topics share, and each line repeats the whole amount.
    if topics > 1:
        budget += f" (shared by the {topics} topics of this call)"
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


def _found(quote: object, words: str) -> bool:
    # A sentence that is not text (missing, or a number) is not found, and the template then refuses it.
    return isinstance(quote, str) and _tidy(quote) in words


def _stored(record: JSON) -> _Stored:
    metadata = _metadata(record)
    title, (opening, opening_line), (deadline, deadline_line), (budget, budget_line) = _facts(metadata)
    lines = [f"{LABELS[0]}: {_tidy(title)}", opening_line, deadline_line, budget_line]
    joined = "\n".join([*lines, _plain(metadata["descriptionByte"][0]), _plain(metadata["topicConditions"][0])])
    words = _tidy(joined)
    return _Stored(
        text=joined,
        words=words,
        title=title,
        opening=Opening(date=opening, quote=opening_line, found=_found(opening_line, words)),
        deadline=Deadline(date=deadline, quote=deadline_line, found=_found(deadline_line, words)),
        budget=Quoted(value=budget, quote=budget_line, found=_found(budget_line, words)),
        link=metadata["url"][0],
        identifier=metadata["identifier"][0],
    )


def text(record: JSON) -> str:
    return _stored(record).text


def ask(messages: list[Message], key: str, client: httpx2.Client) -> str:
    body = {"model": MODEL, "messages": messages}
    response = client.post(ADDRESS, json=body, headers={"Authorization": f"Bearer {key}"}, timeout=180)
    return response.raise_for_status().json()["choices"][0]["message"]["content"]


def _line(reply: str) -> str:
    lines = [line for line in map(str.strip, reply.splitlines()) if line.startswith(COMMAND + " ")]
    if len(lines) != 1:
        raise ValueError(f"the answer must hold exactly one line beginning with {COMMAND}; it holds {len(lines)}")
    return lines[0]


def _flags(line: str) -> dict[str, object]:
    given: dict[str, object] = {}
    at = len(COMMAND)
    while at < len(line):
        flag = _FLAG.match(line, at)
        if flag is None:
            raise ValueError("a flag is expected after each value")
        name, at = flag[1], flag.end()
        if name in given:
            raise ValueError(f"--{name} is given twice")
        if name in ALONE:
            given[name] = ""
        elif name in QUOTED:
            given[name], at = json.JSONDecoder().raw_decode(line, at)
        elif name not in PLAIN:
            raise ValueError(f"--{name} is not a flag the instructions offer")
        elif word := _WORD.match(line, at):
            given[name], at = word[0], word.end()
        else:
            raise ValueError(f"--{name} has no value")
    return given


def _pair(given: dict[str, object], name: str, words: str) -> dict[str, object] | None:
    if name not in given:
        return None
    quote = given.get(f"{name}-quote")
    return {"value": given[name], "quote": quote, "found": _found(quote, words)}


def _notes(call: Call, given: dict[str, object]) -> list[str]:
    notes: list[str] = []
    for name, label in NAMES.items():
        box = getattr(call, name)
        alone = f"{name}-not-stated"
        if isinstance(box, Opening | Deadline | Quoted) and not box.found:
            notes.append(f"{label}: this sentence was not found in the call: {box.quote}")
        elif box is None and alone in given:
            notes.append(f"{label}: empty, because the model marked it not stated")
        elif box is None and alone in ALONE and name not in given:
            notes.append(f"{label}: empty, because the model's answer did not mention it")
    return notes


def _build(stored: _Stored, reply: str) -> tuple[Call, list[str]]:
    given = _flags(_line(reply))
    call = Call.model_validate({
        "title": stored.title,
        "type": given.get("type"),
        "funder": given.get("funder"),
        "opening": stored.opening,
        "deadline": stored.deadline,
        "budget": stored.budget,
        "summary": _pair(given, "summary", stored.words),
        "eligibility": _pair(given, "eligibility", stored.words),
        "area": _pair(given, "area", stored.words),
        "link": stored.link,
        "identifier": stored.identifier,
        "model": MODEL,
        "instructions": INSTRUCTIONS,
    })
    return call, _notes(call, given)


def build(record: JSON, reply: str) -> tuple[Call, list[str]]:
    return _build(_stored(record), reply)


def _misses(call: Call) -> list[str]:
    # The sentences the model gave, each named by the flag it wrote.
    sentences = {"summary-quote": call.summary, "eligibility-quote": call.eligibility, "area-quote": call.area}
    return [
        f"--{flag}: the sentence must be in the text word for word"
        for flag, fact in sentences.items()
        if fact is not None and not fact.found
    ]


def _use(stored: _Stored, reply: str) -> _Answer:
    try:
        call, notes = _build(stored, reply)
    except ValidationError as error:
        refused = [f"{'.'.join(map(str, problem['loc']))}: {problem['msg']}" for problem in error.errors()]
        return _Answer(call=None, notes=[], problems=refused)
    except ValueError as error:
        return _Answer(call=None, notes=[], problems=[str(error)])
    return _Answer(call=call, notes=notes, problems=_misses(call))


def read(record: JSON, key: str, client: httpx2.Client) -> tuple[Call, list[str]]:
    # The text and the copied facts are made first, so a fault in the stored record stops the reading before any request.
    stored = _stored(record)
    instructions = (Path(__file__).parent / "instructions" / f"{INSTRUCTIONS}.md").read_text(encoding="utf-8")
    messages: list[Message] = [{"role": "user", "content": f"{instructions}\n{BEGIN}\n{stored.text}\n{END}"}]
    reply = ask(messages, key, client)
    first = _use(stored, reply)
    if first.call is not None and not first.problems:
        return first.call, first.notes
    noted = [f"first answer: {problem}" for problem in first.problems]
    messages.extend([
        {"role": "assistant", "content": reply},
        {"role": "user", "content": "\n".join([AGAIN, *first.problems])},
    ])
    try:
        again = ask(messages, key, client)
    except Exception as error:
        error.add_note("; ".join(noted))
        raise
    second = _use(stored, again)
    noted += [f"second answer: {problem}" for problem in second.problems]
    if second.call is not None:
        return second.call, [*noted, *second.notes]
    if first.call is not None:
        return first.call, [*noted, *first.notes]
    raise ValueError("; ".join(noted))
