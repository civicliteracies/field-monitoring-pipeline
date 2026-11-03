import re
import tomllib
from pathlib import Path

import pytest
from pydantic import ValidationError

from field_monitoring_pipeline.models import Topic, TopicEntry, TopicList
from field_monitoring_pipeline.tags import read_topic_list, topics

ROOT = Path(__file__).parent.parent
# A small topic list for the tests: two topics the stored call's labels name, and one they do not.
TOPIC_LIST = """[topics.AI-and-civic]
mark = "primary"
words = ["artificial intelligence", "AI"]

[topics.data-journalism]
mark = "secondary"
words = ["journalism"]

[topics.civic-tech]
mark = "primary"
"""
TOPICS = TopicList.model_validate(tomllib.loads(TOPIC_LIST))
AI = Topic(name="AI-and-civic", mark="primary")
JOURNALISM = Topic(name="data-journalism", mark="secondary")
CIVIC_TECH = Topic(name="civic-tech", mark="primary")


def test_the_topic_list_is_read_whole_in_its_order(tmp_path: Path) -> None:
    path = tmp_path / "tags.toml"
    path.write_text(TOPIC_LIST, encoding="utf-8")
    assert read_topic_list(path) == TOPICS
    assert TOPICS.topics == {
        "AI-and-civic": TopicEntry(mark="primary", words=("artificial intelligence", "AI")),
        "data-journalism": TopicEntry(mark="secondary", words=("journalism",)),
        "civic-tech": TopicEntry(mark="primary"),
    }
    assert list(TOPICS.topics) == ["AI-and-civic", "data-journalism", "civic-tech"]


@pytest.mark.parametrize(
    ("text", "refusal"),
    [
        pytest.param(
            '[topics.governance]\nmark = "Secondary"\n', "topics.governance.mark", id="a mark other than the two"
        ),
        pytest.param(
            '[topics.governance]\nmark = "secondary"\nword = ["state"]\n', "topics.governance.word", id="an unknown key"
        ),
        pytest.param('[topic.governance]\nmark = "secondary"\n', "topic\n", id="a misspelt table name"),
        pytest.param("", "topics\n", id="an empty file"),
    ],
)
def test_a_list_that_breaks_its_rules_is_refused_naming_what_was_found(tmp_path: Path, text: str, refusal: str) -> None:
    path = tmp_path / "tags.toml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValidationError, match=re.escape(refusal)):
        read_topic_list(path)


@pytest.mark.parametrize(
    ("label", "given"),
    [
        pytest.param("ethical AI", (AI,), id="a word at the end"),
        pytest.param("AI-driven solutions", (AI,), id="a word before a hyphen"),
        pytest.param("Artificial  Intelligence", (AI,), id="a word in another case and spacing"),
        pytest.param("investigative journalism support", (JOURNALISM,), id="a word inside a label"),
        pytest.param("Civic Tech", (CIVIC_TECH,), id="the name, its hyphen read as a space"),
        pytest.param("civic-tech", (CIVIC_TECH,), id="the name as written"),
        pytest.param("AI4Creatives", (), id="letters followed by a digit"),
        pytest.param("Thailand", (), id="letters inside a word"),
        pytest.param("Development aid", (), id="letters after the phrase"),
        pytest.param("Dubai", (), id="letters before the phrase"),
        pytest.param("gen_AI_tools", (AI,), id="an underscore on each side"),
    ],
)
def test_a_label_gives_a_topic_only_by_a_whole_phrase(label: str, given: tuple[Topic, ...]) -> None:
    assert topics(TOPICS, [label]) == given


def test_topics_come_in_the_list_s_order_and_only_from_it() -> None:
    labels = ["Civic tech", "governance", "investigative journalism", "ethical AI"]
    assert topics(TOPICS, labels) == (AI, JOURNALISM, CIVIC_TECH)
    assert topics(TOPICS, []) == ()


def test_a_topic_is_given_once_however_many_labels_hold_it() -> None:
    assert topics(TOPICS, ["ethical AI", "AI governance", "artificial intelligence"]) == (AI,)


def test_each_label_is_matched_alone() -> None:
    assert topics(TOPICS, ["civic", "tech"]) == ()


def test_the_real_topic_list_reads_through_the_reader() -> None:
    # The list is data CLI edits, so the test holds its shape and not its topics.
    assert read_topic_list(ROOT / "config" / "tags.toml").topics
