import datetime as dt
import runpy
from pathlib import Path

import httpx2
import pytest
from pydantic import ValidationError

from field_monitoring_pipeline.calls import main, run
from field_monitoring_pipeline.data.extract import ADDRESS
from field_monitoring_pipeline.data.store import code
from tests.samples import (
    CODE,
    FETCHED,
    HERITAGE,
    IDENTIFIER,
    KEY,
    LOG,
    NEXT_DAY,
    NO_CONNECTION,
    NOTE,
    REASON,
    REPLIES,
    REPLY,
    ROOT,
    ROW,
    RUN,
    SOURCE,
    STAMP,
    STATUS,
    TIMEOUT,
    URL,
    WATCH_LIST,
    Answer,
    files,
    log,
    portal,
    raising,
    reply,
)

SECOND = ["", "second", "", "", URL]


def moved(request: httpx2.Request) -> httpx2.Response | None:
    if str(request.url) == HERITAGE:
        return httpx2.Response(301, headers={"Location": "https://example.org/gone"})
    return None


def bad_host(request: httpx2.Request) -> httpx2.Response | None:
    if str(request.url) == HERITAGE:
        "ec..europa.eu".encode("idna")
    return None


def test_a_first_run_saves_every_call_and_a_second_adds_only_its_row(
    tmp_path: Path, watch_list: Path, topic_list: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    asked: list[str] = []

    def watch(request: httpx2.Request) -> None:
        if request.method == "GET":
            asked.append(str(request.url))

    data = tmp_path / "data"
    with portal(watch) as client:
        assert run(data, watch_list, topic_list, client, FETCHED, KEY) == 0
    assert capsys.readouterr().out == (
        "EU Funding and Tenders Portal: 4 calls, 4 new, 0 failed\nRead: 4 calls, 4 cards written, 0 set aside, 0 failed\n"
        "Feed: 4 cards, 0 left out\n"
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
        assert run(data, watch_list, topic_list, client, FETCHED + dt.timedelta(days=1), KEY) == 0
    assert capsys.readouterr().out == (
        "EU Funding and Tenders Portal: 4 calls, 0 new, 0 failed\nRead: 0 calls, 0 cards written, 0 set aside, 0 failed\n"
        "Feed: 4 cards, 0 left out\n"
    )
    assert asked == []
    after = files(data)
    assert {name: held for name, held in after.items() if name != LOG} == {
        name: held for name, held in stored.items() if name != LOG
    }
    assert after[LOG].startswith(stored[LOG])
    assert log(data)[len(rows) :] == [[*RUN, NEXT_DAY, "nothing new", "4 calls, 0 new, 0 failed"]]


def test_closed_calls_are_judged_by_the_time_of_the_run(
    tmp_path: Path, watch_list: Path, topic_list: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with portal() as client:
        assert run(tmp_path / "data", watch_list, topic_list, client, dt.datetime(2023, 9, 1, tzinfo=dt.UTC), KEY) == 0
    assert capsys.readouterr().out == (
        "EU Funding and Tenders Portal: 7 calls, 7 new, 0 failed\nRead: 7 calls, 7 cards written, 0 set aside, 0 failed\n"
        "Feed: 7 cards, 0 left out\n"
    )


def test_a_failed_page_is_logged_and_tried_again(
    tmp_path: Path, watch_list: Path, topic_list: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = tmp_path / "data"
    with portal(moved) as client:
        assert run(data, watch_list, topic_list, client, FETCHED, KEY) == 1
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
        assert run(data, watch_list, topic_list, client, FETCHED, KEY) == 0
    assert capsys.readouterr().out == (
        "EU Funding and Tenders Portal: 4 calls, 1 new, 0 failed\nRead: 1 calls, 1 cards written, 0 set aside, 0 failed\n"
        "Feed: 4 cards, 0 left out\n"
    )
    assert log(data)[-4:] == [
        [*ROW, "saved", ""],
        [*RUN, STAMP, "successful", "4 calls, 1 new, 0 failed"],
        [*ROW, "first answer", REPLY],
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
    tmp_path: Path, watch_list: Path, topic_list: Path, answer: Answer, reason: str
) -> None:
    data = tmp_path / "data"
    for _ in range(2):
        with portal(answer) as client:
            assert run(data, watch_list, topic_list, client, FETCHED, KEY) == 1
    rows = log(data)[1:]
    assert sorted(row[STATUS] for row in rows) == (
        ["card written"] * 3 + ["failed"] * 4 + ["first answer"] * 3 + ["saved"] * 3
    )
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
def test_any_other_error_on_a_page_stops_the_run(
    tmp_path: Path, watch_list: Path, topic_list: Path, error: Exception
) -> None:
    data = tmp_path / "data"
    with portal(raising(error, HERITAGE)) as client, pytest.raises(type(error), match="ours"):
        run(data, watch_list, topic_list, client, FETCHED, KEY)
    assert [row[STATUS] for row in log(data)[1:]] == ["saved"]


def test_a_link_that_cannot_be_read_is_logged(tmp_path: Path, watch_list: Path, topic_list: Path) -> None:
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
        assert run(data, watch_list, topic_list, client, FETCHED, KEY) == 1
    rows = log(data)[1:]
    assert sorted(row[STATUS] for row in rows) == (
        ["card written"] * 3 + ["failed"] * 2 + ["first answer"] * 3 + ["saved"] * 3
    )
    assert [row for row in rows if not row[CODE]] == [[*RUN, STAMP, "failed", "4 calls, 3 new, 1 failed"]]
    failed = next(row for row in rows if row[STATUS] == "failed" and row[CODE])
    assert failed[:STATUS] == [*ROW[:4], HERITAGE + "\n", STAMP]
    assert failed[REASON].startswith("httpx2.InvalidURL: ")


def test_two_sources_are_kept_apart(
    tmp_path: Path, watch_list: Path, topic_list: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = tmp_path / "data"
    with portal(moved) as client:
        assert run(data, watch_list, topic_list, client, FETCHED, KEY) == 1
    capsys.readouterr()
    watch_list.write_text(WATCH_LIST + WATCH_LIST.replace(SOURCE, "second"), encoding="utf-8")
    with portal(moved) as client:
        assert run(data, watch_list, topic_list, client, FETCHED, KEY) == 2
    lines = capsys.readouterr().out.splitlines()
    assert [line for line in lines if line.startswith("EU")] == [
        "EU Funding and Tenders Portal: 4 calls, 0 new, 1 failed",
        "EU Funding and Tenders Portal: 4 calls, 3 new, 1 failed",
    ]
    with portal(moved) as client:
        assert run(data, watch_list, topic_list, client, FETCHED, KEY) == 2
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


def test_each_source_gets_its_own_word_and_numbers(tmp_path: Path, watch_list: Path, topic_list: Path) -> None:
    data = tmp_path / "data"
    with portal() as client:
        assert run(data, watch_list, topic_list, client, FETCHED, KEY) == 0
    watch_list.write_text(WATCH_LIST.replace(SOURCE, "second") + WATCH_LIST, encoding="utf-8")
    with portal(moved) as client:
        assert run(data, watch_list, topic_list, client, FETCHED, KEY) == 1
    assert [row for row in log(data)[1:] if not row[CODE]] == [
        [*RUN, STAMP, "successful", "4 calls, 4 new, 0 failed"],
        [*SECOND, STAMP, "failed", "4 calls, 3 new, 1 failed"],
        [*RUN, STAMP, "nothing new", "4 calls, 0 new, 0 failed"],
    ]


def test_every_failed_call_is_counted_and_printed(
    tmp_path: Path, watch_list: Path, topic_list: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = tmp_path / "data"
    with portal(lambda request: httpx2.Response(301) if request.method == "GET" else None) as client:
        assert run(data, watch_list, topic_list, client, FETCHED, KEY) == 4
    out = capsys.readouterr().out
    assert out.startswith("EU Funding and Tenders Portal: 4 calls, 0 new, 4 failed\n")
    assert out.count(": httpx2.HTTPStatusError: Redirect response '301 Moved Permanently'") == 4
    assert out.endswith("\nRead: 0 calls, 0 cards written, 0 set aside, 0 failed\nFeed: 0 cards, 0 left out\n")
    assert [row[STATUS] for row in log(data)[1:]] == ["failed"] * 5
    assert log(data)[-1] == [*RUN, STAMP, "failed", "4 calls, 0 new, 4 failed"]


@pytest.mark.parametrize("field", ["name", "url", "how", "words"])
def test_a_watch_list_without_a_field_stops_before_any_request(
    tmp_path: Path, watch_list: Path, topic_list: Path, field: str
) -> None:
    asked: list[str] = []
    lines = [line for line in WATCH_LIST.splitlines() if not line.startswith(field)]
    watch_list.write_text("\n".join(lines), encoding="utf-8")
    with portal(lambda request: asked.append(str(request.url))) as client, pytest.raises(ValidationError, match=field):
        run(tmp_path / "data", watch_list, topic_list, client, FETCHED, KEY)
    assert asked == []


def test_the_command_ends_with_a_failure_when_a_call_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[httpx2.Client] = []
    failed = 0

    def new_client() -> httpx2.Client:
        opened.append(portal())
        return opened[-1]

    def stand_in(
        data: Path, watch_list: Path, topics: Path, client: httpx2.Client, fetched: dt.datetime, key: str
    ) -> int:
        assert (data, watch_list, topics, key) == (
            Path("data"),
            Path("config/sources.toml"),
            Path("config/tags.toml"),
            KEY,
        )
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


@pytest.mark.usefixtures("watch_list", "topic_list")
def test_the_file_runs_as_the_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["calls", "data"])
    monkeypatch.setenv("GEMINI_API_KEY", KEY)
    monkeypatch.setattr("field_monitoring_pipeline.data.fetch.new_client", portal)
    runpy.run_path(str(ROOT / "src" / "field_monitoring_pipeline" / "calls.py"), run_name="__main__")
    assert capsys.readouterr().out.startswith("EU Funding and Tenders Portal: ")
