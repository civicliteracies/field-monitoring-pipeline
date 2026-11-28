import datetime as dt
import json
from typing import Any

import httpx2
import pytest
from pydantic import ValidationError

from field_monitoring_pipeline.data.fetch import NO_RECORD, Fetched, Posted, fetch, on_or_after, posted_day
from field_monitoring_pipeline.data.reports import titled
from field_monitoring_pipeline.data.settings import Feed, Links, ListPage, WatchList, WordpressPosts
from tests.samples import REPLIES

TODAY = dt.date(2026, 11, 26)
STORIES = "https://data.org/wp-json/wp/v2/story"
PAGES = {"1": "wordpress_stories_page_1.json", "2": "wordpress_stories_page_2.json"}


def wordpress(since: dt.date) -> WordpressPosts:
    return WordpressPosts(name="data.org stories", url=STORIES, how="report-wordpress", kind="reports", since=since)


def stories(seen: list[httpx2.URL]) -> httpx2.Client:
    # data.org's answer, cut to three stories over two pages, with the page count WordPress sends beside it.
    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request.url)
        content = (REPLIES / PAGES[request.url.params["page"]]).read_bytes()
        return httpx2.Response(200, content=content, headers={"X-WP-TotalPages": str(len(PAGES))})

    return httpx2.Client(transport=httpx2.MockTransport(handler))


def served(body: bytes) -> httpx2.Client:
    return httpx2.Client(transport=httpx2.MockTransport(lambda _: httpx2.Response(200, content=body)))


def test_a_day_is_on_or_after_itself_and_not_after_the_next() -> None:
    day = dt.date(2024, 11, 26)
    assert on_or_after(day, day)
    assert on_or_after(day + dt.timedelta(days=1), day)
    assert not on_or_after(day, day + dt.timedelta(days=1))


def test_every_page_of_a_wordpress_answer_is_asked_with_its_labels_and_items_before_the_start_are_left_out() -> None:
    seen: list[httpx2.URL] = []
    with stories(seen) as client:
        found = fetch(wordpress(dt.date(2024, 11, 26)), client, TODAY)
    assert [(url.params["page"], url.params["per_page"], url.params["_embed"]) for url in seen] == [
        ("1", "100", "wp:term"),
        ("2", "100", "wp:term"),
    ]
    page = json.loads((REPLIES / PAGES["1"]).read_bytes())
    assert found == [
        Fetched(item["link"], item["link"], item["title"]["rendered"], Posted("wordpress", item)) for item in page
    ]


def test_an_item_dated_on_the_start_day_is_kept() -> None:
    with stories([]) as client:
        found = fetch(wordpress(dt.date(2025, 1, 16)), client, TODAY)
    assert [item.identifier for item in found] == [
        "https://data.org/stories/ark-solves/",
        "https://data.org/stories/khushi-baby/",
    ]


def test_an_item_on_a_later_page_is_kept_when_the_start_reaches_it() -> None:
    with stories([]) as client:
        found = fetch(wordpress(dt.date(2024, 8, 5)), client, TODAY)
    assert [item.identifier for item in found] == [
        "https://data.org/stories/ark-solves/",
        "https://data.org/stories/khushi-baby/",
        "https://data.org/stories/artpark/",
    ]


def test_a_wordpress_title_is_read_as_text() -> None:
    # data.org's annual report, as its answer writes its title.
    item = {
        "date": "2025-06-02T10:00:00",
        "link": "https://data.org/reports/x/",
        "title": {"rendered": "Accelerate What&#8217;s Possible"},
    }
    reply = httpx2.Response(200, content=json.dumps([item]).encode(), headers={"X-WP-TotalPages": "1"})
    with httpx2.Client(transport=httpx2.MockTransport(lambda _: reply)) as client:
        [found] = fetch(wordpress(dt.date(2024, 11, 26)), client, TODAY)
    assert found.title == "Accelerate What’s Possible"


FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel><title>Reports</title><link>https://example.org/</link>
<item><title>A new report</title><link>https://example.org/reports/new/</link>
<pubDate>Tue, 03 Jun 2025 10:00:00 +0000</pubDate>
<content:encoded><![CDATA[<p>It reached <a href="/schools">1 200 schools</a>.</p>]]></content:encoded></item>
<item><title>An old report</title><link>https://example.org/reports/old/</link>
<pubDate>Mon, 04 Mar 2024 10:00:00 +0000</pubDate><description>Old.</description></item>
</channel></rss>"""


def feed() -> Feed:
    return Feed(
        name="A feed", url="https://example.org/feed/", how="report-feed", kind="reports", since=dt.date(2024, 11, 26)
    )


def test_each_feed_entry_since_the_start_is_one_report_and_its_text_is_kept_word_for_word() -> None:
    with served(FEED) as client:
        [found] = fetch(feed(), client, TODAY)
    assert (found.identifier, found.link, found.title) == (
        "https://example.org/reports/new/",
        "https://example.org/reports/new/",
        "A new report",
    )
    assert isinstance(found.record, Posted)
    assert found.record.form == "feed"
    body: Any = found.record.body
    # Neither the markup is cleaned nor the relative link rewritten.
    assert body["content"][0]["value"] == '<p>It reached <a href="/schools">1 200 schools</a>.</p>'
    # The date feedparser read is kept as text, and is the day the item is dated by.
    assert body["published_parsed"] == "2025-06-03T10:00:00+00:00"
    assert posted_day(found.record) == dt.date(2025, 6, 3)
    json.dumps(body)


def test_a_page_served_in_place_of_a_feed_is_the_source_s_failed_run() -> None:
    with served(b"<html><body>Not a feed</body></html>") as client, pytest.raises(ValueError, match="not a feed"):
        fetch(feed(), client, TODAY)


TITLE, LINKED = "<title>A report</title>", "<link>https://example.org/reports/a/</link>"
DATED = "<pubDate>Tue, 03 Jun 2025 10:00:00 +0000</pubDate>"


def entry(*parts: str) -> bytes:
    # A feed of one entry, made of the parts given.
    return (
        '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>Reports</title>'
        f"<item>{''.join(parts)}</item></channel></rss>"
    ).encode()


def test_a_feed_entry_with_no_date_is_the_source_s_failed_run() -> None:
    reason = "a feed entry has no date: https://example.org/reports/a/"
    with served(entry(TITLE, LINKED)) as client, pytest.raises(ValueError, match=reason):
        fetch(feed(), client, TODAY)


def test_a_feed_entry_with_only_its_last_update_is_dated_by_it() -> None:
    atom = (
        b'<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom"><title>Reports</title>'
        b'<entry><title>A report</title><link href="https://example.org/reports/a/"/>'
        b"<updated>2025-06-03T10:00:00Z</updated></entry></feed>"
    )
    with served(atom) as client:
        [found] = fetch(feed(), client, TODAY)
    assert isinstance(found.record, Posted)
    body: Any = found.record.body
    assert "published_parsed" not in body
    assert posted_day(found.record) == dt.date(2025, 6, 3)


def test_a_feed_entry_with_no_link_is_the_source_s_failed_run() -> None:
    with served(entry(TITLE, DATED)) as client, pytest.raises(ValueError, match="a feed entry has no link: A report"):
        fetch(feed(), client, TODAY)


@pytest.mark.parametrize("title", ["", "<title></title>"], ids=["none", "empty"])
def test_a_feed_entry_with_no_title_is_kept_with_none_so_its_file_gives_it(title: str) -> None:
    with served(entry(title, LINKED, DATED)) as client:
        [found] = fetch(feed(), client, TODAY)
    assert (found.identifier, found.title) == ("https://example.org/reports/a/", None)


LIST = b"""<html><body>
<a href="/reports/first/">First report</a>
<a href="https://example.org/reports/second">Second
  report</a>
<a href="/reports/first/#top">First again</a>
<a href="/reports/">All reports</a>
<a href="/reports/first/annex/">An annex</a>
<a href="https://other.org/reports/third/">Elsewhere</a>
<a href="/about/">About</a>
</body></html>"""


def page(path: str = "/reports/") -> ListPage:
    return ListPage(name="A list", url="https://example.org/reports/", how="report-page", kind="reports", path=path)


def test_each_link_one_level_below_the_path_on_the_same_site_is_one_report_titled_by_its_words_where_it_first_appears() -> (
    None
):
    with served(LIST) as client:
        found = fetch(page(), client, TODAY)
    assert found == [
        Fetched("https://example.org/reports/first/", "https://example.org/reports/first/", "First report", NO_RECORD),
        Fetched("https://example.org/reports/second", "https://example.org/reports/second", "Second report", NO_RECORD),
    ]


def test_a_link_with_no_words_where_it_first_appears_has_no_title_so_its_file_gives_it() -> None:
    listing = (
        b'<html><a href="/reports/first/"><img src="cover.png"></a><a href="/reports/first/">First report</a></html>'
    )
    with served(listing) as client:
        [found] = fetch(page(), client, TODAY)
    assert found == Fetched("https://example.org/reports/first/", "https://example.org/reports/first/", None, NO_RECORD)
    assert titled(found, b"<html><head><title>From the file</title></head></html>").title == "From the file"


def test_a_list_page_with_no_report_link_is_the_source_s_failed_run() -> None:
    with served(LIST) as client, pytest.raises(ValueError, match="no report link under /papers/"):
        fetch(page("/papers/"), client, TODAY)


def test_each_single_link_is_one_report_once_with_no_title_and_no_request() -> None:
    one, two = "https://example.org/a.pdf", "https://example.org/b.docx"
    links = Links(name="Links", url="https://example.org/", how="report-links", kind="reports", links=(one, two, one))

    def refuse(_: httpx2.Request) -> httpx2.Response:
        raise AssertionError("no request is made")

    with httpx2.Client(transport=httpx2.MockTransport(refuse)) as client:
        assert fetch(links, client, TODAY) == [Fetched(one, one, None, NO_RECORD), Fetched(two, two, None, NO_RECORD)]


@pytest.mark.parametrize(
    "entry",
    [
        pytest.param({"how": "report-links", "links": []}, id="a report route without its kind"),
        pytest.param({"how": "report-links", "links": [], "kind": "calls"}, id="a report route marked calls"),
        pytest.param({"how": "eiti-page", "kind": "reports"}, id="a call route marked reports"),
        pytest.param({"how": "report-page", "kind": "reports"}, id="a list page without its path"),
        pytest.param({"how": "report-feed", "kind": "reports"}, id="a feed without its start"),
    ],
)
def test_a_source_s_kind_is_one_its_route_serves(entry: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        WatchList.model_validate({"source": {"one": {"name": "One", "url": "https://example.org/", **entry}}})


def test_a_call_source_s_kind_need_not_be_written() -> None:
    watch = WatchList.model_validate({
        "source": {"one": {"name": "One", "url": "https://example.org/", "how": "eiti-page"}}
    })
    assert watch.source["one"].kind == "calls"
