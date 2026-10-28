"""Run the steps in order for every source on the watch list, read every call without a card, and build the feed.

Fetches each source's calls, skips those already saved, and downloads and stores the rest. A call
whose page fails is written in the log and the run carries on. A search that fails is written in the
log and stops the run. When a source's calls are done, writes one row for it in the log: failed if
any call failed, successful if none failed and at least one was new, nothing new otherwise. The row
holds how many calls were fetched, how many were new and how many failed. Then reads each saved call
that has no card, in a fixed order, and writes a row for each answer the model gives, as it arrives.
Writes the call's card and a row with the reading's notes, or a failed row with the reason, so the
next run reads it again. Last, builds the feed from every card. Prints the numbers for each source
and for the reading, and then each failure.
"""

import datetime as dt
import functools
import json
import os
import sys
import tomllib
import traceback
from pathlib import Path

import httpx2

from field_monitoring_pipeline.extract import read
from field_monitoring_pipeline.fetch import fetch, fetch_page, new_client
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
    stored_record,
)
from field_monitoring_pipeline.write import card, read_card


def _reason(error: Exception) -> str:
    return "".join(traceback.format_exception_only(error)).rstrip("\n")


def _read(data: Path, client: httpx2.Client, fetched: dt.datetime, key: str) -> int:
    unread = sorted(
        (call for call in saved(data) if not carded(data, call)),
        key=lambda call: (call.source, call.identifier),
    )
    failures: list[str] = []
    for call in unread:
        record = stored_record(data, call)
        try:
            made, notes = read(record, key, client, functools.partial(store_answer, data, call, fetched))
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


def run(data: Path, watch_list: Path, client: httpx2.Client, fetched: dt.datetime, key: str) -> int:
    with watch_list.open("rb") as file:
        sources = tomllib.load(file)["source"]
    done = {(call.source, call.identifier) for call in saved(data)}
    failed = 0
    for source in sources:
        source_id, name, url, words = source["id"], source["name"], source["url"], source["words"]
        try:
            calls = fetch(url, words, client, fetched.date())
        except httpx2.HTTPError as error:
            store_run(data, source_id, str(error.request.url), fetched, "failed", _reason(error))
            raise
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            store_run(data, source_id, url, fetched, "failed", _reason(error))
            raise
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
    failed += _read(data, client, fetched, key)
    store_feed(data, feed([(path, read_card(text)) for path, text in cards(data)]))
    return failed


def main() -> None:
    fetched = dt.datetime.now(dt.UTC).replace(microsecond=0)
    with new_client() as client:
        failed = run(Path(sys.argv[1]), Path("config/sources.toml"), client, fetched, os.environ["GEMINI_API_KEY"])
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
