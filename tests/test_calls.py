"""The whole run, end to end, against a stand-in website."""

import json
from pathlib import Path

import httpx
import pytest

from field_monitoring_pipeline.calls import run
from field_monitoring_pipeline.store import RAW, RESPONSES, STATE, Store

WATCH_LIST = """
[[source]]
id = "tai-weekly"
name = "TAI Weekly"
kind = "call"
how = "feed"
url = "https://example.org/feed/"
since = "2026-06-01"

[[source]]
id = "steady"
name = "A source that answers"
kind = "call"
how = "feed"
url = "https://steady.example.org/feed/"
since = "2026-06-01"

[[source]]
id = "a-report-source"
name = "Reports"
kind = "report"
how = "feed"
url = "https://example.org/reports/"
since = "2026-06-01"
"""

SHARED_FEED = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>Two sources, one call</title>
  <item>
    <title>A call both of them carry</title>
    <link>https://funder.example/open-call</link>
    <description>Applications open.</description>
    <pubDate>Mon, 10 Aug 2026 09:00:00 +0000</pubDate>
  </item>
</channel></rss>
"""
"""No guid, so the link names the item. That is the rule that can collide."""

FEED = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>TAI</title>
  <item>
    <title>Open data grant</title>
    <link>https://example.org/call-one</link>
    <guid>post-1</guid>
    <description>Applications open.</description>
    <pubDate>Mon, 10 Aug 2026 09:00:00 +0000</pubDate>
  </item>
</channel></rss>
"""


@pytest.fixture
def config(tmp_path: Path) -> Path:
    path = tmp_path / "sources.toml"
    _ = path.write_text(WATCH_LIST, encoding="utf-8")
    return path


def serving(body: str, status: int = 200, headers: dict[str, str] | None = None) -> httpx.Client:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text=body, headers=headers or {})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_a_run_captures_from_every_call_source(config: Path, tmp_path: Path) -> None:
    store = Store(tmp_path / "data")

    with serving(FEED) as client:
        report = run(config, store, client)

    assert len(report.sources) == 2, "both call sources are read, the report one is not"
    assert all("first look" in source.summary for source in report.sources)
    assert report.new == 0, "a first look announces nothing as new"

    archived = sorted((tmp_path / "data" / RAW).iterdir())
    assert sorted(path.suffix for path in archived) == [".json", ".json", ".txt", ".txt"]


def test_running_twice_captures_the_item_once(config: Path, tmp_path: Path) -> None:
    data = tmp_path / "data"

    with serving(FEED) as client:
        first = run(config, Store(data), client)
        second = run(config, Store(data), client)

    assert first.new == 0, "the first look announces nothing"
    assert second.new == 0, "the second run recognises what the first captured"
    assert len(list((data / RAW).glob("*.txt"))) == 2


def test_the_validator_is_remembered_between_runs(config: Path, tmp_path: Path) -> None:
    data = tmp_path / "data"
    response = httpx.Response(200, text=FEED, headers={"etag": 'W/"seen"'})

    def handler(_request: httpx.Request) -> httpx.Response:
        return response

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        _ = run(config, Store(data), client)

    saved = json.loads((data / STATE / "tai-weekly.json").read_text("utf-8"))
    assert saved["etag"] == 'W/"seen"'


def test_a_broken_source_does_not_stop_the_run(config: Path, tmp_path: Path) -> None:
    store = Store(tmp_path / "data")

    with serving("nothing here", status=404) as client:
        report = run(config, store, client)

    assert report.new == 0
    assert all("skipped" in source.summary for source in report.sources)
    assert not (tmp_path / "data" / RAW).exists(), "nothing is written for a dead source"


def test_the_run_reports_what_it_did(config: Path, tmp_path: Path) -> None:
    with serving(FEED) as client:
        report = run(config, Store(tmp_path / "data"), client)

    lines = report.lines()
    assert "tai-weekly" in lines[0]
    assert "first look" in lines[0]
    assert lines[-1] == "0 new item(s) captured"


def test_nothing_under_config_is_touched(config: Path, tmp_path: Path) -> None:
    before = config.read_bytes()

    with serving(FEED) as client:
        _ = run(config, Store(tmp_path / "data"), client)

    assert config.read_bytes() == before


def routed(**by_host: httpx.Response) -> httpx.Client:
    """A stand-in internet where each host answers differently."""

    def handler(request: httpx.Request) -> httpx.Response:
        return by_host[request.url.host.split(".")[0]]

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_one_broken_source_does_not_stop_the_others(
    config: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The point of skipping a bad source is that the good ones still run."""
    monkeypatch.setattr("field_monitoring_pipeline.fetch.BACKOFF_SECONDS", (0.0, 0.0))
    with routed(
        example=httpx.Response(500),
        steady=httpx.Response(200, text=FEED),
    ) as client:
        report = run(config, Store(tmp_path / "data"), client)

    outcomes = {source.source_id: source for source in report.sources}
    assert "skipped" in outcomes["tai-weekly"].summary
    assert outcomes["steady"].captured == 1, "the working source still captured"


def test_a_feed_body_produces_exactly_the_expected_text(config: Path, tmp_path: Path) -> None:
    """The whole path, from feed body to the bytes on disk."""
    data = tmp_path / "data"

    with routed(
        example=httpx.Response(200, text=FEED),
        steady=httpx.Response(404),
    ) as client:
        _ = run(config, Store(data), client)

    written = sorted((data / RAW).glob("*.txt"))
    assert len(written) == 1
    assert written[0].read_bytes() == b"Open data grant\n\nApplications open."


def test_an_unchanged_source_adds_nothing_and_says_so(config: Path, tmp_path: Path) -> None:
    """A source answering "nothing has changed" costs the run nothing further."""
    data = tmp_path / "data"

    with serving(FEED) as client:
        _ = run(config, Store(data), client)
    with serving("", status=304) as client:
        report = run(config, Store(data), client)

    assert all(source.summary == "unchanged" for source in report.sources)
    assert report.new == 0
    assert len(list((data / RAW).glob("*.txt"))) == 2, "the archive is untouched"


def test_a_later_run_counts_only_the_genuinely_new(config: Path, tmp_path: Path) -> None:
    """After the first look, a fresh item counts and the backlog does not."""
    data = tmp_path / "data"
    grown = FEED.replace(
        "</channel></rss>",
        """  <item>
    <title>A second grant</title>
    <link>https://example.org/call-two</link>
    <guid>post-2</guid>
    <description>Applications open for archives work.</description>
    <pubDate>Tue, 11 Aug 2026 09:00:00 +0000</pubDate>
  </item>
</channel></rss>""",
    )

    with serving(FEED) as client:
        _ = run(config, Store(data), client)
    with serving(grown) as client:
        report = run(config, Store(data), client)

    assert all(source.new == 1 for source in report.sources)
    assert report.new == 2, "one genuinely new item per source, the backlog uncounted"


def test_two_sources_carrying_one_call_each_keep_their_capture(config: Path, tmp_path: Path) -> None:
    """Neither source's capture is lost, and the log matches what is on disk."""
    data = tmp_path / "data"

    with serving(SHARED_FEED) as client:
        _ = run(config, Store(data), client)
    with serving(SHARED_FEED) as client:
        report = run(config, Store(data), client)

    bodies = sorted((data / RAW).glob("*.txt"))
    assert len(bodies) == 2, "one call, two sources, two captures, nothing overwritten"
    assert report.new == 0, "and neither is new on the second run"

    records = [json.loads(body.with_suffix(".json").read_text("utf-8")) for body in bodies]
    assert {record["source_id"] for record in records} == {"steady", "tai-weekly"}
    assert len({record["canonical_url"] for record in records}) == 1, (
        "the link they share is recorded on both, for a later step to match on"
    )


def test_the_log_count_matches_what_the_archive_holds(config: Path, tmp_path: Path) -> None:
    """The run log must never claim a number the archive does not back up."""
    data = tmp_path / "data"

    with serving(FEED) as client:
        _ = run(config, Store(data), client)
    before = len(list((data / RAW).glob("*.txt")))

    with serving(SHARED_FEED) as client:
        report = run(config, Store(data), client)

    after = len(list((data / RAW).glob("*.txt")))
    assert report.new == after - before, "every new item counted is a file that appeared"


def test_what_the_source_served_is_written_down_whole(config: Path, tmp_path: Path) -> None:
    """Capture before derive, meant literally: the response, not what we made of it."""
    data = tmp_path / "data"

    with serving(FEED) as client:
        _ = run(config, Store(data), client)

    served = list((data / RESPONSES).rglob("*.raw"))
    assert served, "the response itself is in the archive"
    assert any(p.read_bytes() == FEED.encode("utf-8") for p in served), (
        "byte for byte as the source served it, not parsed and reassembled"
    )
    assert {p.parent.name for p in served} == {"tai-weekly", "steady"}, "one folder per source"


def test_an_item_names_the_response_it_was_read_out_of(config: Path, tmp_path: Path) -> None:
    """Anything derived later can be traced back to the exact bytes it came from."""
    data = tmp_path / "data"

    with serving(FEED) as client:
        _ = run(config, Store(data), client)

    record = json.loads(next((data / RAW).glob("*.json")).read_text("utf-8"))
    named = record["response_hash"]
    assert (data / RESPONSES / record["source_id"] / f"{named}.raw").is_file(), (
        "and the response it names is really there"
    )


def test_a_source_serving_the_same_response_does_not_churn(config: Path, tmp_path: Path) -> None:
    """A response is named by its own bytes, so an unchanged source rewrites nothing."""
    data = tmp_path / "data"

    with serving(FEED) as client:
        _ = run(config, Store(data), client)
    first = sorted(p.name for p in (data / RESPONSES).rglob("*.raw"))
    with serving(FEED) as client:
        _ = run(config, Store(data), client)

    assert sorted(p.name for p in (data / RESPONSES).rglob("*.raw")) == first


def test_a_blocked_source_is_skipped_and_keeps_no_bookmark(config: Path, tmp_path: Path) -> None:
    """The failure the handover test is built around must not look like health.

    A holding page gives no items, exactly as a quiet source does. If its
    bookmark were saved, every later run would report it unchanged and a dead
    source would look healthy for as long as anyone cared to wait.
    """
    data = tmp_path / "data"
    block = "<html><title>Just a moment...</title><body>Checking your browser</body></html>"

    with serving(block, headers={"etag": 'W/"the-block-page"'}) as client:
        report = run(config, Store(data), client)

    assert all("skipped" in source.summary for source in report.sources)
    assert all("unreadable" in source.summary for source in report.sources)
    assert not (data / STATE).exists(), "no bookmark, so tomorrow looks again rather than believing it"
    assert list((data / RESPONSES).rglob("*.raw")), "but the page itself is kept, as the evidence"


def test_an_empty_feed_is_not_mistaken_for_a_blocked_one(config: Path, tmp_path: Path) -> None:
    """A source with nothing to say is healthy, and must be reported as such."""
    data = tmp_path / "data"
    empty = '<?xml version="1.0"?><rss version="2.0"><channel><title>t</title></channel></rss>'

    with serving(empty, headers={"etag": 'W/"quiet"'}) as client:
        report = run(config, Store(data), client)

    assert all("skipped" not in source.summary for source in report.sources)
    assert (data / STATE / "tai-weekly.json").is_file(), "its bookmark is kept, so tomorrow is cheap"
