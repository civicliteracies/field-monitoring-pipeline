"""Give each item its permanent name and write it down before anything reads it.

The name is always a hash. One of the three things it can be made from is an
identifier the source itself published, which is text from the open web, and the
name becomes part of a file path. Hashing means a name can never contain a
separator, so it can never address anything outside the archive. That removes
the possibility rather than checking for it.

A name identifies one source's capture, so every rule that makes one carries
the source. Two sources that both carry a funding call therefore keep their own
file, their own body and their own record, and nothing a run writes can ever
overwrite what another source captured.

Recognising that two captures are the same call is a different question and it
is not answered here. It cannot be, honestly: a source that republishes a call
links to its own page rather than to the original, and this project resolves no
redirects, so two sources do not produce one address for one call. The link is
still recorded, so the question can be answered later against the funder, the
title and the deadline the card carries, which is real evidence rather than two
strings being equal. See ADR-0028.

Canonicalising still earns its place within a source: one feed listing the same
call twice with different tracking parameters collapses to one file, because
the source is the same on both.

Writing happens before the run asks whether the item was already known. Checking
first would lose an item permanently if the run stopped in between, because
nothing would record that it was ever seen. This way the worst case is a
duplicate, which can be cleaned up.

The same reasoning sets the order of the two files: the origin record first and
the body second, so that a run cut short leaves an item that will be written
again rather than one that is taken for known for ever.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import TYPE_CHECKING, Any, cast

from field_monitoring_pipeline.store import RAW, RESPONSES

if TYPE_CHECKING:
    from field_monitoring_pipeline.models import RawItem
    from field_monitoring_pipeline.store import Store


class KeyRule(StrEnum):
    """Which of the three inputs produced an item's name."""

    SOURCE_ITEM_ID = "source_item_id"
    CANONICAL_URL = "canonical_url"
    BODY = "body"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def item_key(item: RawItem) -> tuple[str, KeyRule]:
    """Return the item's permanent name and which rule produced it.

    The order of preference is the source's own identifier, then the canonical
    link, then the body. Every one of them is hashed, and every one of them
    carries the source, so a name identifies one source's capture and two
    sources can never write over each other. Which rule applies depends on what
    a feed publishes, so leaving any of them unnamespaced would make that
    protection depend on a publisher's habits.
    """
    if item.source_item_id:
        return _sha(f"{item.source_id}\x00{item.source_item_id}"), KeyRule.SOURCE_ITEM_ID
    if item.canonical_url:
        return _sha(f"{item.source_id}\x00{item.canonical_url}"), KeyRule.CANONICAL_URL
    return _sha(f"{item.source_id}\x00{item.raw_hash}"), KeyRule.BODY


def archive_response(source_id: str, body: bytes, store: Store) -> str:
    """Write down exactly what a source served, before anything reads it.

    This is the capture the whole design rests on: the response is kept whole,
    so anything later derived from it can be derived again, and anything this
    version of the code does not look at is still there for a version that
    does. Deriving items from it comes after, never before.

    The name is a hash of the bytes, so a source that serves the same response
    tomorrow writes the same file and the archive does not churn, and a source
    that changes leaves both versions behind.
    """
    fingerprint = _sha_bytes(body)
    _ = store.write(RESPONSES, source_id, f"{fingerprint}.raw", data=body)
    return fingerprint


def _first_captured(store: Store, item_id: str, now: str) -> str:
    """When this item was first captured, kept so a re-capture rewrites nothing.

    Reading it back is what stops the archive churning. Without this the record
    is rewritten every run on the timestamp alone, so a day when nothing changed
    still commits, and the history stops showing when an item really changed.

    A record that cannot be read counts as absent, and this capture becomes the
    first. A file half written by a machine that was torn down must not stop the
    next run.
    """
    saved = store.read(RAW, f"{item_id}.json")
    if saved is None:
        return now
    try:
        record = cast("dict[str, Any]", json.loads(saved))
    except json.JSONDecodeError:
        return now
    earlier = record.get("first_captured_at")
    return earlier if isinstance(earlier, str) else now


def _origin(item: RawItem, item_id: str, key_rule: KeyRule, first_captured_at: str, response_hash: str) -> bytes:
    """The companion record: where this capture came from and how it was named.

    Every field here is a fact about the item rather than about the run that
    happened to see it, so capturing the same item again writes the same bytes
    and a day when nothing changed leaves the archive alone. `first_captured_at`
    is when this item first entered the archive, not when it was last looked at:
    when the run last looked is the run's business and lives with its bookmarks.

    `canonical_url` is the one field not namespaced by source. It is the evidence
    a later step uses to ask whether two captures are the same call, so it is
    kept whole even though the name it helped produce is namespaced.
    """
    payload = {
        "item_id": item_id,
        "key_rule": key_rule.value,
        "source_id": item.source_id,
        "url": item.url,
        "canonical_url": item.canonical_url,
        "first_captured_at": first_captured_at,
        "raw_hash": item.raw_hash,
        "response_hash": response_hash,
    }
    return json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")


def archive(item: RawItem, store: Store, response_hash: str) -> str:
    """Write the item's body and its origin record, then return its permanent name.

    The body is written exactly as it arrived, so the archive stays the thing
    everything else can be rebuilt from. The name is the only thing the run
    needs back: the caller already holds the item, and the keying rule is in
    the sidecar.

    Another source capturing the same call writes its own file beside this one,
    so which sources actually bring calls in, and therefore which are earning
    their place on the watch list, is a question the archive can answer.

    Capturing the same item again writes the same bytes, so a day when nothing
    changed leaves the archive untouched and its history keeps meaning what it
    says: an entry there is an item that actually changed.

    The record names the response this item was read out of, so anything derived
    from it can be traced back to the exact bytes the source served.
    """
    item_id, key_rule = item_key(item)
    first_captured_at = _first_captured(store, item_id, item.fetched_at.isoformat())
    # The origin record goes down first. Whether an item is already known is
    # read from the bodies, so a run that dies between these two writes leaves
    # no body, the item still counts as unseen, and the next run writes both.
    # The other order would strand it: a body with no origin beside it, taken
    # for known for ever.
    _ = store.write(
        RAW,
        f"{item_id}.json",
        data=_origin(item, item_id, key_rule, first_captured_at, response_hash),
    )
    _ = store.write(RAW, f"{item_id}.txt", data=item.raw_text.encode("utf-8"))
    return item_id
