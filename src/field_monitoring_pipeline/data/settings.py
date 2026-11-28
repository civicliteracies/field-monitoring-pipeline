"""Define the typed shapes of the two lists the run reads: the topic list and the watch list.

The topic list gives each topic its mark and the words that also count for it, and four lists the
topic check reads: the weak words, the names that cancel a match, the words of other sectors and the
names not matched as phrases. Each of the four is required. It refuses any other mark and any key it
does not know, a weak word that is not one of its phrases and a name not matched that is not a topic's
name, however the list is made. Its phrases are each topic's name and words, without the names not
matched, each with its topic and whether it is weak.

The watch list maps each source's id to its entry: its name, its address, its route, the kind of item
its route serves and the topics it names. The EU route takes its search words; the reports' WordPress
and feed routes take the first day an item may be dated; the reports' list page route takes the path
its report links start with, and the links route takes its addresses. It refuses an entry with a
required field missing, a field added, a route it does not know or a kind its route does not serve;
the topics may be left out, and a call source's kind, `calls`, need not be written.
"""

import datetime as dt
from collections.abc import Mapping
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from field_monitoring_pipeline.data.models import Mark
from field_monitoring_pipeline.data.phrases import Phrase, form


class TopicEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mark: Mark
    words: tuple[str, ...] = ()


class TopicList(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    weak_words: tuple[str, ...]
    cancelling_names: tuple[str, ...]
    other_sectors: tuple[str, ...]
    names_not_matched: tuple[str, ...]
    topics: Mapping[str, TopicEntry]

    def phrases(self) -> tuple[Phrase, ...]:
        weak = {form(word) for word in self.weak_words}
        return tuple(
            Phrase(text=phrase, topic=name, weak=form(phrase) in weak)
            for name, entry in self.topics.items()
            for phrase in (entry.words if name in self.names_not_matched else (name, *entry.words))
        )

    @model_validator(mode="after")
    def _matchable(self) -> Self:
        known = {form(phrase.text) for phrase in self.phrases()}
        if unknown := sorted(word for word in self.weak_words if form(word) not in known):
            raise ValueError(f"the topic list's weak words that are not phrases of the list: {', '.join(unknown)}")
        if unknown := sorted(set(self.names_not_matched) - set(self.topics)):
            raise ValueError(f"the topic list's names not matched that are not topics' names: {', '.join(unknown)}")
        return self


class _Entry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    url: str
    topics: tuple[str, ...] = ()


class EuSearch(_Entry):
    how: Literal["eu-search"]
    kind: Literal["calls"] = "calls"
    words: tuple[str, ...]


class EitiPage(_Entry):
    how: Literal["eiti-page"]
    kind: Literal["calls"] = "calls"


class WordpressPosts(_Entry):
    how: Literal["report-wordpress"]
    kind: Literal["reports"]
    since: dt.date


class Feed(_Entry):
    how: Literal["report-feed"]
    kind: Literal["reports"]
    since: dt.date


class ListPage(_Entry):
    how: Literal["report-page"]
    kind: Literal["reports"]
    path: str


class Links(_Entry):
    how: Literal["report-links"]
    kind: Literal["reports"]
    links: tuple[str, ...]


type Source = Annotated[EuSearch | EitiPage | WordpressPosts | Feed | ListPage | Links, Field(discriminator="how")]


class WatchList(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: Mapping[str, Source]
