"""A held document's reading: each case of its two tries, and the log rows that let it stop and go on.

The document is the recorded EITI call page, read once more for reports.
"""

import datetime as dt
from pathlib import Path

import httpx2
import pytest

from field_monitoring_pipeline.data.extract import held_text
from field_monitoring_pipeline.data.models import Quoted, Report, Topic
from field_monitoring_pipeline.data.reading import AGAIN_LINES, Found, read
from field_monitoring_pipeline.data.reports import HELD, prepare_held
from field_monitoring_pipeline.data.store import (
    AnswerWord,
    Saved,
    earlier,
    found_item,
    held_read,
    store_answer,
    store_held,
    store_held_answer,
)
from tests.samples import (
    BOARD,
    FOUND_ACCOUNTS,
    FOUND_NOTES,
    FOUND_STUDY,
    INVENTED,
    MISQUOTED,
    MISS_1,
    NO_LINE,
    NONE,
    NOTHING_READ,
    OFFER,
    STUDY_TITLE,
    VIEWS,
    found_line,
    keeping,
    log,
    model,
)

TEXT = held_text(OFFER)
UNREADABLE = found_line("A novel", kind="novel")
UNREAD_2 = (
    "line 2: type: Input should be 'project results report', 'evaluation', 'annual report' or 'research or case study'"
)
NOT_FOUND = f"organisation: this sentence was not found in the document it was found in: {INVENTED}"
DOCUMENT = Saved("eiti", VIEWS, "A call", VIEWS, dt.date(2026, 9, 27))
FOUND = (Topic(name="extractives-eiti", mark="primary"),)
FETCHED = dt.datetime(2026, 11, 30, 20, 17, tzinfo=dt.UTC)


def held(*answers: str | httpx2.Response, before: tuple[str, ...] = ()) -> tuple[list[Found[Report]], list[str], int]:
    seen: list[httpx2.Request] = []
    kept: list[tuple[AnswerWord, int, str]] = []
    with model(*answers, seen=seen) as client:
        found, notes = read(prepare_held(TEXT, before), "the key", client, keeping(kept, seen))
    # Each answer asked for is handed on once, as it arrives, and an answer the log holds is never handed on again.
    assert [word for word, _, _ in kept] == ["first answer", "second answer"][len(before) : len(before) + len(seen)]
    return found, notes, len(seen)


def titles(found: list[Found[Report]]) -> list[str]:
    return [each.subject.title for each in found]


def test_a_held_call_s_text_is_its_page_s_words_without_its_tags() -> None:
    assert BOARD in TEXT
    assert "<" not in TEXT


def test_a_first_answer_with_every_line_read_and_every_sentence_found_is_kept_with_one_request() -> None:
    found, notes, asked = held(f"{FOUND_STUDY}\n{FOUND_ACCOUNTS}")
    assert titles(found) == [STUDY_TITLE, "Annual accounts"]
    assert (notes, asked) == ([], 1)
    assert [each.notes for each in found] == [FOUND_NOTES, FOUND_NOTES]


def test_the_one_line_none_alone_means_no_item_and_is_kept_with_one_request() -> None:
    assert held(NONE) == ([], [], 1)


def test_a_sentence_not_found_goes_back_once_and_the_second_try_asks_for_every_line_again() -> None:
    seen: list[httpx2.Request] = []
    with model(MISQUOTED, FOUND_STUDY, seen=seen) as client:
        found, notes = read(prepare_held(TEXT, ()), "the key", client, lambda word, answer: None)
    assert seen[1].read().decode().count("Write every command line again") == 1
    assert AGAIN_LINES.startswith("This answer cannot be used as it is. Write every command line again")
    assert notes == [f"first answer: {MISS_1}"]
    assert [each.notes for each in found] == [FOUND_NOTES]


def test_a_sentence_still_not_found_stays_on_its_item_marked_with_a_note_on_that_item_alone() -> None:
    found, notes, asked = held(f"{MISQUOTED}\n{FOUND_ACCOUNTS}", f"{MISQUOTED}\n{FOUND_ACCOUNTS}")
    assert asked == 2
    assert notes == [f"first answer: {MISS_1}", f"second answer: {MISS_1}"]
    assert [each.notes for each in found] == [[NOT_FOUND, *FOUND_NOTES], FOUND_NOTES]
    record = found[0].record(found_item(DOCUMENT, "reports", 1, found[0].subject.title, DOCUMENT.day), FOUND)
    assert record.organisation == Quoted(value="EITI Board", quote=INVENTED, found=False)


def test_a_first_answer_read_whole_is_kept_when_the_second_has_a_line_that_cannot_be_read() -> None:
    found, notes, asked = held(f"{MISQUOTED}\n{FOUND_ACCOUNTS}", f"{FOUND_STUDY}\n{UNREADABLE}")
    assert asked == 2
    assert titles(found) == [STUDY_TITLE, "Annual accounts"]
    assert notes == [f"first answer: {MISS_1}", f"second answer: {UNREAD_2}"]
    assert found[0].notes[0] == NOT_FOUND


@pytest.mark.parametrize(
    ("second", "problems"),
    [
        pytest.param(f"{FOUND_STUDY}\n{FOUND_ACCOUNTS}", [], id="every sentence found"),
        pytest.param(f"{MISQUOTED}\n{FOUND_ACCOUNTS}", [f"second answer: {MISS_1}"], id="a sentence not found"),
    ],
)
def test_a_second_answer_read_whole_is_kept_when_the_first_had_a_line_that_cannot_be_read(
    second: str, problems: list[str]
) -> None:
    found, notes, asked = held(f"{FOUND_STUDY}\n{UNREADABLE}", second)
    assert (titles(found), asked) == ([STUDY_TITLE, "Annual accounts"], 2)
    assert notes == [f"first answer: {UNREAD_2}", *problems]


def test_one_unreadable_line_in_each_answer_does_not_fail_the_other_items() -> None:
    found, notes, asked = held(f"{FOUND_ACCOUNTS}\n{UNREADABLE}", f"{FOUND_STUDY}\n{UNREADABLE}")
    assert asked == 2
    assert titles(found) == [STUDY_TITLE]
    assert notes == [f"first answer: {UNREAD_2}", f"second answer: {UNREAD_2}"]


def test_a_found_item_s_order_is_its_line_s_number_in_the_answer() -> None:
    found, notes, _ = held(f"{UNREADABLE}\n{FOUND_STUDY}", f"{UNREADABLE}\n{FOUND_STUDY}")
    assert [each.order for each in found] == [2]
    assert notes[1] == "second answer: " + UNREAD_2.replace("line 2", "line 1")


@pytest.mark.parametrize(
    ("second", "kept", "problems"),
    [
        pytest.param(f"{FOUND_STUDY}\n{FOUND_ACCOUNTS}", [STUDY_TITLE, "Annual accounts"], [], id="read whole"),
        pytest.param(MISQUOTED, [STUDY_TITLE], [f"second answer: {MISS_1}"], id="a sentence not found"),
        pytest.param(f"{FOUND_STUDY}\n{UNREADABLE}", [STUDY_TITLE], [f"second answer: {UNREAD_2}"], id="a line lost"),
    ],
)
def test_a_second_answer_is_kept_when_the_first_cannot_be_read_at_all(
    second: str, kept: list[str], problems: list[str]
) -> None:
    found, notes, asked = held(NO_LINE, second)
    assert (titles(found), asked) == (kept, 2)
    assert notes == [f"first answer: {NOTHING_READ}", *problems]


@pytest.mark.parametrize(
    ("first", "kept", "problem"),
    [
        pytest.param(MISQUOTED, [STUDY_TITLE], MISS_1, id="a sentence not found"),
        pytest.param(f"{FOUND_ACCOUNTS}\n{UNREADABLE}", ["Annual accounts"], UNREAD_2, id="a line that cannot be read"),
    ],
)
def test_a_first_answer_that_reads_is_kept_when_the_second_cannot_be_read_at_all(
    first: str, kept: list[str], problem: str
) -> None:
    found, notes, asked = held(first, NO_LINE)
    assert (titles(found), asked) == (kept, 2)
    assert notes == [f"first answer: {problem}", f"second answer: {NOTHING_READ}"]


@pytest.mark.parametrize(
    ("answer", "problem"),
    [
        pytest.param(NO_LINE, NOTHING_READ, id="no command line"),
        pytest.param(UNREADABLE, UNREAD_2.replace("line 2", "line 1"), id="no line that can be read"),
    ],
)
def test_only_two_answers_that_cannot_be_read_at_all_fail_the_reading(answer: str, problem: str) -> None:
    with pytest.raises(ValueError, match="first answer") as caught:
        held(answer, answer)
    assert str(caught.value) == f"first answer: {problem}; second answer: {problem}"


def test_a_second_request_turned_away_fails_the_reading_and_names_the_first_answer_s_problems() -> None:
    with pytest.raises(httpx2.HTTPStatusError) as caught:
        held(MISQUOTED, httpx2.Response(429))
    assert caught.value.__notes__ == [f"first answer: {MISS_1}"]


def test_a_first_request_turned_away_fails_the_reading_with_no_answer_kept() -> None:
    with pytest.raises(httpx2.HTTPStatusError) as caught:
        held(httpx2.Response(429))
    assert not hasattr(caught.value, "__notes__")


def test_none_beside_another_line_is_a_line_that_cannot_be_read_and_the_other_line_stands() -> None:
    found, notes, asked = held(f"{FOUND_STUDY}\n{NONE}", f"{FOUND_STUDY}\n{NONE}")
    assert (titles(found), asked) == ([STUDY_TITLE], 2)
    assert notes == [
        f"{word}: line 2: --none is not a flag the instructions offer" for word in ("first answer", "second answer")
    ]


def test_a_line_with_no_title_cannot_be_read() -> None:
    found, notes, _ = held(f"{FOUND_STUDY}\n{FOUND_STUDY.replace(f'--title "{STUDY_TITLE}" ', '')}", FOUND_STUDY)
    assert titles(found) == [STUDY_TITLE]
    assert notes == ["first answer: line 2: --title must give the report's title"]


def test_a_stopped_reading_s_first_answer_stands_in_place_of_a_request() -> None:
    found, notes, asked = held(before=(f"{FOUND_STUDY}\n{FOUND_ACCOUNTS}",))
    assert (titles(found), notes, asked) == ([STUDY_TITLE, "Annual accounts"], [], 0)
    found, notes, asked = held(FOUND_STUDY, before=(MISQUOTED,))
    assert (titles(found), notes, asked) == ([STUDY_TITLE], [f"first answer: {MISS_1}"], 1)


def test_a_stopped_reading_s_two_answers_stand_in_place_of_both_requests() -> None:
    found, notes, asked = held(before=(MISQUOTED, f"{FOUND_STUDY}\n{UNREADABLE}"))
    assert (titles(found), asked) == ([STUDY_TITLE], 0)
    assert notes == [f"first answer: {MISS_1}", f"second answer: {UNREAD_2}"]


def test_a_found_item_s_record_is_made_once_it_has_its_topics_and_names_its_document() -> None:
    [found], _, _ = held(FOUND_STUDY)
    saved = found_item(DOCUMENT, "reports", 1, found.subject.title, dt.date(2026, 11, 30))
    assert saved.identifier == f"{VIEWS}#reports-1"
    record = found.record(saved, FOUND)
    assert record.topics == FOUND
    assert (record.title, record.type, record.instructions, record.published) == (STUDY_TITLE, "evaluation", HELD, None)
    assert (record.identifier, record.link) == (saved.identifier, DOCUMENT.link)
    assert (found.subject.other_titles, found.subject.body) == ((), BOARD)


def test_a_held_document_s_rows_name_the_kind_and_its_own_rows_are_never_taken_for_them(tmp_path: Path) -> None:
    store_answer(tmp_path, DOCUMENT, FETCHED, "first answer", "its own reading")
    store_held_answer(tmp_path, "reports", DOCUMENT, FETCHED, "first answer", "one")
    store_held_answer(tmp_path, "reports", DOCUMENT, FETCHED, "second answer", "two")
    assert earlier(tmp_path, "reports", DOCUMENT) == ("one", "two")
    assert held_read(tmp_path, "reports") == set()
    store_held(tmp_path, "reports", DOCUMENT, FETCHED, "read", "1 found")
    assert held_read(tmp_path, "reports") == {(DOCUMENT.source, DOCUMENT.identifier)}
    statuses = [row[6] for row in log(tmp_path)[1:]]
    assert statuses == ["first answer", "first answer for reports", "second answer for reports", "read for reports"]


def test_a_failed_reading_leaves_no_answer_for_the_next_run(tmp_path: Path) -> None:
    store_held_answer(tmp_path, "reports", DOCUMENT, FETCHED, "first answer", "one")
    store_held(tmp_path, "reports", DOCUMENT, FETCHED, "failed", "turned away")
    assert earlier(tmp_path, "reports", DOCUMENT) == ()
    store_held_answer(tmp_path, "reports", DOCUMENT, FETCHED, "first answer", "again")
    assert earlier(tmp_path, "reports", DOCUMENT) == ("again",)
