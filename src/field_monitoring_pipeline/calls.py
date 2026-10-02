"""Run the steps in order for every source on the watch list.

Fetches each source's calls, skips those already saved, and downloads and stores the rest. A call
whose page fails is written in the log and the run carries on. A search that fails is written in the
log and stops the run. Prints, for each source, how many calls were fetched, how many were new and
how many failed, and then each failure.
"""

import datetime as dt
import json
import sys
import tomllib
import traceback
from pathlib import Path

import httpx2

from field_monitoring_pipeline.fetch import fetch, fetch_page, new_client
from field_monitoring_pipeline.store import saved, store, store_failure, store_search_failure


def _reason(error: Exception) -> str:
    return "".join(traceback.format_exception_only(error)).rstrip("\n")


def run(data: Path, watch_list: Path, client: httpx2.Client, fetched: dt.datetime) -> int:
    with watch_list.open("rb") as file:
        sources = tomllib.load(file)["source"]
    done = saved(data)
    failed = 0
    for source in sources:
        source_id, name, url, words = source["id"], source["name"], source["url"], source["words"]
        try:
            calls = fetch(url, words, client, fetched.date())
        except httpx2.HTTPError as error:
            store_search_failure(data, source_id, str(error.request.url), fetched, _reason(error))
            raise
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            store_search_failure(data, source_id, url, fetched, _reason(error))
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
        print(f"{name}: {len(calls)} calls, {new} new, {len(failures)} failed")
        for failure in failures:
            print(failure)
        failed += len(failures)
    return failed


def main() -> None:
    fetched = dt.datetime.now(dt.UTC).replace(microsecond=0)
    with new_client() as client:
        failed = run(Path(sys.argv[1]), Path("config/sources.toml"), client, fetched)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
