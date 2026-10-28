import datetime as dt
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx2
import pytest

from field_monitoring_pipeline.calls import run
from field_monitoring_pipeline.extract import ADDRESS
from field_monitoring_pipeline.fetch import FetchedCall
from field_monitoring_pipeline.publish import CARDS
from field_monitoring_pipeline.store import code, store
from tests.test_calls import (
    CODE,
    KEY,
    NEXT_DAY,
    NOTE,
    PAGES,
    REASON,
    ROW,
    STATUS,
    STORED,
    Answer,
    files,
    model_answer,
    portal,
)
from tests.test_extract import REPLY
from tests.test_fetch import REPLIES
from tests.test_store import FETCHED, IDENTIFIER, log

WHERE = "where: empty, because the model marked it not stated"
HERITAGE_CARD = f"calls/2026-09-27-future-proofing-sustainable-cultural-tourism-{code(IDENTIFIER)[:10]}.md"
# The four current calls of the recorded replies, in the order the reading takes them: by source, then identifier.
CURRENT = {
    IDENTIFIER: "Future-proofing sustainable cultural tourism",
    "HORIZON-CL2-2027-02-DEMOCRACY-09-two-stage": "Open topic on reinvigorating and shielding European democracy",
    "HORIZON-CL6-2026-04-GOVERNANCE-01": "Additional activities for the European Partnership of Agriculture of Data",
    "ISF-2026-TF2-AG-CYBER-DIGITAL": "Digital Investigations",
}


def reading_of(identifier: str, answer: httpx2.Response) -> Answer:
    def special(request: httpx2.Request) -> httpx2.Response | None:
        if str(request.url) == ADDRESS and f"Title: {CURRENT[identifier]}".encode() in request.read():
            return answer
        return None

    return special


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
    reading_rows = [(row[2], row[STATUS]) for row in rows if row[STATUS] in {"first answer", "card written"}]
    assert reading_rows == [(each, status) for each in CURRENT for status in ("first answer", "card written")]
    assert [row[REASON] for row in rows if row[STATUS] == "first answer"] == [REPLY] * 3 + [no_area]
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
    ("answer", "reason", "answers"),
    [
        pytest.param(
            httpx2.Response(503),
            "httpx2.HTTPStatusError: Server error '503 Service Unavailable'",
            [],
            id="refused",
        ),
        pytest.param(
            model_answer("No command line."),
            "ValueError: first answer: ",
            ["first answer", "second answer"],
            id="unusable twice",
        ),
    ],
)
def test_a_reading_that_fails_is_logged_counted_and_read_again_the_next_run(
    tmp_path: Path,
    watch_list: Path,
    capsys: pytest.CaptureFixture[str],
    answer: httpx2.Response,
    reason: str,
    answers: list[str],
) -> None:
    data = tmp_path / "data"
    with portal(reading_of(IDENTIFIER, answer)) as client:
        assert run(data, watch_list, client, FETCHED, KEY) == 1
    out = capsys.readouterr().out
    assert "\nRead: 4 calls, 3 cards written, 1 failed\n" in out
    [failed] = [row for row in log(data) if row[CODE] and row[STATUS] == "failed"]
    assert failed[:STATUS] == ROW
    assert failed[REASON].startswith(reason)
    assert [row[STATUS] for row in log(data) if row[2] == IDENTIFIER] == ["saved", *answers, "failed"]
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
    assert log(data)[-1][STATUS] == "first answer"


def test_the_calls_are_read_by_source_then_identifier(tmp_path: Path, watch_list: Path) -> None:
    data = tmp_path / "data"
    record = json.loads((REPLIES / "stored_call.json").read_bytes())
    own, title = STORED["identifier"][0], STORED["title"][0]
    # Saved first, under a source that sorts after the portal's, with an identifier that sorts before the portal's calls.
    store(data, "zz-source", FetchedCall(own, PAGES + own, title, record), b"", FETCHED)
    with portal() as client:
        assert run(data, watch_list, client, FETCHED, KEY) == 0
    assert [row[2] for row in log(data) if row[STATUS] == "card written"] == [*CURRENT, own]


def test_a_reply_with_no_content_leaves_its_empty_answer_row_before_the_run_stops(
    tmp_path: Path, watch_list: Path
) -> None:
    data = tmp_path / "data"
    democracy = "HORIZON-CL2-2027-02-DEMOCRACY-09-two-stage"
    no_content = httpx2.Response(200, json={"choices": [{"message": {"content": None}}]})
    # A reply with no text cannot be judged, so the run stops there, as before; its empty answer row is already written.
    with portal(reading_of(democracy, no_content)) as client, pytest.raises(AttributeError):
        run(data, watch_list, client, FETCHED, KEY)
    rows = log(data)
    assert [row[STATUS] for row in rows if row[2] == democracy] == ["saved", "first answer"]
    assert rows[-1][2] == democracy
    assert rows[-1][STATUS] == "first answer"
    assert rows[-1][REASON] == ""
    assert "feed.xml" not in files(data)
