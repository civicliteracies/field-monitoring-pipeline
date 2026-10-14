import datetime as dt
import json
from pathlib import Path
from typing import Any

import httpx2
import pytest

from field_monitoring_pipeline.extract import ask, build, text
from field_monitoring_pipeline.models import Call, Deadline, Quoted

ROOT = Path(__file__).parent.parent
REPLIES = Path(__file__).parent / "replies"
INSTRUCTIONS = (ROOT / "src" / "field_monitoring_pipeline" / "instructions" / "v3.md").read_text(encoding="utf-8")
REPLY = (REPLIES / "model_reply.txt").read_text(encoding="utf-8")
LINE = 'fieldbook --type grant --summary "Funds news media." --summary-quote "We fund news media."'


def stored(deadlines: list[str] | None = None, topics: int = 1, **own: Any) -> Any:
    record = json.loads((REPLIES / "stored_call.json").read_bytes())
    metadata = record["metadata"]
    if deadlines is not None:
        metadata["deadlineDate"] = deadlines
    budget = json.loads(metadata["budgetOverview"][0])
    for lines in budget["budgetTopicActionMap"].values():
        if lines[0]["action"].startswith("HORIZON-CL2-2027-01-DEMOCRACY-06 "):
            lines[0].update(own)
            lines += [lines[0] | {"action": f"OTHER-TOPIC-{n} - Research"} for n in range(1, topics)]
    metadata["budgetOverview"] = [json.dumps(budget)]
    return record


def test_page_code_is_stripped_and_a_sentence_keeps_its_stop() -> None:
    assert "See the information in the Horizon Europe Programme Guide." in text(stored())


def test_the_text_begins_with_the_four_lines_from_the_fields() -> None:
    assert text(stored()).startswith(
        "Title: Identifying user-focused solutions to support news media freedom\n"
        "Opening date: 2027-05-13\n"
        "Deadline: 2027-09-23\n"
        "Budget 2027: 12 000 000 € (each winning project: 3 500 000 € to 4 000 000 €); winning projects expected: 3\n"
    )


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
    assert build(stored(deadlines), REPLY).deadline == Deadline(date=date, quote=line)


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
    assert build(stored(**own), REPLY).budget == Quoted(value=value, quote=line)


def test_a_pot_the_call_s_topics_share_says_so() -> None:
    record = stored(
        topics=5, budgetYearMap={"2026": "28000000"}, minContribution=0, maxContribution=0, expectedGrants=0
    )
    assert build(record, REPLY).budget == Quoted(
        value="28 000 000 € (shared by the 5 topics of this call)",
        quote="Budget 2026: 28 000 000 € (shared by the 5 topics of this call)",
    )


def test_each_sentence_the_reply_quotes_is_in_the_text() -> None:
    words = text(stored())
    call = build(stored(), REPLY)
    assert call.summary.quote in words
    for fact in (call.eligibility, call.area):
        assert fact is not None
        assert fact.quote in words


def test_a_recorded_reply_becomes_a_record() -> None:
    assert build(stored(), REPLY) == Call.model_validate({
        "title": "Identifying user-focused solutions to support news media freedom",
        "type": "grant",
        "funder": None,
        "opening": {"date": "2027-05-13", "quote": "Opening date: 2027-05-13"},
        "deadline": {"date": "2027-09-23", "quote": "Deadline: 2027-09-23"},
        "budget": {
            "value": "12 000 000 € (each winning project: 3 500 000 € to 4 000 000 €)",
            "quote": (
                "Budget 2027: 12 000 000 € (each winning project: 3 500 000 € to 4 000 000 €); "
                "winning projects expected: 3"
            ),
        },
        "summary": {
            "value": (
                "Grants to address data gaps and develop innovative models that support news media freedom and "
                "independence."
            ),
            "quote": (
                "Key data gaps affecting the news media sectors at European level are addressed and all relevant "
                "stakeholders dispose of an updated and comprehensive knowledge base."
            ),
        },
        "eligibility": {
            "value": "academia, civil society organisations and news sectors representatives forming consortia",
            "quote": (
                "Consortia should: bring together academia (including from SSH disciplines), civil society "
                "organisations and multiple news sectors representatives (including influencers and other content "
                "creators); where applicable, leverage the data and services available through European Research "
                "Infrastructures federated under the European Open Science Cloud (EOSC), as well as data from "
                "relevant Data Spaces"
            ),
        },
        "area": {
            "value": "Europe",
            "quote": (
                "There are still important quantitative and qualitative data gaps at European level that can help "
                "the news media sectors address these concerns, including accurate diagnoses of the challenges and "
                "opportunities for the news sectors."
            ),
        },
        "link": (
            "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/"
            "HORIZON-CL2-2027-01-DEMOCRACY-06"
        ),
        "model": "gemini-3.5-flash-lite",
        "instructions": "v3",
    })


@pytest.mark.parametrize("flag", [" --eligibility-not-stated", ""])
def test_an_absent_optional_fact_is_not_stated(flag: str) -> None:
    assert build(stored(), LINE + flag).eligibility is None


def test_a_value_with_no_sentence_is_refused() -> None:
    with pytest.raises(ValueError, match="quote"):
        build(stored(), 'fieldbook --type grant --summary "Funds news media."')


@pytest.mark.parametrize(
    ("line", "refusal"),
    [
        (LINE + ' --title-quote "A title."', "--title-quote is not a flag the instructions offer"),
        (LINE + " --type grant", "--type is given twice"),
        ('fieldbook --summary "Funds news media." --summary-quote "We fund news media." --type', "--type has no value"),
    ],
)
def test_a_malformed_line_is_refused(line: str, refusal: str) -> None:
    with pytest.raises(ValueError, match=refusal):
        build(stored(), line)


def test_the_model_is_asked_once_with_the_instructions_and_the_text() -> None:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return httpx2.Response(200, json={"choices": [{"message": {"content": "the reply"}}]})

    with httpx2.Client(transport=httpx2.MockTransport(handler)) as client:
        assert ask("the text", "the key", client) == "the reply"
    [request] = seen
    assert str(request.url) == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    assert request.headers["Authorization"] == "Bearer the key"
    assert "the key" not in str(request.url)
    assert request.extensions["timeout"] == {"connect": 180, "read": 180, "write": 180, "pool": 180}
    body = json.loads(request.read())
    assert body["model"] == "gemini-3.5-flash-lite"
    assert body["messages"] == [
        {
            "role": "user",
            "content": f"{INSTRUCTIONS}\n-----BEGIN SOURCE TEXT-----\nthe text\n-----END SOURCE TEXT-----",
        }
    ]


def test_a_request_the_service_refuses_is_raised() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(503)

    with httpx2.Client(transport=httpx2.MockTransport(handler)) as client, pytest.raises(httpx2.HTTPStatusError):
        ask("the text", "the key", client)


def test_the_instructions_hold_what_the_code_writes_and_their_example_builds() -> None:
    for words in ("`Title`", "`Opening date`", "`Deadline`", "`Budget`"):
        assert words in INSTRUCTIONS
    assert "`-----BEGIN SOURCE TEXT-----`" in INSTRUCTIONS
    assert "`-----END SOURCE TEXT-----`" in INSTRUCTIONS
    [example] = [line for line in INSTRUCTIONS.splitlines() if line.startswith("fieldbook ")]
    assert build(stored(), example).funder == "Example Foundation"
