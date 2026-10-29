import xml.etree.ElementTree as ET
from pathlib import Path

import httpx2
import pytest

from field_monitoring_pipeline.calls import run
from field_monitoring_pipeline.store import COLUMNS
from tests.test_calls import (
    CODE,
    EITI_ENTRY,
    EITI_RUN,
    EITI_TOPICS,
    KEY,
    LOG,
    NO_CONNECTION,
    REASON,
    RUN,
    SEARCH,
    SERVER_ERROR,
    STATUS,
    TIMEOUT,
    WATCH_LIST,
    Answer,
    eiti,
    files,
    portal,
    raising,
    reply,
    server_error,
)
from tests.test_fetch import REPLIES, STUDY
from tests.test_store import FETCHED, SOURCE, STAMP, log


@pytest.mark.parametrize(
    ("answer", "reason"),
    [
        pytest.param(server_error, SERVER_ERROR, id="error status"),
        pytest.param(raising(httpx2.ConnectError("All connection attempts failed")), NO_CONNECTION, id="no connection"),
        pytest.param(raising(httpx2.ReadTimeout("The read operation timed out")), TIMEOUT, id="timeout"),
    ],
)
def test_a_failed_search_is_the_source_s_failed_run_and_the_run_carries_on(
    tmp_path: Path, watch_list: Path, topic_list: Path, capsys: pytest.CaptureFixture[str], answer: Answer, reason: str
) -> None:
    data = tmp_path / "data"
    with portal(answer) as client:
        assert run(data, watch_list, topic_list, client, FETCHED, KEY) == 1
    assert log(data) == [list(COLUMNS), ["", SOURCE, "", "", SEARCH, STAMP, "failed", reason]]
    assert sorted(files(data)) == ["feed.xml", LOG]
    assert capsys.readouterr().out == (
        f"EU Funding and Tenders Portal: {reason}\nRead: 0 calls, 0 cards written, 0 failed\n"
    )


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        pytest.param(b"<html>maintenance</html>", "json.decoder.JSONDecodeError: ", id="not JSON"),
        pytest.param("<html>fermé</html>".encode("latin-1"), "UnicodeDecodeError: ", id="not UTF-8"),
    ],
)
def test_a_search_reply_that_is_not_json_is_the_source_s_failed_run(
    tmp_path: Path, watch_list: Path, topic_list: Path, content: bytes, reason: str
) -> None:
    data = tmp_path / "data"
    with portal(lambda request: httpx2.Response(200, content=content)) as client:
        assert run(data, watch_list, topic_list, client, FETCHED, KEY) == 1
    header, row = log(data)
    assert header == list(COLUMNS)
    assert row[:REASON] == [*RUN, STAMP, "failed"]
    assert row[REASON].startswith(reason)


def test_a_reply_the_fetch_cannot_read_is_the_source_s_failed_run(
    tmp_path: Path, watch_list: Path, topic_list: Path
) -> None:
    def no_dates(request: httpx2.Request) -> httpx2.Response:
        body = reply(request)
        body["results"][0]["metadata"]["deadlineDate"] = []
        return httpx2.Response(200, json=body)

    data = tmp_path / "data"
    with portal(no_dates) as client:
        assert run(data, watch_list, topic_list, client, FETCHED, KEY) == 1
    [row] = log(data)[1:]
    assert row[:REASON] == [*RUN, STAMP, "failed"]
    assert row[REASON].startswith("ValueError: ")


def test_after_a_failed_search_the_next_source_is_searched_and_the_saved_calls_are_read(
    tmp_path: Path, watch_list: Path, topic_list: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def broken(request: httpx2.Request) -> httpx2.Response | None:
        return httpx2.Response(500) if request.url.host == "example.org" else None

    watch_list.write_text(
        WATCH_LIST.replace(SOURCE, "broken").replace("api.tech.ec.europa.eu", "example.org") + WATCH_LIST,
        encoding="utf-8",
    )
    data = tmp_path / "data"
    with portal(broken) as client:
        assert run(data, watch_list, topic_list, client, FETCHED, KEY) == 1
    out = capsys.readouterr().out
    assert out.startswith("EU Funding and Tenders Portal: httpx2.HTTPStatusError: Server error '500 ")
    assert out.endswith(
        "EU Funding and Tenders Portal: 4 calls, 4 new, 0 failed\nRead: 4 calls, 4 cards written, 0 failed\n"
    )
    assert [(row[1], row[STATUS]) for row in log(data)[1:] if not row[CODE]] == [
        ("broken", "failed"),
        (SOURCE, "successful"),
    ]
    assert len(ET.fromstring(files(data)["feed.xml"]).findall("channel/item")) == 4


def test_a_second_source_whose_reply_lacks_a_field_stops_the_run_after_the_first_source_s_row(
    tmp_path: Path, watch_list: Path, topic_list: Path
) -> None:
    def no_results(request: httpx2.Request) -> httpx2.Response | None:
        return httpx2.Response(200, json={"totalResults": 0}) if request.url.host == "example.org" else None

    watch_list.write_text(
        WATCH_LIST + WATCH_LIST.replace(SOURCE, "second").replace("api.tech.ec.europa.eu", "example.org"),
        encoding="utf-8",
    )
    data = tmp_path / "data"
    with portal(no_results) as client, pytest.raises(KeyError, match="results"):
        run(data, watch_list, topic_list, client, FETCHED, KEY)
    assert [(row[1], row[STATUS]) for row in log(data)[1:] if not row[CODE]] == [(SOURCE, "successful")]
    assert "feed.xml" not in files(data)


def test_eiti_s_link_that_cannot_be_read_fails_only_its_call(
    tmp_path: Path, watch_list: Path, topic_list: Path
) -> None:
    listing = (REPLIES / "eiti_list.html").read_bytes()
    broken = listing.replace(b'href="/offers/example-consultancy"', b'href="/offers/example-consultancy\n"')
    watch_list.write_text(WATCH_LIST + EITI_ENTRY, encoding="utf-8")
    topic_list.write_text(EITI_TOPICS, encoding="utf-8")
    data = tmp_path / "data"
    with portal(eiti(broken)) as client:
        assert run(data, watch_list, topic_list, client, FETCHED, KEY) == 1
    [failed] = [row for row in log(data) if row[CODE] and row[STATUS] == "failed"]
    assert failed[2] == STUDY + "\n"
    assert failed[REASON].startswith("httpx2.InvalidURL: ")
    assert [*EITI_RUN, "failed", "2 calls, 1 new, 1 failed"] in log(data)


def test_a_page_in_place_of_eiti_s_list_is_eiti_s_failed_run(
    tmp_path: Path, watch_list: Path, topic_list: Path
) -> None:
    watch_list.write_text(WATCH_LIST + EITI_ENTRY, encoding="utf-8")
    topic_list.write_text(EITI_TOPICS, encoding="utf-8")
    data = tmp_path / "data"
    with portal(eiti(b"<html><main><h1>Just a moment...</h1></main></html>")) as client:
        assert run(data, watch_list, topic_list, client, FETCHED, KEY) == 1
    assert [*EITI_RUN, "failed", "ValueError: the page must hold exactly one list of current calls; it holds 0"] in (
        log(data)
    )
    assert len([row for row in log(data) if row[STATUS] == "card written"]) == 4


def test_eiti_s_list_refused_is_eiti_s_failed_run_with_its_status(
    tmp_path: Path, watch_list: Path, topic_list: Path
) -> None:
    def refused(request: httpx2.Request) -> httpx2.Response | None:
        if request.url.host == "eiti.org":
            return httpx2.Response(403, content=b"<html><main><h1>Just a moment...</h1></main></html>")
        return None

    watch_list.write_text(WATCH_LIST + EITI_ENTRY, encoding="utf-8")
    topic_list.write_text(EITI_TOPICS, encoding="utf-8")
    data = tmp_path / "data"
    with portal(refused) as client:
        assert run(data, watch_list, topic_list, client, FETCHED, KEY) == 1
    [row] = [row for row in log(data) if row[1] == "eiti"]
    assert row[:REASON] == [*EITI_RUN, "failed"]
    assert row[REASON].startswith("httpx2.HTTPStatusError: Client error '403 Forbidden'")
    assert len([row for row in log(data) if row[STATUS] == "card written"]) == 4
    assert len(ET.fromstring(files(data)["feed.xml"]).findall("channel/item")) == 4


def test_a_topic_a_source_names_missing_from_the_topic_list_stops_the_run_after_the_calls_are_saved(
    tmp_path: Path, watch_list: Path, topic_list: Path
) -> None:
    watch_list.write_text(WATCH_LIST + EITI_ENTRY, encoding="utf-8")
    data = tmp_path / "data"
    listing = (REPLIES / "eiti_list.html").read_bytes()
    with portal(eiti(listing)) as client, pytest.raises(ValueError, match="extractives-eiti"):
        run(data, watch_list, topic_list, client, FETCHED, KEY)
    assert [row[STATUS] for row in log(data)[1:] if row[CODE]] == ["saved"] * 6
    assert not any(name.startswith("calls/") for name in files(data))
    assert "feed.xml" not in files(data)
