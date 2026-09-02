"""One broken website must never stop the run, and an unchanged one costs nothing."""

from collections.abc import Callable
from datetime import UTC, date, datetime

import httpx
import pytest
from pydantic import HttpUrl

from field_monitoring_pipeline.fetch import (
    MAX_BYTES,
    Failed,
    Fetched,
    Unchanged,
    Validator,
    fetch,
    read_items,
)
from field_monitoring_pipeline.models import RawItem, Source

Handler = Callable[[httpx.Request], httpx.Response]
"""A stand-in website: given a request, it decides what to answer."""

FEED = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>TAI</title>
  <item>
    <title>Open data grant</title>
    <link>https://example.org/call-one?utm_source=news</link>
    <guid>post-1</guid>
    <description>Applications open for civic data work.</description>
    <pubDate>Mon, 10 Aug 2026 09:00:00 +0000</pubDate>
  </item>
  <item>
    <title>An older call</title>
    <link>https://example.org/call-old</link>
    <guid>post-0</guid>
    <description>This one predates the cutoff.</description>
    <pubDate>Fri, 10 Jan 2026 09:00:00 +0000</pubDate>
  </item>
</channel></rss>
"""


@pytest.fixture
def source() -> Source:
    return Source(
        id="tai-weekly",
        name="TAI Weekly",
        kind="call",
        how="feed",
        url=HttpUrl("https://example.org/feed/"),
        since=date(2026, 6, 1),
    )


def client_for(handler: Handler) -> httpx.Client:
    # Redirects are followed by the fetch step itself, so that every hop can be
    # checked, which is why the client does not follow them.
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)


def items_of(source: Source, outcome: object) -> tuple[RawItem, ...]:
    """What the response turns into, read after the fetch rather than inside it."""
    assert isinstance(outcome, Fetched)
    return read_items(source, outcome.body, datetime(2026, 9, 1, tzinfo=UTC))


def test_a_feed_becomes_items_with_canonical_links(source: Source) -> None:
    with client_for(lambda _request: httpx.Response(200, text=FEED)) as client:
        outcome = fetch(source, None, client)

    items = items_of(source, outcome)
    assert len(items) == 1, "the older item is before the cutoff"

    item = items[0]
    assert item.source_item_id == "post-1"
    assert item.canonical_url == "https://example.org/call-one"
    assert "civic data work" in item.raw_text


def test_an_unchanged_source_is_read_no_further(source: Source) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("if-none-match", ""))
        return httpx.Response(304)

    with client_for(handler) as client:
        outcome = fetch(source, Validator(etag='W/"abc"'), client)

    assert isinstance(outcome, Unchanged)
    assert seen == ['W/"abc"'], "the stored validator must be sent back"


def test_the_validator_is_carried_forward(source: Source) -> None:
    response = httpx.Response(200, text=FEED, headers={"etag": 'W/"v2"'})
    with client_for(lambda _: response) as client:
        outcome = fetch(source, None, client)

    assert isinstance(outcome, Fetched)
    assert outcome.validator.etag == 'W/"v2"'


def test_a_client_error_is_permanent_and_not_retried(source: Source) -> None:
    attempts: list[int] = []

    def handler(_: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(404)

    with client_for(handler) as client:
        outcome = fetch(source, None, client)

    assert isinstance(outcome, Failed)
    assert len(attempts) == 1, "a refusal will not become an acceptance"


def test_a_server_error_is_retried_then_given_up_on(source: Source, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("field_monitoring_pipeline.fetch.BACKOFF_SECONDS", (0.0, 0.0))
    attempts: list[int] = []

    def handler(_: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(503)

    with client_for(handler) as client:
        outcome = fetch(source, None, client)

    assert isinstance(outcome, Failed)
    assert len(attempts) == 3


def test_a_timeout_is_retried_then_given_up_on(source: Source, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("field_monitoring_pipeline.fetch.BACKOFF_SECONDS", (0.0, 0.0))
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        raise httpx.ConnectTimeout("too slow", request=request)

    with client_for(handler) as client:
        outcome = fetch(source, None, client)

    assert isinstance(outcome, Failed)
    assert len(attempts) == 3
    assert "ConnectTimeout" in outcome.reason


def test_an_oversized_response_is_abandoned(source: Source) -> None:
    huge = "x" * (MAX_BYTES + 1)
    with client_for(lambda _request: httpx.Response(200, text=huge)) as client:
        outcome = fetch(source, None, client)

    assert isinstance(outcome, Failed)
    assert "passed" in outcome.reason


def test_an_item_without_a_date_is_kept(source: Source) -> None:
    """A route that publishes no dates has no backlog to bound."""
    undated = FEED.replace("<pubDate>Fri, 10 Jan 2026 09:00:00 +0000</pubDate>", "")

    with client_for(lambda _request: httpx.Response(200, text=undated)) as client:
        outcome = fetch(source, None, client)

    assert len(items_of(source, outcome)) == 2


def test_a_date_validator_is_sent_back_too(source: Source) -> None:
    """Not every source offers an entity tag; some only offer a date."""
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("if-modified-since", ""))
        return httpx.Response(304)

    with client_for(handler) as client:
        outcome = fetch(source, Validator(last_modified="Mon, 10 Aug 2026 09:00:00 GMT"), client)

    assert isinstance(outcome, Unchanged)
    assert seen == ["Mon, 10 Aug 2026 09:00:00 GMT"]


def test_an_entry_with_no_words_is_skipped(source: Source) -> None:
    """A feed sometimes carries a placeholder entry with nothing in it."""
    empty = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>TAI</title>
  <item><link>https://example.org/nothing</link><guid>post-2</guid></item>
</channel></rss>
"""

    with client_for(lambda _request: httpx.Response(200, text=empty)) as client:
        outcome = fetch(source, None, client)

    assert items_of(source, outcome) == ()


def test_a_stalling_response_is_abandoned(source: Source, monkeypatch: pytest.MonkeyPatch) -> None:
    """The time cap bounds the whole read, and passing it is not retried."""
    monkeypatch.setattr("field_monitoring_pipeline.fetch.MAX_READ_SECONDS", -1.0)
    attempts: list[int] = []

    def handler(_: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(200, text=FEED)

    with client_for(handler) as client:
        outcome = fetch(source, None, client)

    assert isinstance(outcome, Failed)
    assert "cap" in outcome.reason
    assert len(attempts) == 1, "passing a cap is abandonment, not a retry"


def test_a_source_that_fails_once_then_answers_is_captured(source: Source, monkeypatch: pytest.MonkeyPatch) -> None:
    """The whole point of retrying: the second attempt is allowed to succeed."""
    monkeypatch.setattr("field_monitoring_pipeline.fetch.BACKOFF_SECONDS", (0.0, 0.0))
    attempts: list[int] = []

    def handler(_: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) == 1:
            return httpx.Response(503)
        return httpx.Response(200, text=FEED)

    with client_for(handler) as client:
        outcome = fetch(source, None, client)

    assert isinstance(outcome, Fetched), "the recovery is returned, not the earlier fault"
    assert len(attempts) == 2, "it stopped as soon as it succeeded"
    assert len(items_of(source, outcome)) == 1


def test_a_response_that_is_not_a_feed_is_refused(source: Source) -> None:
    """A holding page must be told apart from a source that is merely quiet.

    Both parse to no items. Only one of them complains, and that is the whole
    difference between a blocked source and a healthy one with nothing new.
    """
    blocked = b"<html><title>Just a moment...</title><body>Checking your browser</body></html>"
    with pytest.raises(ValueError, match="not a feed"):
        _ = read_items(source, blocked, datetime(2026, 9, 1, tzinfo=UTC))


def test_an_empty_but_valid_feed_is_not_refused(source: Source) -> None:
    """A source with nothing new is not a source that is broken."""
    empty = b'<?xml version="1.0"?><rss version="2.0"><channel><title>t</title></channel></rss>'

    assert read_items(source, empty, datetime(2026, 9, 1, tzinfo=UTC)) == ()


def test_a_failed_source_reports_the_message_not_just_the_name(source: Source) -> None:
    """Months later this line is the only account of why a source stopped."""

    def handler(request: httpx.Request) -> httpx.Response:
        msg = "nodename nor servname provided"
        raise httpx.ConnectError(msg, request=request)

    with client_for(handler) as client:
        outcome = fetch(source, None, client)

    assert isinstance(outcome, Failed)
    assert "ConnectError" in outcome.reason
    assert "nodename nor servname provided" in outcome.reason


@pytest.mark.parametrize(
    "address",
    [
        "http://127.0.0.1:8080/feed",
        "http://localhost/feed",
        "http://169.254.169.254/latest/meta-data/",
        "http://192.168.1.1/feed",
        "http://10.0.0.1/feed",
        "http://[::1]/feed",
        "http://box.internal/feed",
    ],
)
def test_an_address_off_the_open_internet_is_refused(address: str) -> None:
    """A watch list entry cannot point the run at this machine or its network."""
    reached: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        reached.append(str(request.url))
        return httpx.Response(200, text=FEED)

    private = Source(
        id="probe",
        name="probe",
        kind="call",
        how="feed",
        url=HttpUrl(address),
        since=date(2026, 6, 1),
    )
    with client_for(handler) as client:
        outcome = fetch(private, None, client)

    assert isinstance(outcome, Failed)
    assert "not an address on the open internet" in outcome.reason
    assert reached == [], "and it was never even asked for"


def test_a_redirect_off_the_open_internet_is_refused(source: Source) -> None:
    """A listed source is trusted. Where it sends the run next is not.

    This is the shape that matters: the watch list entry is an ordinary public
    address, and the source answers with a redirect to somewhere internal.
    """
    reached: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        reached.append(str(request.url))
        if "169.254.169.254" in str(request.url):
            return httpx.Response(200, text=FEED)
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data/"})

    with client_for(handler) as client:
        outcome = fetch(source, None, client)

    assert isinstance(outcome, Failed)
    assert "not an address on the open internet" in outcome.reason
    assert all("169.254" not in url for url in reached), "the internal address was never reached"


def test_an_ordinary_redirect_is_still_followed(source: Source) -> None:
    """Refusing private addresses must not break a source that simply moved."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/moved/":
            return httpx.Response(200, text=FEED)
        return httpx.Response(301, headers={"location": "/moved/"})

    with client_for(handler) as client:
        outcome = fetch(source, None, client)

    assert len(items_of(source, outcome)) == 1


def test_a_source_that_redirects_in_circles_gives_up(source: Source) -> None:
    """A loop must end in a skipped source rather than a run that never returns."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://example.org/feed/"})

    with client_for(handler) as client:
        outcome = fetch(source, None, client)

    assert isinstance(outcome, Failed)
    assert "redirects" in outcome.reason


def test_the_response_comes_back_exactly_as_served(source: Source) -> None:
    """What the source served is what the run gets, so it can be written down whole."""
    with client_for(lambda _r: httpx.Response(200, text=FEED)) as client:
        outcome = fetch(source, None, client)

    assert isinstance(outcome, Fetched)
    assert outcome.body == FEED.encode("utf-8"), "nothing was read, trimmed or reshaped"
