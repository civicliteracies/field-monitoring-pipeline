import pytest

from field_monitoring_pipeline.data.extract import CALL_PARTS, subject
from field_monitoring_pipeline.data.settings import TopicEntry
from field_monitoring_pipeline.data.tags import Kept, Subject, check
from tests.samples import EITI_CALL, EU, EXTRACTIVES, OFFER, TOPICS, stored

TITLE = "Identifying user-focused solutions to support news media freedom"


def test_a_stored_eu_record_gives_its_title_and_call_title_as_the_head_and_its_description_as_the_body() -> None:
    given = subject(EU, stored())
    assert given.title == TITLE
    assert given.head == (TITLE, "Reshaping democracies: AI and journalism 2027")
    assert given.body.startswith(
        "Expected Outcome: Projects should contribute to all of the following expected outcomes:"
    )
    assert "<p" not in given.body


def test_an_empty_call_title_or_description_leaves_the_title_alone() -> None:
    record = stored()
    record["metadata"] |= {"callTitle": [], "descriptionByte": []}
    assert subject(EU, record) == Subject(title=TITLE, other_titles=(), body="", parts=CALL_PARTS)


def test_a_record_without_a_call_title_stops_the_check() -> None:
    record = stored()
    del record["metadata"]["callTitle"]
    with pytest.raises(KeyError, match="callTitle"):
        subject(EU, record)


def test_an_eiti_page_is_checked_on_its_list_s_title_alone_and_keeps_its_source_s_topic() -> None:
    given = subject(EITI_CALL, OFFER)
    assert given == Subject(title=EITI_CALL.title, other_titles=(), body="", parts=CALL_PARTS)
    listed = TOPICS.model_copy(update={"topics": {**TOPICS.topics, "extractives-eiti": TopicEntry(mark="primary")}})
    assert check(listed, given, ("extractives-eiti",)) == Kept(topics=EXTRACTIVES)
