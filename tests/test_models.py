"""A broken watch list stops the run before any network request, and says where."""

from datetime import date
from pathlib import Path

import pytest

from field_monitoring_pipeline.models import load_sources

GOOD = """
[[source]]
id = "good"
name = "A good source"
kind = "call"
how = "feed"
url = "https://example.org/feed/"
since = "2026-06-01"
"""


def write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "sources.toml"
    _ = path.write_text(body, encoding="utf-8")
    return path


def test_the_watch_list_is_read_and_filtered_by_kind(tmp_path: Path) -> None:
    sources = load_sources(write(tmp_path, GOOD), kind="call")
    assert [source.id for source in sources] == ["good"]
    assert sources[0].since == date(2026, 6, 1)
    assert load_sources(write(tmp_path, GOOD), kind="report") == ()


def test_a_route_nobody_implements_is_named_with_its_block(tmp_path: Path) -> None:
    """The error must say which block is wrong, not only which value."""
    broken = (
        GOOD
        + """
[[source]]
id = "broken"
name = "A typo"
kind = "call"
how = "page"
url = "https://example.org/"
since = "2026-06-01"
"""
    )
    with pytest.raises(ValueError, match="broken"):
        _ = load_sources(write(tmp_path, broken), kind="call")


def test_a_block_missing_its_id_is_named_by_its_position(tmp_path: Path) -> None:
    broken = (
        GOOD
        + """
[[source]]
name = "No id at all"
kind = "call"
how = "feed"
url = "https://example.org/"
since = "2026-06-01"
"""
    )
    with pytest.raises(ValueError, match="in position 2"):
        _ = load_sources(write(tmp_path, broken), kind="call")


def test_the_same_id_twice_is_refused_by_name(tmp_path: Path) -> None:
    """Two entries under one id would share a bookmark and an archive name."""
    twice = (
        GOOD
        + """
[[source]]
id = "good"
name = "The same id again, by mistake"
kind = "call"
how = "feed"
url = "https://elsewhere.example.org/feed/"
since = "2026-06-01"
"""
    )
    with pytest.raises(ValueError, match="good.*more than once"):
        _ = load_sources(write(tmp_path, twice), kind="call")


def test_a_repeat_across_kinds_is_refused_too(tmp_path: Path) -> None:
    """The bookmark a run keeps is filed under the id alone, not the id and kind."""
    twice = (
        GOOD
        + """
[[source]]
id = "good"
name = "Same id, other kind"
kind = "report"
how = "feed"
url = "https://elsewhere.example.org/feed/"
since = "2026-06-01"
"""
    )
    with pytest.raises(ValueError, match="more than once"):
        _ = load_sources(write(tmp_path, twice), kind="call")
