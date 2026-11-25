import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from field_monitoring_pipeline.data.models import Topic
from field_monitoring_pipeline.data.phrases import Phrase
from field_monitoring_pipeline.data.settings import TopicEntry
from field_monitoring_pipeline.data.tags import NO_MATCH, NOT_NEAR, Kept, SetAside, Subject, check, read_topic_list
from tests.samples import AI, CIVIC_TECH, JOURNALISM, LISTS, TOPIC_LIST, TOPICS

ROOT = Path(__file__).parent.parent.parent
CIVIC_SPACE = Topic(name="civic-space", mark="secondary")
GOVERNANCE = Topic(name="governance", mark="secondary")


def _head(*head: str, body: str = "", own: tuple[str, ...] = ()) -> Kept | SetAside:
    return check(TOPICS, Subject(title=head[0], other_titles=head[1:], body=body), own)


def test_the_topic_list_is_read_whole_in_its_order(tmp_path: Path) -> None:
    path = tmp_path / "tags.toml"
    path.write_text(TOPIC_LIST, encoding="utf-8")
    assert read_topic_list(path, ()) == TOPICS
    assert TOPICS.topics["AI-and-civic"] == TopicEntry(mark="primary", words=("artificial intelligence", "AI"))
    assert TOPICS.topics["civic-tech"] == TopicEntry(mark="primary")
    assert list(TOPICS.topics) == ["AI-and-civic", "data-journalism", "civic-tech", "civic-space", "governance"]
    assert (TOPICS.weak_words, TOPICS.cancelling_names) == (("civil society organisations",), ("democratic republic",))
    assert (TOPICS.other_sectors, TOPICS.names_not_matched) == (("farmers",), ("governance",))


@pytest.mark.parametrize(
    ("text", "refusal"),
    [
        pytest.param(
            LISTS + '[topics.governance]\nmark = "Secondary"\n',
            "topics.governance.mark",
            id="a mark other than the two",
        ),
        pytest.param(
            LISTS + '[topics.governance]\nmark = "secondary"\nword = ["state"]\n',
            "topics.governance.word",
            id="an unknown key",
        ),
        pytest.param(LISTS + '[topic.governance]\nmark = "secondary"\n', "topic\n", id="a misspelt table name"),
        pytest.param("", "topics\n", id="an empty file"),
        *(
            pytest.param(
                "\n".join(line for line in TOPIC_LIST.splitlines() if not line.startswith(key)), f"{key}\n", id=key
            )
            for key in ("weak_words", "cancelling_names", "other_sectors", "names_not_matched")
        ),
    ],
)
def test_a_list_that_breaks_its_rules_is_refused_naming_what_was_found(tmp_path: Path, text: str, refusal: str) -> None:
    path = tmp_path / "tags.toml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValidationError, match=re.escape(refusal)):
        read_topic_list(path, ())


def test_a_topic_a_source_names_that_is_not_on_the_list_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "tags.toml"
    path.write_text(TOPIC_LIST, encoding="utf-8")
    assert read_topic_list(path, ("civic-tech", "AI-and-civic")) == TOPICS
    with pytest.raises(ValueError, match="not on the topic list: extractives-eiti, geospatial$"):
        read_topic_list(path, ("geospatial", "civic-tech", "extractives-eiti"))


def test_the_phrases_are_each_topic_s_name_and_words_less_the_names_not_matched() -> None:
    given = TOPICS.phrases()
    assert Phrase(text="civic-tech", topic="civic-tech", weak=False) in given
    assert Phrase(text="civil society organisations", topic="civic-space", weak=True) in given
    assert Phrase(text="good governance", topic="governance", weak=False) in given
    assert [phrase.text for phrase in given if phrase.topic == "governance"] == ["good governance"]


@pytest.mark.parametrize(
    ("title", "given"),
    [
        pytest.param("ethical AI", (AI,), id="a word at the end"),
        pytest.param("AI-driven solutions", (AI,), id="a word before a hyphen"),
        pytest.param("Civic‑tech", (CIVIC_TECH,), id="the name with a non-breaking hyphen"),
        pytest.param("Artificial  Intelligence", (AI,), id="a word in another case and spacing"),
        pytest.param("investigative journalism support", (JOURNALISM,), id="a word inside a title"),
        pytest.param("Civic Tech", (CIVIC_TECH,), id="the name, its hyphen read as a space"),
        pytest.param("civic-tech", (CIVIC_TECH,), id="the name as written"),
        pytest.param("gen_AI_tools", (AI,), id="an underscore on each side"),
        pytest.param("Good governance for all", (GOVERNANCE,), id="a word of a name not matched"),
    ],
)
def test_a_phrase_in_the_head_gives_its_topic(title: str, given: tuple[Topic, ...]) -> None:
    assert _head(title) == Kept(topics=given)


@pytest.mark.parametrize(
    "title",
    [
        pytest.param("AI4Creatives", id="letters followed by a digit"),
        pytest.param("Thailand", id="letters inside a word"),
        pytest.param("Development aid", id="letters after the phrase"),
        pytest.param("Dubai", id="letters before the phrase"),
        pytest.param("Local governance", id="a name not matched, alone"),
    ],
)
def test_only_a_whole_phrase_matches(title: str) -> None:
    assert _head(title) == SetAside(reason=NO_MATCH)


def test_the_head_s_topics_come_in_the_list_s_order_each_once() -> None:
    assert _head("Civic tech and AI", "Investigative journalism, artificial intelligence") == Kept(
        topics=(AI, JOURNALISM, CIVIC_TECH)
    )


def test_a_weak_word_counts_in_the_head() -> None:
    assert _head("Grants", "Support to civil society organisations") == Kept(topics=(CIVIC_SPACE,))


def test_two_phrases_near_each_other_in_the_body_give_their_topics() -> None:
    near = "Funding for " + "AI tools " + "and " * 8 + "journalism today."
    assert _head("Grants", body=near) == Kept(topics=(AI, JOURNALISM))
    far = "Funding for " + "AI tools " + "and " * 9 + "journalism today."
    assert _head("Grants", body=far) == SetAside(reason=NO_MATCH)


@pytest.mark.parametrize(
    "body",
    [
        pytest.param("AI and more AI and AI.", id="one phrase, three times"),
        pytest.param("civil society organisations and AI", id="a weak word beside a phrase"),
        pytest.param("journalism and journalism", id="the same phrase twice"),
        pytest.param("data-journalism and data journalism", id="two entries of the list written the same way"),
        pytest.param("support to data journalism", id="one phrase holding another"),
        pytest.param("support to investigative journalism", id="one phrase holding two others side by side"),
    ],
)
def test_the_body_alone_needs_two_different_phrases_that_are_not_weak(body: str) -> None:
    assert _head("Grants", body=body) == SetAside(reason=NO_MATCH)


def test_a_cancelling_name_hides_the_phrases_inside_it_wherever_it_appears() -> None:
    assert _head("Support to the Democratic Republic of the Congo") == SetAside(
        reason=f"the only match (democratic) was inside a name that cancels: democratic republic; {NOT_NEAR}"
    )
    # A longer form of the name, such as its plural, still cancels.
    assert _head("Democratic Republics") == SetAside(
        reason=f"the only match (democratic) was inside a name that cancels: democratic republic; {NOT_NEAR}"
    )
    assert _head("Democratic Republic of the Congo: democracy") == Kept(topics=(CIVIC_SPACE,))
    assert _head("Grants", body="the democratic republic of AI") == SetAside(reason=NO_MATCH)


def test_a_title_naming_another_sector_cancels_the_head_unless_it_holds_a_phrase() -> None:
    assert _head("Young farmers", "AI for journalism") == SetAside(
        reason=f"title names another sector (farmers); matched only on: AI, journalism; {NOT_NEAR}"
    )
    assert _head("AI for farmers", "Grants") == Kept(topics=(AI,))
    # A phrase inside a cancelling name is no phrase of the title.
    assert _head("Young farmers of the Democratic Republic", "AI") == SetAside(
        reason=f"title names another sector (farmers); matched only on: AI; {NOT_NEAR}"
    )
    # Two phrases near each other in the body still keep it.
    assert _head("Young farmers", "AI", body="AI for journalism") == Kept(topics=(AI, JOURNALISM))


def test_a_source_s_own_topics_keep_an_item_and_join_the_head_s_in_the_list_s_order() -> None:
    assert _head("Kazakhstan reporting", own=("civic-tech",)) == Kept(topics=(CIVIC_TECH,))
    assert _head("Ethical AI", own=("civic-tech", "AI-and-civic", "civic-tech")) == Kept(topics=(AI, CIVIC_TECH))
    assert _head("Young farmers", "AI", own=("civic-tech",)) == Kept(topics=(CIVIC_TECH,))


def test_the_real_topic_list_reads_through_the_reader() -> None:
    # The list is data CLI edits, so the test holds its shape and not its topics.
    assert read_topic_list(ROOT / "config" / "tags.toml", ()).topics
