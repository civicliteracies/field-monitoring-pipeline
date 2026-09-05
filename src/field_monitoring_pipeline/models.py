"""The typed shapes each step of the run hands to the next one.

Keeping every shape in one place means no step has to guess what another gives
it. There are two groups. The first is what the capture works with: a source on
the watch list, read from `config/sources.toml` which people edit by hand, and
one captured item, which the fetcher produces and the archive writes down. The
second is what the extraction builds: a funding call, and the small pieces a call
is made of.

A call carries its evidence. Five of its fields hold a value together with the
exact sentence from the source that supports it, so a value can be checked
against the page it came from long after it was written.
"""

from __future__ import annotations

import tomllib
from datetime import date, datetime
from typing import TYPE_CHECKING, Annotated, Any, Literal

if TYPE_CHECKING:
    from pathlib import Path

from pydantic import BaseModel, ConfigDict, Discriminator, HttpUrl, ValidationError

Kind = Literal["call", "report"]
"""What a source publishes. Calls and reports run on separate schedules."""

Route = Literal["feed"]
"""How a source is reached. Only feeds are implemented so far."""


class Source(BaseModel):
    """One entry on the watch list.

    `since` is the first-run cutoff: on the first look at a source, items
    published before this date are left alone, so a feed's whole back catalogue
    is not pulled in.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    kind: Kind
    how: Route
    url: HttpUrl
    since: date


class RawItem(BaseModel):
    """One item exactly as it arrived, before anything derives from it.

    `source_item_id` is the identifier the source published for the item, where
    it publishes one. It is untrusted text from the open web and is only ever
    hashed, never used as a name.
    """

    model_config = ConfigDict(frozen=True)

    source_id: str
    source_item_id: str | None
    url: str | None
    canonical_url: str | None
    fetched_at: datetime
    raw_text: str
    raw_hash: str


class Field(BaseModel):
    """A value together with the sentence from the source that supports it.

    The quote must appear in the source text word for word. That is what makes a
    value checkable by anyone reading the card, and it is the cheapest guard
    against a model inventing one.
    """

    model_config = ConfigDict(frozen=True)

    value: str
    quote: str


class Dated(BaseModel):
    """A call with a fixed closing date, and the sentence the date was read from.

    The date is checked as a valid date rather than a future one, so a call that
    has closed still validates and the archive keeps it. Whether it is still open
    is worked out when it is displayed. See ADR-0001.

    Anything else is refused rather than quietly dropped. A record read back from
    disk arrives as plain fields, and without this a stored card carrying both a
    closing date and an open basis would load as a dated call with the other half
    silently discarded, which is exactly the state the two shapes exist to make
    impossible.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    basis: Literal["dated"] = "dated"
    deadline: date
    quote: str


OpenBasis = Literal["rolling", "ongoing", "eoi"]
"""The three ways a call can be open. One name, so nothing can drift from it."""


class Open(BaseModel):
    """A call with no fixed close, and the sentence that says so.

    An open status is a claim about the page exactly like a date is, so it
    carries its evidence too. See ADR-0031.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    basis: OpenBasis
    quote: str


Timing = Annotated[Dated | Open, Discriminator("basis")]
"""When a call closes: a fixed date, or an open window. Never both, never neither."""

CallType = Literal[
    "grant",
    "tender",
    "rfp",
    "eoi",
    "framework",
    "fellowship",
    "prize",
    "training",
    "post",
    "other",
]
"""The kinds of call the system recognises. Checked against this list, not quoted."""


class Call(BaseModel):
    """One funding call, as the extraction builds it.

    Four fields may be absent, because a source often does not state them:
    funder, budget, eligibility and area. The other four are always present.
    That marking is the whole list of what may be absent, and a model answering
    "not stated" for one of them is stored as an empty field. See ADR-0033.

    `topics` stays empty here. Tags are assigned from the project's own tag list
    at the tagging slice, never by the model.
    """

    model_config = ConfigDict(frozen=True)

    title: str
    type: CallType
    funder: str | None
    timing: Timing
    budget: Field | None
    summary: Field
    eligibility: Field | None
    area: Field | None
    topics: tuple[str, ...] = ()
    source_url: str


class Extraction(BaseModel):
    """A built record together with what produced it.

    The three versions travel beside the record rather than inside it, because
    the record's shape is the funder's facts and these are facts about this
    system. A stored value is attributable to the exact prompt, model and
    deterministic code that made it, so a bad change can be found and undone.
    See ADR-0034.
    """

    model_config = ConfigDict(frozen=True)

    call: Call
    prompt_version: str
    model_id: str
    builder_version: str


def _validated(block: dict[str, Any], index: int) -> Source:
    """One checked block, or a refusal that names the block it came from."""
    try:
        return Source.model_validate(block)
    except ValidationError as error:
        name = block.get("id") or f"in position {index}"
        msg = f"watch list, source {name}: {error}"
        raise ValueError(msg) from error


def _refuse_a_repeated_id(sources: tuple[Source, ...]) -> None:
    """Two entries sharing an id would share a bookmark and an archive name.

    The check spans every entry rather than one kind, because the bookmark a
    run keeps for a source is filed under the id alone.
    """
    seen: set[str] = set()
    for source in sources:
        if source.id in seen:
            msg = f"watch list, source {source.id}: this id is used more than once"
            raise ValueError(msg)
        seen.add(source.id)


def load_sources(path: Path, kind: Kind) -> tuple[Source, ...]:
    """Read the watch list and return the sources of one kind.

    A malformed entry raises here, before any network request, naming the block
    it sits in, so a typo in the registry is reported rather than half a run
    being carried out. A repeated id is refused for the same reason.
    """
    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    blocks = raw.get("source", [])
    if not blocks:
        # A typo in a block was already reported. A typo in the block's own name
        # was not: the list came back empty, every source was skipped, and the
        # run said it had succeeded. A watch list naming nothing to watch is a
        # mistake in the repository, which is the one thing that stops a run
        # outright rather than being carried past.
        found = ", ".join(sorted(raw)) or "nothing at all"
        msg = f"{path} lists no [[source]] blocks. It contains {found}."
        raise ValueError(msg)
    sources = tuple(_validated(block, index) for index, block in enumerate(blocks, start=1))
    _refuse_a_repeated_id(sources)
    return tuple(source for source in sources if source.kind == kind)
