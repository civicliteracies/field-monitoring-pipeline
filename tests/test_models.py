import datetime as dt
import tomllib
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from field_monitoring_pipeline.models import (
    Call,
    Deadline,
    EuSearch,
    Opening,
    Quoted,
    Topic,
    TopicEntry,
    TopicList,
    WatchList,
)

LINK = "https://Example.org/Calls/One"
CALL: dict[str, Any] = {
    "title": "Grants for Local Civic Data Projects",
    "type": "grant",
    "funder": None,
    "opening": None,
    "deadline": {"date": "2031-10-05", "quote": "Applications close on 5 October 2031.", "found": True},
    "budget": None,
    "summary": {"value": "Funds small teams", "quote": "We fund small teams.", "found": True},
    "eligibility": None,
    "area": None,
    "topics": [{"name": "AI-and-civic", "mark": "primary"}],
    "link": LINK,
    "identifier": "CIVIC-DATA-2031-01",
    "model": "gemini-3.5-flash-lite",
    "instructions": "v3",
}
OPENING: dict[str, Any] = {"date": "2019-03-01", "quote": "Opening for submission: 1 March 2019.", "found": True}
TOPIC: dict[str, Any] = {"name": "AI-and-civic", "mark": "primary"}
ENTRY: dict[str, Any] = {"mark": "primary", "words": ["AI"]}
KNOWN: list[tuple[type[BaseModel], dict[str, Any]]] = [
    (Quoted, {"value": "v", "quote": "q", "found": True}),
    (Opening, OPENING),
    (Deadline, {"date": None, "quote": "q", "found": False}),
    (Call, CALL),
    (Topic, TOPIC),
    (TopicEntry, ENTRY),
    (TopicList, {"topics": {"AI-and-civic": ENTRY}}),
]


def test_a_call_with_a_deadline_builds() -> None:
    call = Call.model_validate(CALL)
    assert call.deadline.date == dt.date(2031, 10, 5)
    assert call.link == LINK


def test_a_call_with_no_deadline_builds() -> None:
    call = Call.model_validate(
        CALL | {"deadline": {"date": None, "quote": "Applications are accepted all year.", "found": True}}
    )
    assert call.deadline.date is None


@pytest.mark.parametrize("date", ["soon", "2031-02-30"])
def test_a_deadline_that_is_not_a_real_date_is_refused(date: str) -> None:
    with pytest.raises(ValidationError):
        Call.model_validate(CALL | {"deadline": {"date": date, "quote": "q", "found": True}})


def test_a_deadline_in_the_past_is_accepted() -> None:
    call = Call.model_validate(CALL | {"deadline": {"date": "2019-01-01", "quote": "q", "found": True}})
    assert call.deadline.date == dt.date(2019, 1, 1)


@pytest.mark.parametrize(("shape", "known"), KNOWN)
def test_a_field_the_template_does_not_know_is_refused(shape: type[BaseModel], known: dict[str, Any]) -> None:
    shape.model_validate(known)
    with pytest.raises(ValidationError):
        shape.model_validate(known | {"added": "x"})


@pytest.mark.parametrize("field", list(CALL))
def test_a_call_with_a_field_left_out_is_refused(field: str) -> None:
    with pytest.raises(ValidationError, match=field):
        Call.model_validate({name: value for name, value in CALL.items() if name != field})


@pytest.mark.parametrize(("shape", "known"), KNOWN[:3])
@pytest.mark.parametrize("mark", [{}, {"found": None}], ids=["left out", "empty"])
def test_a_sentence_without_its_mark_is_refused(
    shape: type[BaseModel], known: dict[str, Any], mark: dict[str, Any]
) -> None:
    unmarked = {name: value for name, value in known.items() if name != "found"}
    with pytest.raises(ValidationError, match="found"):
        shape.model_validate(unmarked | mark)


@pytest.mark.parametrize("opening", [OPENING, None])
def test_a_call_builds_with_an_opening_date_and_with_none(opening: dict[str, Any] | None) -> None:
    call = Call.model_validate(CALL | {"opening": opening})
    assert (call.opening is None) == (opening is None)
    if call.opening is not None:
        assert call.opening.date == dt.date(2019, 3, 1)


@pytest.mark.parametrize(
    "opening", [{"date": "next spring", "quote": "q", "found": True}, {"date": "2027-05-13", "found": True}]
)
def test_an_opening_date_that_breaks_its_rules_is_refused(opening: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        Call.model_validate(CALL | {"opening": opening})


@pytest.mark.parametrize(("shape", "known"), [(Topic, TOPIC), (TopicEntry, ENTRY)])
def test_a_mark_other_than_the_two_is_refused(shape: type[BaseModel], known: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match="mark"):
        shape.model_validate(known | {"mark": "Secondary"})


def test_a_call_keeps_its_topics_in_order_and_may_have_none() -> None:
    two = [{"name": "data-journalism", "mark": "secondary"}, TOPIC]
    assert Call.model_validate(CALL | {"topics": two}).topics == (
        Topic(name="data-journalism", mark="secondary"),
        Topic(name="AI-and-civic", mark="primary"),
    )
    assert Call.model_validate(CALL | {"topics": []}).topics == ()


SOURCE: dict[str, Any] = {"name": "EU", "url": "https://example.org/search", "how": "eu-search", "words": ["democracy"]}
EITI_SOURCE: dict[str, Any] = {"name": "EITI", "url": "https://eiti.org/consultancy-opportunities", "how": "eiti-page"}
WATCH = """
[source.eu-funding-tenders]
name = "EU"
url = "https://example.org/search"
how = "eu-search"
words = ["democracy"]
"""


@pytest.mark.parametrize(("shape", "known"), [(EuSearch, SOURCE), (WatchList, {"source": {"eu": SOURCE}})])
def test_a_watch_list_key_it_does_not_know_is_refused(shape: type[BaseModel], known: dict[str, Any]) -> None:
    shape.model_validate(known)
    with pytest.raises(ValidationError, match="added"):
        shape.model_validate(known | {"added": "x"})


@pytest.mark.parametrize("field", list(SOURCE))
def test_a_watch_list_entry_without_a_field_of_its_route_is_refused(field: str) -> None:
    with pytest.raises(ValidationError, match=field):
        WatchList.model_validate({"source": {"eu": {name: value for name, value in SOURCE.items() if name != field}}})


def test_a_route_it_does_not_know_is_refused() -> None:
    with pytest.raises(ValidationError, match="'eu-search', 'eiti-page'"):
        WatchList.model_validate({"source": {"eu": SOURCE | {"how": "page"}}})


@pytest.mark.parametrize(
    ("entry", "refusal"),
    [
        pytest.param({"url": EITI_SOURCE["url"], "how": "eiti-page"}, "name", id="no name"),
        pytest.param({"name": "EITI", "how": "eiti-page"}, "url", id="no url"),
        pytest.param(EITI_SOURCE | {"words": ["democracy"]}, "words", id="words"),
        pytest.param(EITI_SOURCE | {"added": "x"}, "added", id="an unknown key"),
    ],
)
def test_an_eiti_entry_that_breaks_its_route_s_rules_is_refused(entry: dict[str, Any], refusal: str) -> None:
    WatchList.model_validate({"source": {"eiti": EITI_SOURCE}})
    with pytest.raises(ValidationError, match=refusal):
        WatchList.model_validate({"source": {"eiti": entry}})


@pytest.mark.parametrize(
    "text", ["", WATCH.replace("[source.", "[sources.")], ids=["an empty file", "a misspelt table name"]
)
def test_a_watch_list_without_its_source_table_is_refused(text: str) -> None:
    with pytest.raises(ValidationError, match="\nsource\n  Field required"):
        WatchList.model_validate(tomllib.loads(text))


def test_the_watch_list_keeps_its_order_and_a_source_written_twice_is_refused() -> None:
    watch = WatchList.model_validate(tomllib.loads(WATCH + WATCH.replace("eu-funding-tenders", "second")))
    assert list(watch.source) == ["eu-funding-tenders", "second"]
    assert watch.source["second"] == EuSearch.model_validate(SOURCE)
    with pytest.raises(tomllib.TOMLDecodeError, match="eu-funding-tenders"):
        tomllib.loads(WATCH + WATCH)
