import datetime as dt
import json
import re
import tomllib
from pathlib import Path

import httpx2
import pytest

from field_monitoring_pipeline.fetch import NO_RECORD, FetchedCall, fetch, fetch_page, new_client, search_eu
from field_monitoring_pipeline.models import EitiPage, EuSearch, WatchList
from field_monitoring_pipeline.tags import read_topic_list

ROOT = Path(__file__).parent.parent
REPLIES = Path(__file__).parent / "replies"
URL = "https://api.tech.ec.europa.eu/search-api/prod/rest/search?apiKey=SEDIA"
TODAY = dt.date(2026, 9, 27)
EITI = EitiPage(name="EITI", url="https://eiti.org/consultancy-opportunities", how="eiti-page")
EITI_LIST = (REPLIES / "eiti_list.html").read_text(encoding="utf-8")
VIEWS = "https://eiti.org/offers/example-2027-call-for-views"
STUDY = "https://eiti.org/offers/example-consultancy"
# The current list of the hand-made page with its three rows taken out and its empty mark put in.
EMPTY_LIST = EITI_LIST.replace(
    EITI_LIST[EITI_LIST.index('<div class="c-listing__items ">') : EITI_LIST.index("<!-- end of current -->")],
    '<div class="c-listing__empty o-content-from-editor"><h3 class="c-listing__empty-title">No results found</h3></div>',
)


def eu(*words: str) -> EuSearch:
    return EuSearch(name="EU Funding and Tenders Portal", url=URL, how="eu-search", words=words)


def site(page: str, seen: list[str] | None = None) -> httpx2.Client:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if seen is not None:
            seen.append(str(request.url))
        return httpx2.Response(200, content=page.encode())

    return httpx2.Client(transport=httpx2.MockTransport(handler))


def replay(files: dict[tuple[str, str], str], seen: list[httpx2.Request] | None = None) -> httpx2.Client:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if seen is not None:
            seen.append(request)
        name = files[request.url.params["text"], request.url.params["pageNumber"]]
        return httpx2.Response(200, content=(REPLIES / name).read_bytes())

    return httpx2.Client(transport=httpx2.MockTransport(handler))


def test_the_real_watch_list_reads_into_its_typed_entries_and_its_topics_are_on_the_real_topic_list() -> None:
    # The watch list is data CLI edits, so the test holds its shape and not its sources.
    watch = WatchList.model_validate(tomllib.loads((ROOT / "config" / "sources.toml").read_text(encoding="utf-8")))
    assert watch.source
    read_topic_list(
        ROOT / "config" / "tags.toml", tuple(topic for source in watch.source.values() for topic in source.topics)
    )


def test_eiti_s_reader_returns_each_current_call_once_by_its_full_address() -> None:
    seen: list[str] = []
    with site(EITI_LIST, seen) as client:
        calls = fetch(EITI, client, TODAY)
    assert seen == [EITI.url]
    assert calls == [
        FetchedCall(VIEWS, VIEWS, "Example 2027 EITI Validation: call for views on stakeholder engagement", NO_RECORD),
        FetchedCall(STUDY, STUDY, "Consultancy opportunity: an example study", NO_RECORD),
    ]


def test_eiti_s_empty_list_gives_no_calls() -> None:
    with site(EMPTY_LIST) as client:
        assert fetch(EITI, client, TODAY) == []


@pytest.mark.parametrize("tag", [pytest.param("<br>", id="open"), pytest.param("<br/>", id="self-closing")])
def test_a_line_break_at_the_start_of_each_heading_keeps_every_call_and_its_title_whole(tag: str) -> None:
    with site(EITI_LIST.replace('"c-card__heading">', f'"c-card__heading">{tag}')) as client:
        calls = fetch(EITI, client, TODAY)
    assert [(call.link, call.title) for call in calls] == [
        (VIEWS, "Example 2027 EITI Validation: call for views on stakeholder engagement"),
        (STUDY, "Consultancy opportunity: an example study"),
    ]


@pytest.mark.parametrize(
    ("page", "found"),
    [
        pytest.param(
            "<html><main><h1>Just a moment...</h1></main></html>",
            "the page must hold exactly one list of current calls; it holds 0",
            id="not the list",
        ),
        pytest.param(
            EITI_LIST.replace("view-id-past_offers", "view-id-offers"),
            "the page must hold exactly one list of current calls; it holds 2",
            id="two lists",
        ),
        pytest.param(
            EMPTY_LIST.replace("c-listing__empty ", "c-listing__nothing "),
            "the list of current calls must hold calls or its empty mark, not both; it holds neither",
            id="neither",
        ),
        pytest.param(
            EITI_LIST.replace("<!-- end of current -->", '<div class="c-listing__empty">No results found</div>'),
            "the list of current calls must hold calls or its empty mark, not both; it holds both",
            id="calls and the empty mark",
        ),
        pytest.param(
            EITI_LIST.replace('href="/offers/example-consultancy"', 'href="/news/example"'),
            "a current call must have exactly one title and a link under /offers/; one has 1 and links to '/news/example'",
            id="a link elsewhere",
        ),
        pytest.param(
            EITI_LIST.replace('class="c-card__heading"', 'class="c-card__head"', 1),
            "one has 0 and links to '/offers/example-2027-call-for-views'",
            id="a card with no heading",
        ),
        pytest.param(
            EITI_LIST.replace(
                '<div class="c-card__meta">19 Oct 2026</div>', '<div class="c-card__heading"><span>Again</span></div>'
            ),
            "one has 2 and links to '/offers/example-consultancy'",
            id="a card with two headings",
        ),
    ],
)
def test_a_page_that_is_not_eiti_s_list_raises_naming_what_it_found(page: str, found: str) -> None:
    with site(page) as client, pytest.raises(ValueError, match=re.escape(found)):
        fetch(EITI, client, TODAY)


def test_eiti_s_list_page_must_be_utf_8() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, content=EITI_LIST.replace("Example", "Exemplé").encode("latin-1"))

    with httpx2.Client(transport=httpx2.MockTransport(handler)) as client, pytest.raises(UnicodeDecodeError):
        fetch(EITI, client, TODAY)


def test_eiti_s_list_refused_raises_its_status() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(403, content=b"<html><main><h1>Just a moment...</h1></main></html>")

    with (
        httpx2.Client(transport=httpx2.MockTransport(handler)) as client,
        pytest.raises(httpx2.HTTPStatusError, match="403"),
    ):
        fetch(EITI, client, TODAY)


def test_the_fetch_takes_the_reader_of_the_source_s_route() -> None:
    files = {("democracy", "1"): "democracy.json"}
    with replay(files) as client:
        assert fetch(eu("democracy"), client, TODAY) == search_eu(eu("democracy"), client, TODAY)


def test_one_call_per_identifier() -> None:
    files = {("democracy", "1"): "democracy.json", ('"civil society"', "1"): "civil_society.json"}
    with replay(files) as client:
        calls = search_eu(eu("democracy", '"civil society"'), client, TODAY)
    identifiers = [c.identifier for c in calls]
    assert identifiers.count("HORIZON-CL2-2027-01-HERITAGE-06") == 1


def test_each_call_carries_its_title() -> None:
    with replay({("digital", "1"): "digital_page_1.json", ("digital", "2"): "digital_page_2.json"}) as client:
        calls = search_eu(eu("digital"), client, TODAY)
    assert [c.title for c in calls] == [
        "Digital Investigations",
        "Additional activities for the European Partnership of Agriculture of Data",
    ]


def test_closed_calls_are_left_out() -> None:
    files = {("democracy", "1"): "democracy.json", ('"civil society"', "1"): "civil_society.json"}
    with replay(files) as client:
        calls = search_eu(eu("democracy", '"civil society"'), client, dt.date(2027, 9, 23))
    assert sorted(c.identifier for c in calls) == [
        "HORIZON-CL2-2027-01-HERITAGE-06",
        "HORIZON-CL2-2027-02-DEMOCRACY-09-two-stage",
    ]


def test_every_page_is_read() -> None:
    files = {("digital", "1"): "digital_page_1.json", ("digital", "2"): "digital_page_2.json"}
    with replay(files) as client:
        calls = search_eu(eu("digital"), client, TODAY)
    assert [c.identifier for c in calls] == ["ISF-2026-TF2-AG-CYBER-DIGITAL", "HORIZON-CL6-2026-04-GOVERNANCE-01"]
    assert [c.record for c in calls] == [
        json.loads((REPLIES / name).read_bytes())["results"][0] for name in files.values()
    ]


def test_request_is_right() -> None:
    seen: list[httpx2.Request] = []
    with replay({("democracy", "1"): "democracy.json"}, seen) as client:
        search_eu(eu("democracy"), client, TODAY)
    body = seen[0].read()
    assert seen[0].url.params["apiKey"] == "SEDIA"
    assert b'name="query"' in body
    assert b'"type": ["1"]' in body
    assert b'"status": ["31094501", "31094502"]' in body
    assert b'name="languages"' in body
    assert b'["en"]' in body


def test_page_is_kept_whole() -> None:
    link = "https://example.org/calls/one"
    page = (REPLIES / "page.html").read_bytes()

    asked: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        asked.append(str(request.url))
        return httpx2.Response(200, content=page)

    with httpx2.Client(transport=httpx2.MockTransport(handler)) as client:
        fetched = fetch_page(link, client)
    assert fetched == page
    assert asked == [link]


def test_the_client_names_itself_and_waits_thirty_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NO_PROXY", "*")
    with new_client() as client:
        assert (
            client.headers["User-Agent"] == "Fieldbook (https://github.com/civicliteracies/field-monitoring-pipeline)"
        )
        assert client.timeout == httpx2.Timeout(30)
        assert not client.follow_redirects


def test_a_redirect_stops_the_fetch() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(301, headers={"Location": "https://example.org/gone"})

    with httpx2.Client(transport=httpx2.MockTransport(handler)) as client, pytest.raises(httpx2.HTTPStatusError):
        fetch_page("https://example.org/calls/one", client)
