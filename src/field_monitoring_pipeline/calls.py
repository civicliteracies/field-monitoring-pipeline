"""Run the steps in order for every source on the watch list, read every call without a card, and build the feed.

Reads the watch list into its typed entries. Fetches each source's calls by its route, skips those
already saved, and downloads and stores the rest. A call whose page fails is written in the log and
the run carries on. A search that fails is written in the log and printed as that source's failed
run, and the next source is searched. When a source's calls are done, writes one row for it in the
log: failed if any call failed, successful if none failed and at least one was new, nothing new
otherwise. The row holds how many calls were fetched, how many were new and how many failed. Then
reads the topic list, which stops the run if it cannot be read or lacks a topic a source names, and
reads each saved call that has no card, in a fixed order, from what was stored for it, with that list
and the topics its source names, and writes a row for each answer the model gives, as it arrives.
Writes the call's card and a row with the reading's notes, or a failed row with the reason, so the
next run reads it again. Last, builds the feed from every card. Prints the numbers for each source and
for the reading, and then each failure.
"""

import datetime as dt
import functools
import os
import sys
import tomllib
import traceback
from collections.abc import Mapping
from pathlib import Path

import httpx2

from field_monitoring_pipeline.extract import read
from field_monitoring_pipeline.fetch import fetch, fetch_page, new_client
from field_monitoring_pipeline.models import Source, TopicList, WatchList
from field_monitoring_pipeline.publish import feed
from field_monitoring_pipeline.store import (
    carded,
    cards,
    saved,
    store,
    store_answer,
    store_card,
    store_failure,
    store_feed,
    store_reading,
    store_run,
    stored,
)
from field_monitoring_pipeline.tags import read_topic_list
from field_monitoring_pipeline.write import card, read_card


def _reason(error: Exception) -> str:
    return "".join(traceback.format_exception_only(error)).rstrip("\n")


def _read(
    data: Path, sources: Mapping[str, Source], listed: TopicList, client: httpx2.Client, fetched: dt.datetime, key: str
) -> int:
    unread = sorted(
        (call for call in saved(data) if not carded(data, call)),
        key=lambda call: (call.source, call.identifier),
    )
    failures: list[str] = []
    for call in unread:
        kept = stored(data, call)
        # A saved call whose source has left the watch list is still read, with no topics of its source.
        own = sources[call.source].topics if call.source in sources else ()
        keep = functools.partial(store_answer, data, call, fetched)
        try:
            made, notes = read(call, kept, listed, own, key, client, keep)
        except (ValueError, httpx2.HTTPError) as error:
            reason = _reason(error)
            store_reading(data, call, fetched, "failed", reason)
            failures.append(f"{call.identifier}: {reason}")
            continue
        store_card(data, call, card(made))
        store_reading(data, call, fetched, "card written", "; ".join(notes))
    print(f"Read: {len(unread)} calls, {len(unread) - len(failures)} cards written, {len(failures)} failed")
    for failure in failures:
        print(failure)
    return len(failures)


def run(data: Path, watch_list: Path, topic_list: Path, client: httpx2.Client, fetched: dt.datetime, key: str) -> int:
    with watch_list.open("rb") as file:
        sources = WatchList.model_validate(tomllib.load(file)).source
    done = {(call.source, call.identifier) for call in saved(data)}
    failed = 0
    for source_id, source in sources.items():
        name, url = source.name, source.url
        try:
            calls = fetch(source, client, fetched.date())
        except (httpx2.HTTPError, ValueError) as error:
            # A request that failed names the address it asked; a reply that could not be read names the source's.
            link = str(error.request.url) if isinstance(error, httpx2.HTTPError) else url
            reason = _reason(error)
            store_run(data, source_id, link, fetched, "failed", reason)
            print(f"{name}: {reason}")
            failed += 1
            continue
        new = 0
        failures: list[str] = []
        for call in calls:
            if (source_id, call.identifier) in done:
                continue
            try:
                page = fetch_page(call.link, client)
            except (httpx2.HTTPError, httpx2.InvalidURL, UnicodeEncodeError) as error:
                reason = _reason(error)
                store_failure(data, source_id, call, fetched, reason)
                failures.append(f"{call.identifier}: {reason}")
                continue
            store(data, source_id, call, page, fetched)
            new += 1
        counts = f"{len(calls)} calls, {new} new, {len(failures)} failed"
        outcome = "failed" if failures else "successful" if new else "nothing new"
        store_run(data, source_id, url, fetched, outcome, counts)
        print(f"{name}: {counts}")
        for failure in failures:
            print(failure)
        failed += len(failures)
    listed = read_topic_list(topic_list, tuple(topic for source in sources.values() for topic in source.topics))
    failed += _read(data, sources, listed, client, fetched, key)
    store_feed(data, feed([(path, read_card(text)) for path, text in cards(data)]))
    return failed


def main() -> None:
    fetched = dt.datetime.now(dt.UTC).replace(microsecond=0)
    with new_client() as client:
        failed = run(
            Path(sys.argv[1]),
            Path("config/sources.toml"),
            Path("config/tags.toml"),
            client,
            fetched,
            os.environ["GEMINI_API_KEY"],
        )
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
