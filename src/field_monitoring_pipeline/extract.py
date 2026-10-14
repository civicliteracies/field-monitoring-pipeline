"""Read one stored call into a call record.

Makes the text a language model reads from a stored call: four labelled lines written from the
record's fields (the title, the opening date, the deadline and the budget), then the description and
the conditions with the page's tags stripped. Asks the model once, under the instructions kept beside
this file, and reads the one command line of its reply. Builds the record from the four fields and the
five facts the model names, with the link and the names of the model and the instructions.
"""

import datetime as dt
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, cast, override

import httpx2

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
_FLAG = re.compile(r"\s*--([a-z-]+)\s*")
_WORD = re.compile(r"[^\s\"]+")


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


def _facts(metadata: dict[str, Any]) -> tuple[str, Opening, Deadline, Quoted]:
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
        Opening(date=opening, quote=f"{LABELS[1]}: {opening}"),
        Deadline(date=deadlines[0], quote=deadline_line),
        Quoted(value=budget, quote=budget_line),
    )


def text(record: JSON) -> str:
    metadata = _metadata(record)
    title, opening, deadline, budget = _facts(metadata)
    lines = [f"{LABELS[0]}: {_tidy(title)}", opening.quote, deadline.quote, budget.quote]
    return "\n".join([*lines, _plain(metadata["descriptionByte"][0]), _plain(metadata["topicConditions"][0])])


def ask(words: str, key: str, client: httpx2.Client) -> str:
    instructions = (Path(__file__).parent / "instructions" / f"{INSTRUCTIONS}.md").read_text(encoding="utf-8")
    body = {"model": MODEL, "messages": [{"role": "user", "content": f"{instructions}\n{BEGIN}\n{words}\n{END}"}]}
    response = client.post(ADDRESS, json=body, headers={"Authorization": f"Bearer {key}"}, timeout=180)
    return response.raise_for_status().json()["choices"][0]["message"]["content"]


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


def _pair(given: dict[str, object], name: str) -> dict[str, object] | None:
    return {"value": given[name], "quote": given.get(f"{name}-quote")} if name in given else None


def build(record: JSON, reply: str) -> Call:
    metadata = _metadata(record)
    title, opening, deadline, budget = _facts(metadata)
    [line] = [line.strip() for line in reply.splitlines() if line.strip().startswith(COMMAND + " ")]
    given = _flags(line)
    return Call.model_validate({
        "title": title,
        "type": given.get("type"),
        "funder": given.get("funder"),
        "opening": opening,
        "deadline": deadline,
        "budget": budget,
        "summary": _pair(given, "summary"),
        "eligibility": _pair(given, "eligibility"),
        "area": _pair(given, "area"),
        "link": metadata["url"][0],
        "model": MODEL,
        "instructions": INSTRUCTIONS,
    })
