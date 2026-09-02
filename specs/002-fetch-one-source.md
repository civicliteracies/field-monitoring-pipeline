# PR 2 — fetch one source, capture the raw

**Date:** 2026-09-01 · **Status:** approved 2026-09-01 · **Owner:** build
**Branch:** `feat/fetch-capture` · **Commit type:** `feat(fetch): capture one source's raw items`

## Goal

**One real file in `data/raw/`, fetched from a real source, with nothing copied
by hand.**

The system reaches one funding-call source, reads the items it publishes, and
writes each one into the repository as plain text with a small record of where it
came from. The same item is never written twice.

No model call, no cards, no feed, no dashboard. Those arrive in later slices and
all of them read from what this slice writes.

## Why

The archive is the source of truth. Every card, every feed entry and the whole
dashboard are derived from it and can be deleted and rebuilt at any time. That
promise only holds if capture is right, so capture is built first, alone, with
nothing downstream to hide a fault in it.

The ordering rule matters more than anything else here. **The raw body is written
before anything asks whether the item is already known.** Checking first and
writing second loses an item permanently if the run stops in between, because
nothing recorded that it was ever seen. Writing first means the worst case is a
duplicate, and a duplicate is recoverable.

## Requirements (EARS)

### The source registry

1. WHEN the run starts, THE SYSTEM SHALL read `config/sources.toml` and act only
   on sources whose `kind` is `call`.
2. WHEN a source block is missing a required field, or carries a `how` value the
   system does not implement, THE SYSTEM SHALL stop before any network request
   and name the source and the problem.
3. THE SYSTEM SHALL write every file through a single function that joins a
   relative path onto a fixed root of `data/`, so that writing to `config/` cannot
   be expressed. That directory is edited by people and `data/` is written by the
   run, and a hand edit and a run can therefore never collide.

### Reaching a source

4. WHEN the fetcher is called, THE SYSTEM SHALL take a source drawn from the
   registry and SHALL NOT take a bare web address.
4a. WHEN any address is about to be reached, including one a source redirects to,
   THE SYSTEM SHALL refuse it unless it is on the open internet, and SHALL NOT
   retry a refusal. Loopback, private, link-local, reserved, multicast and
   unspecified addresses are refused, as are names meaning a machine on this
   network. **A name that resolves to a private address is not caught**, because
   that needs the connection intercepted rather than the address read. Redirects
   are followed by this step rather than by the network library, so that each hop
   is checked.
5. WHEN a source is reached and a validator from a previous run is stored, THE
   SYSTEM SHALL send it as a conditional request.
6. WHEN a source answers that nothing has changed, THE SYSTEM SHALL record the
   check and move on without reading a body.
7. WHEN a request times out or the source answers with a server error, THE SYSTEM
   SHALL retry up to three times with increasing pauses, then skip that source and
   log it. **A failing source SHALL NOT stop the run.**
8. WHEN a source answers with a client error, THE SYSTEM SHALL treat it as
   permanent, skip it and log it, without retrying.
9. WHEN a response passes the configured size or time cap, THE SYSTEM SHALL
   abandon it and skip that source.

### Canonicalising and keying

10. WHEN an item's link is read, THE SYSTEM SHALL strip tracking parameters,
    lowercase the scheme and host, drop the fragment, and sort what remains, and
    record the result as the item's canonical link. **Resolving a link that
    redirects is not done here.** It costs one request per item on every run, and
    a feed almost always publishes its own identifier, which takes precedence
    over the link when naming an item. It belongs with the slice that hardens
    canonicalisation, where it can be done only for items that need it.
11. WHEN the canonical link is known, THE SYSTEM SHALL compute `item_id` by
    hashing, in this order of preference: the source identifier together with the
    item's own published identifier where the source publishes one, else the
    canonical link, else the normalised body.
12. **THE SYSTEM SHALL always hash, and SHALL NOT use any value read from a source
    as a filename.** An identifier published by a source is attacker-influenced
    text in the same way its body is, and `item_id` becomes a path. Hashing makes
    every name a fixed-length hexadecimal string, so a name cannot contain a
    separator and cannot address anything outside the archive. This extends
    ADR-0010, which treats fetched text as untrusted, to fetched text that becomes
    a path.
13. WHEN `item_id` is computed, THE SYSTEM SHALL record in the origin sidecar
    which of those three rules produced it, so the store can say how any name was
    derived.
14. WHEN the same canonical link is seen on a later run, THE SYSTEM SHALL produce
    the same `item_id`.

### Capture, then dedup

15. WHEN an item has an `item_id`, THE SYSTEM SHALL write `data/raw/<item_id>.txt`
    and `data/raw/<item_id>.json` **before** anything asks whether that item is
    already known.
15a. WHEN a source answers, THE SYSTEM SHALL write down the response exactly as
    served, before anything reads it, under `data/responses/<source_id>/` named by
    a hash of its own bytes. Items are read out of it afterwards, never instead of
    it, and each item's record SHALL name the response it came from. See ADR-0030.
15b. WHEN a response names no feed format, THE SYSTEM SHALL treat that source as
    unreadable, skip it with the reason, and SHALL NOT store its validator, so a
    source behind a gate is not reported unchanged for ever. An empty but valid
    feed is not unreadable.
16. WHEN the raw body is written, THE SYSTEM SHALL write it without alteration.
    A feed entry is not one body but several fields, so the item's words are its
    title, its summary and its content, joined in that order and otherwise
    untouched. Nothing is trimmed from inside, reworded, or re-encoded, and
    `archive.py` writes through whatever it is given.
17. WHEN a file for that `item_id` was already present before the run began, THE
    SYSTEM SHALL treat the item as already captured and SHALL NOT pass it further
    down the pipeline.
18. WHEN the origin sidecar is written, THE SYSTEM SHALL record the source
    identifier, the address fetched, the canonical link, the time the item first
    entered the archive, the hash of the body, and the keying rule used. **Every
    field SHALL be a fact about the item rather than about the run that saw it**,
    so capturing the same item again writes the same bytes and a day on which
    nothing changed leaves the archive untouched. See ADR-0029.

### Run-owned state

19. WHEN a source is reached successfully, THE SYSTEM SHALL store the response
    validator under `data/state/<source_id>.json` for the next run to send back.

### First run

20. WHEN a source is read for the first time and its route supplies a published
    date, THE SYSTEM SHALL archive items dated on or after that source's `since`
    date.
21. WHEN a route supplies no published date, THE SYSTEM SHALL archive everything
    the source currently lists. A route without dates has no backlog to bound: a
    grants page shows what is open now, so the source's own content is the bound.
    A source that lists closed calls going back years is a source not to add, and
    that is a judgement made when adding it rather than a rule in the code.
22. WHEN a first run archives, THE SYSTEM SHALL NOT treat it as new activity worth
    reporting. The first successful look at a source is recognised by the absence
    of a stored validator for it; the run labels it a first look and counts
    nothing from it as new, because those items are new to the archive rather
    than new in the world. Deleting a source's state file therefore relabels its
    next run as a first look, which changes one line of the run log and nothing
    else.

### The workflow

23. WHEN the workflow is triggered by hand, THE SYSTEM SHALL run the capture and
    commit any new files to the `data` branch.
24. WHEN the schedule fires each morning, THE SYSTEM SHALL run the capture
    unattended and commit any new files to the `data` branch. **The schedule is in
    this slice rather than a later one because a schedule that has never fired is
    untested plumbing**, and proving it end to end is part of what this slice is
    for. The cron is set a few minutes past the hour, because scheduled jobs on the
    hour are the most delayed.
25. WHEN two scheduled runs have completed on separate days, THE SYSTEM SHALL have
    added only genuinely new items on the second and re-keyed nothing already
    captured. This is checked by hand once, because `item_id` is permanent and the
    rebuild step re-extracts without re-keying, so a keying rule changed later
    would orphan what is already captured. At one source and a few days of archive
    the remedy is to delete and re-run, which is why this is a check rather than a
    gate.
26. WHEN the workflow runs, its token SHALL be `contents: read`, raised to
    `contents: write` only on the job that commits.
27. WHEN the workflow commits, it SHALL commit to the `data` branch and never to
    `main`.

## Decisions settled before writing this

Four questions were open. Three were answered by reading the planning documents
rather than deciding fresh, and are recorded here so the reasoning is not lost.

**The libraries were already chosen.** `httpx` for fetching and `feedparser` for
reading feeds, both assessed and approved. `trafilatura` for page text and
`pdfplumber` for PDFs arrive with the first source that needs them, not before.

**The item's shape is one type, as the plan specifies.** An earlier proposal to
split it into a type per pipeline stage was withdrawn: it departed from a settled
contract for a benefit that is currently theoretical.

**The key is the fallback chain as planned.** An earlier proposal to declare the
keying rule per source in the registry was withdrawn as custom, and aimed at a
problem no source has caused. Requirement 13 keeps the only real part of it, which
is that the store records how a name was derived.

**Two departures from the plan, both recorded as decision records.** The first is
the keying correction below. The second is `data/state/`, a run-owned folder for
the conditional-request bookmark: the plan requires conditional requests but never
says where to keep the value, and neither documented tree has a place for it.

**One correction to the chain, found while writing this.** `item_id` becomes a
filename, and its first rule reads an identifier published by the source, which is
attacker-influenced text. Used raw, an identifier of `../../config/sources.toml`
would write outside the archive. Requirement 12 removes the class rather than
checking for it: every rule hashes its input, so a name is always a fixed-length
hexadecimal string and cannot contain a separator. The three rules and their order
are unchanged. `AGENTS.md` states the chain and is corrected in this slice.

**The branch the run writes to is `data`, created as an orphan.** The planning
documents settle that the run owns its own branch and people own the default one,
but never name it. `data` follows the pattern of `gh-pages` and similar branches:
a short lowercase noun naming what the branch holds. It introduces no new word,
because `data/` is already the folder name. Orphan means it shares no history with
`main`, so the capture history and the code history never tangle.

## Files touched

- `config/sources.toml` (new: one call source, reached as a feed)
- `src/field_monitoring_pipeline/calls.py` (new: the run itself, which the
  documented layout never named)
- `src/field_monitoring_pipeline/models.py` (new: `Source`, `RawItem`)
- `src/field_monitoring_pipeline/fetch.py` (new)
- `src/field_monitoring_pipeline/normalize.py` (new)
- `src/field_monitoring_pipeline/archive.py` (new)
- `src/field_monitoring_pipeline/store.py` (new)
- `.github/workflows/calls.yml` (new: scheduled each morning, plus a manual trigger)
- `pyproject.toml` and `uv.lock` (add `httpx` and `feedparser`, pinned exactly)
- `AGENTS.md` (the keying rule corrected to say every rule hashes its input)
- `docs/ARCHITECTURE.md` (an entry for every new file)
- `docs/decisions/` (two new records, ADR-0026 and ADR-0027, and their index
  lines)
- `CHANGELOG.md` (a line under `Added`)
- `tests/` (mirroring each new module)

## Out of scope

The model call. Cards and `data/calls/`. The feed and the dashboard. More than
one source. Page and PDF routes. The health page, the heartbeat and the run log.
Entity resolution, ranking and search.

## New dependencies requiring approval from a member of CLI

All three approved on 2026-09-01. All pinned to an exact version.

| Package | What it does | Why this one |
|---|---|---|
| `httpx` | Fetches over the network, with timeouts and conditional requests | Named and assessed in the technology review as the modern superset of `requests` |
| `feedparser` | Reads the standard formats sites publish new items in | Named and assessed in the same review; handles malformed feeds, which scraped feeds often are |
| `pydantic` | Checks that data has the shape it claims, at the edges | The plan writes every contract as a Pydantic model and `AGENTS.md` requires them. It had never been installed |

## The end-to-end check that proves it works

1. `mise run verify` passes on a clean tree.
2. The `data` orphan branch exists on GitHub. Then trigger the workflow by
   hand, and let the schedule fire once on its own, so both routes are proven.
3. `data/raw/` on the `data` branch gains a `.txt` and a `.json` for at least one
   item, and the text matches what the source actually publishes.
4. Trigger it a second time with nothing changed at the source. **No new files
   appear.** The run reports the source as unchanged where the server honours
   the conditional request, or as 0 new where it does not. The live check on
   2026-09-01 saw the second form: the item-name gate, not the bookmark, is
   what prevents a second capture.
5. Point a source at an address that does not answer. The run finishes, skips it,
   and logs it.

## Tests

- The same canonical link produces the same `item_id` on two separate runs.
- Two addresses differing only by tracking parameters produce one `item_id`.
- **A source publishing an identifier of `../../config/sources.toml` produces an
  ordinary hash, and nothing is written outside `data/raw/`.**
- Every `item_id` matches the shape of a hash, whichever rule produced it.
- An item whose file already exists is not passed on.
- A source that times out does not stop the run, and other sources still capture.
- A source answering with a client error is skipped without retrying.
- A response that stalls past the reading deadline is abandoned without a
  retry.
- The raw file is written before the already-known check runs.
- A real feed body, run through the whole path, produces exactly the expected
  text on disk, so the composition itself is under test rather than only the
  writing of it.
- A second working source still captures when the first one fails.
- The sidecar records which keying rule produced the name.
- Capturing the same item again writes byte-identical files, so a run on a day
  when nothing changed has nothing to commit.
- A route supplying no published date archives everything currently listed, and
  archives nothing again on the second run.
- A first look announces nothing as new, and a later run counts only the
  genuinely new item.
- A malformed watch-list entry stops the run before any network request, and
  the error names the block it sits in.
- A private, loopback or link-local address is refused, whether it is on the
  watch list or a source redirects to it, and an ordinary redirect still works.
- The response is archived exactly as served, and each item names the response
  it was read out of.
- A holding page is skipped and keeps no bookmark; an empty feed is not.

## Build checklist

- [x] `httpx` and `feedparser` added and pinned, `pyproject.toml` and `uv.lock`
      committed together
- [x] `config/sources.toml` with one call source, reached as a feed
- [x] `models.py`: `Source` and `RawItem`
- [x] `normalize.py`: strip tracking parameters, normalise the address, record
      the canonical link. Redirects are not resolved here; see requirement 10
- [x] `fetch.py`: conditional requests, retry and skip, size and time caps
- [x] `archive.py`: compute `item_id` by hashing, write the body and the sidecar
- [x] `store.py`: the already-captured gate, filesystem only
- [x] One write function rooted at `data/`, so `config/` cannot be addressed
- [x] `AGENTS.md`: the keying rule corrected
- [x] `.github/workflows/calls.yml`: scheduled each morning plus manual trigger,
      commits to `data`, actions pinned to a commit SHA
- [x] A decision record for hashing every key input
- [x] A decision record for `data/state/` as run-owned state
- [ ] The `data` orphan branch created, once, deliberately. Creating it is a
      push, so it waits for shipping approval and is listed with everything
      else that ships. Until it exists on GitHub, the workflow's archive
      checkout has nothing to check out
- [x] Tests for every item in the list above
- [x] `docs/ARCHITECTURE.md` entry for each new file
- [x] `CHANGELOG.md` line under `Added`
- [x] `mise run verify` green

## Two things this slice resolved that were open

**The first run for a route that publishes no dates.** This looked undefined and
was going to be deferred. It is not: `since` exists to stop a first run pulling a
feed's backlog going back years, and a grants page has no backlog, because it
shows what is open now. Requirements 20 and 21 make the rule total over both
cases. The one case that genuinely breaks, a page listing closed calls going back
years, is a reason not to add that source, decided when adding it.

**When the schedule turns on: now, with this slice.** I had proposed deferring it
until the keying was proven. That was wrong, and checking against the plan showed
why: the schedule is one of three things this slice exists to prove, and a
schedule that has never fired is untested plumbing. Deferring would not avoid the
risk, only move the discovery of any fault further from where it is cheap to fix.
The keying concern survives as requirement 25, a check done once by hand rather
than a gate, because at one source the remedy is to delete and re-run.

## Found while building

**The source the plan named publishes no feed.** TAI Weekly was to be the first
source, reached as a feed. Every usual feed address answers 404, the page address
the plan gives is gone, and the site advertises no alternate link. It can only be
reached as a web page, which needs a library this slice does not carry, so it
waits. The watch list points at the Hewlett Foundation instead, a real funder in
this sector with a working feed, which proves the capture end to end. Its feed is
the foundation's own writing rather than a calls-only feed, and CLI approved it
on 2026-09-01 as the source that proves the pipeline. The full watch list is
settled at PR 5, where choosing what to watch is the whole point of the slice.

**Pydantic was never actually a dependency.** The plan's data contracts are
written as Pydantic models throughout and `AGENTS.md` requires them, but the
package had never been installed. Added here, pinned exactly, and approved on
2026-09-01 with the other two.

**A run needed a file the documented layout never named.** Something has to
sequence the steps. `calls.py` does that and nothing else.

## Still open

Nothing in this slice. Two items sit outside it and belong to later ones: the
readiness note that gates extraction from running unattended (ADR-0010), and the
two repository settings deferred to the slice where the first key exists.
