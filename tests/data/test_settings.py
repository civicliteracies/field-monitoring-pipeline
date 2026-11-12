import tomllib
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from field_monitoring_pipeline.data.settings import EuSearch, TopicEntry, TopicList, WatchList

ENTRY: dict[str, Any] = {"mark": "primary", "words": ["AI"]}


@pytest.mark.parametrize(("shape", "known"), [(TopicEntry, ENTRY), (TopicList, {"topics": {"AI-and-civic": ENTRY}})])
def test_a_topic_list_key_it_does_not_know_is_refused(shape: type[BaseModel], known: dict[str, Any]) -> None:
    shape.model_validate(known)
    with pytest.raises(ValidationError):
        shape.model_validate(known | {"added": "x"})


def test_a_topic_entry_mark_other_than_the_two_is_refused() -> None:
    with pytest.raises(ValidationError, match="mark"):
        TopicEntry.model_validate(ENTRY | {"mark": "Secondary"})


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
