from itertools import pairwise

import pytest

from field_monitoring_pipeline.data.models import Report
from field_monitoring_pipeline.data.reports import FACTS
from field_monitoring_pipeline.data.store import read_card
from field_monitoring_pipeline.presentation.write import report_card
from tests.samples import ARK_LINK, REPORT

WARNING = "This sentence was not found in the report."
LABELS = ("Organisation", "Who it was for", "Method", "Results", "How long it ran", "Where")
EMPTY = REPORT.model_copy(update=dict.fromkeys((*FACTS, "published")))
MISSED = REPORT.model_copy(update={name: getattr(REPORT, name).model_copy(update={"found": False}) for name in FACTS})
RECORDS = [
    pytest.param(REPORT, id="as read"),
    pytest.param(EMPTY, id="empty fields"),
    pytest.param(MISSED, id="sentences not found"),
    # data.org's annual report, whose title holds a curly apostrophe.
    pytest.param(REPORT.model_copy(update={"title": "Accelerate What\u2019s Possible"}), id="a title not in ASCII"),
]


def half(report: Report) -> str:
    return report_card(report).split("\n---\n\n", 1)[1]


def test_a_report_card_gives_its_title_type_day_and_each_fact_with_its_sentence() -> None:
    assert half(REPORT) == (
        "# ARK Solves: data for smallholder farmers\n\n"
        "Type: research or case study\n\n"
        "Published: 8 September 2026\n\n"
        "Organisation: ARK Solves\n\n> ARK Solves built the platform with farmer cooperatives.\n\n"
        "Who it was for: smallholder farmers\n\n> It serves smallholder farmers across the islands.\n\n"
        "Method: a data platform\n\n> The team built a data platform that links farmers to buyers.\n\n"
        "Results: 4 000 farmers reached\n\n> By June, 4 000 farmers had joined the platform.\n\n"
        "How long it ran: two years\n\n> The work ran for two years.\n\n"
        "Where: the Philippines\n\n> In the Philippines, food insecurity grips 37.8 million people.\n\n"
        f"Link: {ARK_LINK}\n\n"
        "Read by gemini-3.5-flash-lite, with the instructions reports-v1\n"
    )


@pytest.mark.parametrize("report", RECORDS)
def test_each_report_survives_the_round_trip_in_plain_ascii(report: Report) -> None:
    text = report_card(report)
    assert text.split("\n---\n\n", 1)[0].isascii()
    assert read_card("reports", text) == report


def test_a_warning_naming_the_report_sits_under_each_sentence_not_found() -> None:
    text = half(MISSED)
    for name in FACTS:
        assert f"\n\n> {getattr(MISSED, name).quote}\n\n{WARNING}\n\n" in text
    assert text.count(WARNING) == len(FACTS)
    assert "found in the call" not in text


def test_an_empty_fact_and_no_date_say_not_stated() -> None:
    text = half(EMPTY)
    for label in ("Published", *LABELS):
        assert f"\n\n{label}: not stated\n\n" in text
    assert ">" not in text


@pytest.mark.parametrize("report", RECORDS)
def test_each_fact_of_a_report_stands_apart(report: Report) -> None:
    lines = half(report).splitlines()
    assert all(not (one and two) for one, two in pairwise(lines))
