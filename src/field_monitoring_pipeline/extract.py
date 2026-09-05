"""The one step where a machine reads meaning out of a page's words.

Everything else in this system is deterministic: a page is fetched, written down
and named, and the same input always gives the same output. Here a model reads a
captured item and says what it found. Because a model can be wrong in ways no
check can see, the shape of the answer is deliberately narrow: it reasons in
plain prose, then writes one command line naming what it found, and code this
project owns parses that line and checks every claim against the page before a
record exists.

Nothing here writes a file. It returns a record and the three versions that
produced it. Writing the card, and holding an item that fails twice, are later
steps.
"""

from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from html.parser import HTMLParser
from typing import TYPE_CHECKING, Protocol, TypeIs, get_args

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from field_monitoring_pipeline.models import (
    Call,
    CallType,
    Dated,
    Extraction,
    Field,
    Open,
    OpenBasis,
    RawItem,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from field_monitoring_pipeline.models import Timing

BUILDER_VERSION = "b1"
"""The version of the deterministic side: this file's parsing and checking.

It is stored on every record so a value is attributable to the logic that made
it. Bump it when a change alters what this file accepts or produces, and pair
that bump with a decision record and a rebuild. See ADR-0034.
"""

MARKER = "fieldbook"
MAX_REPLY = 60_000
MAX_LINE = 8_000
MIN_QUOTE = 10
MAX_QUOTE = 400
READ_SECONDS = 180.0
CONNECT_SECONDS = 20.0
"""How long one model request may take, split by which part is waiting.

The reading limit is measured rather than guessed: a six thousand character page
with this instruction, answered with a few thousand characters of reasoning, took
long enough to pass sixty seconds at least once. Reaching the far end is a
different matter and gets the same twenty seconds the fetch step allows, because
a name that will not resolve should fail quickly rather than at the pace of a
long answer. Both bound one request and neither is a limit on a whole run, which
the project rules out.
"""

FENCE = "-----BEGIN SOURCE TEXT-----"
FENCE_END = "-----END SOURCE TEXT-----"
FORGED = re.compile(f"(?:{re.escape(FENCE)}|{re.escape(FENCE_END)})")
"""A delimiter written by the page rather than by this code.

Matched wherever it appears. An earlier version matched one alone on its line,
which a page defeated by writing its own prose straight after the delimiter on
the same line, and again by ending the line the Windows way. Neither shape is
exotic. Matching the delimiter itself removes the whole class. BUG-028.

Compiled once here rather than inside the function, like every other pattern in
this file.
"""


class MalformedCommandError(Exception):
    """The reply could not be read as a command. The model is told and tries again."""


class UngroundedClaimError(Exception):
    """A claim is not supported by the source text. Also worth one attempt more."""


class TransientFailureError(Exception):
    """A failure worth one more try, because the request never reached the model.

    Kept apart from the refusals that are permanent for this run. Nothing outside
    the model client sees this: by the time it leaves, it is either an answer or
    a model that could not be reached.
    """


class ModelUnreachableError(Exception):
    """No reply at all: refused, rate limited, timed out, or the model is gone.

    Kept apart from a malformed command on purpose. When a free tier runs out,
    every item fails the same way, and a run that reads as "extraction is broken"
    sends someone looking in the wrong place.
    """


class HeldAfterTwoTriesError(Exception):
    """Two attempts failed. Nothing is built and nothing is written."""


class Model(Protocol):
    """The one seam. A test passes a stand-in and the suite never leaves the machine."""

    def __call__(self, prompt: str) -> str:
        """Send the prompt and return the model's reply as text."""
        ...


# --------------------------------------------------- turning a capture into text

BLOCK_ENDS = "\n\n"
"""What the end of one block of text is written as before anything reads it.

A blank line, always, because that is the only thing the collapsing step treats
as a boundary a quote cannot cross. A single line break was written here first,
and one arrives inside a block too, from a page that wraps its own source. The
collapsing step cannot tell those apart, so it treated both as ordinary space and
the boundary was lost for every shape that produced only one: a line break inside
a paragraph, a block followed by loose text, and one page written `<br>` while
the same page written `<br/>` was fenced correctly. Both frozen pages carry the
first of those. BUG-019 was recorded as fixed and was not.
"""

_BLOCK = frozenset({
    "p",
    "div",
    "li",
    "tr",
    # A cell is its own block. Without these two, the cells of one row were run
    # together with nothing at all between them, so a label in one column and a
    # figure in another read as a single sentence a quote could be built from.
    "td",
    "th",
    "br",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "section",
    "article",
    "header",
    "ul",
    "ol",
    "table",
    "blockquote",
    "figcaption",
    "dd",
    "dt",
})
_SKIP = frozenset({
    # Never words at all.
    "script",
    "style",
    "noscript",
    "template",
    "svg",
    # A page's own furniture. A menu on a funder's site lists that funder's other
    # programmes, and a sentence from one of those is a real substring of this
    # page, so it would pass the quote check while describing a different grant.
    # Measured on both fixtures: dropping these keeps every fact and removes the
    # menus. `header` is deliberately not here, because one of the two pages puts
    # its own heading inside one.
    "nav",
    "footer",
    "aside",
    "form",
})
_INVISIBLE = {0x00A0: " ", 0x200B: None, 0x00AD: None, 0xFEFF: None}


class _ToText(HTMLParser):
    """Keeps the words and drops the markup, using the standard library only."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        # The names of the furniture tags currently open, innermost last. A count
        # would be simpler and was what this held first, but a page that closes a
        # tag it never opened then decrements the count and lets the rest of a
        # menu through as though it were the article. Real pages built by a
        # template do drop tags that way. Matching by name means an unmatched
        # closing tag is what it is, a stray, and changes nothing. BUG-021.
        self.inside: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in _SKIP:
            self.inside.append(tag)
        elif tag in _BLOCK:
            self.out.append(BLOCK_ENDS)

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP:
            if tag in self.inside:
                # Everything opened inside the one being closed is closed with
                # it, and it is the innermost one of that name that is closing.
                # Taking the outermost meant a menu inside a menu ended both, and
                # the rest of the page's furniture was read as the article. That
                # is the very thing matching by name was introduced to stop.
                del self.inside[len(self.inside) - 1 - self.inside[::-1].index(tag) :]
        elif tag in _BLOCK:
            self.out.append(BLOCK_ENDS)

    def handle_data(self, data: str) -> None:
        if not self.inside:
            self.out.append(data)


def readable(captured: str) -> str:
    """The one string the model reads and every quote is checked against.

    A captured item is rarely plain words. A feed entry carries markup inside it
    and a page carries a great deal, and a sentence with a bold word in the
    middle is not one run of characters in the source. So the same derivation
    runs before the model sees the text and before any quote is checked, and both
    sides therefore agree about what the source says.
    """
    parser = _ToText()
    parser.feed(captured)
    parser.close()
    text = "".join(parser.out).translate(_INVISIBLE)
    # A server may end its lines the Windows way, and one of the two frozen pages
    # does. Left alone, a carriage return sits between a line's last character and
    # its newline, so any rule anchored to the end of a line quietly stops
    # matching. That is how a page could still forge the fence in the prompt. The
    # endings are settled here, once, for every reader of this string. BUG-020.
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    # A tag boundary often leaves a space at the end of a line. It is invisible
    # to a reader and would otherwise sit inside a stored quote, so it goes here.
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


BOUNDARY = chr(0xE000)
"""What the end of one block of text is turned into before two strings compare.

It is the first character of the private use area, which no page can mean
anything by and nothing renders. Any copy of it arriving in the text is turned
into a space first, so only a real boundary can ever produce one and nothing can
be smuggled in to imitate one.

The obvious choice, the record separator, is wrong: Python counts it as
whitespace, so the very step this has to survive would collapse it away again.
Measured rather than assumed, after the first attempt did exactly that.
"""


def flat(value: str) -> str:
    """Whitespace collapsed and characters composed, for comparison only.

    Never stored. A card keeps a quote as the source wrote it; this is only how
    two strings are compared, so that a line break in the page does not make a
    sentence fail to match itself.

    The end of a block of text is not whitespace. Collapsing it to a space would
    let a quote begin in one paragraph and end in the next, joining two unrelated
    sentences into something that reads as one and passes as real. That is the
    check the whole record rests on, so the boundary is kept as a character a
    quote cannot cross. A quote that really does span two blocks, copied whole,
    still carries the boundary and still matches. BUG-019.

    NFC and not NFKC. The compatibility form rewrites characters that carry
    meaning here: it turns a superscript five into a plain five, so a grant of
    ten to the fifth would be read as a grant of one hundred and five. This
    function exists to compare text about money, so it must not quietly change
    a number. Collapsing whitespace already covers the non-breaking and narrow
    spaces that NFKC would otherwise be reached for, because Python treats all
    of them as whitespace.
    """
    text = unicodedata.normalize("NFC", value).replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace(BOUNDARY, " ")
    text = re.sub(r"[^\S\n]*\n[^\S\n]*\n\s*", BOUNDARY, text)
    return re.sub(r"\s+", " ", text).strip(f"{BOUNDARY} ")


def lines_of(source: str) -> frozenset[str]:
    """Every non-empty line of the source, for grounding a heading."""
    return frozenset(flat(line) for line in source.split("\n") if line.strip())


# ------------------------------------------------------------------ the prompt


@dataclass(frozen=True, slots=True)
class Prompt:
    """An instruction and the version that names it, which cannot come apart.

    They used to be two arguments. Nothing tied them, so a caller could send one
    file's words and record another file's name, which is exactly what the
    version exists to prevent. Carrying them as one thing makes that impossible
    rather than merely discouraged.
    """

    version: str
    text: str


def load_prompt(directory: Path, version: str) -> Prompt:
    """The instruction sent to the model, read from the file named for its version.

    The version is the file name, so the recorded version and the words actually
    used can never disagree. Changing the instruction means a new file and a new
    version, which is also how the guard pass arrives later without touching any
    code here.
    """
    return Prompt(version=version, text=(directory / f"{version}.md").read_text(encoding="utf-8"))


def build_prompt(instruction: str, source: str) -> str:
    """The instruction with the item's text fenced off inside it.

    Captured text comes from the open web and can be written to look like an
    instruction. Fencing it and saying so is structure rather than detection: it
    does not try to spot an attack, it removes the ambiguity an attack needs.
    See ADR-0010.
    """
    safe = FORGED.sub(lambda m: m.group(0).replace("-", "\u2011"), source)
    return f"{instruction}\n\n{FENCE}\n{safe}\n{FENCE_END}\n"


# ------------------------------------------------------- reading the command line

FLAGS_TEXT = frozenset({"title", "funder", "budget", "summary", "eligibility", "area"})
FLAGS_QUOTE = frozenset(f"{name}-quote" for name in ("budget", "summary", "eligibility", "area", "deadline", "open"))
FLAGS_PLAIN = frozenset({"type", "deadline", "open"})
OPTIONAL = ("funder", "budget", "eligibility", "area")
FLAGS_ABSENT = frozenset(f"{name}-not-stated" for name in OPTIONAL)
KNOWN = FLAGS_TEXT | FLAGS_QUOTE | FLAGS_PLAIN | FLAGS_ABSENT
QUOTED = ("budget", "summary", "eligibility", "area")
NUMBERS_IN_OWN_QUOTE = frozenset({"budget"})
"""Where a stated figure must appear in that field's own sentence.

A budget IS a number, so the sentence carrying it must carry the figure. Every
other field is prose that may mention a year or a count discussed elsewhere on
the same page, and demanding one sentence carry all of them refuses honest
writing. Measured: on one real page, a summary naming the year of an election
failed two runs in three, and the year was on the page throughout. So for those
fields a figure must appear somewhere in the source, which still refuses a number
the page never states.
"""

_FLAG = re.compile(r"\s*--([a-z-]+)")
_PLAIN_VALUE = re.compile(r"\s+([^\s\"][^\s]*)")
_STARTS = re.compile(rf"{MARKER}(?=\s|$)")


def find_command(reply: str) -> str:
    """The one command line in the model's reply.

    Everything before it is the model thinking aloud, which a person reads and no
    code does. Exactly one line may begin with the marker word: none means the
    model did not answer, and two means something in the page produced a line
    shaped like a command.
    """
    if len(reply) > MAX_REPLY:
        msg = f"the reply is longer than {MAX_REPLY} characters"
        raise MalformedCommandError(msg)
    lines = [line.strip() for line in reply.splitlines() if _STARTS.match(line.strip())]
    if len(lines) != 1:
        msg = f"the reply must carry exactly one line starting with {MARKER!r}, found {len(lines)}"
        raise MalformedCommandError(msg)
    if len(lines[0]) > MAX_LINE:
        msg = f"the command line is longer than {MAX_LINE} characters"
        raise MalformedCommandError(msg)
    return lines[0]


def _read_text_value(line: str, name: str, at: int) -> tuple[str, int]:
    """One JSON string, so a quotation mark inside a funder's words cannot break it."""
    tail = line[at:]
    start = at + (len(tail) - len(tail.lstrip()))
    if start >= len(line) or line[start] != '"':
        msg = f"--{name} needs a value in double quotes"
        raise MalformedCommandError(msg)
    try:
        value, end = json.JSONDecoder().raw_decode(line, start)
    except ValueError as error:
        msg = f"--{name} has an unreadable value, {error}"
        raise MalformedCommandError(msg) from error
    return str(value), end


def parse_flags(line: str) -> dict[str, str]:
    """The command line as a plain mapping of flag to value.

    Nothing here decides whether the answer is any good. It only turns one line
    into pieces, refusing anything it cannot read without guessing.
    """
    out: dict[str, str] = {}
    at = len(MARKER)
    while at < len(line):
        head = _FLAG.match(line, at)
        if head is None:
            msg = f"expected a flag, found {line[at : at + 24]!r}"
            raise MalformedCommandError(msg)
        name, at = head.group(1), head.end()
        if name not in KNOWN:
            msg = f"--{name} is not a flag this builder knows"
            raise MalformedCommandError(msg)
        if name in out:
            msg = f"--{name} appears more than once"
            raise MalformedCommandError(msg)
        if name in FLAGS_ABSENT:
            out[name] = ""
        elif name in FLAGS_TEXT or name in FLAGS_QUOTE:
            out[name], at = _read_text_value(line, name, at)
        else:
            plain = _PLAIN_VALUE.match(line, at)
            if plain is None or plain.group(1).startswith("--"):
                msg = f"--{name} needs a plain value"
                raise MalformedCommandError(msg)
            out[name], at = plain.group(1), plain.end()
    return out


# ---------------------------------------------------------------- checking a claim

_MONTH = (
    r"(?:January|February|March|April|May|June|July|August|September|October"
    r"|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec)"
)
_DATE_FORMS = (
    (
        re.compile(rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTH}\.?,?\s+\d{{4}}\b", re.IGNORECASE),
        ("%d %B %Y", "%d %b %Y"),
    ),
    (
        re.compile(rf"\b{_MONTH}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}\b", re.IGNORECASE),
        ("%B %d %Y", "%b %d %Y"),
    ),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}\b"), ("%Y-%m-%d",)),
)
_A_DATE_NOBODY_CAN_READ = re.compile(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b|\b\d{4}[./]\d{1,2}[./]\d{1,2}\b")
"""A date written in figures in a form this project refuses to guess at.

30/09/2026 is the thirtieth of September in most of the world and an impossible
date in the United States, and nothing in the sentence says which was meant. The
reader therefore does not read it, which was right, but it also did not notice
it. So a sentence saying when a call opens in words and when it closes in figures
looked like a sentence naming one date, the guard against two dates never fired,
and the opening date was published as the closing date with that same sentence
stored beside it as its evidence.

Noticing is not the same as reading. This says only that something here is a date
and cannot be read, which is a reason to ask for a narrower quote, never a reason
to pick a meaning. The plain international form is deliberately not matched here,
because the reader can already read it.
"""
_LONG_ABBREVIATION = re.compile(r"\bSept\b", re.IGNORECASE)
"""The one abbreviation the pattern accepts that the date reader cannot parse.

"Sept" is ordinary British usage and appears on real funder pages. The reader
knows the three letter form and the whole word and nothing in between, so
without this a deadline written that way reads as no date at all, and the item
is refused for a reason that is this code's fault rather than the page's.
"""
_ORDINAL = re.compile(r"(?<=\d)(st|nd|rd|th)", re.IGNORECASE)
_RUNS = re.compile(r"\s+")
NUMBER = re.compile(r"\d+(?:[,.  ]\d{3})*(?:\.\d+)?")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

_EMAIL_IN_DISGUISE = re.compile(
    r"[A-Za-z0-9._%+-]+\s*"
    r"(?:\[\s*at\s*\]|\(\s*at\s*\)|\{\s*at\s*\}|＠)\s*"
    r"[A-Za-z0-9._%+-]+\s*(?:\[\s*dot\s*\]|\(\s*dot\s*\)|\s+dot\s+|\.)\s*[A-Za-z]{2,}"
    r"|[A-Za-z0-9._%+-]+\s+at\s+[A-Za-z0-9._%+-]+\s+dot\s+[A-Za-z]{2,}",
    re.IGNORECASE,
)
"""An address written to defeat a machine reading the page rather than a person.

The plain pattern above catches the ordinary form and the ordinary form only. A
page that means to keep its address away from a scraper writes it another way,
and that is exactly the page whose address is most likely to belong to a person
rather than to a shared mailbox, so it is the case that matters most.

The bare spelt out form is only counted when both markers are spelt out
together. Requiring "at" alone would refuse an ordinary English sentence, since
"look at the guidance" carries the same three letters between two words.
"""

_SPELT_THE_SAME = {
    # Dashes a page may use between the groups of a telephone number. Each one is
    # turned into the plain hyphen so that one rule reads them all, and so that
    # the shapes known not to be numbers to ring, which are written with a plain
    # hyphen, still recognise a date or a range of years written with any of them.
    **{c: "-" for c in "‐‑‒–—―−﹘﹣－"},
    # Characters that look like a gap, or like nothing at all, and were therefore
    # a way to hide a telephone number from a rule that only knew the plain
    # space. The project's own boundary character is here because a page can
    # write it, and because flat() turns it back into a space afterwards, so a
    # quote carrying one still matched the page word for word.
    **{
        chr(point): " "
        for point in (
            0x00A0,  # no-break space
            0x00AD,  # soft hyphen
            0x00B7,  # middle dot
            0x2007,  # figure space
            0x2009,  # thin space
            0x0085,  # next line, which is a line break written as one character
            0x2027,  # hyphenation point
            0x202F,  # narrow no-break space
            0x200B,  # zero width space
            0x200C,  # zero width non-joiner
            0x200D,  # zero width joiner
            0x2060,  # word joiner
            0xFEFF,  # zero width no-break space
            0x2028,  # line separator
            0x2029,  # paragraph separator
            0xE000,  # this project owns this one, and a page can write it too
        )
    },
    # Digits written in the wide forms used by East Asian typography.
    **{chr(0xFF10 + n): str(n) for n in range(10)},
}
_PLAINLY = str.maketrans(_SPELT_THE_SAME)
"""Every character that is one of these written another way, mapped to the plain one.

Each stands for exactly one character, so a position in the plainly written text
is the same position in the text as the page wrote it. That matters because the
rule looks at what sits on either side of a number, and it has to look at the
real sentence.
"""

_DIGIT_RUN = re.compile(r"\d[\d\s().+/-]{4,}\d")
_MONEY_BEFORE = re.compile(
    r"(?:[$\u00a3\u20ac\u00a5]|\b(?:USD|EUR|GBP|CHF|ZAR|KES|UGX|NGN|CAD|AUD|SEK|NOK|DKK)\b)"
    r"[\s]*$",
    re.IGNORECASE,
)
_MONEY_AFTER = re.compile(
    r"^[\s]*(?:[$\u00a3\u20ac\u00a5]|\b(?:USD|EUR|GBP|CHF|ZAR|KES|UGX|NGN|CAD|AUD|SEK|NOK|DKK)\b)",
    re.IGNORECASE,
)
"""A currency marker straight after a run of digits, which makes the run money.

Its twin above looks before the run. Only looking before missed the ordinary
European way of writing an amount, so an honest budget written with the currency
last was refused as carrying a telephone number.
"""

MIN_PHONE_DIGITS = 7
MAX_PHONE_DIGITS = 15
"""The shortest and the longest a number somebody could ring may be.

The longest is the standard's. ITU-T Recommendation E.164 sets fifteen digits as
the maximum for an international number. The shortest is this project's own
judgement and nothing more: that Recommendation sets no minimum at all for an
ordinary national number, and saying otherwise dressed a guess up as a rule
somebody else had made.
"""

_BETWEEN_NUMBERS = re.compile(r"[()]|\s{2,}|\s[-‐-―]\s|\s\+")
"""Where a candidate has to be broken, because one number cannot carry on across it.

A run of digits does not stop where a telephone number stops. It carries on
through a bracket, or through a second number written beside the first, and the
whole thing was then counted as too long for anyone to ring and let through. A
number followed by its opening hours did exactly that, and so did two numbers
side by side. Every run is broken here, not only one already too long: breaking
them all was measured against every sentence this project has written down and
changed no answer, while leaving short runs whole let a currency word at one end
of a run clear a telephone number at the other. None of these is a plain single
space, because an ordinary number is written with plain spaces inside it and
breaking on one would take every real number apart. BUG-029 and ADR-0038.
"""
_NOT_A_NUMBER_TO_RING = re.compile(
    r"^(?:"
    r"(?:19|20)\d{2}\s*[-‐-―/]\s*(?:19|20)\d{2}"
    r"|\d{4}[-/.]\d{1,2}[-/.]\d{1,2}"
    r"|(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])"
    r"|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}"
    r")$"
)
"""Runs shaped like a telephone number that are a date or a range of years.

Found by the audit's own reproduction: a deadline quoted as "the closing
date is 2026-09-30" was refused as carrying a contact detail, which would
have broken every deadline a page writes in that form.

The solid form belongs here too, and only became visible once an unbroken run of
eight digits stopped being waved through as money. It is written tightly, as a
plausible year followed by a real month and a real day, so that it exempts a date
without quietly exempting every eight digit number again.
"""


CONTROL = re.compile(
    "[\x00-\x1f\x7f-\x9f"
    "\u00ad"  # soft hyphen, a break the reader cannot see
    "\u200b-\u200f"  # zero width space, the joiners, the direction marks
    "\u2028\u2029"  # line separator and paragraph separator
    "\u202a-\u202e"  # the direction overrides
    "\u2060-\u2064"  # word joiner and the invisible operators
    "\ufeff"  # zero width no-break space
    "]"
)
"""Characters that are not words and must never reach a stored value.

A value is checked after its whitespace is collapsed and stored exactly as the
model wrote it. A line break or a tab hidden inside therefore passes the check
and still reaches the card, where the printed record puts one field on one line
and a person reads it beside the page. A title carrying a line break is also not
the whole line of the source it is required to be. BUG-022.

The rule is that a stored value carries nothing but words, and for a while this
said that while meaning only the characters below the ASCII range. A fresh
reading found the rest: the line and paragraph separators, which are line breaks
by another name, the zero width characters, which put an invisible break inside a
word, and the direction overrides, which make a stored value read on the page as
something other than what it says. All of them are refused now, because a value
is published and a reader has to be able to trust that it says what it appears
to say.

The cost is that a script which uses a zero width joiner as an ordinary part of
its writing would be refused. That costs one further attempt, and the two frozen
pages carry none. It is the same lean the contact rule takes.
"""


def _one_at_a_time(run: str, start: int) -> list[tuple[str, int]]:
    """Each number in a run, with where in the sentence it begins.

    Every run is broken, not only one already too long to ring. The length gate
    that used to stand here was measured and protects nothing: breaking every run
    changed no answer on any sentence this project has written down, while
    leaving short runs whole let one currency word at the end of a run clear a
    telephone number at its start.

    The position travels with each part because the rule has to look at what sits
    on either side of that part. Looking at the two ends of the whole run instead
    was how a currency word cleared every number between them.
    """
    parts: list[tuple[str, int]] = []
    at = 0
    for gap in _BETWEEN_NUMBERS.finditer(run):
        parts.append((run[at : gap.start()], start + at))
        at = gap.end()
    parts.append((run[at:], start + at))
    return [(part, where) for part, where in parts if part.strip()]


def _written_like_an_amount(groups: list[str]) -> bool:
    """Do these groups of digits read as one figure rather than as a number to ring?

    An amount grouped for reading has a first group of one to three digits and
    then nothing but groups of exactly three: 1 500 000. A telephone number does
    not look like that, because its groups are whatever the country writes.
    """
    return len(groups[0]) <= 3 and all(len(group) == 3 for group in groups[1:])


def _a_number_hiding_beside_an_amount(part: str, *, money_first: bool) -> bool:
    """Is part of this run a number to ring, with the rest of it the amount?

    A currency word clears the run it stands beside, which is right when the run
    is only the amount. "Contact 20 41 23 45 250 000 EUR" is not: the amount is
    the last two groups and the first four are somebody's office number, and one
    plain space between them is not something a run can be broken at, because an
    ordinary number is written with plain spaces inside it.

    So the run is read from the currency word inwards. Every shorter piece of it
    that could stand alone is weighed, and one that is long enough to ring and is
    not itself written like a figure means the currency word was clearing more
    than the amount.
    """
    groups = [found.group(0) for found in re.finditer(r"\d+", part)]
    for cut in range(1, len(groups)):
        away_from_the_money = groups[:cut] if money_first is False else groups[cut:]
        digits = sum(len(group) for group in away_from_the_money)
        if MIN_PHONE_DIGITS <= digits <= MAX_PHONE_DIGITS and not _written_like_an_amount(away_from_the_money):
            return True
    return False


def carries_a_contact(text: str) -> bool:
    """Does this sentence carry an email address or a telephone number?

    Deliberately blunt, and widened after an audit showed the first version only
    knew two shapes: an address beginning with a plus, and the American form with
    the area code in brackets. Most of the world writes a number as a bare run of
    digits, and this project's own first funder is in a country that does, so the
    rule missed the case most likely to arise.

    It takes any run of seven to fifteen digits as a number, unless it reads as a
    date or a range of years, or unless a currency marker stands beside that
    particular figure. A run holding more digits than anybody's number, with
    nothing inside it that one number can carry on across, is two numbers written
    side by side and is refused rather than passed over.

    The currency marker clears the figure it stands beside and no more. Clearing
    the whole run it was found in published a telephone number written next to an
    amount, which is how a page announces a grant and gives a number to ring for
    it. See ADR-0038.

    It no longer waves through a run of seven or eight digits written without
    separators. That exemption was for an amount written solid, and it made every
    telephone number written the same way invisible. Denmark's own language
    authority lists the solid eight digit form first among the correct ways to
    write a number there, and Danish and Norwegian funders are on this project's
    watch list. The reference implementation of this problem, Google's phone
    number library, accepts a solid block at every level of strictness it has, so
    the absence of separators is not evidence of anything. And the exemption only
    ever fired where no currency marker had been found, which made it the rule
    that settled pure ambiguity, settling it towards publishing.

    The cost is real and worth naming: an amount written solid, with no currency
    marker beside it, is refused. Refusing one costs a second attempt and, at
    worst, a field recorded as not stated. Missing one publishes somebody's
    telephone number into a public repository that keeps its history. The cost is
    not symmetric, so the rule leans the way it does.
    """
    plain = text.translate(_PLAINLY)
    if EMAIL.search(plain) or _EMAIL_IN_DISGUISE.search(plain):
        return True
    for run in _DIGIT_RUN.finditer(plain):
        for part, at in _one_at_a_time(run.group(0), run.start()):
            digits = re.sub(r"\D", "", part)
            if len(digits) < MIN_PHONE_DIGITS:
                continue
            if len(digits) > MAX_PHONE_DIGITS:
                # More digits than anybody's number, with nothing inside that a
                # single number cannot carry on across. That is two numbers
                # written side by side, which is how a contact line is written,
                # not one very long figure. It used to be waved through for being
                # too long to ring, which made the rule weakest exactly where a
                # page puts a number.
                return True
            if _NOT_A_NUMBER_TO_RING.match(part.strip()):
                continue
            before, after = plain[:at], plain[at + len(part) :]
            money_first = bool(_MONEY_BEFORE.search(before))
            if money_first or _MONEY_AFTER.match(after):
                if _a_number_hiding_beside_an_amount(part, money_first=money_first):
                    return True
                continue
            return True
    return False


def dates_in(span: str) -> list[date]:
    """Every date a strict reader can find in a sentence.

    Strict on purpose. A reader that guesses would agree with a model's guess,
    and the whole point of reading the date back is to disagree when the model is
    wrong. A phrase like "next Friday" is treated as unreadable, which ends the
    attempt rather than inventing a date.
    """
    found: list[date] = []
    for pattern, formats in _DATE_FORMS:
        for match in pattern.finditer(span):
            clean = _ORDINAL.sub("", _LONG_ABBREVIATION.sub("Sep", match.group(0)))
            clean = _RUNS.sub(" ", clean.replace(",", " ").replace(".", " ")).strip()
            for form in formats:
                try:
                    found.append(datetime.strptime(clean, form).date())  # noqa: DTZ007
                except ValueError:
                    continue
                break
    return found


def numbers_in(text: str) -> list[str]:
    """Every number worth checking: one holding two or more digits.

    A separator continues a number only when it groups thousands, so a comma
    between two separate numbers ends the first. An earlier version read
    "before 2020, 5 years" as the single number "2020, 5", which appears in no
    real sentence, so a truthful claim was refused as ungrounded.
    """
    out: list[str] = []
    for match in NUMBER.finditer(text):
        run = match.group(0).strip(" ,. ")
        if len(re.sub(r"\D", "", run)) >= 2:
            out.append(run)
    return out


def check_quote(name: str, quote: str, source: str, value: str | None = None) -> str:
    """A quote must be real, long enough to mean something, and clean of contacts.

    Where the value carries a figure, that figure must appear in the quote as
    well. A budget is the number a reader acts on, and this is the cheapest way
    to hold it to what the page actually says. See ADR-0032.
    """
    if CONTROL.search(quote):
        msg = f"--{name}-quote carries a line break or another character that is not a word"
        raise UngroundedClaimError(msg)
    # Measured on the form the check compares, so padding a short quote with
    # spaces cannot buy it past the floor. It bought four spaces before.
    said = flat(quote)
    if not MIN_QUOTE <= len(said) <= MAX_QUOTE:
        msg = f"--{name}-quote must be {MIN_QUOTE} to {MAX_QUOTE} characters, it is {len(said)}"
        raise UngroundedClaimError(msg)
    if carries_a_contact(quote):
        msg = (
            f"--{name}-quote carries a contact detail. Ground the field on another "
            f"sentence, or say --{name}-not-stated."
        )
        raise UngroundedClaimError(msg)
    whole = flat(source)
    if said not in whole:
        msg = f"--{name}-quote is not a real substring of the source text"
        raise UngroundedClaimError(msg)
    if value is not None:
        own = name in NUMBERS_IN_OWN_QUOTE
        # Every number the evidence states, as whole numbers rather than as a run
        # of characters. Asking whether the digits appear anywhere would ground a
        # claimed 87 on a page that only ever says 1987. BUG-023.
        stated = {flat(n) for n in numbers_in(said if own else whole)}
        missing = [n for n in numbers_in(value) if flat(n) not in stated]
        if missing:
            where = "its quote does not say" if own else "the source does not state"
            msg = f"--{name} states {', '.join(missing)}, which {where}"
            raise UngroundedClaimError(msg)
    return quote


# ------------------------------------------------------------- building the record


def _timing(flags: dict[str, str], source: str) -> Timing:
    """A closing date read back out of its own sentence, or an open basis with its own."""
    if ("deadline" in flags) == ("open" in flags):
        msg = "give exactly one of --deadline or --open"
        raise MalformedCommandError(msg)
    stray = "open-quote" if "deadline" in flags else "deadline-quote"
    if stray in flags:
        # A command carrying evidence for both kinds of timing has not decided
        # what the page says. Ignoring the spare one would hide that.
        msg = f"--{stray} was given but the timing is not that kind"
        raise MalformedCommandError(msg)
    if "open" in flags:
        return _open_timing(flags, source)
    return _dated_timing(flags, source)


def _is_call_type(value: str) -> TypeIs[CallType]:
    """Narrow a string to one of the ten kinds, for the checker as well as us."""
    return value in get_args(CallType)


def _is_open_basis(value: str) -> TypeIs[OpenBasis]:
    """Narrow a string to one of the three open bases, for the checker as well as us.

    Written as a narrowing check rather than a plain comparison so the type
    checker sees the same guarantee the code does. The earlier version reflected
    on the model's own annotation, which resolves through an unknown type, so a
    divergence between the check and the shape would have reached Pydantic as an
    unchecked string and raised a kind of error the retry does not catch.
    """
    return value in get_args(OpenBasis)


def _open_timing(flags: dict[str, str], source: str) -> Open:
    """A call with no fixed close, and the sentence that says so."""
    if "open-quote" not in flags:
        msg = "--open needs --open-quote"
        raise MalformedCommandError(msg)
    basis = flags["open"]
    if not _is_open_basis(basis):
        allowed = ", ".join(get_args(OpenBasis))
        msg = f"--open {basis} is not one of {allowed}"
        raise MalformedCommandError(msg)
    return Open(basis=basis, quote=check_quote("open", flags["open-quote"], source))


def _dated_timing(flags: dict[str, str], source: str) -> Dated:
    """A closing date, read back out of the sentence the model quoted for it."""
    if "deadline-quote" not in flags:
        msg = "--deadline needs --deadline-quote"
        raise MalformedCommandError(msg)
    quote = check_quote("deadline", flags["deadline-quote"], source)
    try:
        typed = date.fromisoformat(flags["deadline"])
    except ValueError as error:
        msg = f"--deadline must look like 2026-09-30, {error}"
        raise MalformedCommandError(msg) from error
    found = sorted(set(dates_in(quote)))
    if not found:
        msg = "no date can be read from --deadline-quote"
        raise UngroundedClaimError(msg)
    if how_many := len(_A_DATE_NOBODY_CAN_READ.findall(quote)):
        # A second date the reader cannot read is still a second date, and the
        # guard below never saw it. Refusing costs one more attempt. Accepting
        # publishes a closing date that the evidence stored beside it contradicts.
        #
        # The count is said and the dates themselves are not. This error travels
        # into the next request, and putting the page's own words in it would
        # send them to the model a second time. See requirement 39.
        msg = (
            f"--deadline-quote also states {how_many} date(s) written in figures, which "
            "could be read more than one way. Quote a narrower span naming only the closing date."
        )
        raise UngroundedClaimError(msg)
    if len(found) > 1:
        stated = ", ".join(str(one) for one in found)
        msg = (
            f"--deadline-quote states more than one date ({stated}). "
            "Quote a narrower span naming only the closing date."
        )
        raise UngroundedClaimError(msg)
    if typed != found[0]:
        msg = f"--deadline {typed} is not the date its quote states, which is {found[0]}"
        raise UngroundedClaimError(msg)
    return Dated(deadline=typed, quote=quote)


def _words_only(name: str, value: str) -> str:
    """A stored value, refused if it carries anything that is not a word.

    The same rule a quote is held to, and for the same reason: the value is
    compared with its whitespace collapsed and stored exactly as the model wrote
    it, so a line break hidden inside passes the check and still reaches the
    card. See CONTROL.

    The contact rule is applied here too, and that is the point of this function
    rather than an extra. It used to run in one place only, on the quote, so the
    title, the funder and all four values reached the card unchecked. The funder
    was the easiest way through of all, because it is deliberately ungrounded in
    phase one, so the model's own words became a stored value with nothing
    looking at them. A rule that keeps contact details out of a published record
    has to run wherever a published value is made, not at one of the places.
    """
    if CONTROL.search(value):
        msg = f"--{name} carries a line break or another character that is not a word"
        raise MalformedCommandError(msg)
    if carries_a_contact(value):
        msg = (
            f"--{name} carries a contact detail. Say it in words that do not name "
            f"a way to reach somebody, or say the field is not stated."
        )
        raise UngroundedClaimError(msg)
    return value


def _one_quoted_field(name: str, flags: dict[str, str], source: str) -> Field | None:
    """One value with its quote, or nothing when the source is said not to state it."""
    absent = f"{name}-not-stated" in flags
    value, quote = flags.get(name), flags.get(f"{name}-quote")
    if absent and (value is not None or quote is not None):
        msg = f"--{name}-not-stated cannot be given with a value"
        raise MalformedCommandError(msg)
    if absent:
        return None
    if value is None and quote is None:
        msg = f"say either --{name} with --{name}-quote, or --{name}-not-stated"
        raise MalformedCommandError(msg)
    if value is None or quote is None:
        msg = f"--{name} and --{name}-quote must both be given"
        raise MalformedCommandError(msg)
    if not value.strip():
        # An empty value is a third way of saying nothing, and the design allows
        # exactly one. Saying it out loud is the honest form, and this is not.
        msg = f"--{name} is empty. Give a value, or say --{name}-not-stated."
        raise MalformedCommandError(msg)
    return Field(value=_words_only(name, value), quote=check_quote(name, quote, source, value))


def _funder(flags: dict[str, str]) -> str | None:
    """The stated funder, or nothing. Deliberately ungrounded in phase one, ADR-0032."""
    if "funder-not-stated" in flags and "funder" in flags:
        msg = "--funder-not-stated cannot be given with a value"
        raise MalformedCommandError(msg)
    if "funder" not in flags and "funder-not-stated" not in flags:
        msg = "say either --funder or --funder-not-stated"
        raise MalformedCommandError(msg)
    named = flags.get("funder")
    if named is not None and not named.strip():
        msg = "--funder is empty. Give a name, or say --funder-not-stated."
        raise MalformedCommandError(msg)
    return named if named is None else _words_only("funder", named)


def build(flags: dict[str, str], source: str, source_url: str) -> Call:
    """Turn a read command into a record, refusing anything the page does not support."""
    for needed in ("title", "type", "summary", "summary-quote"):
        if needed not in flags:
            msg = f"--{needed} is required and missing"
            raise MalformedCommandError(msg)
    if not _is_call_type(flags["type"]):
        allowed = ", ".join(get_args(CallType))
        msg = f"--type {flags['type']} is not one of {allowed}"
        raise MalformedCommandError(msg)
    if not flags["title"].strip():
        msg = "--title is empty"
        raise MalformedCommandError(msg)
    _words_only("title", flags["title"])
    if flat(flags["title"]) not in lines_of(source):
        msg = "--title must be a whole heading or line of the source text, word for word"
        raise UngroundedClaimError(msg)

    fields = {name: _one_quoted_field(name, flags, source) for name in QUOTED}
    summary = fields["summary"]
    if summary is None:  # pragma: no cover - the absent path already raised above
        msg = "--summary is required"
        raise MalformedCommandError(msg)

    return Call(
        title=flags["title"],
        type=flags["type"],
        funder=_funder(flags),
        timing=_timing(flags, source),
        budget=fields["budget"],
        summary=summary,
        eligibility=fields["eligibility"],
        area=fields["area"],
        topics=(),
        source_url=source_url,
    )


# ------------------------------------------------------------------- the whole step


def source_url_of(item: RawItem) -> str:
    """Where a reader is sent. Taken from the capture, never from the model."""
    return item.canonical_url or item.url or ""


def extract(
    item: RawItem,
    model: Model,
    prompt: Prompt,
    model_id: str,
    watch: Callable[[int, str], None] | None = None,
) -> Extraction:
    """Read one captured item into one record, or raise having built nothing.

    One attempt, and if the command cannot be read or a claim cannot be grounded,
    one more with the reason handed back. A second failure raises and nothing
    partial is returned. A call that produces no reply at all is a different
    thing and consumes no attempt.

    A retry is this same step attempted again rather than a second AI step, so
    the rule that only extraction uses a model still holds.
    """
    source = readable(item.raw_text)
    asked = build_prompt(prompt.text, source)
    url = source_url_of(item)
    refusals: list[str] = []

    for attempt in (1, 2):
        request = asked if attempt == 1 else f"{asked}\nYour last answer failed: {refusals[-1]}\n"
        reply = model(prompt=request)
        if watch is not None:
            # The check done by eye needs to see the model reasoning and the
            # line it wrote, not only the record built from them.
            watch(attempt, reply)
        try:
            call = build(parse_flags(find_command(reply)), source, url)
        except (MalformedCommandError, UngroundedClaimError) as error:
            refusals.append(str(error))
            continue
        return Extraction(
            call=call,
            prompt_version=prompt.version,
            model_id=model_id,
            builder_version=BUILDER_VERSION,
        )

    reasons = "; then ".join(refusals)
    msg = f"{item.raw_hash[:12]} at {url}: held after 2 attempts. Refused because {reasons}"
    raise HeldAfterTwoTriesError(msg)


def describe(extraction: Extraction) -> str:
    """The record as a person reads it, for the check done by hand."""
    call = extraction.call
    lines = [
        f"title       {call.title}",
        f"type        {call.type}",
        f"funder      {call.funder or 'not stated'}",
    ]
    if isinstance(call.timing, Dated):
        lines += [f"deadline    {call.timing.deadline}", f"  quote     {call.timing.quote}"]
    else:
        lines += [f"open        {call.timing.basis}", f"  quote     {call.timing.quote}"]
    claims: tuple[tuple[str, Field | None], ...] = (
        ("budget", call.budget),
        ("summary", call.summary),
        ("eligibility", call.eligibility),
        ("area", call.area),
    )
    for name, got in claims:
        if got is None:
            lines.append(f"{name:11s} not stated")
        else:
            lines += [f"{name:11s} {got.value}", f"  quote     {got.quote}"]
    lines += [
        f"link        {call.source_url}",
        f"prompt      {extraction.prompt_version}",
        f"model       {extraction.model_id}",
        f"builder     {extraction.builder_version}",
    ]
    return "\n".join(lines)


# ------------------------------------------------------------- reaching a model

DEFAULT_MODEL = "gemini-3.5-flash-lite"
"""The small free-tier model, pinned to an exact name rather than a moving alias.

An alias that points at a changing model would make a stored model name a label
rather than a thing, which removes the only reason for storing it.
"""

PROMPT_VERSION = "v2"
"""Which instruction to send. The file in `prompts/` named for it holds the words.

Version one worked on both test pages and read the browser tab line as the title,
copied a sentence in place of a summary on one page, and answered not stated for
a field a sentence did support. Version two says what to do about each.
"""

KEY_NAME = "GEMINI_API_KEY"
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
OK = 200
TOO_MANY_REQUESTS = 429
SERVER_ERROR = 500
TRANSIENT_TRIES = 3
TRANSIENT_PAUSES = (2.0, 8.0)
"""How often a request that never reached the model is sent again, and the wait.

Three kinds of failure look alike from here and must not be treated alike.

A refusal for quota or rate is permanent for this run: asking again cannot make
the account fuller, and every later item will meet the same wall, so it consumes
no attempt and ends the pass.

A wrong key or a wrong model name is permanent full stop, and repeating it only
wastes time.

A dropped connection or a fault at the far end is neither. The request never
reached the model, so nothing was spent, and one more try a moment later usually
succeeds. Without this a single blip loses the item, which happened on the first
end to end run of this step: one page failed with a dropped connection and the
same page succeeded immediately afterwards.

This is the same shape `fetch.py` already uses for sources, with a shorter ladder
because a model call is expensive in time and a source fetch is not.

Two ladders sit one inside the other, and the cost of that is worth stating
plainly. This one runs inside a single attempt at reading an item, and an item
gets two attempts, so one item can make six requests in all. On a bad network,
where each attempt waits out the reading limit before failing, the worst case is
a quarter of an hour on one item. Nothing is lost when that happens and no guess
is published, but a maintainer reading only the paragraph above would expect
minutes.

Three rather than two, measured. Three calls in a row on this provider's free
tier gave two answers and one refusal with a server error, each taking around a
minute, and a page needs one good answer. At that rate two attempts lose roughly
one item in nine, and a third attempt takes that to about one in twenty seven for
the cost of a couple of minutes on an item that was going to be lost anyway. The
pauses widen the way the fetch step's do, because a provider having a bad moment
is more likely to have recovered after eight seconds than after two.
"""


class _Part(BaseModel):
    """One piece of the model's answer, as the provider sends it."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    text: str = ""


class _Content(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    parts: list[_Part] = []


class _Candidate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    content: _Content = _Content()


class _Answer(BaseModel):
    """What the provider sends back, in the only shape this code reads.

    Written as a shape rather than navigated with casts, because a cast asserts
    without checking: a body carrying the right keys with the wrong kinds of
    value would have passed four of them and then raised a kind of error the
    caller does not expect. Anything unfamiliar is ignored rather than refused,
    so the provider can add fields without breaking this.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    candidates: list[_Candidate] = []


class _Trouble(BaseModel):
    """What the provider says went wrong, when it says anything.

    Worth relaying rather than swallowing. "This model is currently experiencing
    high demand" tells a maintainer to wait. A bare 503 sends them looking at
    their own code, which is the misdiagnosis this error type exists to prevent.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    message: str = ""


class _Refusal(BaseModel):
    """A reply that carries a refusal rather than an answer."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    error: _Trouble = _Trouble()


def _what_it_said(answer: httpx.Response) -> str:
    """The provider's own explanation, shortened, or nothing if it gave none."""
    try:
        return _Refusal.model_validate(answer.json()).error.message[:200]
    except (ValueError, ValidationError):
        return ""


class MissingKeyError(Exception):
    """No key is available, said before any item is read rather than partway through."""


def read_key(root: Path) -> str:
    """The model key, from the environment or from an ignored file beside the code.

    Never committed, never printed, and never written into a record or a log.
    """
    from_env = os.environ.get(KEY_NAME, "").strip()
    if from_env:
        return from_env
    env_file = root / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            name, _, value = line.partition("=")
            if name.strip() == KEY_NAME:
                found = value.strip().strip("'\"")
                if found:
                    return found
                # The committed template ends with the setting and no value, so
                # this is what copying it and forgetting to paste the key looks
                # like. Saying the key is missing is the whole point of this
                # function, and returning an empty one defeats it. BUG-027.
    msg = (
        f"no model key. Put {KEY_NAME}=your-key in a file called .env at the root of "
        "this project, which git already ignores, or set it in the environment."
    )
    raise MissingKeyError(msg)


@dataclass(frozen=True, slots=True)
class Gemini:
    """The one place this system talks to a model.

    It sends text and returns text. It knows nothing about commands, flags or
    records, so moving to another provider means writing another of these and
    changing nothing else.
    """

    key: str = field(repr=False)
    client: httpx.Client
    model_id: str = DEFAULT_MODEL

    def _ask(self, prompt: str) -> httpx.Response:
        """One request, or a refusal that says which kind of failure it was."""
        try:
            answer = self.client.post(
                ENDPOINT.format(model=self.model_id),
                headers={"x-goog-api-key": self.key, "content-type": "application/json"},
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=httpx.Timeout(READ_SECONDS, connect=CONNECT_SECONDS, write=CONNECT_SECONDS),
            )
        except httpx.HTTPError as error:
            msg = f"the model could not be reached, {type(error).__name__}"
            raise TransientFailureError(msg) from error

        if answer.status_code == TOO_MANY_REQUESTS:
            msg = "the model refused the request, the free tier is spent or the rate is capped"
            raise ModelUnreachableError(msg)
        if answer.status_code >= SERVER_ERROR:
            msg = f"the model answered {answer.status_code}, which is its own trouble and not ours"
            said = _what_it_said(answer)
            raise TransientFailureError(f"{msg}. It said: {said}" if said else msg)
        if answer.status_code != OK:
            msg = f"the model answered {answer.status_code}, check the key and the model name {self.model_id}"
            raise ModelUnreachableError(msg)
        return answer

    def _asked(self, prompt: str) -> httpx.Response:
        """The reply, trying again only when the request never reached the model."""
        last: TransientFailureError | None = None
        for attempt in range(1, TRANSIENT_TRIES + 1):
            try:
                return self._ask(prompt)
            except TransientFailureError as error:
                last = error
                if attempt < TRANSIENT_TRIES:
                    time.sleep(TRANSIENT_PAUSES[attempt - 1])
        raise ModelUnreachableError(str(last)) from last

    def __call__(self, prompt: str) -> str:
        """Ask, and turn whatever comes back into the model's own words."""
        answer = self._asked(prompt)

        try:
            body = _Answer.model_validate(answer.json())
        except (ValueError, ValidationError) as error:
            msg = "the model answered with something that is not readable as an answer"
            raise ModelUnreachableError(msg) from error
        if not body.candidates:
            msg = "the model returned no answer at all"
            raise ModelUnreachableError(msg)
        text = "".join(part.text for part in body.candidates[0].content.parts)
        if not text.strip():
            msg = "the model returned an empty answer"
            raise ModelUnreachableError(msg)
        return text
