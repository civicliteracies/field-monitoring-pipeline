# CLAUDE.md

@constitution.md
@AGENTS.md

Both files above are imported, so they load with this one at the start of every
session rather than waiting to be opened. `constitution.md` holds the six rules
that never bend. `AGENTS.md` is the shared, tool-neutral source of working rules,
kept as one copy rather than two that drift. This file adds the build sequence and
the working loop, which are specific to how Fieldbook is being built rather than
to how any agent should behave.

## What Fieldbook is

A near-zero-cost, self-running monitor of the transparency and accountability
funding sector, built for the Civic Literacy Initiative. It watches the funders
and organisations CLI follows, captures every funding call and project report as
a plain text file in this repository, reads the stated facts out of each with one
bounded AI step, and publishes the calls as an RSS feed and a searchable
dashboard. Once a quarter it derives a plain-figures read of where the sector is
heading, with no AI at all. A companion skill widens the watch-list on demand.

CLI maintains it after the build, and it has to keep working through long
stretches when nobody is looking at it. Every choice favours the simplest, most
durable option over the cleverest one.

## The three rules that never bend

1. **One small pull request per step.** A thin vertical slice that runs and shows
   a visible result. Never batch. Never leave a half-built feature on `main`.
2. **Green before review.** `mise run verify` passes on this machine before
   anything is pushed. The push hook runs it, so a red gate never leaves here.
   The same task runs again on Linux for every pull request, which reports and
   blocks nothing. Write the tests as part of the slice, not after.
3. **Two stops, both mandatory.** Stop before anything leaves the machine: ask
   before `git push` or `gh pr create`, a draft included. Then stop again at the
   merge line: a member of CLI reviews and merges, and that merge is the deployment.
   Passing the first stop does not carry you through the second.

## The build sequence

Nineteen pull requests, in strict order, one at a time.

| Phase | Pull requests |
|---|---|
| 1. The thin slice | 1 quality gate · 2 fetch and capture · 3 extract one item · 4 validate, write, first card |
| 2. Detection | 5 all call sources · 6 canonicalise and store-once · 7 baseline and run log |
| 3. Processing | 8 tagging · 9 extraction guards · 10 rebuild |
| 4. The surfaces | 11 RSS feed · **12 dashboard, built by the CLI team** · 13 urgency ordering |
| 5. Control room | 14 health and heartbeat · 15 try-a-link sandbox · 16 admin docs · 17 discovery skill · 18 reports · 19 quarterly read |

**PR 12 is a handoff, not a skip.** The dashboard front end is built by the CLI
team. Build through PR 11, hand PR 12 over, and resume at PR 13 once it exists.
The card files in `data/calls/` and the RSS feed are a stable contract the
dashboard reads; leave `site/` to the team.

The riskiest step, extraction, is proven first on real items before anything
depends on it. Extraction does not join the scheduled run until its guards and
the readiness note are done at PR 9.

## The per-PR working loop

1. **Specification first**, approved by a member of CLI before any code. See `AGENTS.md`.
2. **Branch** off `main`, short-lived, named for the slice.
3. **Implement** the slice and its tests together. Type everything. Add the file's
   docstring and its `docs/ARCHITECTURE.md` entry in the same pull request.
4. **Run `mise run verify`** until green. The push hook runs it too, so this is
   the gate rather than a rehearsal for one.
5. **Commit** with a Conventional Commit message. Keep the diff small.
6. **Ask, then open a draft pull request.** Say what would be pushed and wait for
   an explicit yes. Once approved, state in one line what it adds, what runs
   after it merges, and what to look at.
7. **The advisory Linux run reports.** The gate is already green, because the
   push hook would not have let the branch out otherwise; this is the same task
   on a different operating system, and it blocks nothing.
8. **Second-opinion review** in a fresh context, seeing only the diff and the
   spec, scoped to correctness and requirement gaps. Fix what it finds.
9. **Review by a member of CLI.** They approve the spec and the green gate, not the diff line
   by line.
10. **They merge.** Never merge your own.
11. **Record it, when there is something to record.** A decision record when the
    change touched the schema, extraction, a source route, or the cadence; a bug
    record with its guarding test when something was broken. An ordinary slice
    needs neither: the commit is the history.
12. **Then the next slice.**

## Definition of done

Funding-call cards flowing to the feed and the dashboard, the discovery skill
available, the health page and heartbeat live, the admin guides written, and
reports collection plus the first quarterly read turned on.

**The handover test:** a member of CLI adds a source and reads a card unaided, and can
recover from the two most likely first-year failures. A broken source that is
skipped and flagged, and an extraction held after two tries and re-run once
fixed, with `rebuild.py` as the reset.

## When documents disagree

This file and the records in `docs/decisions/` carry the latest settled
decisions and win. If a
detail is genuinely unspecified, prefer the simplest option that honours the
Constitution, open the smallest pull request that proves it, and let a member of CLI
confirm. Do not invent scope, and do not bring back anything on the "must never
appear" list in `AGENTS.md`.
