import datetime as dt
import json
import runpy
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2
import pytest

from field_monitoring_pipeline.calls import main, run
from field_monitoring_pipeline.store import COLUMNS, code
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
STATUS, REASON = COLUMNS.index("status"), COLUMNS.index("reason")
SEARCH = f"{URL}&text=democracy&pageSize=100&pageNumber=1"
SERVER_ERROR = (
    f"httpx2.HTTPStatusError: Server error '500 Internal Server Error' for url '{SEARCH}'\n"
    "For more information check: https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/500"
)
TIMEOUT = "httpx2.ReadTimeout: The read operation timed out"
NO_CONNECTION = "httpx2.ConnectError: All connection attempts failed"

type Answer = Callable[[httpx2.Request], httpx2.Response | None]


def reply(request: httpx2.Request) -> dict[str, Any]:
    name = SEARCHES[request.url.params["text"], request.url.params["pageNumber"]]
    return json.loads((REPLIES / name).read_bytes())


def portal(special: Answer | None = None) -> httpx2.Client:
    def handler(request: httpx2.Request) -> httpx2.Response:
        if special is not None and (answer := special(request)) is not None:
            return answer
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


def files(data: Path) -> dict[str, bytes]:
    return {path.relative_to(data).as_posix(): path.read_bytes() for path in data.rglob("*") if path.is_file()}


@pytest.fixture
def watch_list(tmp_path: Path) -> Path:
    path = tmp_path / "config" / "sources.toml"
    path.parent.mkdir()
    path.write_text(WATCH_LIST, encoding="utf-8")
    return path


def test_a_first_run_saves_every_call_and_a_second_changes_nothing(
    tmp_path: Path, watch_list: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    asked: list[str] = []

    def watch(request: httpx2.Request) -> None:
        if request.method == "GET":
            asked.append(str(request.url))

    data = tmp_path / "data"
    with portal(watch) as client:
        assert run(data, watch_list, client, FETCHED) == 0
    assert capsys.readouterr().out == "EU Funding and Tenders Portal: 4 calls, 4 new, 0 failed\n"
    assert len(asked) == 4
    stored = files(data)
    assert len(stored) == 9
    assert stored[f"raw/{SOURCE}/{code(IDENTIFIER)}.html"] == (REPLIES / "page.html").read_bytes()
    assert [*ROW, "saved", ""] in log(data)

    asked.clear()
    with portal(watch) as client:
        assert run(data, watch_list, client, FETCHED + dt.timedelta(days=1)) == 0
    assert capsys.readouterr().out == "EU Funding and Tenders Portal: 4 calls, 0 new, 0 failed\n"
    assert asked == []
    assert files(data) == stored


def test_closed_calls_are_judged_by_the_time_of_the_run(
    tmp_path: Path, watch_list: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with portal() as client:
        assert run(tmp_path / "data", watch_list, client, dt.datetime(2023, 9, 1, tzinfo=dt.UTC)) == 0
    assert capsys.readouterr().out == "EU Funding and Tenders Portal: 7 calls, 7 new, 0 failed\n"


def test_a_failed_page_is_logged_and_tried_again(
    tmp_path: Path, watch_list: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = tmp_path / "data"
    with portal(moved) as client:
        assert run(data, watch_list, client, FETCHED) == 1
    failed = [row for row in log(data) if row[STATUS] == "failed"]
    assert len(failed) == 1
    assert failed[0][:STATUS] == ROW
    assert failed[0][REASON].startswith("httpx2.HTTPStatusError: Redirect response '301 Moved Permanently'")
    assert len(files(data)) == 7
    out = capsys.readouterr().out
    assert out.startswith("EU Funding and Tenders Portal: 4 calls, 3 new, 1 failed\n")
    assert f"{IDENTIFIER}: {failed[0][REASON]}\n" in out

    with portal() as client:
        assert run(data, watch_list, client, FETCHED) == 0
    assert capsys.readouterr().out == "EU Funding and Tenders Portal: 4 calls, 1 new, 0 failed\n"
    assert log(data)[-1] == [*ROW, "saved", ""]
    assert len(files(data)) == 9


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
            assert run(data, watch_list, client, FETCHED) == 1
    rows = log(data)[1:]
    assert sorted(row[STATUS] for row in rows) == ["failed", "failed", "saved", "saved", "saved"]
    assert all(row[:STATUS] == ROW and row[REASON].startswith(reason) for row in rows if row[STATUS] == "failed")


@pytest.mark.parametrize(
    "error",
    [ValueError("ours"), UnicodeDecodeError("utf-8", b"\xff", 0, 1, "ours"), OSError("ours")],
    ids=["a value", "a decoding", "the system"],
)
def test_any_other_error_on_a_page_stops_the_run(tmp_path: Path, watch_list: Path, error: Exception) -> None:
    data = tmp_path / "data"
    with portal(raising(error, HERITAGE)) as client, pytest.raises(type(error), match="ours"):
        run(data, watch_list, client, FETCHED)
    assert [row[STATUS] for row in log(data)[1:]] == ["saved"]


def test_a_link_that_cannot_be_read_is_logged(tmp_path: Path, watch_list: Path) -> None:
    def broken_link(request: httpx2.Request) -> httpx2.Response | None:
        if request.method != "POST":
            return None
        body = reply(request)
        for record in body["results"]:
            if record["metadata"]["url"][0] == HERITAGE:
                record["metadata"]["url"][0] += "\n"
        return httpx2.Response(200, json=body)

    data = tmp_path / "data"
    with portal(broken_link) as client:
        assert run(data, watch_list, client, FETCHED) == 1
    rows = log(data)[1:]
    assert sorted(row[STATUS] for row in rows) == ["failed", "saved", "saved", "saved"]
    failed = next(row for row in rows if row[STATUS] == "failed")
    assert failed[:STATUS] == [*ROW[:4], HERITAGE + "\n", STAMP]
    assert failed[REASON].startswith("httpx2.InvalidURL: ")


def test_two_sources_are_kept_apart(tmp_path: Path, watch_list: Path, capsys: pytest.CaptureFixture[str]) -> None:
    data = tmp_path / "data"
    with portal(moved) as client:
        assert run(data, watch_list, client, FETCHED) == 1
    capsys.readouterr()
    watch_list.write_text(WATCH_LIST + WATCH_LIST.replace(SOURCE, "second"), encoding="utf-8")
    with portal(moved) as client:
        assert run(data, watch_list, client, FETCHED) == 2
    lines = capsys.readouterr().out.splitlines()
    assert [line for line in lines if line.startswith("EU")] == [
        "EU Funding and Tenders Portal: 4 calls, 0 new, 1 failed",
        "EU Funding and Tenders Portal: 4 calls, 3 new, 1 failed",
    ]
    with portal(moved) as client:
        assert run(data, watch_list, client, FETCHED) == 2
    lines = capsys.readouterr().out.splitlines()
    assert [line for line in lines if line.startswith("EU")] == [
        "EU Funding and Tenders Portal: 4 calls, 0 new, 1 failed"
    ] * 2
    assert len(files(data)) == 13


def test_every_failed_call_is_counted_and_printed(
    tmp_path: Path, watch_list: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = tmp_path / "data"
    with portal(lambda request: httpx2.Response(301) if request.method == "GET" else None) as client:
        assert run(data, watch_list, client, FETCHED) == 4
    out = capsys.readouterr().out
    assert out.startswith("EU Funding and Tenders Portal: 4 calls, 0 new, 4 failed\n")
    assert out.count(": httpx2.HTTPStatusError: Redirect response '301 Moved Permanently'") == 4
    assert [row[STATUS] for row in log(data)[1:]] == ["failed"] * 4


@pytest.mark.parametrize("field", ["id", "name", "url", "words"])
def test_a_watch_list_without_a_field_stops_before_any_request(tmp_path: Path, watch_list: Path, field: str) -> None:
    asked: list[str] = []
    lines = [line for line in WATCH_LIST.splitlines() if not line.startswith(field)]
    watch_list.write_text("\n".join(lines), encoding="utf-8")
    with portal(lambda request: asked.append(str(request.url))) as client, pytest.raises(KeyError, match=field):
        run(tmp_path / "data", watch_list, client, FETCHED)
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
        run(data, watch_list, client, FETCHED)
    assert log(data) == [list(COLUMNS), ["", SOURCE, "", "", SEARCH, STAMP, "failed", reason]]
    assert list(files(data)) == ["raw/log.csv"]
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
        run(data, watch_list, client, FETCHED)
    header, row = log(data)
    assert header == list(COLUMNS)
    assert row[:REASON] == ["", SOURCE, "", "", URL, STAMP, "failed"]
    assert row[REASON].startswith(reason)


def test_a_reply_the_fetch_cannot_read_is_not_a_failed_search(tmp_path: Path, watch_list: Path) -> None:
    def no_dates(request: httpx2.Request) -> httpx2.Response:
        body = reply(request)
        body["results"][0]["metadata"]["deadlineDate"] = []
        return httpx2.Response(200, json=body)

    data = tmp_path / "data"
    with portal(no_dates) as client, pytest.raises(ValueError, match="empty"):
        run(data, watch_list, client, FETCHED)
    assert files(data) == {}


def test_the_command_ends_with_a_failure_when_a_call_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[httpx2.Client] = []
    failed = 0

    def new_client() -> httpx2.Client:
        opened.append(portal())
        return opened[-1]

    def stand_in(data: Path, watch_list: Path, client: httpx2.Client, fetched: dt.datetime) -> int:
        assert (data, watch_list) == (Path("data"), Path("config/sources.toml"))
        assert client is opened[-1]
        assert (fetched.tzinfo, fetched.microsecond) == (dt.UTC, 0)
        assert abs(dt.datetime.now(dt.UTC) - fetched) < dt.timedelta(minutes=1)
        return failed

    monkeypatch.setattr("sys.argv", ["calls", "data"])
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
    monkeypatch.setattr("field_monitoring_pipeline.fetch.new_client", portal)
    runpy.run_path(str(ROOT / "src" / "field_monitoring_pipeline" / "calls.py"), run_name="__main__")
    assert capsys.readouterr().out.startswith("EU Funding and Tenders Portal: ")
