"""A claim reaches a record only when the page it came from really says it.

Every test here runs offline against a stand-in model, so the suite needs no key,
costs nothing, and never fails because a website or a provider had a bad morning.
The two fixtures are real funding calls, frozen exactly as the servers served
them.
"""

from datetime import date

import pytest

from field_monitoring_pipeline.extract import (
    BOUNDARY,
    flat,
    lines_of,
    readable,
)
from field_monitoring_pipeline.models import Dated

# --------------------------------------------------- turning a capture into text


def test_markup_inside_a_sentence_does_not_break_the_sentence() -> None:
    """This is the whole reason a derivation step exists.

    A page writes a date in bold. The sentence a person reads is one run of
    words; the sentence in the source is split around a tag. Without this the
    quote check would refuse a perfectly honest quote.
    """
    captured = "<p>Applications close on <b>16 February</b> 2024.</p>"

    assert "close on 16 February 2024." in readable(captured)


def test_script_and_style_content_never_reaches_the_text() -> None:
    captured = "<style>p{color:red}</style><p>A grant.</p><script>var x=1;</script>"

    assert readable(captured) == "A grant."


@pytest.mark.parametrize(
    ("captured", "expected"),
    [
        ("<p>a&nbsp;b</p>", "a b"),
        ("<p>a\u200bb</p>", "ab"),
        ("<p>a­b</p>", "ab"),
        ("<p>a&amp;b</p>", "a&b"),
    ],
)
def test_invisible_and_escaped_characters_are_settled(captured: str, expected: str) -> None:
    """A card is read by a person, so a stray invisible character is a bug in the card."""
    assert readable(captured) == expected


@pytest.mark.parametrize(
    ("captured", "expected"),
    [
        pytest.param("", "", id="nothing-at-all"),
        pytest.param("Just a sentence.", "Just a sentence.", id="no-markup"),
        # A blank line, because the second paragraph opening is the end of the
        # first. This read as a single line break until a fresh reading found
        # that the collapsing step turns one of those into an ordinary space,
        # which is the splice BUG-019 exists to stop. See BLOCK_ENDS.
        pytest.param("<p>unclosed <b>bold <i>and <p>another", "unclosed bold and\n\nanother", id="never-closed"),
    ],
)
def test_odd_input_gives_the_words_back(captured: str, expected: str) -> None:
    """A source serving broken markup is a source problem, not a reason to stop.

    The words are asserted rather than the type, because the return type is
    already guaranteed by the checker and asserting it proves nothing.
    """
    assert readable(captured) == expected


def test_a_line_break_does_not_stop_a_sentence_matching_itself() -> None:
    """Whitespace is collapsed on both sides, so a wrapped sentence still matches."""
    assert flat("one   two\nthree") == flat("one two three")


def test_a_heading_is_a_whole_line_and_a_fragment_of_one_is_not() -> None:
    """A title carries no separate quote, so its own words are its evidence.

    Requiring any substring would let a single common word through. Requiring a
    whole line means the title has to be something the page actually presents as
    a heading.
    """
    source = readable("<h1>Civic Data Grants 2026</h1><p>A fund for the year.</p>")

    assert flat("Civic Data Grants 2026") in lines_of(source)
    assert flat("Civic Data") not in lines_of(source)
    assert flat("the") not in lines_of(source)


def test_a_dated_call_keeps_a_closed_deadline() -> None:
    """A call that has closed still validates. Open or closed is worked out at display.

    The date is long past, so building this at all is the whole assertion. See
    ADR-0001: a deadline validates as a valid date rather than a future one, and
    the archive keeps closed calls.
    """
    kept = Dated(deadline=date(2024, 2, 16), quote="The deadline for applications is 16 February 2024.")

    assert kept.deadline == date(2024, 2, 16)


def test_comparing_two_strings_never_changes_a_number() -> None:
    """The compatibility form of Unicode would rewrite a figure, so it is not used.

    A grant of ten to the fifth is a real way to write a hundred thousand. Under
    the compatibility form the superscript becomes a plain digit, and the value
    reads as one hundred and five. This function exists to compare text about
    money, so it must leave every digit exactly where it was.
    """
    assert flat("a grant of 10\u2075 euro") == "a grant of 10\u2075 euro"
    assert flat("\u00bd of the budget") == "\u00bd of the budget"


@pytest.mark.parametrize(
    "space",
    ["\u00a0", "\u2007", "\u202f", "\u2000", "\u3000"],
    ids=["non-breaking", "figure", "narrow-no-break", "en-quad", "ideographic"],
)
def test_an_unusual_space_in_the_page_still_matches_a_plain_one(space: str) -> None:
    """Which is why the compatibility form is not needed for spacing either."""
    page = f"a grant of USD{space}5,000 per year"

    assert flat("a grant of USD 5,000 per year") in flat(page)


def test_a_pages_own_menu_is_not_part_of_what_it_says() -> None:
    """A menu lists the funder's other programmes, and a sentence from one is real.

    It would pass the quote check while describing a different grant entirely.
    Dropping the parts a page declares as furniture removes that whole class of
    mistake, and it removes rather than selects, so it cannot fail by keeping
    nothing.
    """
    page = (
        "<nav><a>Our other fund: applications close 1 March 2030</a></nav>"
        "<h1>The Real Fund</h1><p>Applications close on 30 September 2026.</p>"
        "<footer>Registered charity. Our other grants pay up to USD 900,000.</footer>"
    )

    text = readable(page)

    assert "The Real Fund" in text
    assert "30 September 2026" in text
    assert "1 March 2030" not in text
    assert "900,000" not in text


def test_a_heading_inside_a_header_is_still_the_title() -> None:
    """One of the two real pages puts its heading in a header, so headers are kept."""
    page = "<header><h1>A Fund With Its Heading In A Header</h1></header><p>Text.</p>"

    assert flat("A Fund With Its Heading In A Header") in lines_of(readable(page))


# ------------------------------------ the bugs an audit reproduced, each guarded

TWO_PARAGRAPHS = readable(
    "<h1>The Real Fund</h1>"
    "<p>Our sister programme awarded grants of $2,000,000 last year.</p>"
    "<p>Applicants to this fund must be registered charities in Kenya.</p>"
)


def test_a_quote_cannot_begin_in_one_paragraph_and_end_in_the_next() -> None:
    """Reproduced by an audit, and this is the check the whole record rests on.

    Two unrelated paragraphs, joined with a space, read as one sentence and were
    accepted as really being on the page. A budget from a different programme
    could be attached to this call and pass every check. The end of a block is
    not whitespace, so it is no longer collapsed into a space.
    """
    spliced = (
        "Our sister programme awarded grants of $2,000,000 last year. "
        "Applicants to this fund must be registered charities in Kenya."
    )

    assert spliced not in TWO_PARAGRAPHS
    assert flat(spliced) not in flat(TWO_PARAGRAPHS)


@pytest.mark.parametrize(
    "quote",
    [
        pytest.param("Our sister programme awarded grants of $2,000,000 last year.", id="a-whole-sentence"),
        pytest.param("must be registered charities in Kenya", id="part-of-one"),
        pytest.param(
            "Our sister programme awarded grants of $2,000,000 last year.\n\n"
            "Applicants to this fund must be registered charities in Kenya.",
            id="both-copied-whole-with-the-break",
        ),
    ],
)
def test_an_honest_quote_still_matches_after_that(quote: str) -> None:
    """The fix must refuse the splice without refusing anything real.

    Including a quote that really does cross a block boundary, copied whole. That
    text is on the page, break and all, so it is still evidence.
    """
    assert flat(quote) in flat(TWO_PARAGRAPHS)


def test_the_boundary_marker_cannot_be_smuggled_in() -> None:
    """Otherwise a model could write the marker itself and splice two blocks anyway.

    Any copy arriving in the text becomes a space before real boundaries are
    marked, so only this code can ever produce one.
    """
    forged = (
        f"Our sister programme awarded grants of $2,000,000 last year.{BOUNDARY}"
        "Applicants to this fund must be registered charities in Kenya."
    )

    assert flat(forged) not in flat(TWO_PARAGRAPHS)


def test_the_boundary_marker_is_not_whitespace() -> None:
    """The obvious choice was, and the step it has to survive collapsed it away.

    Stated here as a fact rather than a comment, because the whole paragraph rule
    silently stops working if this ever becomes true.
    """
    assert not BOUNDARY.isspace()


@pytest.mark.parametrize(
    ("windows", "unix"),
    [
        pytest.param("<p>a\r\nb</p>", "<p>a\nb</p>", id="inside-a-paragraph"),
        pytest.param("<p>a</p>\r\n<p>b</p>", "<p>a</p>\n<p>b</p>", id="between-paragraphs"),
        pytest.param("<p>a\rb</p>", "<p>a\nb</p>", id="a-carriage-return-alone"),
    ],
)
def test_a_page_served_with_windows_line_endings_reads_the_same(windows: str, unix: str) -> None:
    """Reproduced by an audit: a stray carriage return defeated the fence guard.

    A rule anchored to the end of a line stops matching when a carriage return
    sits before the newline, and one of the two frozen pages is served that way.
    The endings are settled once, here, so the same page served either way gives
    the same text to everything downstream.
    """
    text = readable(windows)

    assert "\r" not in text
    assert text == readable(unix)


def test_a_stray_closing_tag_does_not_let_a_menu_through() -> None:
    """Reproduced by an audit: one shared count let a page unwind the filter.

    A page that closes a tag it never opened dropped the count to nothing while
    still inside a menu, so the rest of the menu was read as though it were the
    article. Pages built by a template really do drop tags like this. Matching by
    name means a stray closing tag changes nothing.
    """
    page = (
        "<nav>Our other fund: apply by 1 March 2030 for USD 900,000.</form>"
        "A sentence from the menu that must not be quotable.</nav>"
        "<h1>The Real Fund</h1><p>Applications close 30 September 2026.</p>"
    )

    text = readable(page)

    assert "A sentence from the menu" not in text
    assert "1 March 2030" not in text
    assert "The Real Fund" in text
    assert "30 September 2026" in text


@pytest.mark.parametrize(
    ("captured", "expected"),
    [
        pytest.param("<nav>a<form>b</form>c</nav>keep", "keep", id="nested-and-both-closed"),
        pytest.param("<p>keep</p><nav>drop", "keep", id="never-closed-swallows-the-rest"),
        pytest.param("<nav>drop</nav>keep", "keep", id="opened-and-closed-normally"),
    ],
)
def test_furniture_is_dropped_however_the_page_nests_it(captured: str, expected: str) -> None:
    assert readable(captured) == expected


# ------------- what a second opinion found the derivation was still letting past


@pytest.mark.parametrize(
    "captured",
    [
        pytest.param("<p>Alpha.</p><p>Beta.</p>", id="two-paragraphs"),
        pytest.param("<p>Alpha.<br>Beta.</p>", id="a-line-break-inside-a-paragraph"),
        pytest.param("<p>Alpha.<br/>Beta.</p>", id="a-self-closing-line-break"),
        pytest.param("<p>Alpha.</p>Beta.", id="a-paragraph-then-loose-text"),
        pytest.param("<div>Alpha.</div>Beta.", id="a-division-then-loose-text"),
        pytest.param("<ul><li>Alpha.</li><li>Beta.</li></ul>", id="two-list-items"),
        pytest.param("<h1>Alpha.</h1><p>Beta.</p>", id="a-heading-then-a-paragraph"),
        pytest.param("<table><tr><td>Alpha.</td></tr><tr><td>Beta.</td></tr></table>", id="two-rows"),
        pytest.param("<table><tr><td>Alpha.</td><td>Beta.</td></tr></table>", id="two-cells-in-one-row"),
        pytest.param("<blockquote>Alpha.</blockquote><p>Beta.</p>", id="a-blockquote-then-a-paragraph"),
    ],
)
def test_a_quote_cannot_cross_any_shape_of_block_boundary(captured: str) -> None:
    """The end of a block was written as a single line break, and one is not enough.

    A line break also arrives inside a block, from a page that wraps its own
    source, and the collapsing step cannot tell the two apart. It treated both as
    an ordinary space, so the boundary was lost for every shape that produced
    only one: a line break inside a paragraph, a block followed by loose text,
    and a page written one way while the same page written the other was fenced
    correctly. Both frozen pages carry the first of those, and a fresh reading
    found the defect BUG-019 was recorded as having fixed.

    Two cells of one row were worse than spliced. They were run together with
    nothing at all between them.
    """
    assert flat("Alpha. Beta.") not in flat(readable(captured))


@pytest.mark.parametrize(
    "captured",
    [
        pytest.param("<p>Alpha and\nBeta together.</p>", id="a-soft-line-break-in-the-source"),
        pytest.param("<p>Alpha <strong>and</strong> Beta together.</p>", id="a-sentence-broken-by-markup"),
        pytest.param("<p>Alpha and\n   Beta together.</p>", id="a-sentence-wrapped-and-indented"),
    ],
)
def test_one_continuous_sentence_still_matches_itself(captured: str) -> None:
    """The cost of the rule above, held to the shape it must not break.

    A page wraps its own source wherever it likes, and a sentence broken that way
    is still one sentence. Fencing on a single line break would refuse an honest
    quote from every page written that way.
    """
    assert flat("Alpha and Beta together.") in flat(readable(captured))


@pytest.mark.parametrize(
    "captured",
    [
        pytest.param("<p>Real.</p><nav>menu<nav>sub</nav> leaked </nav><p>End.</p>", id="a-menu-inside-a-menu"),
        pytest.param("<p>Real.</p><aside>a<aside>b</aside> leaked </aside><p>End.</p>", id="an-aside-inside-an-aside"),
    ],
)
def test_closing_furniture_closes_the_innermost_one_of_that_name(captured: str) -> None:
    """Closing the outermost ended both, and the rest of the furniture read as article.

    Matching by name was introduced so that a stray closing tag changes nothing.
    It searched from the wrong end, so a page that nests the same furniture tag,
    which a template does whenever a menu holds a submenu, ended the whole filter
    at the inner closing tag and the remaining menu text was read as the page.
    """
    assert readable(captured) == "Real.\n\nEnd."
