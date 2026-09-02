"""The typed shapes each step of the run hands to the next one.

This file holds two things and nothing else: what a source on the watch list
looks like, and what one captured item looks like. Keeping them in one place
means no step has to guess what another gives it. A source is read from
`config/sources.toml`, which people edit by hand; a raw item is what the fetcher
produces and the archive writes down.
"""

from __future__ import annotations

import tomllib
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from pathlib import Path

from pydantic import BaseModel, ConfigDict, HttpUrl, ValidationError

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
    sources = tuple(_validated(block, index) for index, block in enumerate(blocks, start=1))
    _refuse_a_repeated_id(sources)
    return tuple(source for source in sources if source.kind == kind)
