import datetime as dt
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2
import pytest

from field_monitoring_pipeline.extract import build, read, text
from field_monitoring_pipeline.models import Call, Deadline, Quoted, Topic, TopicList
from field_monitoring_pipeline.store import AnswerWord, Saved
from tests.test_fetch import VIEWS
from tests.test_tags import TOPICS

ROOT = Path(__file__).parent.parent
REPLIES = Path(__file__).parent / "replies"
INSTRUCTIONS = (ROOT / "src" / "field_monitoring_pipeline" / "instructions" / "v3.md").read_text(encoding="utf-8")
REPLY = (REPLIES / "model_reply.txt").read_text(encoding="utf-8")
GUIDE = "See the information in the Horizon Europe Programme Guide."
CONSUMPTION = "Users’ consumption patterns of news are identified (online and offline)."
LINE = f'fieldbook --type grant --summary "Funds news media." --summary-quote "{GUIDE}"'
# The recorded reply with words dropped from the middle of its summary's sentence.
DROPPED = REPLY.replace("sectors at European level are addressed", "sectors are addressed")
AGAIN = "This answer cannot be used as it is. Write the one command line again, with each problem below put right:"
MISSED = "--summary-quote: the sentence must be in the text word for word"
FUNDER = "funder: empty, because the model marked it not stated"
DAY = dt.date(2026, 9, 27)
EU = Saved("eu-funding-tenders", "HORIZON-CL2-2027-01-DEMOCRACY-06", "Not read from here", "https://e.org", DAY)
EITI_CALL = Saved("eiti", VIEWS, "Example 2027 EITI Validation: call for views on stakeholder engagement", VIEWS, DAY)
OFFER = (REPLIES / "eiti_offer.html").read_bytes()
BOARD = "The EITI Board asks for views on how stakeholders take part in EITI implementation in the example country."
EITI_REPLY = (
    f'fieldbook --type other --funder "EITI Board" --summary "Asks for views." --summary-quote "{BOARD}" '
    "--eligibility-not-stated --area-not-stated"
)
EXTRACTIVES = TopicList.model_validate({"topics": {"extractives-eiti": {"mark": "primary"}}})


def stored(deadlines: list[str] | None = None, shared: int = 1, **own: Any) -> Any:
    record = json.loads((REPLIES / "stored_call.json").read_bytes())
    metadata = record["metadata"]
    if deadlines is not None:
        metadata["deadlineDate"] = deadlines
    budget = json.loads(metadata["budgetOverview"][0])
    for lines in budget["budgetTopicActionMap"].values():
        if lines[0]["action"].startswith("HORIZON-CL2-2027-01-DEMOCRACY-06 "):
            lines[0].update(own)
            lines += [lines[0] | {"action": f"OTHER-TOPIC-{n} - Research"} for n in range(1, shared)]
    metadata["budgetOverview"] = [json.dumps(budget)]
    return record


def model(*answers: str | httpx2.Response, seen: list[httpx2.Request]) -> httpx2.Client:
    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        answer = answers[len(seen) - 1]
        if isinstance(answer, httpx2.Response):
            return answer
        return httpx2.Response(200, json={"choices": [{"message": {"content": answer}}]})

    return httpx2.Client(transport=httpx2.MockTransport(handler))


def keeping(kept: list[tuple[AnswerWord, int, str]], seen: list[httpx2.Request]) -> Callable[[AnswerWord, str], None]:
    # Each answer is kept with its word and how many requests had been sent when it was handed on.
    return lambda word, answer: kept.append((word, len(seen), answer))


def reading(*answers: str) -> tuple[Call, list[str], list[Any]]:
    seen: list[httpx2.Request] = []
    with model(*answers, seen=seen) as client:
        call, notes = read(EU, stored(), TOPICS, (), "the key", client, keeping([], seen))
    return call, notes, [json.loads(request.read())["messages"] for request in seen]


def test_a_recorded_reply_becomes_a_record_with_every_sentence_found() -> None:
    assert build(stored(), TOPICS, REPLY) == (
        Call.model_validate({
            "title": "Identifying user-focused solutions to support news media freedom",
            "type": "grant",
            "funder": None,
            "opening": {"date": "2027-05-13", "quote": "Opening date: 2027-05-13", "found": True},
            "deadline": {"date": "2027-09-23", "quote": "Deadline: 2027-09-23", "found": True},
            "budget": {
                "value": "12 000 000 € (each winning project: 3 500 000 € to 4 000 000 €)",
                "quote": (
                    "Budget 2027: 12 000 000 € (each winning project: 3 500 000 € to 4 000 000 €); "
                    "winning projects expected: 3"
                ),
                "found": True,
            },
            "summary": {
                "value": (
                    "Grants to address data gaps and develop innovative models that support news media freedom and "
                    "independence."
                ),
                "quote": (
                    "Key data gaps affecting the news media sectors at European level are addressed and all relevant "
                    "stakeholders dispose of an updated and comprehensive knowledge base."
                ),
                "found": True,
            },
            "eligibility": {
                "value": "academia, civil society organisations and news sectors representatives forming consortia",
                "quote": (
                    "Consortia should: bring together academia (including from SSH disciplines), civil society "
                    "organisations and multiple news sectors representatives (including influencers and other "
                    "content creators); where applicable, leverage the data and services available through European "
                    "Research Infrastructures federated under the European Open Science Cloud (EOSC), as well as "
                    "data from relevant Data Spaces"
                ),
                "found": True,
            },
            "area": {
                "value": "Europe",
                "quote": (
                    "There are still important quantitative and qualitative data gaps at European level that can "
                    "help the news media sectors address these concerns, including accurate diagnoses of the "
                    "challenges and opportunities for the news sectors."
                ),
                "found": True,
            },
            "topics": [
                {"name": "AI-and-civic", "mark": "primary"},
                {"name": "data-journalism", "mark": "secondary"},
            ],
            "link": (
                "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/"
                "HORIZON-CL2-2027-01-DEMOCRACY-06"
            ),
            "identifier": "HORIZON-CL2-2027-01-DEMOCRACY-06",
            "model": "gemini-3.5-flash-lite",
            "instructions": "v3",
        }),
        [FUNDER],
    )


@pytest.mark.parametrize(
    ("line", "reason"),
    [
        (LINE, "the model's answer did not mention it"),
        (LINE + " --area-not-stated --eligibility-not-stated --funder-not-stated", "the model marked it not stated"),
    ],
)
def test_each_empty_box_gets_its_note_in_the_record_s_own_order(line: str, reason: str) -> None:
    _, notes = build(stored(), TOPICS, line)
    assert notes == [f"{name}: empty, because {reason}" for name in ("funder", "who can apply", "where")]


def test_a_call_whose_labels_match_nothing_gets_no_topic_and_a_note_last() -> None:
    record = stored()
    record["metadata"]["tags"] = ["Disaster risk reduction", "Journalistic magazines"]
    call, notes = build(record, TOPICS, LINE)
    assert call.topics == ()
    assert notes == [
        *(
            f"{name}: empty, because the model's answer did not mention it"
            for name in ("funder", "who can apply", "where")
        ),
        "topics: empty, because the call gets no topic on the topic list from its source or its labels",
    ]


def test_a_value_with_no_sentence_is_refused() -> None:
    with pytest.raises(ValueError, match="quote"):
        build(stored(), TOPICS, 'fieldbook --type grant --summary "Funds news media."')


@pytest.mark.parametrize(
    ("line", "refusal"),
    [
        (LINE + ' --title-quote "A title."', "--title-quote is not a flag the instructions offer"),
        (LINE + " --type grant", "--type is given twice"),
        (f'fieldbook --summary "Funds news media." --summary-quote "{GUIDE}" --type', "--type has no value"),
    ],
)
def test_a_malformed_line_is_refused(line: str, refusal: str) -> None:
    with pytest.raises(ValueError, match=refusal):
        build(stored(), TOPICS, line)


def test_a_sentence_in_the_text_is_found_and_the_model_asked_once() -> None:
    call, notes, asked = reading(REPLY)
    assert len(asked) == 1
    assert call.summary.found
    assert notes == [FUNDER]


def test_a_quote_is_found_whatever_its_line_breaks_and_spaces() -> None:
    quote = GUIDE.replace("information in", "information\\n in").replace("Horizon", " Horizon")
    call, _ = build(stored(), TOPICS, f'fieldbook --type grant --summary "Funds news media." --summary-quote "{quote}"')
    assert call.summary.quote == "See the information\n in the  Horizon Europe Programme Guide."
    assert call.summary.found


@pytest.mark.parametrize(
    "quote",
    [
        pytest.param(CONSUMPTION.replace("’", "'"), id="straight apostrophe"),
        pytest.param(CONSUMPTION.lower(), id="letter case"),
    ],
)
def test_a_quote_is_found_only_letter_for_letter(quote: str) -> None:
    line = 'fieldbook --type grant --summary "Funds news media." --summary-quote "{}"'
    assert build(stored(), TOPICS, line.format(CONSUMPTION))[0].summary.found
    assert not build(stored(), TOPICS, line.format(quote))[0].summary.found


def test_a_sentence_with_words_dropped_is_caught_and_asked_about_once_more() -> None:
    call, notes, asked = reading(DROPPED, REPLY)
    first, second = asked
    assert second == [
        *first,
        {"role": "assistant", "content": DROPPED},
        {"role": "user", "content": f"{AGAIN}\n{MISSED}"},
    ]
    assert call == build(stored(), TOPICS, REPLY)[0]
    assert notes == [f"first answer: {MISSED}", FUNDER]


@pytest.mark.parametrize(
    ("words", "changed", "flag"),
    [
        ("comprehensive knowledge base", "complete knowledge base", "summary"),
        ("multiple news sectors", "many news sectors", "eligibility"),
        ("accurate diagnoses", "exact diagnoses", "area"),
    ],
)
def test_the_problem_line_of_a_sentence_not_found_names_its_flag(words: str, changed: str, flag: str) -> None:
    _, _, asked = reading(REPLY.replace(words, changed), REPLY)
    assert asked[1][-1]["content"] == f"{AGAIN}\n--{flag}-quote: the sentence must be in the text word for word"


def test_a_sentence_with_one_figure_changed_is_missed_twice_and_kept_marked() -> None:
    sentence = (
        "The granting authority may, up to 4 years after the end of the action, object to a transfer of ownership"
    )
    assert sentence in text(stored())
    changed = sentence.replace("4 years", "3 years")
    answer = f'fieldbook --type grant --funder-not-stated --summary "Funds news media." --summary-quote "{changed}"'
    call, notes, asked = reading(answer, answer)
    assert len(asked) == 2
    assert call.summary == Quoted(value="Funds news media.", quote=changed, found=False)
    assert notes == [
        f"first answer: {MISSED}",
        f"second answer: {MISSED}",
        FUNDER,
        f"summary: this sentence was not found in the call: {changed}",
        "who can apply: empty, because the model's answer did not mention it",
        "where: empty, because the model's answer did not mention it",
    ]


def test_a_usable_second_answer_is_kept_even_when_it_misses_more() -> None:
    first = REPLY.replace("comprehensive knowledge", "complete knowledge").replace("accurate", "exact")
    second = first.replace("multiple news sectors", "many news sectors")
    call, notes, asked = reading(first, second)
    expected, expected_notes = build(stored(), TOPICS, second)
    rule = "the sentence must be in the text word for word"
    assert asked[1][-1]["content"] == f"{AGAIN}\n--summary-quote: {rule}\n--area-quote: {rule}"
    assert call == expected
    assert notes == [
        *(f"first answer: --{flag}-quote: {rule}" for flag in ("summary", "area")),
        *(f"second answer: --{flag}-quote: {rule}" for flag in ("summary", "eligibility", "area")),
        *expected_notes,
    ]


def test_a_usable_first_answer_is_kept_when_the_second_cannot_be_used() -> None:
    call, notes, _ = reading(DROPPED, "I could not decide.")
    assert call == build(stored(), TOPICS, DROPPED)[0]
    assert not call.summary.found
    assert notes == [
        f"first answer: {MISSED}",
        "second answer: the answer must hold exactly one line beginning with fieldbook; it holds 0",
        FUNDER,
        f"summary: this sentence was not found in the call: {call.summary.quote}",
    ]


def test_a_second_request_that_fails_fails_the_reading_with_the_first_answer_s_problems() -> None:
    seen: list[httpx2.Request] = []
    with model(DROPPED, httpx2.Response(503), seen=seen) as client, pytest.raises(httpx2.HTTPStatusError) as caught:
        read(EU, stored(), TOPICS, (), "the key", client, keeping([], seen))
    assert caught.value.__notes__ == [f"first answer: {MISSED}"]


@pytest.mark.parametrize(
    ("answer", "count"),
    [pytest.param("I could not decide.", 0, id="none"), pytest.param(REPLY + "\n" + LINE, 2, id="two")],
)
def test_an_answer_with_no_command_line_or_two_is_sent_back_with_the_rule(answer: str, count: int) -> None:
    problem = f"the answer must hold exactly one line beginning with fieldbook; it holds {count}"
    call, notes, asked = reading(answer, REPLY)
    assert asked[1][-1]["content"] == f"{AGAIN}\n{problem}"
    assert call == build(stored(), TOPICS, REPLY)[0]
    assert notes == [f"first answer: {problem}", FUNDER]


def test_a_record_the_template_refuses_is_sent_back_and_noted_short() -> None:
    problems = [
        (
            "type: Input should be 'grant', 'tender', 'rfp', 'eoi', 'framework', 'fellowship', 'prize', 'training', "
            "'post' or 'other'"
        ),
        "summary.value: Input should be a valid string",
    ]
    _, notes, asked = reading(f'fieldbook --type gift --summary 5 --summary-quote "{GUIDE}"', REPLY)
    message = asked[1][-1]["content"]
    assert message == "\n".join([AGAIN, *problems])
    assert notes == [*(f"first answer: {problem}" for problem in problems), FUNDER]


def test_an_answer_unusable_twice_raises_naming_both_answers_problems() -> None:
    seen: list[httpx2.Request] = []
    with model("I could not decide.", LINE + "\n" + LINE, seen=seen) as client, pytest.raises(ValueError) as caught:
        read(EU, stored(), TOPICS, (), "the key", client, keeping([], seen))
    assert str(caught.value) == (
        "first answer: the answer must hold exactly one line beginning with fieldbook; it holds 0; "
        "second answer: the answer must hold exactly one line beginning with fieldbook; it holds 2"
    )
    assert len(seen) == 2


def test_the_first_request_holds_the_instructions_and_the_text() -> None:
    seen: list[httpx2.Request] = []
    with model(REPLY, seen=seen) as client:
        read(EU, stored(), TOPICS, (), "the key", client, keeping([], seen))
    [request] = seen
    assert str(request.url) == "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    assert request.headers["Authorization"] == "Bearer the key"
    assert "the key" not in str(request.url)
    assert request.extensions["timeout"] == {"connect": 180, "read": 180, "write": 180, "pool": 180}
    body = json.loads(request.read())
    assert body["model"] == "gemini-3.5-flash-lite"
    assert body["messages"] == [
        {
            "role": "user",
            "content": f"{INSTRUCTIONS}\n-----BEGIN SOURCE TEXT-----\n{text(stored())}\n-----END SOURCE TEXT-----",
        }
    ]


def test_a_request_the_service_refuses_is_raised() -> None:
    seen: list[httpx2.Request] = []
    with model(httpx2.Response(503), seen=seen) as client, pytest.raises(httpx2.HTTPStatusError) as caught:
        read(EU, stored(), TOPICS, (), "the key", client, keeping([], seen))
    assert not hasattr(caught.value, "__notes__")


def test_the_instructions_hold_what_the_code_writes_and_their_example_builds() -> None:
    for words in ("`Title`", "`Opening date`", "`Deadline`", "`Budget`"):
        assert words in INSTRUCTIONS
    assert "`-----BEGIN SOURCE TEXT-----`" in INSTRUCTIONS
    assert "`-----END SOURCE TEXT-----`" in INSTRUCTIONS
    [example] = [line for line in INSTRUCTIONS.splitlines() if line.startswith("fieldbook ")]
    call, _ = build(stored(), TOPICS, example)
    assert call.funder == "Example Foundation"


def test_a_clean_first_answer_is_handed_on_as_sent() -> None:
    kept: list[tuple[AnswerWord, int, str]] = []
    seen: list[httpx2.Request] = []
    with model(REPLY, seen=seen) as client:
        read(EU, stored(), TOPICS, (), "the key", client, keeping(kept, seen))
    assert kept == [("first answer", 1, REPLY)]


def test_both_answers_are_handed_on_after_a_second_try() -> None:
    kept: list[tuple[AnswerWord, int, str]] = []
    seen: list[httpx2.Request] = []
    with model(DROPPED, REPLY, seen=seen) as client:
        read(EU, stored(), TOPICS, (), "the key", client, keeping(kept, seen))
    assert kept == [("first answer", 1, DROPPED), ("second answer", 2, REPLY)]


def test_both_answers_are_handed_on_when_the_reading_fails() -> None:
    kept: list[tuple[AnswerWord, int, str]] = []
    seen: list[httpx2.Request] = []
    with model("I could not decide.", LINE + "\n" + LINE, seen=seen) as client, pytest.raises(ValueError):
        read(EU, stored(), TOPICS, (), "the key", client, keeping(kept, seen))
    assert kept == [("first answer", 1, "I could not decide."), ("second answer", 2, f"{LINE}\n{LINE}")]


def test_the_first_answer_is_handed_on_when_the_second_request_fails() -> None:
    kept: list[tuple[AnswerWord, int, str]] = []
    seen: list[httpx2.Request] = []
    with model(DROPPED, httpx2.Response(503), seen=seen) as client, pytest.raises(httpx2.HTTPStatusError):
        read(EU, stored(), TOPICS, (), "the key", client, keeping(kept, seen))
    assert kept == [("first answer", 1, DROPPED)]


def test_each_answer_is_handed_on_exactly_as_sent() -> None:
    kept: list[tuple[AnswerWord, int, str]] = []
    seen: list[httpx2.Request] = []
    first, second = f"\r\n {DROPPED}\n\n", f"  {REPLY}\r\n"
    with model(first, second, seen=seen) as client:
        read(EU, stored(), TOPICS, (), "the key", client, keeping(kept, seen))
    assert kept == [("first answer", 1, first), ("second answer", 2, second)]


def test_the_first_answer_is_handed_on_before_it_is_judged() -> None:
    kept: list[tuple[AnswerWord, int, str]] = []
    seen: list[httpx2.Request] = []
    no_text = httpx2.Response(200, json={"choices": [{"message": {"content": None}}]})
    # A reply with no text cannot be judged, so the reading stops there, as before; the answer is already handed on.
    with model(no_text, seen=seen) as client, pytest.raises(AttributeError):
        read(EU, stored(), TOPICS, (), "the key", client, keeping(kept, seen))
    assert [(word, sent) for word, sent, _ in kept] == [("first answer", 1)]


def test_the_second_answer_is_handed_on_before_it_is_judged() -> None:
    kept: list[tuple[AnswerWord, int, str]] = []
    seen: list[httpx2.Request] = []
    no_text = httpx2.Response(200, json={"choices": [{"message": {"content": None}}]})
    # A reply with no text cannot be judged, so the reading stops there, as before; the answer is already handed on.
    with model(DROPPED, no_text, seen=seen) as client, pytest.raises(AttributeError):
        read(EU, stored(), TOPICS, (), "the key", client, keeping(kept, seen))
    assert [(word, sent) for word, sent, _ in kept] == [("first answer", 1), ("second answer", 2)]


def test_a_fault_keeping_the_second_answer_carries_no_notes() -> None:
    kept: list[tuple[AnswerWord, int, str]] = []
    seen: list[httpx2.Request] = []

    def keep(word: AnswerWord, answer: str) -> None:
        if word == "second answer":
            raise ValueError("the second answer cannot be kept")
        kept.append((word, len(seen), answer))

    with model(DROPPED, REPLY, seen=seen) as client, pytest.raises(ValueError, match="cannot be kept") as caught:
        read(EU, stored(), TOPICS, (), "the key", client, keep)
    assert not hasattr(caught.value, "__notes__")
    assert kept == [("first answer", 1, DROPPED)]


def test_an_eiti_call_is_read_from_its_page_alone_with_the_topic_its_source_names() -> None:
    seen: list[httpx2.Request] = []
    with model(EITI_REPLY, seen=seen) as client:
        call, notes = read(EITI_CALL, OFFER, EXTRACTIVES, ("extractives-eiti",), "the key", client, keeping([], seen))
    [sent] = json.loads(seen[0].read())["messages"]
    source = sent["content"].split("-----BEGIN SOURCE TEXT-----\n")[1]
    assert source.startswith(
        "Title: Example 2027 EITI Validation: call for views on stakeholder engagement\n"
        "Opening date: not stated\n"
        "Deadline: 2027-01-01\n"
        "Budget: not stated\n"
        "Example 2027 EITI Validation: call for views on stakeholder engagement | EITI Home Countries "
    )
    assert BOARD in source
    assert "Subscribe to our newsletter" in source
    assert "dataLayer" not in source
    assert "baseUrl" not in source
    assert "color: red" not in source
    assert (call.identifier, call.link, call.title) == (VIEWS, VIEWS, EITI_CALL.title)
    assert (call.opening, call.budget) == (None, None)
    assert call.deadline == Deadline(date=dt.date(2027, 1, 1), quote="Deadline: 2027-01-01", found=True)
    assert call.summary.found
    assert call.topics == (Topic(name="extractives-eiti", mark="primary"),)
    assert notes == [
        "opening date: empty, because this source's page has no field for it",
        "budget: empty, because this source's page has no field for it",
        "who can apply: empty, because the model marked it not stated",
        "where: empty, because the model marked it not stated",
    ]


@pytest.mark.parametrize(
    ("page", "error"),
    [
        pytest.param(OFFER.replace(b"<time ", b"<span "), "exactly one closing date; it holds 0", id="no closing date"),
        pytest.param(OFFER.replace(b"</dd>", b'<time datetime="2027-02-01">x</time></dd>'), "it holds 2", id="two"),
        pytest.param(
            OFFER.replace(b"2027-01-01T", b"1 Jan 2027T"),
            "the page's closing date cannot be read: '1 Jan 2027T12:00:00Z'",
            id="not a date",
        ),
        pytest.param(OFFER.replace(b"Example", "Exemplé".encode("latin-1")), "can't decode", id="not UTF-8"),
    ],
)
def test_a_page_that_is_not_a_call_fails_its_reading_before_any_request(page: bytes, error: str) -> None:
    seen: list[httpx2.Request] = []
    with model(seen=seen) as client, pytest.raises(ValueError, match=error):
        read(EITI_CALL, page, EXTRACTIVES, ("extractives-eiti",), "the key", client, keeping([], seen))
    assert seen == []
