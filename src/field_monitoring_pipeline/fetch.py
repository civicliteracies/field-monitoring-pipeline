"""Fetch the calls of the source on the watch list.

Asks the EU Funding and Tenders Portal's public search service, in English, for the grant topics that
match each search word, reading every page. Each call is kept once, by its identifier, and a call whose
every closing date has passed is left out. Each call comes back as the search record exactly as received,
and its web page can be fetched as the portal serves it.
"""

import datetime as dt
import json
from dataclasses import dataclass

import httpx2

type JSON = dict[str, JSON] | list[JSON] | str | int | float | bool | None

GRANT_TOPIC = "1"
ANNOUNCED = "31094501"
OPEN = "31094502"
QUERY = json.dumps({"bool": {"must": [{"terms": {"type": [GRANT_TOPIC]}}, {"terms": {"status": [ANNOUNCED, OPEN]}}]}})
# English only: otherwise the portal returns each call once per EU language, and the first copy may not be English.
ENGLISH = json.dumps(["en"])
PAGE_SIZE = 100


@dataclass(frozen=True)
class FetchedCall:
    identifier: str
    link: str
    record: JSON


def new_client() -> httpx2.Client:
    headers = {"User-Agent": "Fieldbook (https://github.com/civicliteracies/field-monitoring-pipeline)"}
    return httpx2.Client(headers=headers, timeout=30)


def fetch(url: str, words: list[str], client: httpx2.Client, today: dt.date) -> list[FetchedCall]:
    files = {
        "query": ("query.json", QUERY, "application/json"),
        "languages": ("languages.json", ENGLISH, "application/json"),
    }
    found: dict[str, FetchedCall] = {}
    for word in words:
        page = 1
        while True:
            address = httpx2.URL(url).copy_merge_params({"text": word, "pageSize": PAGE_SIZE, "pageNumber": page})
            body = client.post(address, files=files).raise_for_status().json()
            for record in body["results"]:
                metadata = record["metadata"]
                identifier: str = metadata["identifier"][0]
                if (
                    identifier not in found
                    and max(dt.date.fromisoformat(date[:10]) for date in metadata["deadlineDate"]) >= today
                ):
                    found[identifier] = FetchedCall(identifier, metadata["url"][0], record)
            if page * PAGE_SIZE >= body["totalResults"]:
                break
            page += 1
    return list(found.values())


def fetch_page(link: str, client: httpx2.Client) -> bytes:
    return client.get(link).raise_for_status().content
