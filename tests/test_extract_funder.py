import pytest

from field_monitoring_pipeline.extract import build, text
from field_monitoring_pipeline.models import Named
from field_monitoring_pipeline.write import card, read_card
from tests.test_extract import AGAIN, FUNDER, LINE, REPLY, reading, stored
from tests.test_tags import TOPICS

FOUND = "Horizon Europe"
GONE = "European Commission"
EMPTY = "funder: empty, because the model's answer gave no name"


def test_the_stored_test_call_holds_the_found_name_and_not_the_missing_one() -> None:
    # The tests below rest on this: the text the model reads, with its spacing tidied as the check tidies it.
    words = " ".join(text(stored()).split())
    assert FOUND in words
    assert GONE not in words


def test_a_funder_named_as_in_the_text_is_found_and_the_card_has_no_warning() -> None:
    call, notes = build(stored(), TOPICS, f'{LINE} --funder "{FOUND}"')
    assert call.funder == Named(name=FOUND, found=True)
    assert not any(note.startswith("funder:") for note in notes)
    assert "This name was not found in the call." not in card(call)


def test_a_funder_not_in_the_text_is_kept_marked_with_a_warning_and_a_note() -> None:
    call, notes = build(stored(), TOPICS, f'{LINE} --funder "{GONE}"')
    assert call.funder == Named(name=GONE, found=False)
    assert notes[0] == f"funder: this name was not found in the call: {GONE}"


@pytest.mark.parametrize(
    ("line", "note"),
    [
        (LINE + " --funder-not-stated", "funder: empty, because the model marked it not stated"),
        (LINE, "funder: empty, because the model's answer did not mention it"),
    ],
)
def test_an_empty_funder_by_the_answer_keeps_its_note(line: str, note: str) -> None:
    call, notes = build(stored(), TOPICS, line)
    assert call.funder is None
    assert notes[0] == note


@pytest.mark.parametrize("given", ['""', '"   "', r'" \t\n "', "null"])
def test_an_empty_or_null_name_is_not_stated_with_its_note_and_no_second_request(given: str) -> None:
    call, notes, asked = reading(REPLY.replace("--funder-not-stated", f"--funder {given}"))
    assert call.funder is None
    assert notes == [EMPTY]
    assert len(asked) == 1
    assert "\n\nFunder: not stated\n\n" in card(call)


@pytest.mark.parametrize("given", ["-", "2027"])
def test_a_text_with_no_letter_becomes_a_name_with_its_mark(given: str) -> None:
    call, _ = build(stored(), TOPICS, f'{LINE} --funder "{given}"')
    assert call.funder == Named(name=given, found=True)


@pytest.mark.parametrize("name", [FOUND, GONE])
def test_a_card_with_a_funder_reads_back_to_the_same_record(name: str) -> None:
    call, _ = build(stored(), TOPICS, f'{LINE} --funder "{name}"')
    assert read_card(card(call)) == call


def test_the_name_is_matched_after_the_same_tidying_as_a_sentence() -> None:
    spaced = r"  Horizon \n  Europe "
    call, _ = build(stored(), TOPICS, f'{LINE} --funder "{spaced}"')
    assert call.funder == Named(name="  Horizon \n  Europe ", found=True)


def test_a_name_not_found_alone_causes_no_second_request() -> None:
    call, notes, asked = reading(REPLY.replace("--funder-not-stated", f'--funder "{GONE}"'))
    assert len(asked) == 1
    assert call.funder == Named(name=GONE, found=False)
    assert notes == [f"funder: this name was not found in the call: {GONE}"]


PROBLEM = "funder.name: Input should be a valid string"
NOT_TEXT = ["5", "true", "[]", '{"name": "Horizon Europe", "found": true}']


@pytest.mark.parametrize("given", NOT_TEXT)
def test_a_funder_that_is_not_text_is_not_used_and_asked_once_more(given: str) -> None:
    call, notes, asked = reading(REPLY.replace("--funder-not-stated", f"--funder {given}"), REPLY)
    assert asked[1][-1]["content"] == f"{AGAIN}\n{PROBLEM}"
    assert notes == [f"first answer: {PROBLEM}", FUNDER]
    assert call.funder is None


@pytest.mark.parametrize("given", NOT_TEXT)
def test_a_funder_not_text_twice_fails_the_reading_without_stopping_the_run(given: str) -> None:
    bad = REPLY.replace("--funder-not-stated", f"--funder {given}")
    with pytest.raises(ValueError) as caught:
        reading(bad, bad)
    assert str(caught.value) == f"first answer: {PROBLEM}; second answer: {PROBLEM}"
