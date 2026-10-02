import datetime as dt
import json
import tomllib
from pathlib import Path

import httpx2
import pytest

from field_monitoring_pipeline.fetch import fetch, fetch_page, new_client

ROOT = Path(__file__).parent.parent
REPLIES = Path(__file__).parent / "replies"
URL = "https://api.tech.ec.europa.eu/search-api/prod/rest/search?apiKey=SEDIA"
TODAY = dt.date(2026, 9, 27)


def replay(files: dict[tuple[str, str], str], seen: list[httpx2.Request] | None = None) -> httpx2.Client:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if seen is not None:
            seen.append(request)
        name = files[request.url.params["text"], request.url.params["pageNumber"]]
        return httpx2.Response(200, content=(REPLIES / name).read_bytes())

    return httpx2.Client(transport=httpx2.MockTransport(handler))


def test_watch_list_shape() -> None:
    source = tomllib.loads((ROOT / "config" / "sources.toml").read_text(encoding="utf-8"))["source"][0]
    assert source["id"]
    assert source["name"]
    assert source["url"]
    assert source["words"]


def test_one_call_per_identifier() -> None:
    files = {("democracy", "1"): "democracy.json", ('"civil society"', "1"): "civil_society.json"}
    with replay(files) as client:
        calls = fetch(URL, ["democracy", '"civil society"'], client, TODAY)
    identifiers = [c.identifier for c in calls]
    assert identifiers.count("HORIZON-CL2-2027-01-HERITAGE-06") == 1


def test_each_call_carries_its_title() -> None:
    with replay({("digital", "1"): "digital_page_1.json", ("digital", "2"): "digital_page_2.json"}) as client:
        calls = fetch(URL, ["digital"], client, TODAY)
    assert [c.title for c in calls] == [
        "Digital Investigations",
        "Additional activities for the European Partnership of Agriculture of Data",
    ]


def test_closed_calls_are_left_out() -> None:
    files = {("democracy", "1"): "democracy.json", ('"civil society"', "1"): "civil_society.json"}
    with replay(files) as client:
        calls = fetch(URL, ["democracy", '"civil society"'], client, dt.date(2027, 9, 23))
    assert sorted(c.identifier for c in calls) == [
        "HORIZON-CL2-2027-01-HERITAGE-06",
        "HORIZON-CL2-2027-02-DEMOCRACY-09-two-stage",
    ]


def test_every_page_is_read() -> None:
    files = {("digital", "1"): "digital_page_1.json", ("digital", "2"): "digital_page_2.json"}
    with replay(files) as client:
        calls = fetch(URL, ["digital"], client, TODAY)
    assert [c.identifier for c in calls] == ["ISF-2026-TF2-AG-CYBER-DIGITAL", "HORIZON-CL6-2026-04-GOVERNANCE-01"]
    assert [c.record for c in calls] == [
        json.loads((REPLIES / name).read_bytes())["results"][0] for name in files.values()
    ]


def test_request_is_right() -> None:
    seen: list[httpx2.Request] = []
    with replay({("democracy", "1"): "democracy.json"}, seen) as client:
        fetch(URL, ["democracy"], client, TODAY)
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
