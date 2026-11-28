"""The sample data and stand-ins the test files share."""

import csv
import datetime as dt
import json
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2

from field_monitoring_pipeline.data.extract import CALL_PARTS, build, prepare
from field_monitoring_pipeline.data.models import Call, Quoted, Report, Topic
from field_monitoring_pipeline.data.reading import ADDRESS, read
from field_monitoring_pipeline.data.settings import TopicList
from field_monitoring_pipeline.data.store import (
    COLUMNS,
    AnswerWord,
    Saved,
    code,
)
from field_monitoring_pipeline.data.tags import no_title_match, not_near

ROOT = Path(__file__).parent.parent
REPLIES = Path(__file__).parent / "replies"
URL = "https://api.tech.ec.europa.eu/search-api/prod/rest/search?apiKey=SEDIA"

VIEWS = "https://eiti.org/call-for-proposals/example-2027-call-for-views"
STUDY = "https://eiti.org/call-for-proposals/example-consultancy"

SOURCE = "eu-funding-tenders"
FETCHED = dt.datetime(2026, 9, 27, 6, 0, tzinfo=dt.UTC)
STAMP = "2026-09-27T06:00:00+00:00"

IDENTIFIER = "HORIZON-CL2-2027-01-HERITAGE-06"

# A call's reason for being set aside when neither its titles nor its description match.
NOT_NEAR = not_near(CALL_PARTS)
NO_MATCH = f"{no_title_match(CALL_PARTS)}; {NOT_NEAR}"


def log(data: Path) -> list[list[str]]:
    with (data / "raw" / "log.csv").open(encoding="utf-8", newline="") as file:
        return list(csv.reader(file))


# A small topic list for the tests, with one entry in each of the four lists the check reads.
LISTS = """weak_words = ["civil society organisations"]
cancelling_names = ["democratic republic"]
other_sectors = ["farmers"]
names_not_matched = ["governance"]
"""
TOPIC_LIST = (
    LISTS
    + """
[topics.AI-and-civic]
mark = "primary"
words = ["artificial intelligence", "AI"]

[topics.data-journalism]
mark = "secondary"
words = ["journalism", "data journalism", "investigative", "investigative journalism"]

[topics.civic-tech]
mark = "primary"

[topics.civic-space]
mark = "secondary"
words = ["civil society organisations", "democratic", "democracy"]

[topics.governance]
mark = "secondary"
words = ["good governance"]
"""
)
TOPICS = TopicList.model_validate(tomllib.loads(TOPIC_LIST))
AI = Topic(name="AI-and-civic", mark="primary")
JOURNALISM = Topic(name="data-journalism", mark="secondary")
CIVIC_TECH = Topic(name="civic-tech", mark="primary")

REPLY = (REPLIES / "model_reply.txt").read_text(encoding="utf-8")
GUIDE = "See the information in the Horizon Europe Programme Guide."

LINE = f'fieldbook --type grant --summary "Funds news media." --summary-quote "{GUIDE}"'

AGAIN = "This answer cannot be used as it is. Write the one command line again, with each problem below put right:"

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
# Topics given by hand to the recorded EU call, and the topic an EITI call takes from its source.
GIVEN = (AI, JOURNALISM)
EXTRACTIVES = (Topic(name="extractives-eiti", mark="primary"),)


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
        call, notes = read(prepare(EU, stored(), GIVEN), "the key", client, keeping([], seen))
    return call, notes, [json.loads(request.read())["messages"] for request in seen]


EITI_ENTRY = """
[source.eiti]
name = "EITI"
url = "https://eiti.org/consultancy-opportunities"
how = "eiti-page"
topics = ["extractives-eiti"]
"""
EITI_RUN = ["", "eiti", "", "", "https://eiti.org/consultancy-opportunities", STAMP]
# The topic EITI's entry names, added to the test topic list for each run that reads EITI.
EITI_TOPICS = TOPIC_LIST + '\n[topics.extractives-eiti]\nmark = "primary"\n'


def eiti(listing: bytes) -> Callable[[httpx2.Request], httpx2.Response | None]:
    def special(request: httpx2.Request) -> httpx2.Response | None:
        if str(request.url) == ADDRESS and b"Budget: not stated" in request.read():
            return httpx2.Response(200, json={"choices": [{"message": {"content": EITI_REPLY}}]})
        if request.url.host != "eiti.org":
            return None
        if request.url.path == "/consultancy-opportunities":
            return httpx2.Response(200, content=listing)
        return httpx2.Response(200, content=(REPLIES / "eiti_offer.html").read_bytes())

    return special


SEARCHES = {
    ("democracy", "1"): "democracy.json",
    ('"civil society"', "1"): "civil_society.json",
    ("digital", "1"): "digital_page_1.json",
    ("digital", "2"): "digital_page_2.json",
}
WATCH_LIST = f"""[source.{SOURCE}]
name = "EU Funding and Tenders Portal"
url = "{URL}"
how = "eu-search"
words = ["democracy", '"civil society"', "digital"]
"""
PAGES = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-details/"
HERITAGE = PAGES + IDENTIFIER
ROW = [code(IDENTIFIER), SOURCE, IDENTIFIER, "Future-proofing sustainable cultural tourism", HERITAGE, STAMP]
CODE, STATUS, REASON = COLUMNS.index("code"), COLUMNS.index("status"), COLUMNS.index("reason")
SEARCH = f"{URL}&text=democracy&pageSize=100&pageNumber=1"
RUN = ["", SOURCE, "", "", URL]

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
STORED = json.loads((REPLIES / "stored_call.json").read_bytes())["metadata"]
OWN = STORED["identifier"][0] + " "

type Answer = Callable[[httpx2.Request], httpx2.Response | None]


def reply(request: httpx2.Request) -> dict[str, Any]:
    name = SEARCHES[request.url.params["text"], request.url.params["pageNumber"]]
    body = json.loads((REPLIES / name).read_bytes())
    # Each recorded call takes the fields the reading uses from the stored call, and the budget line takes its identifier.
    for record in body["results"]:
        metadata = record["metadata"]
        metadata |= {field: STORED[field] for field in ("callTitle", "startDate", "descriptionByte", "topicConditions")}
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


def server_error(request: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(500)


def files(data: Path) -> dict[str, bytes]:
    return {path.relative_to(data).as_posix(): path.read_bytes() for path in data.rglob("*") if path.is_file()}


CALL, _ = build(stored(), GIVEN, REPLY)


def pdf(*lines: str, title: str = "") -> bytes:
    # A one-page PDF written by hand, with its text in the standard Helvetica font and, when given, its own title.
    stream = "BT /F1 12 Tf 72 720 Td 14 TL " + " ".join(f"({line}) Tj T*" for line in lines) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Title ({title}) >>",
    ]
    out = b"%PDF-1.4\n"
    offsets: list[int] = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n{body}\nendobj\n".encode("latin-1")
    table = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{offset:010d} 00000 n \n" for offset in offsets).encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info 6 0 R >>\nstartxref\n{table}\n%%EOF\n".encode()
    return out


# The answers a model gives when the recorded EITI call page is read for the reports it names: one command line a report.
SEND = "Send your views through the address given on this page before the closing date."
INVENTED = "The board will publish every answer it receives."
STUDY_TITLE = "A study of journalism in the example country"


def found_line(title: str, quote: str = BOARD, kind: str = "evaluation") -> str:
    return (
        f'fieldbook --title "{title}" --type "{kind}" --organisation "EITI Board" --organisation-quote "{quote}" '
        "--audience-not-stated --methodology-not-stated --results-not-stated --duration-not-stated --area-not-stated"
    )


FOUND_STUDY = found_line(STUDY_TITLE)
FOUND_ACCOUNTS = found_line("Annual accounts", SEND, "annual report")
MISQUOTED = found_line(STUDY_TITLE, INVENTED)
NO_LINE = "The document names two reports, but I cannot tell them apart."
NONE = "fieldbook --none"
MISS_1 = "line 1: --organisation-quote: the sentence must be in the text word for word"
NOTHING_READ = "the answer must hold a line beginning with fieldbook for each item; it holds none"
# The notes of a report found with only its organisation stated.
FOUND_NOTES = [
    *(
        f"{label}: empty, because the model marked it not stated"
        for label in ("who it was for", "method", "results", "how long it ran", "where")
    ),
    "published: empty, because the document it was found in gives no date for it",
]

ARK_LINK = "https://data.org/stories/ark-solves/"


def _quoted(value: str, quote: str) -> Quoted:
    return Quoted(value=value, quote=quote, found=True)


# A report read in full, its facts in the words of a data.org story.
REPORT = Report(
    title="ARK Solves: data for smallholder farmers",
    type="research or case study",
    organisation=_quoted("ARK Solves", "ARK Solves built the platform with farmer cooperatives."),
    audience=_quoted("smallholder farmers", "It serves smallholder farmers across the islands."),
    methodology=_quoted("a data platform", "The team built a data platform that links farmers to buyers."),
    results=_quoted("4 000 farmers reached", "By June, 4 000 farmers had joined the platform."),
    duration=_quoted("two years", "The work ran for two years."),
    area=_quoted("the Philippines", "In the Philippines, food insecurity grips 37.8 million people."),
    published=dt.date(2026, 9, 8),
    topics=(Topic(name="open-data", mark="primary"),),
    link=ARK_LINK,
    identifier=ARK_LINK,
    model="gemini-3.5-flash-lite",
    instructions="reports-v1",
)
