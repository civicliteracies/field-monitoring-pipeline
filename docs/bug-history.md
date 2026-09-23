# Bug history

Serious faults in Fieldbook: what went wrong, what caused it, and what stops it returning. Open
faults come first, so a reader sees what is wrong today before reading what was wrong before. A fault
keeps its number when it is fixed, and its entry moves down among the fixed faults, which are kept in
two groups: those fixed in earlier work on this design, and those fixed here.

An entry is opened among the open faults when a serious fault is found, and completed in the same
pull request as the fix. Where a fault produced a rule that changes how the tool works, the rule is
written in [`docs/decision-log.md`](decision-log.md) as well, because the code can show the guard but
not the reason for it.

## 0. Open faults

None today.

An open fault is titled the way a reader would describe the symptom, and carries its severity, its
class, what is wrong, what happens in the meantime and what that costs, and the technical detail of
where the fault lives.

## 1. Faults fixed in earlier work

The three below were found while building an earlier version of this design, before anything was
released, and were fixed there. That code is not in this repository, which is being built again from
the start. They are recorded because each one is the reason a rule in this build exists, and each
entry names the change that carries the rule in.

### BUG-001: a run that failed partway kept nothing of what it had collected

**Severity:** high. **Class:** data loss. **Status:** fixed in earlier work; the rule it produced is
carried here.

**Summary.** The daily run saved what it had collected only when the collecting step finished without
an error. When collecting failed partway, nothing was saved, including items already written down.

**Root cause.** The step that saves the run's work was made conditional on the collecting step
succeeding, so one failure cancelled work that had already been done.

**Fix.** The saving step was changed to run whatever happened before it, so what was already written
down is kept even when the run does not finish.

**Prevention.** No step may make its own success a condition of another step's output being kept.

**Technical detail.** The rule lands with change 6 in the plan, whose daily commit saves what was
stored even when the run stopped with an error. Test that now fails on the old behaviour: none yet.

### BUG-002: every day produced a commit, even when nothing had changed

**Severity:** medium. **Class:** correctness of the record. **Status:** fixed in earlier work; the
rule it produced is carried here.

**Summary.** The daily run committed to the archive every morning whether or not anything new had
arrived, so the history filled with changes that changed nothing.

**Root cause.** The note stored beside each item recorded the moment it was collected. That moment
differs on every run, so every item looked new every day.

**Fix.** The note was changed to record the date the source published the item rather than the time
it was collected, and the run was changed to commit only when something had changed.

**Prevention.** Nothing written to the archive may carry a value that changes between runs when the
item has not changed. The same item stored twice produces the same bytes.

**Technical detail.** The rule lands with change 5, which writes each item only when its file does not
exist yet, so nothing stored is ever rewritten, and with change 6, which makes the daily commit and asks
git whether anything is there to commit before making one. Test that now fails on the old behaviour:
none yet.

### BUG-003: line endings were rewritten, so a quote checked on one machine failed on another

**Severity:** high. **Class:** correctness of the evidence. **Status:** fixed in earlier work; the
rule it produced is carried here.

**Summary.** A sentence that matched the stored page on the machine that collected it failed the same
check elsewhere, which would have made honest cards look invented.

**Root cause.** Git converts line endings by itself, through a setting that is on by default on
Windows. The stored text was therefore not the same text everywhere, while the check compares it
exactly.

**Fix.** A rules file on each branch was added to tell git to leave stored text alone, and stored
files were written with one kind of line ending, stated explicitly.

**Prevention.** Anything stored as evidence is written byte for byte and protected from conversion.
Unchanged has to mean unchanged on every machine, including the ones that did not write the file.

**Technical detail.** The setting is git's `core.autocrlf`. In this build the rule is kept without a
rules file: each item is stored as one JSON file, which reads back the same on every machine, and a
quote is compared after whitespace is collapsed, so a changed line ending cannot make it fail. A rules
file returns if raw page files are ever stored as they arrived. Test that now fails on the old
behaviour: none yet.

## 2. Faults fixed in this build

### BUG-004: two copies of the same tool, at two versions, checked the same code

**Severity:** medium. **Class:** correctness of the checks. **Status:** fixed in this build.

**Summary.** The checks git runs before a commit fetched their own copies of ruff and commitizen, at
versions written by hand in the hook settings, while the project installed the versions the lock file
named. The two copies of ruff disagreed about what counts as a mistake: a function whose default
argument calls `range` is an error to 0.16.0 and not to 0.16.1, so the commit hook refused code that
`mise run check` accepted. No wrong result reached this repository, which holds no code to check yet.

**Root cause.** The version of a tool was answered in two places: the lock file, written by the
package manager, and the hook settings, written by hand. A comment in the hook settings asked for ruff
to be kept in step with the lock file, but nothing enforced it, and the two numbers differed from the
day they were written.

**Fix.** Every hook runs its tool from the project's own environment, so the hook settings name no
version at all.

**Prevention.** The hook settings name no version. Every hook runs its tool through `uv run`, the
push hook by way of `mise run verify`, so it uses the copy `uv.lock` pins, the same copy the matching
`mise run` task uses.

**Technical detail.** The hooks are local, with `language: system`, and keep what the published hooks
carried: `--force-exclude`, so a folder the project excludes is left alone even though pre-commit
names files explicitly; the file types the published hooks named, which are Python, stub and
notebook files; and serial execution, because ruff works in parallel by itself. Test that now fails on the
old behaviour: none yet, because this repository holds no code. What can be checked instead is that
the hook settings contain no version number at all.
