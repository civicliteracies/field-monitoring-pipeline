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

import re
import unicodedata
from html.parser import HTMLParser

BUILDER_VERSION = "b1"
"""The version of the deterministic side: this file's parsing and checking.

It is stored on every record so a value is attributable to the logic that made
it. Bump it when a change alters what this file accepts or produces, and pair
that bump with a decision record and a rebuild. See ADR-0034.
"""


# --------------------------------------------------- turning a capture into text

_BLOCK = frozenset({
    "p",
    "div",
    "li",
    "tr",
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
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in _SKIP:
            self.skip += 1
        elif tag in _BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in _BLOCK:
            self.out.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip:
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
    text = re.sub(r"[ \t]+", " ", text)
    # A tag boundary often leaves a space at the end of a line. It is invisible
    # to a reader and would otherwise sit inside a stored quote, so it goes here.
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def flat(value: str) -> str:
    """Whitespace collapsed and characters composed, for comparison only.

    Never stored. A card keeps a quote as the source wrote it; this is only how
    two strings are compared, so that a line break in the page does not make a
    sentence fail to match itself.

    NFC and not NFKC. The compatibility form rewrites characters that carry
    meaning here: it turns a superscript five into a plain five, so a grant of
    ten to the fifth would be read as a grant of one hundred and five. This
    function exists to compare text about money, so it must not quietly change
    a number. Collapsing whitespace already covers the non-breaking and narrow
    spaces that NFKC would otherwise be reached for, because Python treats all
    of them as whitespace.
    """
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value)).strip()


def lines_of(source: str) -> frozenset[str]:
    """Every non-empty line of the source, for grounding a heading."""
    return frozenset(flat(line) for line in source.split("\n") if line.strip())
