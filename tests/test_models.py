import datetime as dt
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from field_monitoring_pipeline.models import Call, Deadline, Opening, Quoted

LINK = "https://Example.org/Calls/One"
CALL: dict[str, Any] = {
    "title": "Grants for Local Civic Data Projects",
    "type": "grant",
    "funder": None,
    "opening": None,
    "deadline": {"date": "2031-10-05", "quote": "Applications close on 5 October 2031."},
    "budget": None,
    "summary": {"value": "Funds small teams", "quote": "We fund small teams."},
    "eligibility": None,
    "area": None,
    "link": LINK,
}
OPENING: dict[str, Any] = {"date": "2019-03-01", "quote": "Opening for submission: 1 March 2019."}
KNOWN: list[tuple[type[BaseModel], dict[str, Any]]] = [
    (Quoted, {"value": "v", "quote": "q"}),
    (Opening, OPENING),
    (Deadline, {"date": None, "quote": "q"}),
    (Call, CALL),
]


def test_a_call_with_a_deadline_builds() -> None:
    call = Call.model_validate(CALL)
    assert call.deadline.date == dt.date(2031, 10, 5)
    assert call.link == LINK


def test_a_call_with_no_deadline_builds() -> None:
    call = Call.model_validate(CALL | {"deadline": {"date": None, "quote": "Applications are accepted all year."}})
    assert call.deadline.date is None


@pytest.mark.parametrize("date", ["soon", "2031-02-30"])
def test_a_deadline_that_is_not_a_real_date_is_refused(date: str) -> None:
    with pytest.raises(ValidationError):
        Call.model_validate(CALL | {"deadline": {"date": date, "quote": "q"}})


def test_a_deadline_in_the_past_is_accepted() -> None:
    call = Call.model_validate(CALL | {"deadline": {"date": "2019-01-01", "quote": "q"}})
    assert call.deadline.date == dt.date(2019, 1, 1)


@pytest.mark.parametrize(("shape", "known"), KNOWN)
def test_a_field_the_template_does_not_know_is_refused(shape: type[BaseModel], known: dict[str, Any]) -> None:
    shape.model_validate(known)
    with pytest.raises(ValidationError):
        shape.model_validate(known | {"added": "x"})


@pytest.mark.parametrize("opening", [OPENING, None])
def test_a_call_builds_with_an_opening_date_and_with_none(opening: dict[str, Any] | None) -> None:
    call = Call.model_validate(CALL | {"opening": opening})
    assert (call.opening is None) == (opening is None)
    if call.opening is not None:
        assert call.opening.date == dt.date(2019, 3, 1)


@pytest.mark.parametrize("opening", [{"date": "next spring", "quote": "q"}, {"date": "2027-05-13"}])
def test_an_opening_date_that_breaks_its_rules_is_refused(opening: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        Call.model_validate(CALL | {"opening": opening})
