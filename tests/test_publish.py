import datetime as dt
import xml.etree.ElementTree as ET

import pytest

from field_monitoring_pipeline.models import Call, Topic
from field_monitoring_pipeline.publish import feed
from field_monitoring_pipeline.store import code
from tests.test_tags import AI, CIVIC_TECH, JOURNALISM
from tests.test_write import CALL

PATH = "calls/2026-10-15-identifying-user-focused-solutions-to-support-news-media-8cf6b3041b.md"
CARD = "https://github.com/civicliteracies/field-monitoring-pipeline/blob/data/data/" + PATH
OTHER = CALL.model_copy(update={"title": "Digital Investigations", "identifier": "ISF-2026-TF2-AG-CYBER-DIGITAL"})
OTHER_PATH = "calls/2026-10-14-digital-investigations-36827741b5.md"
TITLE = "Identifying user-focused solutions to support news media freedom"


def items(text: str) -> list[ET.Element]:
    return ET.fromstring(text).findall("channel/item")


def with_deadline(date: dt.date | None) -> Call:
    return CALL.model_copy(update={"deadline": CALL.deadline.model_copy(update={"date": date})})


def test_one_entry_per_card_in_the_order_given() -> None:
    entries = items(feed([(PATH, CALL), (OTHER_PATH, OTHER)]))
    assert [entry.findtext("link") for entry in entries] == [CARD, CARD.replace(PATH, OTHER_PATH)]
    assert items(feed([])) == []


@pytest.mark.parametrize(
    ("call", "title"),
    [
        pytest.param(with_deadline(dt.date(2027, 9, 5)), f"{TITLE} (closes 5 September 2027)", id="a day under 10"),
        pytest.param(with_deadline(None), f"{TITLE} (stays open)", id="no deadline"),
        pytest.param(
            with_deadline(dt.date(2020, 1, 1)), f"{TITLE} (closes 1 January 2020)", id="a deadline in the past"
        ),
        pytest.param(
            CALL.model_copy(update={"title": "Grants & prizes <for media>"}),
            "Grants &amp; prizes &lt;for media&gt; (closes 23 September 2027)",
            id="a title with & and <",
        ),
    ],
)
def test_an_entry_in_full(call: Call, title: str) -> None:
    assert (
        "\n    <item>\n"
        f"      <title>{title}</title>\n"
        f"      <link>{CARD}</link>\n"
        f"      <description>{CALL.summary.value}</description>\n"
        '      <category domain="topic">AI-and-civic</category>\n'
        '      <category domain="topic">data-journalism</category>\n'
        '      <category domain="mark">primary</category>\n'
        '      <category domain="mark">secondary</category>\n'
        f'      <guid isPermaLink="false">{code(CALL.identifier)}</guid>\n'
        "    </item>\n"
    ) in feed([(PATH, call)])


def test_the_channel_names_the_archive() -> None:
    channel = ET.fromstring(feed([])).find("channel")
    assert channel is not None
    assert [(part.tag, part.text) for part in channel] == [
        ("title", "Fieldbook"),
        ("link", "https://github.com/civicliteracies/field-monitoring-pipeline/tree/data"),
        ("description", "Funding calls Fieldbook has found, one entry per card"),
    ]


def test_the_identity_is_the_full_code_and_survives_a_new_title() -> None:
    [entry] = items(feed([(PATH, CALL)]))
    [renamed] = items(feed([(PATH, CALL.model_copy(update={"title": "A new title"}))]))
    assert entry.findtext("guid") == renamed.findtext("guid") == code(CALL.identifier)
    assert len(code(CALL.identifier)) == 64
    guid = entry.find("guid")
    assert guid is not None
    assert guid.get("isPermaLink") == "false"


def test_the_same_cards_give_the_same_bytes() -> None:
    assert feed([(PATH, CALL)]).encode() == feed([(PATH, CALL.model_copy())]).encode()


def test_the_feed_reads_as_rss() -> None:
    text = feed([(PATH, CALL)])
    assert text.startswith("<?xml version='1.0' encoding='utf-8'?>\n<rss version=\"2.0\">\n")
    assert text.endswith("</rss>\n")
    assert ET.fromstring(text).get("version") == "2.0"


@pytest.mark.parametrize(
    ("topics", "marks"),
    [
        # The secondary topic comes first, and its mark still follows the primary one.
        pytest.param((JOURNALISM, AI, CIVIC_TECH), ["primary", "secondary"], id="both marks"),
        pytest.param((AI, CIVIC_TECH), ["primary"], id="primary only"),
        pytest.param((JOURNALISM,), ["secondary"], id="secondary only"),
    ],
)
def test_an_entry_carries_a_category_per_topic_then_per_distinct_mark_primary_first(
    topics: tuple[Topic, ...], marks: list[str]
) -> None:
    [entry] = items(feed([(PATH, CALL.model_copy(update={"topics": topics}))]))
    assert [(category.get("domain"), category.text) for category in entry.findall("category")] == [
        *(("topic", topic.name) for topic in topics),
        *(("mark", mark) for mark in marks),
    ]


def test_a_card_with_no_topic_has_no_category() -> None:
    [entry] = items(feed([(PATH, CALL.model_copy(update={"topics": ()}))]))
    assert entry.findall("category") == []
