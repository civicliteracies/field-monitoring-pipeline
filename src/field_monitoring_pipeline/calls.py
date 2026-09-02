"""Run the funding-call capture once. This is what the workflow executes.

It sequences the other files and does nothing else itself, so the order of the
run reads in one place: reach each source, write down whatever came back, and
only then ask which of those items were already known.

A source that fails is reported and the run continues to the next one. The run
only fails as a whole if the watch list itself cannot be read, because that is a
mistake in the repository rather than a website having a bad day.

The archive lives on its own branch, so on GitHub it is checked out somewhere
other than beside the code. `FIELDBOOK_DATA` says where; without it the run
writes to `data/` beside the code, which is what happens on a developer machine.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

from field_monitoring_pipeline.archive import archive, archive_response
from field_monitoring_pipeline.fetch import Failed, Fetched, Unchanged, Validator, fetch, read_items
from field_monitoring_pipeline.models import load_sources
from field_monitoring_pipeline.store import STATE, Store

USER_AGENT = "fieldbook (+https://github.com/civicliteracies/field-monitoring-pipeline)"
"""Sources are entitled to know who is asking and where to complain."""


@dataclass(frozen=True, slots=True)
class SourceReport:
    """What happened to one source during one run."""

    source_id: str
    summary: str
    captured: int = 0
    new: int = 0


@dataclass(frozen=True, slots=True)
class RunReport:
    """What happened to every source, in the order they were read."""

    sources: tuple[SourceReport, ...]

    @property
    def new(self) -> int:
        return sum(report.new for report in self.sources)

    def lines(self) -> tuple[str, ...]:
        rows = tuple(f"  {report.source_id}: {report.summary}" for report in self.sources)
        return (*rows, f"{self.new} new item(s) captured")


def _load_validator(store: Store, source_id: str) -> Validator | None:
    saved = store.read(STATE, f"{source_id}.json")
    if saved is None:
        return None
    return Validator.model_validate_json(saved)


def _save_validator(store: Store, source_id: str, validator: Validator) -> None:
    payload = validator.model_dump_json(indent=2).encode("utf-8")
    _ = store.write(STATE, f"{source_id}.json", data=payload)


def run(config: Path, store: Store, client: httpx.Client) -> RunReport:
    """Capture every call source on the watch list once."""
    reports: list[SourceReport] = []

    for source in load_sources(config, kind="call"):
        validator = _load_validator(store, source.id)
        outcome = fetch(source, validator, client)

        match outcome:
            case Unchanged():
                reports.append(SourceReport(source.id, "unchanged"))
            case Failed(reason):
                reports.append(SourceReport(source.id, f"skipped, {reason}"))
            case Fetched(body, fresh):
                # What the source served goes down before anything reads it.
                # That is the rule the whole archive rests on, and it is why
                # this happens here rather than inside the fetch.
                response_hash = archive_response(source.id, body, store)
                try:
                    items = read_items(source, body, datetime.now(UTC))
                except ValueError as error:
                    # Not a feed: a holding page, or something malformed. The
                    # response is kept, because it is the evidence, but the
                    # bookmark is not, because saving it would make the source
                    # report "unchanged" for ever and hide the problem.
                    reports.append(SourceReport(source.id, f"skipped, unreadable, {error}"))
                    continue
                # Write every item down first. Only then ask which were new,
                # using the names that were present before this run began.
                archived = tuple(archive(item, store, response_hash) for item in items)
                _save_validator(store, source.id, fresh)
                if validator is None:
                    # The first successful look at a source archives its
                    # backlog without announcing it: these items are new to
                    # the archive, not new in the world.
                    summary = f"first look, {len(archived)} item(s) archived"
                    reports.append(SourceReport(source.id, summary, captured=len(archived)))
                else:
                    # By name, so a feed listing the same item twice counts once.
                    # Two sources carrying one call are two captures, and the log
                    # says two because the archive holds two.
                    new = len({name for name in archived if store.is_new(name)})
                    summary = f"{len(archived)} item(s), {new} new"
                    reports.append(SourceReport(source.id, summary, captured=len(archived), new=new))

    return RunReport(tuple(reports))


def main() -> int:
    """Entry point for the workflow. Returns 0 unless the watch list is broken."""
    root = Path(__file__).resolve().parents[2]
    override = os.environ.get("FIELDBOOK_DATA")
    store = Store(Path(override) if override else root / "data")

    # Redirects are followed by the fetch step itself, so that every hop can be
    # checked against the watch list rather than taken on trust.
    with httpx.Client(follow_redirects=False, headers={"user-agent": USER_AGENT}) as client:
        report = run(root / "config" / "sources.toml", store, client)

    sys.stdout.write("\n".join(report.lines()) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
