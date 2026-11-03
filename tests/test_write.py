import datetime as dt
from itertools import pairwise

import pytest

from field_monitoring_pipeline.extract import build
from field_monitoring_pipeline.models import Call, Deadline, Opening
from field_monitoring_pipeline.write import card, read_card
from tests.test_extract import REPLY, stored
from tests.test_tags import TOPICS

CALL, _ = build(stored(), TOPICS, REPLY)
WARNING = "This sentence was not found in the call."
SENTENCES = ("opening", "deadline", "budget", "summary", "eligibility", "area")
EMPTY = CALL.model_copy(
    update={"funder": None, "opening": None, "budget": None, "eligibility": None, "area": None, "topics": ()}
)
MISSED = CALL.model_copy(
    update={"funder": "European Commission"}
    | {name: getattr(CALL, name).model_copy(update={"found": False}) for name in SENTENCES}
)
TITLED = CALL.model_copy(update={"title": 'Grants: the “open” call, "Media: now"'})
RECORDS = [
    pytest.param(CALL, id="as read"),
    pytest.param(EMPTY, id="empty fields"),
    pytest.param(MISSED, id="sentences not found"),
    pytest.param(TITLED, id="a title with a colon and quotation marks"),
]


def half(call: Call) -> str:
    return card(call).split("\n---\n\n", 1)[1]


def test_the_record_sits_on_top_and_the_half_for_people_below() -> None:
    text = card(CALL)
    block, rest = text.split("\n---\n\n", 1)
    assert block.startswith('---\ntitle: "Identifying user-focused solutions to support news media freedom"\n')
    assert '\nopening:\n  date: "2027-05-13"\n  quote: "Opening date: 2027-05-13"\n  found: true\n' in block
    assert "\nfunder: null\n" in block
    assert "\\u20ac" in block
    assert "€" not in block
    assert rest.startswith("# Identifying user-focused solutions to support news media freedom\n\nType: grant\n\n")
    assert text.endswith("\n")
    assert "\r" not in text


def test_the_model_and_the_instructions_are_in_the_block() -> None:
    block = card(CALL).split("\n---\n\n", 1)[0]
    assert '\nmodel: "gemini-3.5-flash-lite"\ninstructions: "v3"' in block


def test_the_same_record_gives_the_same_bytes() -> None:
    assert card(CALL).encode() == card(build(stored(), TOPICS, REPLY)[0]).encode()


@pytest.mark.parametrize("call", RECORDS)
def test_each_record_survives_the_round_trip_in_plain_ascii(call: Call) -> None:
    text = card(call)
    assert text.split("\n---\n\n", 1)[0].isascii()
    assert read_card(text) == call


def test_a_warning_sits_under_each_sentence_not_found() -> None:
    text = half(MISSED)
    for name in SENTENCES:
        assert f"\n\n> {getattr(MISSED, name).quote}\n\n{WARNING}\n\n" in text
    assert text.count(WARNING) == len(SENTENCES)
    assert WARNING not in half(CALL)


def test_an_empty_field_says_not_stated_and_a_named_funder_is_shown() -> None:
    text = half(EMPTY)
    for label in ("Funder", "Opens", "Budget", "Who can apply", "Where"):
        assert f"\n\n{label}: not stated\n\n" in text
    assert "\n\nFunder: European Commission\n\n" in half(MISSED)


@pytest.mark.parametrize("call", RECORDS)
def test_each_fact_stands_apart(call: Call) -> None:
    lines = half(call).splitlines()
    assert all(not (one and two) for one, two in pairwise(lines))


@pytest.mark.parametrize(
    ("deadline", "line"),
    [
        pytest.param(dt.date(2027, 9, 5), "Deadline: 5 September 2027", id="a date"),
        pytest.param(None, "Deadline: stays open", id="no date"),
    ],
)
def test_a_day_under_10_on_both_dates(deadline: dt.date | None, line: str) -> None:
    opening = Opening(date=dt.date(2027, 5, 3), quote="Opening date: 2027-05-03", found=True)
    closing = Deadline(date=deadline, quote="Deadline: 2027-09-05", found=True)
    text = half(CALL.model_copy(update={"opening": opening, "deadline": closing}))
    assert "\n\nOpens: 3 May 2027\n\n> Opening date: 2027-05-03\n\n" in text
    assert f"\n\n{line}\n\n> Deadline: 2027-09-05\n\n" in text


def test_the_half_for_people_ends_with_the_link_and_the_model() -> None:
    assert half(CALL).endswith(
        "\n\nLink: https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/"
        "topic-details/HORIZON-CL2-2027-01-DEMOCRACY-06\n\nRead by gemini-3.5-flash-lite, with the instructions v3\n"
    )


def test_the_topics_sit_in_the_record_each_with_its_mark_and_not_below() -> None:
    block, rest = card(CALL).split("\n---\n\n", 1)
    assert (
        '\ntopics: [{"name": "AI-and-civic", "mark": "primary"}, '
        '{"name": "data-journalism", "mark": "secondary"}]\nlink: '
    ) in block
    assert "\ntopics: []\n" in card(EMPTY)
    assert "AI-and-civic" not in rest
