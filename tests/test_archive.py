"""Names are permanent, always hashed, and written before anything is checked."""

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from field_monitoring_pipeline.archive import KeyRule, archive, item_key
from field_monitoring_pipeline.models import RawItem
from field_monitoring_pipeline.store import RAW, Store

HASH = re.compile(r"^[0-9a-f]{64}$")
RESPONSE = "d" * 64
"""Stands in for the hash of the response an item was read out of."""


def make_item(
    *,
    source_item_id: str | None = None,
    canonical: str | None = "https://example.org/call",
    text: str = "A grant for open data work.",
) -> RawItem:
    return RawItem(
        source_id="tai-weekly",
        source_item_id=source_item_id,
        url=canonical,
        canonical_url=canonical,
        fetched_at=datetime(2026, 9, 1, 6, 17, tzinfo=UTC),
        raw_text=text,
        raw_hash="0" * 64,
    )


def test_the_same_link_always_gives_the_same_name() -> None:
    first, rule = item_key(make_item())
    second, _ = item_key(make_item())

    assert first == second
    assert rule is KeyRule.CANONICAL_URL


def test_the_sources_own_identifier_wins_when_there_is_one() -> None:
    name, rule = item_key(make_item(source_item_id="post-4471"))

    assert rule is KeyRule.SOURCE_ITEM_ID
    assert name != item_key(make_item())[0]


def test_the_body_is_the_last_resort() -> None:
    """With nothing else to go on, the body names the item, alongside the source."""
    name, rule = item_key(make_item(canonical=None))

    assert rule is KeyRule.BODY
    assert HASH.match(name)
    assert name != "0" * 64, "the body hash alone would not say whose capture this is"


def test_two_sources_publishing_the_same_identifier_do_not_collide() -> None:
    one = make_item(source_item_id="1")
    two = one.model_copy(update={"source_id": "other-source"})

    assert item_key(one)[0] != item_key(two)[0]


def test_a_name_is_always_a_hash_whichever_rule_made_it() -> None:
    for item in (
        make_item(source_item_id="post-1"),
        make_item(),
        make_item(canonical=None),
    ):
        name, _ = item_key(item)
        assert HASH.match(name), f"{name} is not a hash"


def test_a_hostile_identifier_cannot_escape_the_archive(tmp_path: Path) -> None:
    """A feed is open-web content, and the name it suggests becomes a file path."""
    hostile = make_item(source_item_id="../../config/sources.toml")
    store = Store(tmp_path)

    item_id = archive(hostile, store, RESPONSE)

    assert HASH.match(item_id)
    assert (tmp_path / RAW / f"{item_id}.txt").is_file()
    assert not (tmp_path.parent / "config").exists()


def test_the_body_is_written_byte_for_byte(tmp_path: Path) -> None:
    text = "  Leading space, trailing newline, and a é accent.\n"
    store = Store(tmp_path)

    item_id = archive(make_item(text=text), store, RESPONSE)

    written = (tmp_path / RAW / f"{item_id}.txt").read_bytes()
    assert written == text.encode("utf-8")


def test_the_sidecar_records_where_it_came_from_and_how_it_was_named(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path)
    item_id = archive(make_item(source_item_id="post-9"), store, RESPONSE)

    sidecar = json.loads((tmp_path / RAW / f"{item_id}.json").read_text("utf-8"))

    assert sidecar["item_id"] == item_id
    assert sidecar["key_rule"] == KeyRule.SOURCE_ITEM_ID.value
    assert sidecar["source_id"] == "tai-weekly"
    assert sidecar["canonical_url"] == "https://example.org/call"
    assert sidecar["first_captured_at"].startswith("2026-09-01")
    assert sidecar["raw_hash"] == "0" * 64


def test_the_origin_record_is_written_before_the_body(tmp_path: Path) -> None:
    """A run cut short between the two writes must leave the item still unseen.

    Whether an item is already known is read from the bodies. If the body landed
    first, a run that died in between would strand it: a body with no origin
    beside it, taken for known for ever and never written again.
    """
    store = Store(tmp_path)
    written: list[str] = []
    real_write = store.write

    def write_then_die(*parts: str, data: bytes) -> Path:
        written.append(parts[-1])
        if len(written) == 2:
            msg = "the runner was torn down"
            raise OSError(msg)
        return real_write(*parts, data=data)

    store.write = write_then_die  # pyright: ignore[reportAttributeAccessIssue]

    with pytest.raises(OSError, match="torn down"):
        _ = archive(make_item(source_item_id="post-1"), store, RESPONSE)

    assert written[0].endswith(".json"), "the origin record goes down first"
    assert not list((tmp_path / RAW).glob("*.txt")), "no body survived the interruption"
    assert Store(tmp_path).known == frozenset(), "so the next run still counts it as unseen"


def test_every_rule_names_one_source_capture(tmp_path: Path) -> None:
    """Whichever rule applies, two sources never write over each other.

    Which rule applies depends on what a feed publishes. If any rule left the
    source out, that protection would depend on a publisher's habits.
    """
    by_rule = {
        KeyRule.SOURCE_ITEM_ID: make_item(source_item_id="post-1"),
        KeyRule.CANONICAL_URL: make_item(),
        KeyRule.BODY: make_item(canonical=None),
    }

    for expected, mine in by_rule.items():
        theirs = mine.model_copy(update={"source_id": "another-source"})

        my_name, rule = item_key(mine)
        their_name, _ = item_key(theirs)

        assert rule is expected
        assert my_name != their_name, f"{expected.value} does not carry its source"
        assert HASH.match(my_name)

    store = Store(tmp_path)
    for mine in by_rule.values():
        _ = archive(mine, store, RESPONSE)
        _ = archive(mine.model_copy(update={"source_id": "another-source"}), store, RESPONSE)

    assert len(list((tmp_path / RAW).glob("*.txt"))) == 6, "three calls, two sources, six files"


def test_the_same_source_reporting_again_keeps_one_file(tmp_path: Path) -> None:
    """Namespacing must not break the dedup that does work: within one source."""
    store = Store(tmp_path)
    item = make_item()

    first = archive(item, store, RESPONSE)
    # A different body as well as a different link, so only the link rule can
    # collapse these two. Falling through to the body rule would name them apart.
    second = archive(
        item.model_copy(
            update={
                "url": "https://example.org/call?utm_source=news",
                "raw_text": "the same call, reworded",
                "raw_hash": "e" * 64,
            }
        ),
        store,
        RESPONSE,
    )

    assert first == second, "tracking parameters still collapse to one capture"
    assert len(list((tmp_path / RAW).glob("*.txt"))) == 1


def test_the_link_is_kept_unnamespaced_for_matching_later(tmp_path: Path) -> None:
    """The name cannot match across sources. The link is the evidence that can."""
    store = Store(tmp_path)
    shared = "https://funder.example/open-call"
    mine = make_item(canonical=shared)
    theirs = mine.model_copy(update={"source_id": "an-aggregator"})

    my_id = archive(mine, store, RESPONSE)
    their_id = archive(theirs, store, RESPONSE)

    assert my_id != their_id, "two captures, two names"
    records = [json.loads((tmp_path / RAW / f"{name}.json").read_text("utf-8")) for name in (my_id, their_id)]
    assert {record["canonical_url"] for record in records} == {shared}, (
        "and one shared link recorded, so a later step can ask whether they are one call"
    )


def test_capturing_the_same_item_again_writes_the_same_bytes(tmp_path: Path) -> None:
    """A day when nothing changed must leave the archive untouched.

    The bodies never churned, because identical bytes are not a change. The
    records did, because they carried the moment of the fetch, so every run
    rewrote them and every day committed something that recorded nothing.
    """
    store = Store(tmp_path)
    item = make_item(source_item_id="post-1")

    item_id = archive(item, store, RESPONSE)
    first = {p.name: p.read_bytes() for p in sorted((tmp_path / RAW).iterdir())}

    # The same item, seen again tomorrow: a later fetch, identical content.
    tomorrow = item.model_copy(update={"fetched_at": datetime(2026, 9, 2, 6, 17, tzinfo=UTC)})
    assert archive(tomorrow, Store(tmp_path), RESPONSE) == item_id

    again = {p.name: p.read_bytes() for p in sorted((tmp_path / RAW).iterdir())}
    assert again == first, "nothing on disk changed, so there is nothing to commit"


def test_the_first_capture_is_the_one_the_record_keeps(tmp_path: Path) -> None:
    """When the item entered the archive is a fact about the item, and does not move."""
    store = Store(tmp_path)
    item = make_item(source_item_id="post-1")
    item_id = archive(item, store, RESPONSE)

    later = item.model_copy(
        update={
            "fetched_at": datetime(2027, 3, 4, 9, 0, tzinfo=UTC),
            "raw_text": "the call, reworded by the funder",
        }
    )
    _ = archive(later, Store(tmp_path), RESPONSE)

    record = json.loads((tmp_path / RAW / f"{item_id}.json").read_text("utf-8"))
    assert record["first_captured_at"].startswith("2026-09-01"), (
        "the first sighting stands, even when the words later change"
    )


def test_an_unreadable_record_does_not_stop_the_next_run(tmp_path: Path) -> None:
    """A file half written by a machine that was torn down is not fatal."""
    store = Store(tmp_path)
    item = make_item(source_item_id="post-1")
    item_id, _ = item_key(item)
    _ = store.write(RAW, f"{item_id}.json", data=b'{"first_captured_at": "2026')

    assert archive(item, store, RESPONSE) == item_id

    record = json.loads((tmp_path / RAW / f"{item_id}.json").read_text("utf-8"))
    assert record["first_captured_at"].startswith("2026-09-01"), "this capture becomes the first"
