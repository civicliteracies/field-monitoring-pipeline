"""The store owns `data/`, and nothing can write outside it."""

from pathlib import Path

import pytest

from field_monitoring_pipeline.store import RAW, Store


def test_writes_land_inside_the_store(tmp_path: Path) -> None:
    store = Store(tmp_path)
    written = store.write(RAW, "abc.txt", data=b"hello")

    assert written == tmp_path / RAW / "abc.txt"
    assert written.read_bytes() == b"hello"


def test_a_path_that_escapes_the_store_is_refused(tmp_path: Path) -> None:
    store = Store(tmp_path)
    with pytest.raises(ValueError, match="outside the store"):
        _ = store.write("..", "..", "config", "sources.toml", data=b"owned")

    assert not (tmp_path.parent / "config").exists()


def test_known_names_are_read_once_when_the_store_opens(tmp_path: Path) -> None:
    raw = tmp_path / RAW
    raw.mkdir(parents=True)
    _ = (raw / "already-here.txt").write_bytes(b"old")

    store = Store(tmp_path)
    assert store.known == frozenset({"already-here"})
    assert not store.is_new("already-here")
    assert store.is_new("brand-new")


def test_writing_an_item_does_not_change_whether_it_was_new(tmp_path: Path) -> None:
    """The whole ordering rule rests on this: write first, and the answer holds."""
    store = Store(tmp_path)
    assert store.is_new("fresh")

    _ = store.write(RAW, "fresh.txt", data=b"body")

    assert store.is_new("fresh"), "the snapshot must predate anything this run wrote"


def test_reading_a_missing_file_returns_nothing(tmp_path: Path) -> None:
    assert Store(tmp_path).read("state", "nobody.json") is None
