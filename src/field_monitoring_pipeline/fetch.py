"""Reach one source and bring back what it served, unread.

Everything that can go wrong at the edge of the system is handled here: a slow
site, a site that is down, a site that has not changed since we last looked, a
response too large or too slow to be worth reading, and an address that is not
on the open internet. A source that fails is skipped and the run carries on,
because one broken website must never stop the others.

This step does not read what it fetched. It returns the response exactly as the
source served it, so the run can write that down before anything derives from
it. Turning a response into items is `read_items`, and it happens after the
capture rather than inside the fetch.

The function takes a source from the watch list rather than a bare address, so a
run cannot be pointed somewhere that is not on the list. Where a listed source
redirects, each hop is checked too, because a redirect is an address the list
never chose.
"""

from __future__ import annotations

import hashlib
import ipaddress
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, cast

import feedparser  # pyright: ignore[reportMissingTypeStubs]
import httpx
from pydantic import BaseModel

from field_monitoring_pipeline.models import RawItem, Source
from field_monitoring_pipeline.normalize import canonical_url

if TYPE_CHECKING:
    from collections.abc import Iterator

NOT_MODIFIED = 304
"""The answer a source gives when nothing has changed since we last looked."""

MAX_BYTES = 5_000_000
"""A feed larger than this is not a feed we want; abandon it rather than read it."""

TIMEOUT_SECONDS = 20.0
"""How long any single network step may take: connecting, or one read."""

MAX_READ_SECONDS = 30.0
"""Total time allowed for one body. A source that trickles forever is abandoned."""

MAX_REDIRECTS = 5
"""Hops allowed before a source is treated as sending the run in circles."""

RETRIES = 3
BACKOFF_SECONDS = (1.0, 2.0)
"""The pauses between attempts: two pauses for three attempts."""

LOCAL_NAMES = ("localhost",)
LOCAL_SUFFIXES = (".localhost", ".local", ".internal", ".home.arpa")
"""Names that mean a machine on this network rather than a source on the web."""


class NotOnTheOpenInternetError(Exception):
    """An address the watch list never chose, and the run will not reach.

    Raised for the source's own address and for any address it redirects to. It
    is deliberately not one of the network library's own faults, because those
    are retried and this must not be: the address will be just as private on the
    third attempt.
    """


def _is_public(host: str | None) -> bool:
    """Is this an address on the open internet, rather than one of ours?

    A literal address is checked outright. A name is checked against the endings
    that mean a local machine. A name that resolves to a private address is not
    caught here, because catching that means intercepting the connection itself
    rather than reading the address, and that is a larger piece of machinery
    than this project needs against an attack nobody here has faced. What is
    caught is the case that actually happens: a redirect to a loopback,
    link-local or private address.
    """
    if not host:
        return False
    lowered = host.strip("[]").lower()
    if lowered in LOCAL_NAMES or lowered.endswith(LOCAL_SUFFIXES):
        return False
    try:
        address = ipaddress.ip_address(lowered)
    except ValueError:
        return True  # an ordinary name
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


class Validator(BaseModel):
    """What a source gave us last time, so it can tell us if nothing changed.

    Sending these back means an unchanged source answers in one short exchange
    and costs nothing to check.
    """

    etag: str | None = None
    last_modified: str | None = None

    def as_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.etag:
            headers["If-None-Match"] = self.etag
        if self.last_modified:
            headers["If-Modified-Since"] = self.last_modified
        return headers


@dataclass(frozen=True, slots=True)
class Unchanged:
    """The source said nothing has changed since we last looked."""


@dataclass(frozen=True, slots=True)
class Fetched:
    """The source answered, and this is exactly what it served.

    The body is unread on purpose. The run writes it down before anything looks
    at it, which is the rule the whole archive rests on.
    """

    body: bytes
    validator: Validator


@dataclass(frozen=True, slots=True)
class Failed:
    """The source could not be read. The run continues without it."""

    reason: str


Outcome = Unchanged | Fetched | Failed
"""Exactly one of three things happens to a source. There is no fourth."""


def _read_capped(response: httpx.Response) -> bytes | None:
    """Read the body, giving up if it passes the size or time cap."""
    deadline = time.monotonic() + MAX_READ_SECONDS
    body = bytearray()
    for chunk in response.iter_bytes():
        body.extend(chunk)
        if len(body) > MAX_BYTES or time.monotonic() > deadline:
            return None
    return bytes(body)


def _published(entry: dict[str, Any]) -> date | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed is None:
        return None
    return date(parsed.tm_year, parsed.tm_mon, parsed.tm_mday)


def _entry_text(entry: dict[str, Any]) -> str:
    """The item's own words, preferring the fullest field the feed offers."""
    contents = cast("list[dict[str, Any]]", entry.get("content") or [])
    body = contents[0].get("value", "") if contents else ""
    parts = [
        str(entry.get("title", "")),
        str(entry.get("summary", "")),
        str(body),
    ]
    return "\n\n".join(part for part in parts if part).strip()


def read_items(source: Source, body: bytes, fetched_at: datetime) -> tuple[RawItem, ...]:
    """Turn a captured response into items, dropping anything before `since`.

    This runs after the response has been written down, never before, so the
    thing everything is rebuilt from is what the source served rather than what
    this function made of it.

    A response that is not a feed at all raises. That is how a source behind a
    gate is told apart from a source that is merely quiet, and the two look
    identical by item count: both give none. What tells them apart is that a
    feed always names its own format and a holding page never does. Without that
    distinction a blocked source reports zero items, has its bookmark saved, and
    is reported unchanged for ever after, which is a dead source that looks
    healthy for as long as anyone cares to wait.
    """
    parsed = cast("dict[str, Any]", feedparser.parse(body))  # pyright: ignore[reportUnknownMemberType]
    if not parsed.get("version"):
        fault = parsed.get("bozo_exception")
        detail = f", {fault}" if fault else ""
        msg = f"not a feed, the response names no feed format{detail}"
        raise ValueError(msg)
    entries = cast("list[dict[str, Any]]", parsed.get("entries", []))

    items: list[RawItem] = []
    for entry in entries:
        published = _published(entry)
        if published is not None and published < source.since:
            continue

        text = _entry_text(entry)
        if not text:
            continue

        link = entry.get("link")
        url = str(link) if link else None
        native = entry.get("id") or entry.get("guid")
        items.append(
            RawItem(
                source_id=source.id,
                source_item_id=str(native) if native else None,
                url=url,
                canonical_url=canonical_url(url) if url else None,
                fetched_at=fetched_at,
                raw_text=text,
                raw_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            )
        )
    return tuple(items)


def _hops(client: httpx.Client, url: str, headers: dict[str, str]) -> Iterator[httpx.Response]:
    """Walk a source's redirects, refusing any address off the open internet.

    Redirects are followed here rather than by the network library, because a
    redirect names an address the watch list never chose and each one has to be
    checked before it is reached.
    """
    for _hop in range(MAX_REDIRECTS + 1):
        if not _is_public(httpx.URL(url).host):
            msg = f"{url} is not an address on the open internet"
            raise NotOnTheOpenInternetError(msg)
        with client.stream("GET", url, headers=headers, timeout=TIMEOUT_SECONDS) as response:
            if not response.is_redirect:
                yield response
                return
            location = response.headers.get("location")
            if not location:
                yield response
                return
            url = str(httpx.URL(url).join(location))
    msg = f"more than {MAX_REDIRECTS} redirects"
    raise NotOnTheOpenInternetError(msg)


def fetch(source: Source, validator: Validator | None, client: httpx.Client) -> Outcome:
    """Reach one source once, retrying only faults that might pass.

    A timeout or a fault at the far end is retried with a widening pause. An
    answer that the request itself was wrong is permanent and is not retried,
    and so is an address that is not on the open internet.
    """
    headers = validator.as_headers() if validator else {}
    last_reason = "no attempt was made"

    for attempt in range(RETRIES):
        try:
            for response in _hops(client, str(source.url), headers):
                if response.status_code == NOT_MODIFIED:
                    return Unchanged()

                if 400 <= response.status_code < 500:
                    return Failed(f"{source.id}: refused with {response.status_code}")

                if response.status_code >= 500:
                    last_reason = f"{source.id}: server error {response.status_code}"
                    break

                body = _read_capped(response)
                if body is None:
                    return Failed(f"{source.id}: response passed the size or time cap")

                return Fetched(
                    body=body,
                    validator=Validator(
                        etag=response.headers.get("etag"),
                        last_modified=response.headers.get("last-modified"),
                    ),
                )
        except NotOnTheOpenInternetError as error:
            # Permanent by nature: it will be just as private next time.
            return Failed(f"{source.id}: refused, {error}")
        except httpx.HTTPError as error:
            # The message as well as the name: months later this line is the
            # only account of why a source stopped answering.
            last_reason = f"{source.id}: {type(error).__name__}: {error}"

        if attempt < RETRIES - 1:
            time.sleep(BACKOFF_SECONDS[attempt])

    return Failed(last_reason)
