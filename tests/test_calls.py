import datetime as dt
import json
import runpy
import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2
import pytest

from field_monitoring_pipeline.calls import main, run
from field_monitoring_pipeline.extract import ADDRESS
from field_monitoring_pipeline.fetch import FetchedCall
from field_monitoring_pipeline.publish import CARDS
from field_monitoring_pipeline.store import COLUMNS, code, store
from tests.test_extract import REPLY
from tests.test_fetch import REPLIES, ROOT, URL
from tests.test_store import FETCHED, IDENTIFIER, SOURCE, STAMP, log

SEARCHES = {
    ("democracy", "1"): "democracy.json",
    ('"civil society"', "1"): "civil_society.json",
    ("digital", "1"): "digital_page_1.json",
    ("digital", "2"): "digital_page_2.json",
}
WATCH_LIST = f"""[[source]]
id = "{SOURCE}"
name = "EU Funding and Tenders Portal"
url = "{URL}"
words = ["democracy", '"civil society"', "digital"]
"""
PAGES = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/"
HERITAGE = PAGES + IDENTIFIER
ROW = [code(IDENTIFIER), SOURCE, IDENTIFIER, "Future-proofing sustainable cultural tourism", HERITAGE, STAMP]
CODE, STATUS, REASON = COLUMNS.index("code"), COLUMNS.index("status"), COLUMNS.index("reason")
SEARCH = f"{URL}&text=democracy&pageSize=100&pageNumber=1"
RUN = ["", SOURCE, "", "", URL]
SECOND = ["", "second", "", "", URL]
NEXT_DAY = "2026-09-28T06:00:00+00:00"
LOG = "raw/log.csv"
SERVER_ERROR = (
    f"httpx2.HTTPStatusError: Server error '500 Internal Server Error' for url '{SEARCH}'\n"
    "For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/500"
)
TIMEOUT = "httpx2.ReadTimeout: The read operation timed out"
NO_CONNECTION = "httpx2.ConnectError: All connection attempts failed"
KEY = "the key"
NOTE = "funder: empty, because the model marked it not stated"
WHERE = "where: empty, because the model marked it not stated"
HERITAGE_CARD = f"calls/2026-09-27-future-proofing-sustainable-cultural-tourism-{code(IDENTIFIER)[:10]}.md"
# The four current calls of the recorded replies, in the order the reading takes them: by source, then identifier.
CURRENT = {
    IDENTIFIER: "Future-proofing sustainable cultural tourism",
    "HORIZON-CL2-2027-02-DEMOCRACY-09-two-stage": "Open topic on reinvigorating and shielding European democracy",
    "HORIZON-CL6-2026-04-GOVERNANCE-01": "Additional activities for the European Partnership of Agriculture of Data",
    "ISF-2026-TF2-AG-CYBER-DIGITAL": "Digital Investigations",
}
STORED = json.loads((REPLIES / "stored_call.json").read_bytes())["metadata"]
OWN = STORED["identifier"][0] + " "

type Answer = Callable[[httpx2.Request], httpx2.Response | None]


def reply(request: httpx2.Request) -> dict[str, Any]:
    name = SEARCHES[request.url.params["text"], request.url.params["pageNumber"]]
    body = json.loads((REPLIES / name).read_bytes())
    # Each recorded call takes the fields the reading uses from the stored call, and the budget line takes its identifier.
    for record in body["results"]:
        metadata = record["metadata"]
        metadata |= {field: STORED[field] for field in ("startDate", "descriptionByte", "topicConditions")}
        metadata["budgetOverview"] = [STORED["budgetOverview"][0].replace(OWN, metadata["identifier"][0] + " ")]
    return body


def model_answer(content: str) -> httpx2.Response:
    return httpx2.Response(200, json={"choices": [{"message": {"content": content}}]})


def portal(special: Answer | None = None) -> httpx2.Client:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if special is not None and (answer := special(request)) is not None:
            return answer
        if str(request.url) == ADDRESS:
            # The model service answers only the key the tests hand to the run.
            if request.headers["Authorization"] != f"Bearer {KEY}":
                return httpx2.Response(401)
            return model_answer(REPLY)
        if request.method == "POST":
            return httpx2.Response(200, json=reply(request))
        return httpx2.Response(200, content=(REPLIES / "page.html").read_bytes())

    return httpx2.Client(transport=httpx2.MockTransport(handler))


def raising(error: Exception, link: str | None = None) -> Answer:
    def answer(request: httpx2.Request) -> httpx2.Response | None:
        if link is None or str(request.url) == link:
            raise error
        return None

    return answer


def moved(request: httpx2.Request) -> httpx2.Response | None:
    if str(request.url) == HERITAGE:
        return httpx2.Response(301, headers={"Location": "https://example.org/gone"})
    return None


def bad_host(request: httpx2.Request) -> httpx2.Response | None:
    if str(request.url) == HERITAGE:
        "ec..europa.eu".encode("idna")
    return None


def server_error(request: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(500)


def reading_of(identifier: str, answer: httpx2.Response) -> Answer:
    def special(request: httpx2.Request) -> httpx2.Response | None:
        if str(request.url) == ADDRESS and f"Title: {CURRENT[identifier]}".encode() in request.read():
            return answer
        return None

    return special


def files(data: Path) -> dict[str, bytes]:
    return {path.relative_to(data).as_posix(): path.read_bytes() for path in data.rglob("*") if path.is_file()}


@pytest.fixture
def watch_list(tmp_path: Path) -> Path:
    path = tmp_path / "config" / "sources.toml"
    path.parent.mkdir()
    path.write_text(WATCH_LIST, encoding="utf-8")
    return path


def test_a_first_run_saves_every_call_and_a_second_adds_only_its_row(
    tmp_path: Path, watch_list: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    asked: list[str] = []

    def watch(request: httpx2.Request) -> None:
        if request.method == "GET":
            asked.append(str(request.url))

    data = tmp_path / "data"
    with portal(watch) as client:
        assert run(data, watch_list, client, FETCHED, KEY) == 0
    assert capsys.readouterr().out == (
        "EU Funding and Tenders Portal: 4 calls, 4 new, 0 failed\nRead: 4 calls, 4 cards written, 0 failed\n"
    )
    assert len(asked) == 4
    stored = files(data)
    assert len(stored) == 14
    assert stored[f"raw/{SOURCE}/{code(IDENTIFIER)}.html"] == (REPLIES / "page.html").read_bytes()
    rows = log(data)
    assert [*ROW, "saved", ""] in rows
    assert [row for row in rows if not row[CODE]] == [[*RUN, STAMP, "successful", "4 calls, 4 new, 0 failed"]]

    asked.clear()
    with portal(watch) as client:
        assert run(data, watch_list, client, FETCHED + dt.timedelta(days=1), KEY) == 0
    assert capsys.readouterr().out == (
        "EU Funding and Tenders Portal: 4 calls, 0 new, 0 failed\nRead: 0 calls, 0 cards written, 0 failed\n"
    )
    assert asked == []
    after = files(data)
    assert {name: held for name, held in after.items() if name != LOG} == {
        name: held for name, held in stored.items() if name != LOG
    }
    assert after[LOG].startswith(stored[LOG])
    assert log(data)[len(rows) :] == [[*RUN, NEXT_DAY, "nothing new", "4 calls, 0 new, 0 failed"]]


def test_each_saved_call_without_a_card_is_read_once_and_in_order(tmp_path: Path, watch_list: Path) -> None:
    read: list[bytes] = []
    no_area = REPLY.split(' --area "Europe"')[0] + " --area-not-stated"
    last = reading_of("ISF-2026-TF2-AG-CYBER-DIGITAL", model_answer(no_area))

    def watch(request: httpx2.Request) -> httpx2.Response | None:
        if str(request.url) == ADDRESS:
            read.append(request.read())
        return last(request)

    data = tmp_path / "data"
    with portal(watch) as client:
        assert run(data, watch_list, client, FETCHED, KEY) == 0
    assert len(read) == 4
    assert all(f"Title: {title}".encode() in body for title, body in zip(CURRENT.values(), read, strict=True))
    rows = log(data)
    assert [row[2] for row in rows if row[STATUS] == "card written"] == list(CURRENT)
    assert [row[REASON] for row in rows if row[STATUS] == "card written"] == [NOTE] * 3 + [f"{NOTE}; {WHERE}"]
    cards = sorted(name for name in files(data) if name.startswith("calls/"))
    assert cards == [
        "calls/2026-09-27-additional-activities-for-the-european-partnership-of-bec3f00136.md",
        "calls/2026-09-27-digital-investigations-36827741b5.md",
        "calls/2026-09-27-future-proofing-sustainable-cultural-tourism-b710c74df0.md",
        "calls/2026-09-27-open-topic-on-reinvigorating-and-shielding-european-7e9df70773.md",
    ]


def test_the_feed_is_built_from_every_card_after_the_reading(tmp_path: Path, watch_list: Path) -> None:
    data = tmp_path / "data"
    with portal() as client:
        assert run(data, watch_list, client, FETCHED, KEY) == 0
    cards = sorted(name for name in files(data) if name.startswith("calls/"))
    built = files(data)["feed.xml"]
    entries = ET.fromstring(built).findall("channel/item")
    assert [entry.findtext("link") for entry in entries] == [CARDS + name for name in cards]
    assert len(cards) == 4
    (data / "feed.xml").unlink()
    with portal() as client:
        assert run(data, watch_list, client, FETCHED + dt.timedelta(days=1), KEY) == 0
    assert files(data)["feed.xml"] == built


@pytest.mark.parametrize(
    ("answer", "reason"),
    [
        pytest.param(
            httpx2.Response(503), "httpx2.HTTPStatusError: Server error '503 Service Unavailable'", id="refused"
        ),
        pytest.param(model_answer("No command line."), "ValueError: first answer: ", id="unusable twice"),
    ],
)
def test_a_reading_that_fails_is_logged_counted_and_read_again_the_next_run(
    tmp_path: Path, watch_list: Path, capsys: pytest.CaptureFixture[str], answer: httpx2.Response, reason: str
) -> None:
    data = tmp_path / "data"
    with portal(reading_of(IDENTIFIER, answer)) as client:
        assert run(data, watch_list, client, FETCHED, KEY) == 1
    out = capsys.readouterr().out
    assert "\nRead: 4 calls, 3 cards written, 1 failed\n" in out
    [failed] = [row for row in log(data) if row[CODE] and row[STATUS] == "failed"]
    assert failed[:STATUS] == ROW
    assert failed[REASON].startswith(reason)
    assert f"{IDENTIFIER}: {failed[REASON]}\n" in out
    assert not any(name.endswith(f"{code(IDENTIFIER)[:10]}.md") for name in files(data))
    assert len(ET.fromstring(files(data)["feed.xml"]).findall("channel/item")) == 3

    with portal() as client:
        assert run(data, watch_list, client, FETCHED + dt.timedelta(days=1), KEY) == 0
    assert capsys.readouterr().out.endswith("\nRead: 1 calls, 1 cards written, 0 failed\n")
    assert log(data)[-1] == [*ROW[:5], NEXT_DAY, "card written", NOTE]
    assert HERITAGE_CARD in files(data)


def test_any_other_error_in_a_reading_stops_the_run_and_keeps_what_was_written(
    tmp_path: Path, watch_list: Path
) -> None:
    data = tmp_path / "data"
    no_choices = httpx2.Response(200, json={"choices": []})
    with (
        portal(reading_of("HORIZON-CL2-2027-02-DEMOCRACY-09-two-stage", no_choices)) as client,
        pytest.raises(IndexError),
    ):
        run(data, watch_list, client, FETCHED, KEY)
    rows = log(data)
    assert [row[2] for row in rows if row[STATUS] == "card written"] == [IDENTIFIER]
    assert [name for name in files(data) if name.startswith("calls/")] == [HERITAGE_CARD]
    assert rows[-1][2] == IDENTIFIER
    assert "feed.xml" not in files(data)


def test_a_morning_with_no_key_saves_every_call_and_fails_every_reading(
    tmp_path: Path, watch_list: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = tmp_path / "data"
    with portal() as client:
        assert run(data, watch_list, client, FETCHED, "") == 4
    assert "\nRead: 4 calls, 0 cards written, 4 failed\n" in capsys.readouterr().out
    assert [row[STATUS] for row in log(data)[1:] if row[CODE]] == ["saved"] * 4 + ["failed"] * 4
    assert not any(name.startswith("calls/") for name in files(data))


def test_a_card_that_cannot_be_written_stops_the_run_before_its_row(tmp_path: Path, watch_list: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    (data / "calls").write_bytes(b"")
    with portal() as client, pytest.raises(FileExistsError):
        run(data, watch_list, client, FETCHED, KEY)
    assert [row for row in log(data) if row[STATUS] == "card written"] == []


def test_the_calls_are_read_by_source_then_identifier(tmp_path: Path, watch_list: Path) -> None:
    data = tmp_path / "data"
    record = json.loads((REPLIES / "stored_call.json").read_bytes())
    own, title = STORED["identifier"][0], STORED["title"][0]
    # Saved first, under a source that sorts after the portal's, with an identifier that sorts before the portal's calls.
    store(data, "zz-source", FetchedCall(own, PAGES + own, title, record), b"", FETCHED)
    with portal() as client:
        assert run(data, watch_list, client, FETCHED, KEY) == 0
    assert [row[2] for row in log(data) if row[STATUS] == "card written"] == [*CURRENT, own]


def test_closed_calls_are_judged_by_the_time_of_the_run(
    tmp_path: Path, watch_list: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with portal() as client:
        assert run(tmp_path / "data", watch_list, client, dt.datetime(2023, 9, 1, tzinfo=dt.UTC), KEY) == 0
    assert capsys.readouterr().out == (
        "EU Funding and Tenders Portal: 7 calls, 7 new, 0 failed\nRead: 7 calls, 7 cards written, 0 failed\n"
    )


def test_a_failed_page_is_logged_and_tried_again(
    tmp_path: Path, watch_list: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = tmp_path / "data"
    with portal(moved) as client:
        assert run(data, watch_list, client, FETCHED, KEY) == 1
    failed = [row for row in log(data) if row[STATUS] == "failed"]
    assert len(failed) == 2
    assert failed[0][:STATUS] == ROW
    assert failed[1] == [*RUN, STAMP, "failed", "4 calls, 3 new, 1 failed"]
    assert failed[0][REASON].startswith("httpx2.HTTPStatusError: Redirect response '301 Moved Permanently'")
    assert len(files(data)) == 11
    out = capsys.readouterr().out
    assert out.startswith("EU Funding and Tenders Portal: 4 calls, 3 new, 1 failed\n")
    assert f"{IDENTIFIER}: {failed[0][REASON]}\n" in out

    with portal() as client:
        assert run(data, watch_list, client, FETCHED, KEY) == 0
    assert capsys.readouterr().out == (
        "EU Funding and Tenders Portal: 4 calls, 1 new, 0 failed\nRead: 1 calls, 1 cards written, 0 failed\n"
    )
    assert log(data)[-3:] == [
        [*ROW, "saved", ""],
        [*RUN, STAMP, "successful", "4 calls, 1 new, 0 failed"],
        [*ROW, "card written", NOTE],
    ]
    assert len(files(data)) == 14


@pytest.mark.parametrize(
    ("answer", "reason"),
    [
        pytest.param(raising(httpx2.ReadTimeout("The read operation timed out"), HERITAGE), TIMEOUT, id="timeout"),
        pytest.param(
            raising(httpx2.ConnectError("All connection attempts failed"), HERITAGE), NO_CONNECTION, id="no connection"
        ),
        pytest.param(bad_host, "UnicodeEncodeError: 'idna' codec can't encode character", id="bad host"),
    ],
)
def test_a_page_that_cannot_be_downloaded_is_logged_on_every_run(
    tmp_path: Path, watch_list: Path, answer: Answer, reason: str
) -> None:
    data = tmp_path / "data"
    for _ in range(2):
        with portal(answer) as client:
            assert run(data, watch_list, client, FETCHED, KEY) == 1
    rows = log(data)[1:]
    assert sorted(row[STATUS] for row in rows) == ["card written"] * 3 + ["failed"] * 4 + ["saved"] * 3
    tried = [row for row in rows if row[STATUS] == "failed" and row[CODE]]
    assert len(tried) == 2
    assert all(row[:STATUS] == ROW and row[REASON].startswith(reason) for row in tried)
    assert [row for row in rows if not row[CODE]] == [
        [*RUN, STAMP, "failed", "4 calls, 3 new, 1 failed"],
        [*RUN, STAMP, "failed", "4 calls, 0 new, 1 failed"],
    ]


@pytest.mark.parametrize(
    "error",
    [ValueError("ours"), UnicodeDecodeError("utf-8", b"\xff", 0, 1, "ours"), OSError("ours")],
    ids=["a value", "a decoding", "the system"],
)
def test_any_other_error_on_a_page_stops_the_run(tmp_path: Path, watch_list: Path, error: Exception) -> None:
    data = tmp_path / "data"
    with portal(raising(error, HERITAGE)) as client, pytest.raises(type(error), match="ours"):
        run(data, watch_list, client, FETCHED, KEY)
    assert [row[STATUS] for row in log(data)[1:]] == ["saved"]


def test_a_link_that_cannot_be_read_is_logged(tmp_path: Path, watch_list: Path) -> None:
    def broken_link(request: httpx2.Request) -> httpx2.Response | None:
        if request.method != "POST" or str(request.url) == ADDRESS:
            return None
        body = reply(request)
        for record in body["results"]:
            if record["metadata"]["url"][0] == HERITAGE:
                record["metadata"]["url"][0] += "\n"
        return httpx2.Response(200, json=body)

    data = tmp_path / "data"
    with portal(broken_link) as client:
        assert run(data, watch_list, client, FETCHED, KEY) == 1
    rows = log(data)[1:]
    assert sorted(row[STATUS] for row in rows) == ["card written"] * 3 + ["failed"] * 2 + ["saved"] * 3
    assert [row for row in rows if not row[CODE]] == [[*RUN, STAMP, "failed", "4 calls, 3 new, 1 failed"]]
    failed = next(row for row in rows if row[STATUS] == "failed" and row[CODE])
    assert failed[:STATUS] == [*ROW[:4], HERITAGE + "\n", STAMP]
    assert failed[REASON].startswith("httpx2.InvalidURL: ")


def test_two_sources_are_kept_apart(tmp_path: Path, watch_list: Path, capsys: pytest.CaptureFixture[str]) -> None:
    data = tmp_path / "data"
    with portal(moved) as client:
        assert run(data, watch_list, client, FETCHED, KEY) == 1
    capsys.readouterr()
    watch_list.write_text(WATCH_LIST + WATCH_LIST.replace(SOURCE, "second"), encoding="utf-8")
    with portal(moved) as client:
        assert run(data, watch_list, client, FETCHED, KEY) == 2
    lines = capsys.readouterr().out.splitlines()
    assert [line for line in lines if line.startswith("EU")] == [
        "EU Funding and Tenders Portal: 4 calls, 0 new, 1 failed",
        "EU Funding and Tenders Portal: 4 calls, 3 new, 1 failed",
    ]
    with portal(moved) as client:
        assert run(data, watch_list, client, FETCHED, KEY) == 2
    lines = capsys.readouterr().out.splitlines()
    assert [line for line in lines if line.startswith("EU")] == [
        "EU Funding and Tenders Portal: 4 calls, 0 new, 1 failed"
    ] * 2
    assert len(files(data)) == 17
    assert [row for row in log(data)[1:] if not row[CODE]] == [
        [*RUN, STAMP, "failed", "4 calls, 3 new, 1 failed"],
        [*RUN, STAMP, "failed", "4 calls, 0 new, 1 failed"],
        [*SECOND, STAMP, "failed", "4 calls, 3 new, 1 failed"],
        [*RUN, STAMP, "failed", "4 calls, 0 new, 1 failed"],
        [*SECOND, STAMP, "failed", "4 calls, 0 new, 1 failed"],
    ]


def test_each_source_gets_its_own_word_and_numbers(tmp_path: Path, watch_list: Path) -> None:
    data = tmp_path / "data"
    with portal() as client:
        assert run(data, watch_list, client, FETCHED, KEY) == 0
    watch_list.write_text(WATCH_LIST.replace(SOURCE, "second") + WATCH_LIST, encoding="utf-8")
    with portal(moved) as client:
        assert run(data, watch_list, client, FETCHED, KEY) == 1
    assert [row for row in log(data)[1:] if not row[CODE]] == [
        [*RUN, STAMP, "successful", "4 calls, 4 new, 0 failed"],
        [*SECOND, STAMP, "failed", "4 calls, 3 new, 1 failed"],
        [*RUN, STAMP, "nothing new", "4 calls, 0 new, 0 failed"],
    ]


def test_every_failed_call_is_counted_and_printed(
    tmp_path: Path, watch_list: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = tmp_path / "data"
    with portal(lambda request: httpx2.Response(301) if request.method == "GET" else None) as client:
        assert run(data, watch_list, client, FETCHED, KEY) == 4
    out = capsys.readouterr().out
    assert out.startswith("EU Funding and Tenders Portal: 4 calls, 0 new, 4 failed\n")
    assert out.count(": httpx2.HTTPStatusError: Redirect response '301 Moved Permanently'") == 4
    assert out.endswith("\nRead: 0 calls, 0 cards written, 0 failed\n")
    assert [row[STATUS] for row in log(data)[1:]] == ["failed"] * 5
    assert log(data)[-1] == [*RUN, STAMP, "failed", "4 calls, 0 new, 4 failed"]


@pytest.mark.parametrize("field", ["id", "name", "url", "words"])
def test_a_watch_list_without_a_field_stops_before_any_request(tmp_path: Path, watch_list: Path, field: str) -> None:
    asked: list[str] = []
    lines = [line for line in WATCH_LIST.splitlines() if not line.startswith(field)]
    watch_list.write_text("\n".join(lines), encoding="utf-8")
    with portal(lambda request: asked.append(str(request.url))) as client, pytest.raises(KeyError, match=field):
        run(tmp_path / "data", watch_list, client, FETCHED, KEY)
    assert asked == []


@pytest.mark.parametrize(
    ("answer", "raised", "reason"),
    [
        pytest.param(server_error, httpx2.HTTPStatusError, SERVER_ERROR, id="error status"),
        pytest.param(
            raising(httpx2.ConnectError("All connection attempts failed")),
            httpx2.ConnectError,
            NO_CONNECTION,
            id="no connection",
        ),
        pytest.param(
            raising(httpx2.ReadTimeout("The read operation timed out")), httpx2.ReadTimeout, TIMEOUT, id="timeout"
        ),
    ],
)
def test_a_failed_search_is_logged_and_stops_the_run(
    tmp_path: Path, watch_list: Path, answer: Answer, raised: type[httpx2.HTTPError], reason: str
) -> None:
    data = tmp_path / "data"
    with portal(answer) as client, pytest.raises(raised):
        run(data, watch_list, client, FETCHED, KEY)
    assert log(data) == [list(COLUMNS), ["", SOURCE, "", "", SEARCH, STAMP, "failed", reason]]
    assert list(files(data)) == [LOG]
    assert not (data / "raw" / SOURCE).exists()


@pytest.mark.parametrize(
    ("content", "raised", "reason"),
    [
        pytest.param(
            b"<html>maintenance</html>", json.JSONDecodeError, "json.decoder.JSONDecodeError: ", id="not JSON"
        ),
        pytest.param(
            "<html>fermé</html>".encode("latin-1"), UnicodeDecodeError, "UnicodeDecodeError: ", id="not UTF-8"
        ),
    ],
)
def test_a_search_reply_that_is_not_json_is_logged(
    tmp_path: Path, watch_list: Path, content: bytes, raised: type[Exception], reason: str
) -> None:
    data = tmp_path / "data"
    with portal(lambda request: httpx2.Response(200, content=content)) as client, pytest.raises(raised):
        run(data, watch_list, client, FETCHED, KEY)
    header, row = log(data)
    assert header == list(COLUMNS)
    assert row[:REASON] == [*RUN, STAMP, "failed"]
    assert row[REASON].startswith(reason)


def test_a_reply_the_fetch_cannot_read_is_not_a_failed_search(tmp_path: Path, watch_list: Path) -> None:
    def no_dates(request: httpx2.Request) -> httpx2.Response:
        body = reply(request)
        body["results"][0]["metadata"]["deadlineDate"] = []
        return httpx2.Response(200, json=body)

    data = tmp_path / "data"
    with portal(no_dates) as client, pytest.raises(ValueError, match="empty"):
        run(data, watch_list, client, FETCHED, KEY)
    assert files(data) == {}


def test_the_command_ends_with_a_failure_when_a_call_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[httpx2.Client] = []
    failed = 0

    def new_client() -> httpx2.Client:
        opened.append(portal())
        return opened[-1]

    def stand_in(data: Path, watch_list: Path, client: httpx2.Client, fetched: dt.datetime, key: str) -> int:
        assert (data, watch_list, key) == (Path("data"), Path("config/sources.toml"), KEY)
        assert client is opened[-1]
        assert (fetched.tzinfo, fetched.microsecond) == (dt.UTC, 0)
        assert abs(dt.datetime.now(dt.UTC) - fetched) < dt.timedelta(minutes=1)
        return failed

    monkeypatch.setattr("sys.argv", ["calls", "data"])
    monkeypatch.setenv("GEMINI_API_KEY", KEY)
    monkeypatch.setattr("field_monitoring_pipeline.calls.new_client", new_client)
    monkeypatch.setattr("field_monitoring_pipeline.calls.run", stand_in)
    for failed in (1, 2):
        with pytest.raises(SystemExit) as caught:
            main()
        assert caught.value.code == 1
    failed = 0
    main()
    assert [client.is_closed for client in opened] == [True, True, True]


@pytest.mark.usefixtures("watch_list")
def test_the_file_runs_as_the_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["calls", "data"])
    monkeypatch.setenv("GEMINI_API_KEY", KEY)
    monkeypatch.setattr("field_monitoring_pipeline.fetch.new_client", portal)
    runpy.run_path(str(ROOT / "src" / "field_monitoring_pipeline" / "calls.py"), run_name="__main__")
    assert capsys.readouterr().out.startswith("EU Funding and Tenders Portal: ")
