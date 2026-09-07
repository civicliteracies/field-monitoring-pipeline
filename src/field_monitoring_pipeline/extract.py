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
