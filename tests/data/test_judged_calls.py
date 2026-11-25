"""The topic check over 235 EU calls, 230 of them judged by hand as in CLI's field, borderline, or not.

Each call carries the topics, or the reason it is set aside, that the measured rule gave it with the
topic list kept beside it, a run of spacing read as one space. The rule keeps 44: 14 in the field,
24 borderline and 6 not, so 86% of what it keeps is in the field or borderline. It finds 14 of the 15
calls in the field, and 38 of the 59 in the field or borderline. One test asks the check for the same
answer on every call; another counts these figures from the check's own answers.
"""

import json
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from field_monitoring_pipeline.data.models import Topic
from field_monitoring_pipeline.data.tags import Kept, SetAside, Subject, check, read_topic_list

JUDGED = Path(__file__).parent / "judged"
LISTED = read_topic_list(JUDGED / "topic-list.toml", ())
CALLS: list[dict[str, Any]] = json.loads((JUDGED / "calls.json").read_text(encoding="utf-8"))


def _subject(call: dict[str, Any]) -> Subject:
    return Subject(title=call["title"], other_titles=(call["call"],) if call["call"] else (), body=call["description"])


def test_the_judged_calls_are_all_there() -> None:
    assert len(CALLS) == 235
    assert sum(bool(call["topics"]) for call in CALLS) == 44


@pytest.mark.parametrize("call", CALLS, ids=[f"call {number}" for number in range(1, len(CALLS) + 1)])
def test_each_judged_call_gets_the_measured_answer(call: dict[str, Any]) -> None:
    expected = (
        Kept(
            topics=tuple(
                Topic(name=name, mark=entry.mark) for name, entry in LISTED.topics.items() if name in call["topics"]
            )
        )
        if call["topics"]
        else SetAside(reason=call["reason"])
    )
    assert check(LISTED, _subject(call), ()) == expected


def test_the_measured_figures_are_the_check_s_own() -> None:
    # Y is in CLI's field, B borderline, N not, U not judged.
    marks = Counter(call["judged"] for call in CALLS)
    kept = Counter(call["judged"] for call in CALLS if isinstance(check(LISTED, _subject(call), ()), Kept))
    assert (kept["Y"], kept["B"], kept["N"], kept.total()) == (14, 24, 6, 44)
    assert round(100 * (kept["Y"] + kept["B"]) / kept.total()) == 86
    assert (kept["Y"], marks["Y"]) == (14, 15)
    assert (kept["Y"] + kept["B"], marks["Y"] + marks["B"]) == (38, 59)
