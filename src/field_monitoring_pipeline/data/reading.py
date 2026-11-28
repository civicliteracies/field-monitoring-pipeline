"""Read one item's text with the model, the same way for every kind.

Holds what every kind's reader needs: the words a reader sees on a page, the quote check, the request,
the one command line and its flags, the several lines of a held document's answer, and the two tries. A
kind's reader gives a Prepared: the text, the name of its instructions, the words that open a second try,
its function from a reply to an answer, and, for a held document whose reading stopped, the answers the
log already holds. An answer is usable, with what it gives, or refused, with its problems. A held
document's answer gives one item per command line, or none for the one line that says none; a line that
cannot be read is a problem naming its number, and the other lines stand. The loop asks, hands each answer
on as it arrives, and asks once more, in the same conversation, when the first answer cannot be used, has
a line that cannot be read, or quotes a sentence that is not in the text. An answer the log already holds
stands in place of its request. It keeps the second answer when that can be used, unless the second lost a
line and the first lost none; keeps a usable first answer when the second is refused; and fails only when
both are refused.
"""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Literal, TypedDict, override

import httpx2
from pydantic import ValidationError

from field_monitoring_pipeline.data.models import Topic
from field_monitoring_pipeline.data.store import AnswerWord, Saved
from field_monitoring_pipeline.data.tags import Subject

MODEL = "gemini-3.5-flash-lite"
ADDRESS = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
COMMAND = "fieldbook"
BEGIN = "-----BEGIN SOURCE TEXT-----"
END = "-----END SOURCE TEXT-----"
# A space only where a block begins or ends, so a link or a bold word inside a sentence leaves no space before its stop.
BLOCKS = frozenset({"p", "div", "h4", "li", "ul", "ol", "br"})
# The contents of these tags are not text a reader sees.
HIDDEN = frozenset({"script", "style"})
AGAIN = "This answer cannot be used as it is. Write the one command line again, with each problem below put right:"
AGAIN_LINES = "This answer cannot be used as it is. Write every command line again, with each problem below put right:"
# The one line of a held document's answer that says it names no item.
NONE = "--none"
FIRST_ANSWER: AnswerWord = "first answer"
SECOND_ANSWER: AnswerWord = "second answer"
_FLAG = re.compile(r"\s*--([a-z-]+)\s*")
_WORD = re.compile(r"[^\s\"]+")


class Message(TypedDict):
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class Usable[R]:
    """An answer that can be used: what it gives, its notes, the sentences it quotes that are not in the text."""

    record: R
    notes: list[str]
    misses: list[str]
    # A held document's lines that could not be read; an own item's answer is one line, so it has none.
    unread: list[str] = field(default_factory=list[str])


@dataclass(frozen=True)
class Refused:
    """An answer that cannot be read at all, with each problem it has."""

    problems: list[str]


type Answer[R] = Usable[R] | Refused


@dataclass(frozen=True)
class Found[R]:
    """One item found in a held document: what the topic check reads of it, its record once it has topics, its notes."""

    # Its order in the answer: the number of its line among the answer's command lines.
    order: int
    subject: Subject
    record: Callable[[Saved, tuple[Topic, ...]], R]
    notes: list[str]


@dataclass(frozen=True)
class Prepared[R]:
    text: str
    instructions: str
    again: str
    use: Callable[[str], Answer[R]]
    # The answers the log already holds for a held document whose reading stopped; an own item gives none.
    earlier: tuple[str, ...] = ()


class Words(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.pieces: list[str] = []
        self.hidden = False

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.hidden = self.hidden or tag in HIDDEN
        if tag in BLOCKS:
            self.pieces.append(" ")

    @override
    def handle_endtag(self, tag: str) -> None:
        self.hidden = self.hidden and tag not in HIDDEN
        if tag in BLOCKS:
            self.pieces.append(" ")

    @override
    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.pieces.append(data)


def tidy(words: str) -> str:
    return " ".join(words.split())


def plain(markup: str) -> str:
    parser = Words()
    parser.feed(markup)
    parser.close()
    return tidy("".join(parser.pieces))


def found(quote: object, words: str) -> bool:
    # A value that is not text (no quote given, a number, an object) is not found;
    # the template then refuses the record, because its fields hold only text.
    # A quote with no words is not a sentence, so it is not found either.
    return isinstance(quote, str) and bool(tidy(quote)) and tidy(quote) in words


def ask(messages: list[Message], key: str, client: httpx2.Client) -> str:
    body = {"model": MODEL, "messages": messages}
    response = client.post(ADDRESS, json=body, headers={"Authorization": f"Bearer {key}"}, timeout=180)
    return response.raise_for_status().json()["choices"][0]["message"]["content"]


def _lines(reply: str) -> list[str]:
    return [each for each in map(str.strip, reply.splitlines()) if each.startswith(COMMAND + " ")]


def line(reply: str) -> str:
    lines = _lines(reply)
    if len(lines) != 1:
        raise ValueError(f"the answer must hold exactly one line beginning with {COMMAND}; it holds {len(lines)}")
    return lines[0]


def refusals(error: ValidationError) -> list[str]:
    return [f"{'.'.join(map(str, problem['loc']))}: {problem['msg']}" for problem in error.errors()]


def several[R](one: Callable[[int, str], tuple[Found[R], list[str]]], reply: str) -> Answer[list[Found[R]]]:
    # Given the kind's function from a line's number and the line to its item and its sentences not found.
    lines = _lines(reply)
    if [each.split() for each in lines] == [[COMMAND, NONE]]:
        return Usable(record=[], notes=[], misses=[])
    items: list[Found[R]] = []
    misses: list[str] = []
    unread: list[str] = []
    for number, each in enumerate(lines, 1):
        try:
            item, missed = one(number, each)
        except ValidationError as error:
            unread += [f"line {number}: {refusal}" for refusal in refusals(error)]
        except ValueError as error:
            unread.append(f"line {number}: {error}")
        else:
            items.append(item)
            misses += [f"line {number}: {problem}" for problem in missed]
    if not items:
        return Refused(unread or [f"the answer must hold a line beginning with {COMMAND} for each item; it holds none"])
    return Usable(record=items, notes=[], misses=misses, unread=unread)


def flags(
    command: str, *, alone: frozenset[str], quoted: frozenset[str], plain_words: frozenset[str]
) -> dict[str, object]:
    given: dict[str, object] = {}
    at = len(COMMAND)
    while at < len(command):
        flag = _FLAG.match(command, at)
        if flag is None:
            raise ValueError("a flag is expected after each value")
        name, at = flag[1], flag.end()
        if name in given:
            raise ValueError(f"--{name} is given twice")
        if name in alone:
            given[name] = ""
        elif name in quoted:
            given[name], at = json.JSONDecoder().raw_decode(command, at)
        elif name not in plain_words:
            raise ValueError(f"--{name} is not a flag the instructions offer")
        elif word := _WORD.match(command, at):
            given[name], at = word[0], word.end()
        else:
            raise ValueError(f"--{name} has no value")
    return given


# The reasons a note gives, the same for every kind; the noun names the text that was searched.
MARKED_NOT_STATED = "empty, because the model marked it not stated"
NOT_MENTIONED = "empty, because the model's answer did not mention it"


def not_found(label: str, noun: str, quote: str) -> str:
    return f"{label}: this sentence was not found in the {noun}: {quote}"


def miss(flag: str) -> str:
    # What a second try is told of a sentence it quoted that is not in the text.
    return f"--{flag}: the sentence must be in the text word for word"


def pair(given: dict[str, object], name: str, words: str) -> dict[str, object] | None:
    if name not in given:
        return None
    quote = given.get(f"{name}-quote")
    return {"value": given[name], "quote": quote, "found": found(quote, words)}


def _problems[R](answer: Answer[R]) -> list[str]:
    match answer:
        case Usable():
            return [*answer.unread, *answer.misses]
        case Refused():
            return answer.problems


def read[R](
    reading: Prepared[R], key: str, client: httpx2.Client, keep: Callable[[AnswerWord, str], None]
) -> tuple[R, list[str]]:
    instructions = (Path(__file__).parent / "instructions" / f"{reading.instructions}.md").read_text(encoding="utf-8")
    messages: list[Message] = [{"role": "user", "content": f"{instructions}\n{BEGIN}\n{reading.text}\n{END}"}]
    # An answer the log already holds stands in place of a request; only an answer asked for is handed on.
    earlier = iter(reading.earlier)
    reply = next(earlier, None)
    if reply is None:
        reply = ask(messages, key, client)
        keep(FIRST_ANSWER, reply)
    first = reading.use(reply)
    if isinstance(first, Usable) and not _problems(first):
        return first.record, first.notes
    noted = [f"{FIRST_ANSWER}: {problem}" for problem in _problems(first)]
    messages.extend([
        {"role": "assistant", "content": reply},
        {"role": "user", "content": "\n".join([reading.again, *_problems(first)])},
    ])
    again = next(earlier, None)
    if again is None:
        try:
            again = ask(messages, key, client)
        except Exception as error:
            error.add_note("; ".join(noted))
            raise
        keep(SECOND_ANSWER, again)
    second = reading.use(again)
    noted += [f"{SECOND_ANSWER}: {problem}" for problem in _problems(second)]
    # When the second lost a line and the first lost none, each of the first's items had an answer that could be used.
    if isinstance(second, Usable) and not (second.unread and isinstance(first, Usable) and not first.unread):
        return second.record, [*noted, *second.notes]
    if isinstance(first, Usable):
        return first.record, [*noted, *first.notes]
    raise ValueError("; ".join(noted))
