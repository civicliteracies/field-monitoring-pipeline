# Bug history

Every defect found in Fieldbook, what caused it, what fixed it, and the test that
now guards it. Newest first.

**Why this file exists.** So the same problem is not rediscovered later, and so
anyone maintaining Fieldbook can see how it behaves under stress without having
to open closed issues one at a time. A changelog line says what changed for
someone using Fieldbook. This says what broke, and why.

**What goes in it.** A defect in how the system behaves: wrong output, a crash, a
requirement with nothing behind it, a check that could never fire. Not a wording
correction to a document, and not the removal of code nothing used. Those are
ordinary work, and a history that carries everything stops being read.

**How it sits with the other records.** A defect lives in the repository's issue
tracker while it is open and comes here once it is fixed. It also gets a line
under `Fixed` in [`CHANGELOG.md`](../CHANGELOG.md) when someone using Fieldbook
would notice the difference. When a fix establishes a lasting rule, that rule
becomes a numbered record in [`docs/decisions/`](decisions/), and the two link to
each other so neither has to repeat the other. See
[ADR-0025](decisions/0025-conventional-file-layout.md).

**A fix is not accepted without a test that fails on the pre-change behaviour.**
Every entry below names its test. Where a defect was found in the specification
before the code it concerns existed, the entry says which slice brings the test.

---

## BUG-002 — The heartbeat was described two ways and worked as neither

**Found** 2026-08-26, in the specification, before the code existed.

**Symptom.** The heartbeat was described in some places as written on every run
and in others as written only after a run that produced data, and was said to
make an empty run visible. Neither version does that.

**Cause.** One mechanism was being asked to prove two different things: that a run
happened at all, and that a run found something.

**Fix.** The heartbeat proves liveness only. It is written on every run that
executes, so a run that is silently dropped goes stale, which is the real alarm.
Whether a run found anything is a separate check, the per-source item count
baseline.

**Rule this established.**
[ADR-0002](decisions/0002-heartbeat-proves-liveness-not-emptiness.md).

**Test.** Arrives with the health page and the heartbeat at PR 7 and PR 14, where
this behaviour is built.

## BUG-001 — A passing deadline would have made a stored call fail validation

**Found** 2026-08-26, in the specification, before the code existed.

**Symptom.** Validation required a dated call's deadline to parse as a date in the
future, and validation re-runs on every push. The day a deadline passed, the
stored call would fail its check and the rebuild step would reject every expired
call. Keeping closed calls is a stated goal: finding the January report in July,
and counting past activity in the quarterly read.

**Cause.** Whether a call is still open was treated as a property of the stored
record rather than as something worked out when the call is shown.

**Fix.** The permanent check is that the deadline parses as a valid date. Open
against closed is derived from today's date at the moment of display, and the
archive keeps closed calls.

**Rule this established.**
[ADR-0001](decisions/0001-deadline-validates-as-a-valid-date.md).

**Test.** Arrives with validation at PR 4, where this rule is implemented.
