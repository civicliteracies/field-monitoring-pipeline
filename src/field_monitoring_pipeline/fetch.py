"""Fetch the calls of a source on the watch list, by the source's route.

The EU route asks the EU Funding and Tenders Portal's public search service, in English, for the grant
topics that match each of the source's search words, reading every page. Each call is kept once, by its
identifier, and a call whose every closing date has passed is left out. Each call comes back as the
search record exactly as received. The EITI route reads the one list of current calls on EITI's
consultancy opportunities page and returns each call once, by its full address, with the title its
heading gives, and no record. A list page that holds no such list or two of them, a list that holds
both calls and its empty mark or neither, or a call without exactly one title and a link under
/offers/, fails the source. A call's web page can be fetched as the site serves it.
"""

import datetime as dt
import json
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import override

import httpx2

from field_monitoring_pipeline.models import EitiPage, EuSearch, Source

type JSON = dict[str, JSON] | list[JSON] | str | int | float | bool | None

GRANT_TOPIC = "1"
ANNOUNCED = "31094501"
OPEN = "31094502"
QUERY = json.dumps({"bool": {"must": [{"terms": {"type": [GRANT_TOPIC]}}, {"terms": {"status": [ANNOUNCED, OPEN]}}]}})
# English only: otherwise the portal returns each call once per EU language, and the first copy may not be English.
ENGLISH = json.dumps(["en"])
PAGE_SIZE = 100
# The marks of EITI's list page: the list of current calls, its empty mark, each call's card and the card's heading.
CURRENT = "view-id-offers"
EMPTY = "c-listing__empty"
CARD = "c-card"
HEADING = "c-card__heading"
OFFERS = "/offers/"
# Tags that have no closing tag, so they never count in the depth of the list.
VOID = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"})


@dataclass(frozen=True)
class NoRecord:
    """The source gives no record of the call: its page holds the call's text."""


NO_RECORD = NoRecord()


@dataclass(frozen=True)
class FetchedCall:
    identifier: str
    link: str
    title: str
    record: JSON | NoRecord


def new_client() -> httpx2.Client:
    headers = {"User-Agent": "Fieldbook (https://github.com/civicliteracies/field-monitoring-pipeline)"}
    return httpx2.Client(headers=headers, timeout=30)


def search_eu(source: EuSearch, client: httpx2.Client, today: dt.date) -> list[FetchedCall]:
    files = {
        "query": ("query.json", QUERY, "application/json"),
        "languages": ("languages.json", ENGLISH, "application/json"),
    }
    found: dict[str, FetchedCall] = {}
    for word in source.words:
        page = 1
        while True:
            address = httpx2.URL(source.url).copy_merge_params({
                "text": word,
                "pageSize": PAGE_SIZE,
                "pageNumber": page,
            })
            body = client.post(address, files=files).raise_for_status().json()
            for record in body["results"]:
                metadata = record["metadata"]
                identifier = metadata["identifier"][0]
                if (
                    identifier not in found
                    and max(dt.date.fromisoformat(date[:10]) for date in metadata["deadlineDate"]) >= today
                ):
                    found[identifier] = FetchedCall(identifier, metadata["url"][0], metadata["title"][0], record)
            if page * PAGE_SIZE >= body["totalResults"]:
                break
            page += 1
    return list(found.values())


class _Offers(HTMLParser):
    # Counts the lists of current calls, and reads each one up to its own closing tag, found by depth:
    # each card's link and the words of its headings, and how many empty marks it holds.
    def __init__(self) -> None:
        super().__init__()
        self.lists = 0
        self.depth = 0
        self.empty = 0
        self.rows: list[tuple[str, list[str]]] = []
        self.heading = 0

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        found = dict(attrs)
        classes = (found.get("class") or "").split()
        if CURRENT in classes:
            self.lists += 1
        if tag in VOID or not (self.depth or CURRENT in classes):
            return
        self.depth += 1
        if EMPTY in classes:
            self.empty += 1
        elif CARD in classes:
            self.rows.append((found.get("href") or "", []))
        elif HEADING in classes and self.rows and not self.heading:
            self.heading = self.depth
            self.rows[-1][1].append("")

    @override
    def handle_endtag(self, tag: str) -> None:
        if tag in VOID or not self.depth:
            return
        if self.depth == self.heading:
            self.heading = 0
        self.depth -= 1

    @override
    def handle_data(self, data: str) -> None:
        if self.heading:
            headings = self.rows[-1][1]
            headings[-1] += data


def search_eiti(source: EitiPage, client: httpx2.Client) -> list[FetchedCall]:
    offers = _Offers()
    offers.feed(client.get(source.url).raise_for_status().content.decode("utf-8"))
    offers.close()
    if offers.lists != 1:
        raise ValueError(f"the page must hold exactly one list of current calls; it holds {offers.lists}")
    if bool(offers.rows) == bool(offers.empty):
        held = "both" if offers.rows else "neither"
        raise ValueError(f"the list of current calls must hold calls or its empty mark, not both; it holds {held}")
    site = httpx2.URL(source.url)
    found: dict[str, FetchedCall] = {}
    for href, headings in offers.rows:
        titles = [title for heading in headings if (title := " ".join(heading.split()))]
        if len(titles) != 1 or not href.startswith(OFFERS):
            raise ValueError(
                f"a current call must have exactly one title and a link under {OFFERS}; "
                f"one has {len(titles)} and links to {href!r}"
            )
        # Passed on as text, so a link that cannot be read fails only its own call when its page is fetched.
        link = f"{site.scheme}://{site.host}{href}"
        found.setdefault(link, FetchedCall(link, link, titles[0], NO_RECORD))
    return list(found.values())


def fetch(source: Source, client: httpx2.Client, today: dt.date) -> list[FetchedCall]:
    match source:
        case EuSearch():
            return search_eu(source, client, today)
        case EitiPage():
            return search_eiti(source, client)


def fetch_page(link: str, client: httpx2.Client) -> bytes:
    return client.get(link).raise_for_status().content
