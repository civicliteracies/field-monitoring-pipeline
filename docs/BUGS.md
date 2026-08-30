# Bug history

Every defect found in Fieldbook and how it was fixed, so the same problem is not
rediscovered later and so a maintainer can see how the system behaves under
stress. Cédric asked the build to keep this record.

**What belongs here.** Something behaved wrongly and was corrected. A wrong
result, a crash, a check that passed when it should have failed, a check that
failed when it should have passed.

**What does not.** A design choice with alternatives goes to
[`docs/DECISIONS.md`](DECISIONS.md). A failure the founders should expect in
production, and what to do about it, goes to `docs/runbook.md` when that is
written at PR 16. The difference in tense is the test: this file records defects
we **already fixed**; the runbook describes failures we **expect**.

**When a bug's fix establishes a lasting rule**, the incident is recorded here and
the rule is recorded as a decision record, and the two link to each other. Neither
file is then incomplete, and nothing is written twice.

**Every fix must add a test that fails on the pre-change behaviour** (RISK 11).
Without it, "fixed" is a claim rather than a fact, and nothing stops the bug
returning. The `Test` field below is not optional.

**Records are immutable and additive**, on the same rule as the decision log. If a
fix turns out to be wrong, add a new record and link the two rather than editing
the old one.

## Format

```
## BUG-NNN — one-line summary
**Status:** Fixed | Open | Superseded by BUG-NNN. **Found:** date. **Fixed:** date. **Owner:** name.
**Symptom.** What was observed, in plain language. What did the wrong thing.
**Cause.** Why it happened. The actual mechanism, not a guess.
**Fix.** What changed, and where.
**Test.** The test that now guards it, and why it fails on the old behaviour.
**Related.** Any decision record, pull request, or other bug.
```

## Index

| # | Status | Title | Found |
|---|---|---|---|
| BUG-001 | Fixed | Retained expired calls failed validation | 2026-08-26 |
| BUG-002 | Fixed | The heartbeat could not distinguish a dropped run from a quiet one | 2026-08-26 |

---

## BUG-001 — Retained expired calls failed validation
**Status:** Fixed (in specification, before any code). **Found:** 2026-08-26. **Fixed:** 2026-08-26. **Owner:** build.

**Symptom.** Validation required a dated call's deadline to be a *future* date, and
it re-ran on every push. So on the day a deadline passed, a call already sitting
in the archive would start failing the check, and the rebuild step would reject
every expired call it tried to re-derive.

**Cause.** A derived, time-varying property was written into the schema as a
stored invariant. "Is this deadline still ahead?" changes with the calendar, so
any record asserting it becomes false through no change of its own. This broke a
stated goal of the system, which is to keep closed calls so the January report can
be found in July and past activity can be counted in the quarterly read.

**Fix.** Validation checks only that the deadline **parses as a valid date**.
Whether it still lies ahead is computed at display time and used to order and flag
calls. The archive keeps closed calls, and `rebuild.py` never rejects one.

**Test.** A closed call, with a deadline in the past, must pass validation and be
written. On the pre-change behaviour this test fails, because the old rule
rejected any non-future deadline. Named in the PR 4 test list.

**Related.** [ADR-0001](DECISIONS.md), which records the resulting rule. This
record predates [ADR-0017](DECISIONS.md), the split of bugs from decisions, so the
rule lives there and the incident lives here.

## BUG-002 — The heartbeat could not distinguish a dropped run from a quiet one
**Status:** Fixed (in specification, before any code). **Found:** 2026-08-26. **Fixed:** 2026-08-26. **Owner:** build.

**Symptom.** The heartbeat was described as written "each run" in some places and
"only after a run that produced data" in others, and was said to make an empty run
visible. Neither version works. If it is written only when data is found, a
healthy quiet week looks identical to a system that has stopped. If it is written
every run, it cannot report emptiness.

**Cause.** Two different failures were assigned to one signal. A run that never
fired and a run that fired but found nothing are separate problems with separate
evidence, and no single indicator can report both.

**Fix.** The heartbeat proves **liveness** alone: it is written on every run that
executes, so a silently dropped run goes stale on the health page, which is the
failure a page cannot otherwise report about itself. Emptiness is a separate
check, the per-source item-count baseline, which flags a usually productive source
returning nothing.

**Test.** Two tests, and they must both hold. A dropped run leaves a stale
heartbeat. An empty but completed run does **not** stale the heartbeat, and
instead raises a baseline flag. The second fails on the pre-change behaviour,
because the old rule withheld the heartbeat when nothing was found. Named in the
PR 14 test list.

**Related.** [ADR-0002](DECISIONS.md), which records the resulting rule. RISK 5 in
the risk register describes the failure mode this guards against.

---

*No build-phase defects yet. The two records above were found during the document
review, before any code existed, which is the cheapest place to find them.*
