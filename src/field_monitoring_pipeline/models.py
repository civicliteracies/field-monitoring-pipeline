"""Define the typed shapes the run passes and reads: a funding call, the topic list and the watch list.

A call has a title, a type, a funder, an opening date, a deadline, a budget, a summary, who can
apply, where, its topics, and a link, and it names the call's identifier, as the source gives it or
else the call's full address, and the model and the instructions that read it. Both dates, the
budget, the summary, who can apply and where each carry a sentence beside the value, so a person can
check it. Each of those sentences carries a mark saying whether it was found in the text the model
read. Where the source gives a date or the budget in a labelled field, that sentence is the field
written out as one plain line. The funder, the opening date, the budget, who can apply and where are
empty when the source does not give them, and a call with no deadline stays open. Each topic carries
its name and the mark it had on the topic list that day, primary or secondary, and a call may have
no topic. This template refuses a call with a field missing, a field added, or a date it cannot read.
It accepts a date in the past, and keeps the link exactly as given. A call cannot be changed once it
is made. The topic list gives each topic its mark and the words that also count for it, and refuses
any other mark and any key it does not know.

The watch list maps each source's id to its entry: its name, its address, its route and the topics
it names, with the search words the EU route takes. It refuses an entry with a required field
missing, a field added or a route it does not know; the topics may be left out.
"""

import datetime as dt
from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

type CallType = Literal[
    "grant", "tender", "rfp", "eoi", "framework", "fellowship", "prize", "training", "post", "other"
]
# The feed gives a card's marks in this order.
type Mark = Literal["primary", "secondary"]


class Quoted(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    value: str
    quote: str
    found: bool


class Opening(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    date: dt.date
    quote: str
    found: bool


class Deadline(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    date: dt.date | None
    quote: str
    found: bool


class Topic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    mark: Mark


class TopicEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mark: Mark
    words: tuple[str, ...] = ()


class TopicList(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    topics: Mapping[str, TopicEntry]


class Call(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str
    type: CallType
    funder: str | None
    opening: Opening | None
    deadline: Deadline
    budget: Quoted | None
    summary: Quoted
    eligibility: Quoted | None
    area: Quoted | None
    topics: tuple[Topic, ...]
    link: str
    identifier: str
    model: str
    instructions: str


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
