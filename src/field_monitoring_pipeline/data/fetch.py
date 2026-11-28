"""Fetch the calls or reports of a source on the watch list, by the source's route.

The EU route asks the EU Funding and Tenders Portal's public search service, in English, for the grant
topics that match each of the source's search words, reading every page. Each call is kept once, by its
identifier, and a call whose every closing date has passed is left out. Each call comes back as the
search record exactly as received. The EITI route reads the one list of current calls on EITI's
consultancy opportunities page and returns each call once, by its full address, with the title its
heading gives, and no record. A list page that holds no such list or two of them, a list that holds
both calls and its empty mark or neither, or a call without exactly one title and a link under
/call-for-proposals/, fails the source. A call's web page can be fetched as the site serves it.

The four report routes keep each report once, by its address. The WordPress route asks every page of
the site's posts with their labels, and the feed route reads every entry; both leave out an item dated
before the source's start, and keep each item's record as received, marked by its form. A reply that is
not a feed, or an entry with no date or no link, fails the source; an entry with no title has none until
its file gives one. The list page route keeps each link on the same site exactly one level below the
source's path, titled by its words where it first appears, or by its file when it has none, and fails the
source when it finds none, or when the page holds a link that cannot be read. The single links route asks
nothing: each link is one report, with no title until its file gives one.
"""

import datetime as dt
import html
import json
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Literal, cast, override

import feedparser
import httpx2

from field_monitoring_pipeline.data.settings import EitiPage, EuSearch, Feed, Links, ListPage, Source, WordpressPosts

type JSON = dict[str, JSON] | list[JSON] | str | int | float | bool | None

GRANT_TOPIC = "1"
ANNOUNCED = "31094501"
OPEN = "31094502"
QUERY = json.dumps({"bool": {"must": [{"terms": {"type": [GRANT_TOPIC]}}, {"terms": {"status": [ANNOUNCED, OPEN]}}]}})
# English only: otherwise the portal returns each call once per EU language, and the first copy may not be English.
ENGLISH = json.dumps(["en"])
PAGE_SIZE = 100
# WordPress gives at most 100 items an answer.
WORDPRESS_PAGE = 100
# The marks of EITI's list page: the list of current calls, its empty mark, each call's card and the card's heading.
CURRENT = "view-id-offers"
EMPTY = "c-listing__empty"
CARD = "c-card"
HEADING = "c-card__heading"
# The path that the link of each current call starts with: the address of EITI's call pages.
OFFERS = "/call-for-proposals/"
# Tags that have no closing tag, so they never count in the depth of the list.
VOID = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"})


@dataclass(frozen=True)
class NoRecord:
    """The source gives no record of the call: its page holds the call's text."""


NO_RECORD = NoRecord()


# The two forms of a report source's own record of an item, each read by its own rule.
type Form = Literal["wordpress", "feed"]


@dataclass(frozen=True)
class Posted:
    """A report source's record of an item, with the form its route gives it in."""

    form: Form
    body: JSON


@dataclass(frozen=True)
class Fetched:
    identifier: str
    link: str
    # None when the source gives no title: only the item's file can give one, once it is downloaded.
    title: str | None
    record: JSON | Posted | NoRecord


def on_or_after(date: dt.date, day: dt.date) -> bool:
    # The one place that says which side of a given day is kept: the day itself is.
    return date >= day


def new_client() -> httpx2.Client:
    headers = {"User-Agent": "Fieldbook (https://github.com/civicliteracies/field-monitoring-pipeline)"}
    return httpx2.Client(headers=headers, timeout=30)


def search_eu(source: EuSearch, client: httpx2.Client, today: dt.date) -> list[Fetched]:
    files = {
        "query": ("query.json", QUERY, "application/json"),
        "languages": ("languages.json", ENGLISH, "application/json"),
    }
    found: dict[str, Fetched] = {}
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
                if identifier not in found and on_or_after(
                    max(dt.date.fromisoformat(date[:10]) for date in metadata["deadlineDate"]), today
                ):
                    found[identifier] = Fetched(identifier, metadata["url"][0], metadata["title"][0], record)
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


def search_eiti(source: EitiPage, client: httpx2.Client) -> list[Fetched]:
    offers = _Offers()
    offers.feed(client.get(source.url).raise_for_status().content.decode("utf-8"))
    offers.close()
    if offers.lists != 1:
        raise ValueError(f"the page must hold exactly one list of current calls; it holds {offers.lists}")
    if bool(offers.rows) == bool(offers.empty):
        held = "both" if offers.rows else "neither"
        raise ValueError(f"the list of current calls must hold calls or its empty mark, not both; it holds {held}")
    site = httpx2.URL(source.url)
    found: dict[str, Fetched] = {}
    for href, headings in offers.rows:
        titles = [title for heading in headings if (title := " ".join(heading.split()))]
        if len(titles) != 1 or not href.startswith(OFFERS):
            raise ValueError(
                f"a current call must have exactly one title and a link under {OFFERS}; "
                f"one has {len(titles)} and links to {href!r}"
            )
        # Passed on as text, so a link that cannot be read fails only its own call when its page is fetched.
        link = f"{site.scheme}://{site.host}{href}"
        found.setdefault(link, Fetched(link, link, titles[0], NO_RECORD))
    return list(found.values())


def search_wordpress(source: WordpressPosts, client: httpx2.Client) -> list[Fetched]:
    found: dict[str, Fetched] = {}
    page = 1
    while True:
        address = httpx2.URL(source.url).copy_merge_params({
            "per_page": WORDPRESS_PAGE,
            "page": page,
            "_embed": "wp:term",
        })
        reply = client.get(address).raise_for_status()
        for item in reply.json():
            link = item["link"]
            posted = Posted("wordpress", item)
            if link not in found and on_or_after(posted_day(posted), source.since):
                found[link] = Fetched(link, link, html.unescape(item["title"]["rendered"]), posted)
        # WordPress names how many pages the whole answer takes.
        if page >= int(reply.headers["X-WP-TotalPages"]):
            break
        page += 1
    return list(found.values())


def search_feed(source: Feed, client: httpx2.Client) -> list[Fetched]:
    # Kept word for word: no cleaning of the entries' markup and no rewriting of their links.
    parsed = feedparser.parse(
        client.get(source.url).raise_for_status().content, sanitize_html=False, resolve_relative_uris=False
    )
    # A page served in place of a feed is read with no error and no version.
    if not parsed["version"]:
        raise ValueError("the reply is not a feed")
    found: dict[str, Fetched] = {}
    for entry in parsed["entries"]:
        # An entry's link is its identifier, so an entry with none fails the source, as one with no date does.
        link: str | None = entry.get("link")
        if not link:
            raise ValueError(f"a feed entry has no link: {entry.get('title') or 'an entry with no title'}")
        # The dates feedparser read are kept as text, so the record is JSON and its day is the one read here.
        body: JSON = {key: _iso(value) if key.endswith("_parsed") else value for key, value in entry.items()}
        posted = Posted("feed", body)
        if link not in found and on_or_after(posted_day(posted), source.since):
            # An entry with no title, or an empty one, has none: its file gives it once it is downloaded.
            found[link] = Fetched(link, link, entry.get("title") or None, posted)
    return list(found.values())


def _iso(when: time.struct_time | None) -> str | None:
    # feedparser gives each date it reads in UTC.
    return None if when is None else dt.datetime(*when[:6], tzinfo=dt.UTC).isoformat()


def posted_day(posted: Posted) -> dt.date:
    """The day a WordPress item or a feed entry was posted: the item's date, or the entry's, else its last update."""
    body = cast("dict[str, Any]", posted.body)
    match posted.form:
        case "wordpress":
            return dt.date.fromisoformat(body["date"][:10])
        case "feed":
            when = body.get("published_parsed") or body.get("updated_parsed")
            if when is None:
                raise ValueError(f"a feed entry has no date: {body['link']}")
            return dt.date.fromisoformat(when[:10])


class _Anchors(HTMLParser):
    # Each link on a page, with the words inside it.
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, list[str]]] = []
        self.open = False

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self.links.append((dict(attrs).get("href") or "", []))
            self.open = True

    @override
    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self.open = False

    @override
    def handle_data(self, data: str) -> None:
        if self.open:
            self.links[-1][1].append(data)


def search_page(source: ListPage, client: httpx2.Client) -> list[Fetched]:
    anchors = _Anchors()
    anchors.feed(client.get(source.url).raise_for_status().content.decode("utf-8"))
    anchors.close()
    site = httpx2.URL(source.url)
    found: dict[str, Fetched] = {}
    for href, words in anchors.links:
        address = site.join(href).copy_with(fragment=None)
        rest = address.path.removeprefix(source.path)
        # A report is one level below the path, on the same site; a link that appears twice keeps its first
        # appearance, and one with no words there has no title, so its file gives it.
        if address.host == site.host and rest != address.path and rest.strip("/") and "/" not in rest.strip("/"):
            link = str(address)
            found.setdefault(link, Fetched(link, link, " ".join("".join(words).split()) or None, NO_RECORD))
    if not found:
        raise ValueError(f"the page holds no report link under {source.path}")
    return list(found.values())


def fetch(source: Source, client: httpx2.Client, today: dt.date) -> list[Fetched]:
    match source:
        case EuSearch():
            return search_eu(source, client, today)
        case EitiPage():
            return search_eiti(source, client)
        case WordpressPosts():
            return search_wordpress(source, client)
        case Feed():
            return search_feed(source, client)
        case ListPage():
            return search_page(source, client)
        case Links():
            return [Fetched(link, link, None, NO_RECORD) for link in dict.fromkeys(source.links)]


def fetch_page(link: str, client: httpx2.Client) -> bytes:
    return client.get(link).raise_for_status().content
