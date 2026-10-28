"""Write the RSS feed from the cards.

One entry per card, in the order of the cards' names. Each entry holds the title with the closing date,
a link to the card on github.com, the summary, one category for each of its topics and one for each
mark they carry, primary before secondary, told apart by their RSS `domain`, and the call's code as
its identity. No date of the build goes in, so the same cards give the same file.
"""

# The checker refuses this module by name because its readers are unsafe on XML from outside; here it only writes.
import xml.etree.ElementTree as ET  # noqa: S405
from typing import get_args

from field_monitoring_pipeline.models import Call, Mark
from field_monitoring_pipeline.store import code
from field_monitoring_pipeline.write import STAYS_OPEN, day

TITLE = "Fieldbook"
DESCRIPTION = "Funding calls Fieldbook has found, one entry per card"
REPOSITORY = "https://github.com/civicliteracies/field-monitoring-pipeline"
ARCHIVE = f"{REPOSITORY}/tree/data"
CARDS = f"{REPOSITORY}/blob/data/data/"
# The marks in the order the type names them, whatever the order of a card's topics.
MARKS: tuple[Mark, ...] = get_args(Mark.__value__)


def _title(call: Call) -> str:
    deadline = call.deadline.date
    closes = STAYS_OPEN if deadline is None else f"closes {day(deadline)}"
    return f"{call.title} ({closes})"


def _categories(call: Call) -> list[tuple[str, str]]:
    marks = {topic.mark for topic in call.topics}
    return [("topic", topic.name) for topic in call.topics] + [("mark", mark) for mark in MARKS if mark in marks]


def feed(cards: list[tuple[str, Call]]) -> str:
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    for name, text in (("title", TITLE), ("link", ARCHIVE), ("description", DESCRIPTION)):
        ET.SubElement(channel, name).text = text
    for path, call in cards:
        item = ET.SubElement(channel, "item")
        for name, text in (("title", _title(call)), ("link", CARDS + path), ("description", call.summary.value)):
            ET.SubElement(item, name).text = text
        for domain, text in _categories(call):
            ET.SubElement(item, "category", domain=domain).text = text
        ET.SubElement(item, "guid", isPermaLink="false").text = code(call.identifier)
    ET.indent(rss)
    return ET.tostring(rss, encoding="unicode", xml_declaration=True) + "\n"
