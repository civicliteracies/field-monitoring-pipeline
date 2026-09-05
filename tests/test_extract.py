"""A claim reaches a record only when the page it came from really says it.

Every test here runs offline against a stand-in model, so the suite needs no key,
costs nothing, and never fails because a website or a provider had a bad morning.
The two fixtures are real funding calls, frozen exactly as the servers served
them.
"""

from datetime import date

import pytest

from field_monitoring_pipeline.extract import (
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
        pytest.param("<p>unclosed <b>bold <i>and <p>another", "unclosed bold and\nanother", id="never-closed"),
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
