"""Read the topic list, and give a call the topics its source names and the topics the labels its source put on it name.

The topic list is the `[topics]` table of one file, one entry per topic, read whole in one step, so an
error names the topic it is in. A topic a source names that is not on the list is refused when the list
is read. A topic is given when its source names it, or when one of the labels holds the topic's name or
one of its words as a whole phrase, preceded and followed by anything that is not a letter or a digit.
Both sides are read in one form: case ignored, a hyphen read as a space, and a run of spacing read as
one space. The topics come in the list's order, each once, with its mark.
"""

import re
import tomllib
from collections.abc import Sequence
from pathlib import Path

from field_monitoring_pipeline.models import Topic, TopicList


def read_topic_list(path: Path, named: tuple[str, ...]) -> TopicList:
    with path.open("rb") as file:
        listed = TopicList.model_validate(tomllib.load(file))
    if missing := sorted(set(named) - set(listed.topics)):
        raise ValueError(f"the watch list names topics that are not on the topic list: {', '.join(missing)}")
    return listed


def _form(text: str) -> str:
    return " ".join(text.replace("-", " ").casefold().split())


def _holds(label: str, phrase: str) -> bool:
    # A letter or a digit is a word character that is not an underscore.
    return re.search(rf"(?<![^\W_]){re.escape(phrase)}(?![^\W_])", label) is not None


def topics(listed: TopicList, labels: Sequence[str], own: tuple[str, ...]) -> tuple[Topic, ...]:
    formed = [_form(label) for label in labels]
    return tuple(
        Topic(name=name, mark=entry.mark)
        for name, entry in listed.topics.items()
        if name in own or any(_holds(label, _form(phrase)) for phrase in (name, *entry.words) for label in formed)
    )
