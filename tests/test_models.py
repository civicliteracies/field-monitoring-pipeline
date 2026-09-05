"""A broken watch list is refused early, and a record cannot hold an impossible state."""

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from field_monitoring_pipeline.models import Call, Dated, Field, Open, load_sources

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


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(GOOD.replace("[[source]]", "[[sources]]"), id="the-table-name-mis-spelt"),
        pytest.param("", id="a-watch-list-with-nothing-in-it"),
    ],
)
def test_a_watch_list_naming_nothing_to_watch_is_refused(tmp_path: Path, body: str) -> None:
    """A typo inside a block was reported. A typo in the block's own name was not.

    The list simply came back empty, every source was skipped without being
    mentioned, and the run reported that it had succeeded. A source that is never
    looked at is indistinguishable from a source with nothing to say, so this
    could have gone unnoticed for as long as anybody cared to wait, which is the
    failure this project is built to avoid.
    """
    with pytest.raises(ValueError, match="no \\[\\[source\\]\\] blocks"):
        _ = load_sources(write(tmp_path, body), kind="call")


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


def test_a_timing_refuses_a_field_belonging_to_the_other_shape() -> None:
    """Making the state impossible to express is cheaper than a guard to remember.

    An earlier version of this test built each shape and checked it reported its
    own name, which the type checker already proves and which said nothing about
    the rule. It was also wrong: a record read back from disk arrives as plain
    fields, and without refusing extra ones an open call carrying a closing date
    loaded happily with the date silently dropped.
    """
    with pytest.raises(ValidationError):
        Open.model_validate({
            "basis": "rolling",
            "quote": "Applications are accepted on a rolling basis.",
            "deadline": "2026-01-01",
        })

    with pytest.raises(ValidationError):
        Dated.model_validate({
            "basis": "dated",
            "deadline": "2026-01-01",
            "quote": "Applications close on 1 January 2026.",
            "open": "rolling",
        })


def test_an_open_timing_is_read_back_as_the_shape_it_was_written_as() -> None:
    """The dated shape had this and the open one did not, so a break there was invisible."""
    written = Call.model_validate({
        **_a_call().model_dump(),
        "timing": {"basis": "rolling", "quote": "Applications are accepted on a rolling basis."},
    })

    again = Call.model_validate(written.model_dump())

    assert isinstance(again.timing, Open)
    assert again.timing.basis == "rolling"


def test_a_timing_is_read_back_as_the_shape_it_was_written_as() -> None:
    """A stored card is read again on every push, so the discriminator has to work."""
    call = _a_call()

    again = Call.model_validate(call.model_dump())

    assert isinstance(again.timing, Dated)
    assert again.timing.deadline == date(2026, 9, 30)


def test_a_call_cannot_be_built_without_a_summary() -> None:
    """A card with no summary has nothing on it, so the shape refuses to hold one."""
    with pytest.raises(ValidationError):
        Call.model_validate({
            "title": "A Fund",
            "type": "grant",
            "funder": None,
            "timing": {"basis": "rolling", "quote": "Applications are accepted on a rolling basis."},
            "budget": None,
            "eligibility": None,
            "area": None,
            "source_url": "https://example.org/x",
        })


def test_a_kind_outside_the_ten_is_refused() -> None:
    with pytest.raises(ValidationError):
        Call.model_validate({**_a_call().model_dump(), "type": "sponsorship"})


def test_topics_start_empty_because_tagging_is_a_later_step() -> None:
    """The model never names a topic. They come from the project's own tag list."""
    assert _a_call().topics == ()


def test_a_built_record_cannot_be_changed_afterwards() -> None:
    """A record is evidence. Editing one in place would leave no trace."""
    call = _a_call()

    with pytest.raises(ValidationError):
        call.title = "something else"


def _a_call() -> Call:
    return Call(
        title="A Fund",
        type="grant",
        funder="Example Foundation",
        timing=Dated(deadline=date(2026, 9, 30), quote="Applications close on 30 September 2026."),
        budget=Field(value="EUR 20,000", quote="Grants of EUR 20,000 are available."),
        summary=Field(value="A fund.", quote="This is a fund for open data."),
        eligibility=None,
        area=None,
        source_url="https://example.org/x",
    )
