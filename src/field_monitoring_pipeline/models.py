"""Define what a funding call is made of.

A call has a title, a type, a funder, an opening date, a deadline, a budget, a summary, who can
apply, where, and a link. Both dates, the budget, the summary, who can apply and where each carry a
sentence beside the value, so a person can check it. The funder, the opening date, the budget, who
can apply and where are empty when the source does not give them, and a call with no deadline stays
open. This template refuses a call with a field missing, a field added, or a date it cannot read.
It accepts a date in the past, and keeps the link exactly as given. A call cannot be changed once it
is made.
"""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict

type CallType = Literal[
    "grant", "tender", "rfp", "eoi", "framework", "fellowship", "prize", "training", "post", "other"
]


class Quoted(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    value: str
    quote: str


class Opening(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    date: dt.date
    quote: str


class Deadline(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    date: dt.date | None
    quote: str


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
    link: str
