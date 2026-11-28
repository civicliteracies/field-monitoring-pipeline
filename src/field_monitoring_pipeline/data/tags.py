"""Read the topic list, and decide before any request whether a stored item is in CLI's field.

The topic list is one file, read whole in one step, so an error names the entry it is in. The run stops
when a topic a source names is not on the list, or when the list breaks one of its own rules.

The check is given an item's title, any other title its source gives it (the title and these are its
head), its body, and the topics its source names. A phrase matches as a whole phrase, preceded and
followed by anything that is not a letter or a digit, with both sides read in one form (`phrases.form`).
A cancelling name is taken out of the text before matching wherever it appears, a longer form such as a
plural included, so no phrase inside it counts. Every phrase found in the head gives its topic, a weak
one included, unless the title holds no phrase and names another sector. In the body, two different
phrases that are not weak give their topics when they stand within ten words of each other: different
in form, at places that do not overlap, and neither inside a longer phrase found there, so one mention of
a phrase that holds others is one phrase.
An item with any topic, or whose source names topics, is kept with its topics, in the list's order, each
once, with its mark. Any other item is set aside, with a reason in two halves: what the head gave (no
phrase, a phrase only inside a cancelling name, or a title naming another sector), then that the body
held no near pair. The reason calls the head and the body by the names the item's subject gives them, such
as a call's titles and description.
"""

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from field_monitoring_pipeline.data.models import Topic
from field_monitoring_pipeline.data.phrases import Phrase, form
from field_monitoring_pipeline.data.settings import TopicList

NEAR = 10


@dataclass(frozen=True)
class Parts:
    # What a reason calls an item's head and its body.
    head: str
    body: str


def no_title_match(parts: Parts) -> str:
    return f"no phrase of the topic list in the {parts.head}"


def not_near(parts: Parts) -> str:
    return f"in the {parts.body}, no two different phrases that are not weak within ten words of each other"


@dataclass(frozen=True)
class Subject:
    title: str
    other_titles: tuple[str, ...]
    body: str
    parts: Parts

    @property
    def head(self) -> tuple[str, ...]:
        return (self.title, *self.other_titles)


@dataclass(frozen=True)
class Kept:
    topics: tuple[Topic, ...]


@dataclass(frozen=True)
class SetAside:
    reason: str


def _pattern(phrase: str) -> re.Pattern[str]:
    # A letter or a digit is a word character that is not an underscore.
    return re.compile(rf"(?<![^\W_]){re.escape(form(phrase))}(?![^\W_])")


def _holds(text: str, phrase: str) -> bool:
    return _pattern(phrase).search(text) is not None


def read_topic_list(path: Path, named: tuple[str, ...]) -> TopicList:
    with path.open("rb") as file:
        listed = TopicList.model_validate(tomllib.load(file))
    if missing := sorted(set(named) - set(listed.topics)):
        raise ValueError(f"the watch list names topics that are not on the topic list: {', '.join(missing)}")
    return listed


def _cancel(listed: TopicList, text: str) -> str:
    for name in listed.cancelling_names:
        text = text.replace(form(name), " ")
    return text


def _near(every: tuple[Phrase, ...], body: str) -> set[str]:
    # Each match of a phrase that is not weak, with its place in the body.
    found = [
        (match.start(), match.end(), phrase)
        for phrase in every
        if not phrase.weak
        for match in _pattern(phrase.text).finditer(body)
    ]
    # One mention is one phrase: a match inside a longer match is part of that mention, not a mention of its own.
    at = sorted(
        (
            (len(body[:start].split()), start, end, phrase)
            for start, end, phrase in found
            if not any(s <= start and end <= e and e - s > end - start for s, e, _ in found)
        ),
        key=lambda place: place[0],
    )
    named: set[str] = set()
    for index, (words, start, end, phrase) in enumerate(at):
        for later, other_start, other_end, other in at[index + 1 :]:
            if later - words > NEAR:
                break
            apart = other_end <= start or other_start >= end
            if apart and form(other.text) != form(phrase.text):
                named |= {phrase.topic, other.topic}
    return named


def _head(listed: TopicList, every: tuple[Phrase, ...], subject: Subject) -> set[str] | SetAside:
    # The head's topics, never empty, or what the titles gave instead.
    raw = form(" | ".join(subject.head))
    found = [phrase for phrase in every if _holds(_cancel(listed, raw), phrase.text)]
    if not found:
        inside = sorted({phrase.text for phrase in every if _holds(raw, phrase.text)})
        if not inside:
            return SetAside(reason=no_title_match(subject.parts))
        cancelling = ", ".join(name for name in listed.cancelling_names if form(name) in raw)
        return SetAside(reason=f"the only match ({', '.join(inside)}) was inside a name that cancels: {cancelling}")
    title = form(subject.title)
    sectors = [word for word in listed.other_sectors if _holds(title, word)]
    if sectors and not any(_holds(_cancel(listed, title), phrase.text) for phrase in every):
        matched = ", ".join(sorted({phrase.text for phrase in found}))
        return SetAside(reason=f"title names another sector ({', '.join(sectors)}); matched only on: {matched}")
    return {phrase.topic for phrase in found}


def check(listed: TopicList, subject: Subject, own: tuple[str, ...]) -> Kept | SetAside:
    every = listed.phrases()
    named = _near(every, _cancel(listed, form(subject.body))) | set(own)
    match _head(listed, every, subject):
        case SetAside(reason=titles) if not named:
            return SetAside(reason=f"{titles}; {not_near(subject.parts)}")
        case SetAside():
            pass
        case set() as found:
            named |= found
    return Kept(
        topics=tuple(Topic(name=name, mark=entry.mark) for name, entry in listed.topics.items() if name in named)
    )
