import datetime as dt
from typing import Any

import pytest

from field_monitoring_pipeline.extract import build, text
from field_monitoring_pipeline.models import Deadline, Quoted
from tests.test_extract import GUIDE, REPLY, stored
from tests.test_tags import TOPICS


def test_the_page_tags_are_stripped_and_a_sentence_keeps_its_stop() -> None:
    assert GUIDE in text(stored())


def test_the_text_begins_with_the_four_lines_from_the_fields() -> None:
    assert text(stored()).startswith(
        "Title: Identifying user-focused solutions to support news media freedom\n"
        "Opening date: 2027-05-13\n"
        "Deadline: 2027-09-23\n"
        "Budget 2027: 12 000 000 € (each winning project: 3 500 000 € to 4 000 000 €); winning projects expected: 3\n"
    )


def test_the_description_comes_before_the_conditions() -> None:
    record = stored()
    record["metadata"]["descriptionByte"] = ["<p>What the call funds.</p>"]
    record["metadata"]["topicConditions"] = ["<p>Who may apply.</p>"]
    assert text(record).endswith("winning projects expected: 3\nWhat the call funds.\nWho may apply.")


@pytest.mark.parametrize(
    ("deadlines", "date", "line"),
    [
        (["2027-01-28T00:00:00.000+0000"], dt.date(2027, 1, 28), "Deadline: 2027-01-28"),
        (
            ["2027-09-30T00:00:00.000+0000", "2027-05-04T00:00:00.000+0000"],
            dt.date(2027, 5, 4),
            "Deadline: 2027-05-04 (two stages: 2027-05-04 and 2027-09-30)",
        ),
    ],
)
def test_each_form_of_the_deadline_line(deadlines: list[str], date: dt.date, line: str) -> None:
    call, _ = build(stored(deadlines), TOPICS, REPLY)
    assert call.deadline == Deadline(date=date, quote=line, found=True)


@pytest.mark.parametrize(
    ("own", "value", "line"),
    [
        (
            {
                "budgetYearMap": {"2027": "20000000"},
                "minContribution": 3500000,
                "maxContribution": 4000000,
                "expectedGrants": 5,
            },
            "20 000 000 € (each winning project: 3 500 000 € to 4 000 000 €)",
            "Budget 2027: 20 000 000 € (each winning project: 3 500 000 € to 4 000 000 €); winning projects expected: 5",
        ),
        (
            {
                "budgetYearMap": {"2027": "12000000"},
                "minContribution": 6000000,
                "maxContribution": 6000000,
                "expectedGrants": 2,
            },
            "12 000 000 € (each winning project: 6 000 000 €)",
            "Budget 2027: 12 000 000 € (each winning project: 6 000 000 €); winning projects expected: 2",
        ),
        (
            {
                "budgetYearMap": {"2027": "32500000"},
                "minContribution": 0,
                "maxContribution": 2500000,
                "expectedGrants": 13,
            },
            "32 500 000 € (each winning project: up to 2 500 000 €)",
            "Budget 2027: 32 500 000 € (each winning project: up to 2 500 000 €); winning projects expected: 13",
        ),
        (
            {"budgetYearMap": {"2026": "28000000"}, "minContribution": 0, "maxContribution": 0, "expectedGrants": 0},
            "28 000 000 €",
            "Budget 2026: 28 000 000 €",
        ),
    ],
)
def test_each_form_of_the_budget_line(own: dict[str, Any], value: str, line: str) -> None:
    call, _ = build(stored(**own), TOPICS, REPLY)
    assert call.budget == Quoted(value=value, quote=line, found=True)


def test_a_pot_the_call_s_topics_share_says_so() -> None:
    record = stored(
        shared=5, budgetYearMap={"2026": "28000000"}, minContribution=0, maxContribution=0, expectedGrants=0
    )
    call, _ = build(record, TOPICS, REPLY)
    assert call.budget == Quoted(
        value="28 000 000 € (shared by the 5 topics of this call)",
        quote="Budget 2026: 28 000 000 € (shared by the 5 topics of this call)",
        found=True,
    )


def test_script_and_style_contents_are_not_text() -> None:
    record = stored()
    record["metadata"]["descriptionByte"] = ["<p>Shown.</p><script>var x = {a: 1};</script><style>p{color:red}</style>"]
    record["metadata"]["topicConditions"] = ["<p>Who may apply.</p>"]
    assert text(record).endswith("winning projects expected: 3\nShown.\nWho may apply.")
