"""Define the typed shapes the run passes from step to step: a funding call and a report.

A call has a title, a type, a funder, an opening date, a deadline, a budget, a summary, who can
apply, where, its topics, and a link, and it names the call's identifier, as the source gives it or
else the call's full address, and the model and the instructions that read it. Both dates, the
budget, the summary, who can apply and where each carry a sentence beside the value, so a person can
check it. Each of those sentences, and the funder's name, carries a mark saying whether it was found
in the text the model read. Where the source gives a date or the budget in a labelled field, that
sentence is the field written out as one plain line. The funder, the opening date, the budget, who
can apply and where are empty when the source does not give them, and a call with no deadline stays
open. A call has at least one topic, and each carries its name and the mark it had on the topic list
that day, primary or secondary. This template refuses a call with a field missing, a field added, no
topic, or a date it cannot read. It accepts a date in the past, and keeps the link exactly as
given. A call cannot be changed once it is made.

A report has a title, a type, the date its source gives, its topics and a link, and it names its
identifier and the model and the instructions that read it. The organisation doing the work, the
audience, the methodology, the results, the duration and where each carry a sentence beside the value,
and each is empty when the source does not give it; the date is empty when the source gives none. A
report holds the same rules as a call: at least one topic, no field missing or added, never changed.
"""

import datetime as dt
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

type CallType = Literal[
    "grant", "tender", "rfp", "eoi", "framework", "fellowship", "prize", "training", "post", "other"
]
# The feed gives a card's marks in this order.
type Mark = Literal["primary", "secondary"]
# The kinds of item the run collects: the command's word, a card folder's name, and a source's kind on the watch list.
type Kind = Literal["calls", "reports"]
# The kinds whose documents a later kind's run reads once more.
type Held = Literal["calls"]
# What a reading's text and a card say for a fact the source does not give.
NOT_STATED = "not stated"


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


class Named(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    found: bool


class Call(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str
    type: CallType
    funder: Named | None
    opening: Opening | None
    deadline: Deadline
    budget: Quoted | None
    summary: Quoted
    eligibility: Quoted | None
    area: Quoted | None
    topics: Annotated[tuple[Topic, ...], Field(min_length=1)]
    link: str
    identifier: str
    model: str
    instructions: str


type ReportType = Literal["project results report", "evaluation", "annual report", "research or case study"]


class Report(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str
    type: ReportType
    organisation: Quoted | None
    audience: Quoted | None
    methodology: Quoted | None
    results: Quoted | None
    duration: Quoted | None
    area: Quoted | None
    published: dt.date | None
    topics: Annotated[tuple[Topic, ...], Field(min_length=1)]
    link: str
    identifier: str
    model: str
    instructions: str
