"""Run the steps in order for one kind, calls or reports, for every source of that kind on the watch list.

The command's first word names the kind. Reads the watch list into its typed entries and keeps the
sources of that kind. Fetches each source's items by its route, skips those already saved, and
downloads and stores the rest; an item its source gives no title is titled from its file when it is
saved. An item whose page fails is written in the log and the run carries on. A search that fails is
written in the log and
printed as that source's failed run, and the next source is searched. When a source's items are done,
writes one row for it in the log: failed if any item failed, successful if none failed and at least
one was new, nothing new otherwise. The row holds how many items were fetched, how many were new and
how many failed. Then reads the topic list, which stops the run if it cannot be read or breaks one of
its rules, and takes each saved item of the kind that has neither a card nor a set aside row, in a
fixed order. Checks it against the topic list, from what was stored for it and the topics its source
names, before any request: an item with no topic gets a set aside row with the check's reason and is
never read. An item with topics is read with them, and a row is written for each answer the model
gives, as it arrives. Writes the item's card and a row with the reading's notes, or a failed row with
the reason, so the next run checks and reads it again.
A calls run then builds the feed from every card it can read back; a card it cannot read back is left
out of the feed and written in the log with the reason. A reports run then reads each call already
held, once, for the reports it names. Each answer is written in the log as it arrives, so a reading
that stopped goes on from the answers it left. Each report found is checked against the topic list on
what its line gives, then gets its card or its set aside row; the call's own row, read or failed for
reports, comes last.
Prints the numbers for each source, for the reading and for the feed or the held documents, and then
each failure. Once its work is done, the run ends with a failure if a page, a search, a reading or a
card failed.
"""

import datetime as dt
import functools
import os
import sys
import tomllib
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, get_args

import httpx2

from field_monitoring_pipeline.data import extract, reports
from field_monitoring_pipeline.data.fetch import fetch, fetch_page, new_client
from field_monitoring_pipeline.data.models import Held, Kind, Topic
from field_monitoring_pipeline.data.reading import Found, Prepared, read
from field_monitoring_pipeline.data.settings import TopicList, WatchList
from field_monitoring_pipeline.data.store import (
    Saved,
    carded,
    cards,
    earlier,
    ended,
    found_item,
    held_read,
    item_key,
    layout,
    read_card,
    saved,
    store,
    store_answer,
    store_card,
    store_failure,
    store_feed,
    store_held,
    store_held_answer,
    store_left_out,
    store_reading,
    store_run,
    stored,
    unread,
)
from field_monitoring_pipeline.data.tags import Kept, SetAside, Subject, check, read_topic_list
from field_monitoring_pipeline.presentation.publish import CARDS, feed
from field_monitoring_pipeline.presentation.write import card, report_card

if TYPE_CHECKING:
    from field_monitoring_pipeline.data.models import Call

# The command's first word, checked against the kinds themselves.
KINDS: tuple[Kind, ...] = get_args(Kind.__value__)


def _reason(error: Exception) -> str:
    return "".join(traceback.format_exception_only(error)).rstrip("\n")


def _checked[K, R](
    listed: TopicList,
    own: Callable[[Saved], tuple[str, ...]],
    subject: Callable[[Saved, K], Subject],
    prepare: Callable[[Saved, K, tuple[Topic, ...]], Prepared[R]],
) -> Callable[[Saved, K], Prepared[R] | SetAside]:
    # An item's topic check, made before its reading: the reader gives the subject, the check decides,
    # and the reader prepares the reading with the topics the check made.
    def checked(item: Saved, kept: K) -> Prepared[R] | SetAside:
        match check(listed, subject(item, kept), own(item)):
            case SetAside() as aside:
                return aside
            case Kept(topics=found):
                return prepare(item, kept, found)

    return checked


def _own[K, R](
    data: Path,
    kind: Kind,
    client: httpx2.Client,
    fetched: dt.datetime,
    key: str,
    load: Callable[[Saved], K],
    prepare: Callable[[Saved, K], Prepared[R] | SetAside],
    card: Callable[[R], str],
) -> int:
    items = unread(data, kind)
    written = 0
    aside = 0
    failures: list[str] = []
    for item in items:
        # Outside the item's try: a stored copy that cannot be read at all is our own fault and stops the run.
        kept = load(item)
        keep = functools.partial(store_answer, data, item, fetched)
        try:
            match prepare(item, kept):
                case SetAside(reason=reason):
                    store_reading(data, item, fetched, "set aside", reason)
                    aside += 1
                    continue
                case prepared:
                    made, notes = read(prepared, key, client, keep)
        except (ValueError, httpx2.HTTPError) as error:
            reason = _reason(error)
            store_reading(data, item, fetched, "failed", reason)
            failures.append(f"{item.identifier}: {reason}")
            continue
        store_card(data, kind, item, item_key(item), card(made))
        store_reading(data, item, fetched, "card written", "; ".join(notes))
        written += 1
    print(f"Read: {len(items)} {kind}, {written} cards written, {aside} set aside, {len(failures)} failed")
    for failure in failures:
        print(failure)
    return len(failures)


def _document(data: Path, kind: Held, document: Saved) -> Callable[[], str]:
    # A held document's text is its own kind's reader's to give. Its stored copy is read now, outside the
    # document's try, as an own item's is; its text is made inside it.
    match kind:
        case "calls":
            kept = stored(data, "calls", document)
            return lambda: extract.held_text(kept)


def _held[R](
    data: Path,
    kind: Kind,
    listed: TopicList,
    client: httpx2.Client,
    fetched: dt.datetime,
    key: str,
    prepare: Callable[[str, tuple[str, ...]], Prepared[list[Found[R]]]],
    card: Callable[[R], str],
) -> int:
    read_before = held_read(data, kind)
    documents: list[tuple[Held, Saved]] = [
        (holds, document)
        for holds in layout(kind).holds
        for document in sorted(saved(data, holds), key=lambda document: (document.source, document.identifier))
        if (document.source, document.identifier) not in read_before
    ]
    written = 0
    failures: list[str] = []
    for holds, document in documents:
        text = _document(data, holds, document)
        keep = functools.partial(store_held_answer, data, kind, document, fetched)
        try:
            found, notes = read(prepare(text(), earlier(data, kind, document)), key, client, keep)
        except (ValueError, httpx2.HTTPError) as error:
            reason = _reason(error)
            store_held(data, kind, document, fetched, "failed", reason)
            failures.append(f"{document.identifier}: {reason}")
            continue
        done = ended(data)
        for each in found:
            item = found_item(document, kind, each.order, each.subject.title, fetched.date())
            # After a stop the same answers give the same items: an item already given its row gets nothing more,
            # and one whose card was written before its row gets that row and no second card.
            if item.identifier in done:
                continue
            if carded(data, kind, item_key(item)):
                store_reading(data, item, fetched, "card written", "; ".join(each.notes))
                continue
            # A found item exists only in the reading's answer, so its topic check comes after the reading.
            match check(listed, each.subject, ()):
                case SetAside(reason=reason):
                    store_reading(data, item, fetched, "set aside", reason)
                case Kept(topics=topics):
                    store_card(data, kind, item, item_key(item), card(each.record(item, topics)))
                    store_reading(data, item, fetched, "card written", "; ".join(each.notes))
                    written += 1
        # The document's own row comes after its items' cards and rows, so a run that stops between them reads it again.
        store_held(data, kind, document, fetched, "read", "; ".join([f"{len(found)} found", *notes]))
    print(f"Held documents: {len(documents)} read, {written} cards written, {len(failures)} failed")
    for failure in failures:
        print(failure)
    return len(failures)


def _publish(data: Path, fetched: dt.datetime) -> int:
    readable: list[tuple[str, Call]] = []
    failures: list[str] = []
    for path, text in cards(data, "calls"):
        try:
            readable.append((path, read_card("calls", text)))
        except ValueError as error:
            reason = _reason(error)
            store_left_out(data, CARDS + path, fetched, reason)
            failures.append(f"{path}: {reason}")
    store_feed(data, feed(readable))
    print(f"Feed: {len(readable)} cards, {len(failures)} left out")
    for failure in failures:
        print(failure)
    return len(failures)


def run(
    kind: Kind, data: Path, watch_list: Path, topic_list: Path, client: httpx2.Client, fetched: dt.datetime, key: str
) -> int:
    with watch_list.open("rb") as file:
        watched = WatchList.model_validate(tomllib.load(file)).source
    sources = {source_id: source for source_id, source in watched.items() if source.kind == kind}
    done = {(item.source, item.identifier) for item in saved(data, kind)}
    failed = 0
    for source_id, source in sources.items():
        name, url = source.name, source.url
        try:
            items = fetch(source, client, fetched.date())
        except (httpx2.HTTPError, httpx2.InvalidURL, ValueError) as error:
            # A request that failed names the address it asked; a reply that could not be read names the source's.
            link = str(error.request.url) if isinstance(error, httpx2.HTTPError) else url
            reason = _reason(error)
            store_run(data, source_id, link, fetched, "failed", reason)
            print(f"{name}: {reason}")
            failed += 1
            continue
        new = 0
        failures: list[str] = []
        for item in items:
            if (source_id, item.identifier) in done:
                continue
            try:
                page = fetch_page(item.link, client)
            except (httpx2.HTTPError, httpx2.InvalidURL, UnicodeEncodeError) as error:
                reason = _reason(error)
                store_failure(data, source_id, item, fetched, reason)
                failures.append(f"{item.identifier}: {reason}")
                continue
            store(data, kind, source_id, reports.titled(item, page), page, fetched)
            new += 1
        counts = f"{len(items)} {kind}, {new} new, {len(failures)} failed"
        outcome = "failed" if failures else "successful" if new else "nothing new"
        store_run(data, source_id, url, fetched, outcome, counts)
        print(f"{name}: {counts}")
        for failure in failures:
            print(failure)
        failed += len(failures)
    listed = read_topic_list(topic_list, tuple(topic for source in sources.values() for topic in source.topics))

    def own(item: Saved) -> tuple[str, ...]:
        # A saved item whose source has left the watch list is still checked, with no topics of its source.
        return sources[item.source].topics if item.source in sources else ()

    # Each arm hands its kind's reader and card writer to the shared loops, which are generic over what a
    # reading gives, so the type check holds each arm's reader and card writer together.
    match kind:
        case "calls":
            checked = _checked(listed, own, extract.subject, extract.prepare)
            failed += _own(data, kind, client, fetched, key, lambda item: stored(data, "calls", item), checked, card)
            failed += _publish(data, fetched)
        case "reports":
            checked = _checked(listed, own, reports.subject, reports.prepare)
            load = functools.partial(stored, data, "reports")
            failed += _own(data, kind, client, fetched, key, load, checked, report_card)
            failed += _held(data, kind, listed, client, fetched, key, reports.prepare_held, report_card)
    return failed


def _kind(word: str) -> Kind:
    for kind in KINDS:
        if kind == word:
            return kind
    raise SystemExit(f"the first word must be one of: {', '.join(KINDS)}")


def main() -> None:
    fetched = dt.datetime.now(dt.UTC).replace(microsecond=0)
    kind = _kind(sys.argv[1])
    with new_client() as client:
        failed = run(
            kind,
            Path(sys.argv[2]),
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
