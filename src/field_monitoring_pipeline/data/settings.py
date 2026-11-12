"""Define the typed shapes of the two lists the run reads: the topic list and the watch list.

The topic list gives each topic its mark and the words that also count for it, and refuses any other
mark and any key it does not know.

The watch list maps each source's id to its entry: its name, its address, its route and the topics
it names, with the search words the EU route takes. It refuses an entry with a required field
missing, a field added or a route it does not know; the topics may be left out.
"""

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from field_monitoring_pipeline.data.models import Mark


class TopicEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mark: Mark
    words: tuple[str, ...] = ()


class TopicList(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    topics: Mapping[str, TopicEntry]


class _Entry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    url: str
    topics: tuple[str, ...] = ()


class EuSearch(_Entry):
    how: Literal["eu-search"]
    words: tuple[str, ...]


class EitiPage(_Entry):
    how: Literal["eiti-page"]


type Source = Annotated[EuSearch | EitiPage, Field(discriminator="how")]


class WatchList(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: Mapping[str, Source]
