# PR 1 — the quality gate and one-time project guardrails

**Date:** 2026-08-29 · **Status:** ready to propose · **Owner:** build
**Branch:** `chore/quality-gate` · **Commit type:** `chore: run the whole gate before every push`

## Goal

Make the quality bar bind. Every check this project has runs on the maintainer's
machine before anything is pushed, so nothing broken and nothing undocumented can
leave here without someone deliberately overriding the hook.

## Why

The scaffold already carries the toolchain: ruff, basedpyright strict, pytest,
commitizen, and git hooks. What is missing is the layer above it. The hooks ran
the tests and nothing else, so strict type-checking ran nowhere automatic. This PR
makes the whole gate one command that runs before every push. It adds no pipeline
code at
all. Checks live on the maintainer's machine rather than on GitHub, per
[ADR-0021](../docs/decisions/0021-every-check-runs-on-the-maintainers-machine.md).

## Requirements (EARS)

### The local gate

1. WHEN anything is pushed from this machine, THE SYSTEM SHALL run
   `mise run verify` first and SHALL refuse the push if any part of it fails.
2. WHEN `mise run verify` runs, THE SYSTEM SHALL check formatting, lint,
   type-check in strict mode, and run the tests, and SHALL NOT modify any file
   while doing so.
3. WHEN every dev tool is declared, THE SYSTEM SHALL pin it to an exact version
   rather than a range, so a version changes only when someone changes it
   deliberately and that change arrives as a pull request to be discussed.
4. WHEN `uv.lock` and `pyproject.toml` disagree, uv SHALL refuse to run. No
   separate check is added: this behaviour comes with the tool.

### Documentation

5. WHEN a file under `src/` has no module docstring, THE SYSTEM SHALL fail the
   lint step (ruff `D100`).
6. WHEN a change makes a file's entry in `docs/ARCHITECTURE.md` wrong, the same
   change SHALL fix the entry. This is a working rule and is deliberately not
   automated: a check firing on every edit to a covered file also fires on
   changes below the level the entry describes, and a check that cries wolf gets
   ignored.

7 and 8. **Withdrawn 2026-08-31.** They required a mechanical documentation guard
   and its opt-out. Requirement 6 replaces them. Numbering is left as it was so
   every cross-reference below still points at the right thing. See ADR-0022.

### The added machine-gate thresholds

9. WHEN a function's cyclomatic complexity exceeds the configured cap, THE SYSTEM
   SHALL fail the lint step (ruff `C901`).
10. WHEN code uses a bare `except` or catches a blind exception, THE SYSTEM SHALL
    fail the lint step (ruff `E722`, `BLE`).
11. WHEN the test suite runs, THE SYSTEM SHALL measure coverage and SHALL fail if
    total coverage falls below 80 per cent. This is whole-project coverage, not
    coverage of the lines changed. True diff coverage needs a further dependency,
    and this is the boring approximation until it proves inadequate.
12. **Withdrawn 2026-08-31.** It required a vulnerability scan in the gate.
    Requirement 3 replaces it: versions are pinned exactly, so a change to one
    arrives as a pull request and is discussed there. See ADR-0022.

### The governance files

13. WHEN the repository is checked out, THE SYSTEM SHALL carry `AGENTS.md` as the
    canonical agent-instructions file, `CLAUDE.md` importing it via `@AGENTS.md`,
    and `constitution.md` holding the six non-negotiables.
14. WHEN a change reaches `main`, THE SYSTEM SHALL require that it arrives as a
    pull request, and SHALL block force-pushes and deletion of the branch.
    (A code owners file was declined on 2026-08-29 as too much process for a team
    of three. No status check and no approval count are required: the whole gate
    runs before every push instead. See [ADR-0021](../docs/decisions/0021-every-check-runs-on-the-maintainers-machine.md).)
15. WHEN the repository is checked out, THE SYSTEM SHALL carry a seeded
    `docs/ARCHITECTURE.md`, a seeded `docs/decisions/` holding ADR-0001 through
    ADR-0025 as one numbered file per record with an index beside them, and a
    `CHANGELOG.md` opening with an `Unreleased` section.

### The supply chain

16. WHEN a commit is attempted that contains a private key, THE SYSTEM SHALL block
    it (`detect-private-key` pre-commit hook).
17. WHEN a commit is attempted that adds a file above the configured size budget,
    THE SYSTEM SHALL block it (`check-added-large-files` pre-commit hook).
18. **Withdrawn 2026-08-31.** It required automatic dependency update proposals,
    then a vulnerability scan. Requirement 3 replaces both: a version changes only
    when someone changes it, and that change is discussed on its pull request.

### The records

Requirements 19 to 21 are stated in the Stop-hook section below, and 22 in the
journal section below. These two complete the set.

23. WHEN a bug is fixed, THE SYSTEM SHALL NOT accept the fix without a test that
    fails on the pre-change behaviour, and SHALL record the fix under `Fixed` in
    `CHANGELOG.md`. An open defect belongs in the repository's issue tracker.
24. WHEN fixing a bug also establishes a lasting rule, THE SYSTEM SHALL record
    that rule as a numbered record in `docs/decisions/`, so the reasoning
    survives beyond the one changelog line. See
    [ADR-0025](../docs/decisions/0025-conventional-file-layout.md).

### The advisory run

25. WHEN a pull request is opened, THE SYSTEM SHALL run `mise run verify` on Linux
    and report the result, and SHALL NOT block the merge on it. Its purpose is the
    operating system: every check it runs has already run on the maintainer's
    machine, and Linux is the one thing that gate cannot see.

## Files touched

- `mise.toml` (the `verify` task: the gate, read-only)
- `.github/workflows/ci.yml` (new, the advisory Linux run)
- `pyproject.toml` (ruff `D100`, `C901`, `BLE`/`E722`; coverage config; dev tools pinned to exact versions)
- `.pre-commit-config.yaml` (add `detect-private-key`, `check-added-large-files`; run the gate on push)
- `AGENTS.md`, `CLAUDE.md`, `constitution.md`, `CHANGELOG.md` (new, repository root)
- `CONTRIBUTING.md` (the rule that a bug fix carries a failing test)
- `docs/ARCHITECTURE.md` (new, seeded)
- `docs/decisions/` (new: ADR-0001 to ADR-0025, one file per record, plus the index)
- `specs/001-quality-gate.md` (this file)
- `uv.lock` (regenerated when the dev group was pinned)

## New dependencies requiring approval from a member of CLI

The Constitution forbids adding a dependency without written approval. One is
needed, to satisfy requirement 11:

- `pytest-cov` (dev) — measures coverage for the new-code floor.

**Approved by a member of CLI on 2026-08-29.** `pip-audit` was approved on the same
day and has since been removed: requirement 12 is withdrawn, and pinning exact
versions does the job instead. Every dev tool is now pinned to an exact version
rather than a range.

## Out of scope

- Any pipeline code. No `fetch.py`, no `models.py`, no `config/`, no `data/`.
- `datapackage.json` (proposed for PR 8, once the fields are settled).
- `docs/runbook.md` and `docs/reference.md` (proposed for PR 16).
- The full documentation introspection test. There are no fields or config
  options yet to introspect, so it grows with the PRs that add them.
- The dashboard and anything under `site/` (PR 12, built by the team).

## Resolved: the repository is public

**The repository was made public on 2026-08-29.** Verified: rulesets now return
`[]` rather than `403`. The three items previously blocked are back in scope and
ship in this PR:

- Branch rules on `main`: a pull request required for every change, no
  force-push, no deletion.
- Secret scanning with push protection.
- Dependabot alerts, the setting that emails when a library we already use is
  found to have a security hole.

The OpenSSF Scorecard workflow was dropped with the rest of the GitHub automation;
see [ADR-0021](../docs/decisions/0021-every-check-runs-on-the-maintainers-machine.md). GitHub Pages is available for the dashboard
at PR 12. The repository's full history was scanned before the change took effect:
eleven files, no secret ever committed.

The two settings still outstanding need a repository admin. The builder holds
`push` and not `admin`, so a member of CLI applies them.

## The `main` ruleset as configured

A ruleset named `PR-only` was applied to `refs/heads/main` on 2026-08-30. Read
back from the API, it enforces three things: a pull request is required for every
change to `main`, force-pushing to `main` is blocked, and deleting `main` is
blocked. Direct pushes to `main` are therefore impossible, which was its purpose.

Two of the five requirements listed above are still missing. The ruleset sets
`required_approving_review_count: 0` and carries no status-check rule, so **a
pull request with a failing quality gate can be merged, and can be merged by its
own author.** Neither is being added. A required check is redundant at this team
size, because the whole gate runs in the pre-push hook and the team agrees to run
it, and an unreviewed self-merge is a matter of team agreement rather than
repository risk.

Enforcement lives in the pre-push hook, which runs the whole gate before anything
leaves the machine. One advisory workflow runs the same gate on Linux for every
pull request, because a local gate cannot see an operating system it does not run
on; it reports and blocks nothing, so there is still no status check to require.
Recorded as [ADR-0021](../docs/decisions/0021-every-check-runs-on-the-maintainers-machine.md) and
[ADR-0023](../docs/decisions/0023-one-advisory-linux-run.md). This departs from the original plan, which asked
for the gate to enforce on GitHub, and the departure is written down rather than
left to drift.

The ruleset lists no bypass actors, and none is needed. The scheduled run commits
to its own branch rather than to `main`, so the pull request rule never applies to
it and nothing has to be excepted. See [ADR-0018](../docs/decisions/0018-scheduled-run-commits-to-its-own-branch.md).

Recording this here discloses nothing: on a public repository the ruleset is
served in full to anonymous callers, and it describes the repository's own
configuration rather than any person's access.

## The end-to-end check that proves it works

1. Run `mise run verify` on a clean tree. Every part passes.
2. Add a file under `src/` with no module docstring. The gate fails on `D100`.
3. Attempt to commit a test private key. The pre-commit hook blocks it before the
   commit exists.
4. Attempt to push with any part of the gate red. The push is refused.
5. Confirm `main` refuses a direct push and takes changes only by pull request.
6. Open the pull request and confirm the Linux run appears and goes green, and
   that a red one would not prevent a merge.

## Open questions for CLI

1. **Repository visibility.** Resolved 2026-08-29: public. No longer open.
2. **`pytest-cov` and `pip-audit`.** Approved 2026-08-29. `pip-audit` has since been removed, ADR-0022. No longer open.
3. **The `.claude/` Stop hook.** Researched and settled; see the section below.
   Confirm the approach.
4. **CODEOWNERS.** Declined by a member of CLI on 2026-08-29. No longer open.
   Branch protection carries the enforcement instead.

## Decision: the `.claude/` Stop hook is committed, and treated as a dangerous path

**Researched 2026-08-29 against the Claude Code documentation.** This supersedes
the blanket `.claude/` entry currently in `.gitignore`.

**What the documentation establishes.** `.claude/settings.json` is the shared
project scope: "In a git repository, commit it so teammates get it", carrying
"Team permissions, hooks, plugins, and the environment variables the project
needs", and described elsewhere as "settings your team checks into source
control". The personal counterpart, `.claude/settings.local.json`, is added to
the user's global git excludes by Claude Code, not to the repository's
`.gitignore`.

**The security position, stated accurately.** The permissions page table "What
runs before you trust a folder" shows that `permissions.allow` rules and
`additionalDirectories` wait for the workspace trust dialog, while `deny` and
`ask` rules "aren't affected, since they only restrict" and therefore bind
immediately on any clone. Hooks in settings files, however, are marked "Used" in
both untrusted situations (a trusted parent folder, and a `claude -p` or SDK
run), so a committed hook is executable content that can run without a dialog in
those two paths.

**Decision.** Commit `.claude/settings.json`, and guard it.

- It is the documented, intended design.
- Committed `deny` rules are the only mechanism that makes the Constitution's
  hard limits bind mechanically on any clone from the first second, with no
  trust step. An uncommitted file provides no such fence. This directly serves
  ADR-0006.
- An ignored hook must be recreated by hand on every machine. Fading attention is
  the most likely cause of this project's death, so anything that depends on being
  remembered will eventually be forgotten.

**The guards that answer the residual risk.**

- A change under `.claude/` reaches `main` only as a reviewed pull request with a
  green gate, the same as any other path, since branch protection applies
  repository-wide. This is weaker than a path-specific owner but adequate at this
  team size, and it is CLI's call.
- The Stop hook runs one fixed command, `mise run verify`, with nothing dynamic
  and nothing interpolated.
- No secret ever enters the file, since the `env` block is also used before trust.
- `.gitignore` drops the blanket `.claude/` line and ignores
  `.claude/settings.local.json` explicitly, which is what the documentation
  instructs when that file is created by hand.

**Additional requirements this adds to PR 1.**

19. WHEN a Claude Code session attempts to end while `mise run verify` fails, THE
    SYSTEM SHALL refuse to end the turn (Stop hook in `.claude/settings.json`).
20. WHEN the repository is cloned, THE SYSTEM SHALL apply its `deny` rules
    without requiring the workspace trust step.
21. WHEN a pull request changes anything under `.claude/`, THE SYSTEM SHALL
    require the same green gate and one approving review as any other change,
    since branch protection covers every path equally.

**Files this adds to the list above:** `.claude/settings.json` (new),
`.gitignore` (replace the `.claude/` line).

**Sources.** Claude Code settings documentation (`code.claude.com/docs/en/settings`),
permissions documentation, section "Project allow rules and workspace trust" and
the table "What runs before you trust a folder"
(`code.claude.com/docs/en/permissions`).

## The journal is not published

22. **Withdrawn 2026-08-31.** It required a journal in the repository recording
    every action taken on the project.

The original plan specified a journal at `WORKLOG/YYYYMMDD.md`, one file per day.
That became a single running file, and that file is now out of the repository
entirely. A journal records how the work was made rather than what was built, and
this repository's own test asks exactly that question of anything written here.
The commit history already publishes what was done and when, with an author and a
date on every entry, so a prose journal beside it was a second copy that could
drift and that alone could carry a name, an access detail, or a reference to
something a reader cannot open. It continues in the team's private notes.

Two records stay, and each describes the system rather than its making:
`docs/decisions/` is why a choice was made and what it costs, and
`docs/ARCHITECTURE.md` is what each file is. `CHANGELOG.md` sits with them,
recording what changed for anyone using Fieldbook. See
[ADR-0024](../docs/decisions/0024-build-journal-is-not-published.md) and
[ADR-0025](../docs/decisions/0025-conventional-file-layout.md).

---

## Build checklist

Every item PR 1 must produce, derived from the original plan, ADR-0004, and the
decisions taken during this build. Each line names its source so the list is auditable. Tick as built.

**State as of 2026-08-31: 38 of 40 done, and the two remaining are deferred to PR 3, where the first key exists. Everything in PR 1's own scope is finished and `mise run verify` is green. Not yet proposed.**

### A. Repository settings (these need a repository admin to apply)

- [x] Ruleset on `main`: pull request required, force-push blocked, deletion blocked — *applied by a repository admin 2026-08-30*
- [x] ~~Ruleset additions: a required status check and an approving review~~ — **not being added**, ADR-0021 and ADR-0022. The whole gate runs before every push, so there is no build-server check left to require, and merge review is a matter of team agreement rather than a repository rule
- [ ] Secret scanning with push protection enabled — *ADR-0008. Deferred to PR 3, where the first key exists. Apply it while PR 3 is being prepared, not after it ships: the point is that no key is ever pushed unprotected*
- [ ] Dependabot alerts enabled, the setting that emails when a library already in use is found to have a security hole — *ADR-0008. Deferred to PR 3 with the secret scanning, applied at the same time and before PR 3 ships, since both are settings changes and worth doing in one go*

### B. The gate, on the maintainer's machine

- [x] `mise run verify`: formatting checked, lint, strict type-check, tests, and it modifies nothing — *requirements 1 and 2* — **done 2026-08-31**
- [x] The pre-push hook runs `mise run verify`, so a red gate never leaves this machine — *requirement 1* — **done 2026-08-31**
- [x] Every dev tool pinned to an exact version in `pyproject.toml` — *requirement 3* — **done 2026-08-31**
- [x] `.github/workflows/ci.yml`: `mise run verify` on Linux for every pull request, advisory, every action pinned to a commit SHA, token `contents: read` — *requirement 25; ADR-0023* — **done 2026-08-31**
- [x] ~~GitHub workflows for any of the above~~ — **removed 2026-08-31**, ADR-0021. GitHub runs the scheduled scraping job and nothing else
- [x] ~~`uv lock --check`, `pip-audit`, a file-size script, and a documentation-guard script inside the gate~~ — **removed 2026-08-31**, ADR-0022. uv already refuses to run when the dependency files disagree; pinned versions plus a discussed pull request cover the rest

### C. Configuration edits

- [x] `pyproject.toml`: enable ruff `D100`, module docstring required under `src/` — *requirement 6* — **done 2026-08-30**
- [x] `pyproject.toml`: complexity cap, ruff `C901` — *ADR-0004; requirement 9* — **done 2026-08-30**
- [x] `pyproject.toml`: no bare or blind except, ruff `E722` and `BLE` — *ADR-0004; requirement 10* — **done 2026-08-30**
- [x] `pyproject.toml`: coverage configuration and the 80 per cent new-code floor — *ADR-0004; requirement 11* — **done 2026-08-30**
- [x] `pyproject.toml` and `uv.lock`: add `pytest-cov` — *approved by a member of CLI 2026-08-29* — **done 2026-08-30**
- [x] ~~`pyproject.toml` and `uv.lock`: add `pip-audit`~~ — **removed 2026-08-31**, ADR-0022. Replaced by pinning every dev tool to an exact version
- [x] ~~File-size budget, Python files 150 to 500 lines~~ — **removed 2026-08-31**, ADR-0022. A cap on files that do not exist yet, guarding a problem nobody here has had
- [x] `.pre-commit-config.yaml`: add `detect-private-key` — *requirement 16* — **done 2026-08-30**
- [x] `.pre-commit-config.yaml`: add `check-added-large-files` — *requirement 17* — **done 2026-08-30**
- [x] `.gitignore`: replace the blanket `.claude/` with `.claude/settings.local.json` — *ADR-0015* — **done 2026-08-30**

### D. Governance files

- [x] `constitution.md`: the six non-negotiables — *ADR-0006* — **done 2026-08-30**
- [x] `AGENTS.md`: the canonical, tool-neutral agent instructions — *ADR-0007* — **done 2026-08-30**
- [x] `CLAUDE.md`: the build sequence and the working loop, importing `@AGENTS.md` and `@constitution.md`, with build-machine paths stripped — *the original plan* — **done 2026-08-30**
- [x] `.claude/settings.json`: the Stop hook running `mise run verify`, plus deny rules — *ADR-0009, ADR-0015; requirements 19 to 21* — **done 2026-08-30**
- [x] ~~`.github/dependabot.yml`: delayed version updates~~ — **removed 2026-08-31**, ADR-0021. Pinned versions plus a discussed pull request cover it
- [x] ~~`.github/CODEOWNERS`~~ — **declined by a member of CLI**, ADR-0014

### E. The records

- [x] `docs/ARCHITECTURE.md`: the living plain-language map, seeded — *so the project can be handed over* — **done 2026-08-30**
- [x] `docs/decisions/`: seeded, ADR-0001 to ADR-0025, one numbered file per record with an index — *done 2026-09-01, ADR-0025*
- [x] `CHANGELOG.md`: opened with an `Unreleased` section, Keep a Changelog format — *done 2026-09-01, ADR-0025*
- [x] `specs/001-quality-gate.md`: this specification, numbered rather than dated — *done 2026-09-01, ADR-0025*
- [x] ~~`docs/BUGS.md`: seeded, BUG-001 and BUG-002 with the failing-test rule~~ — **retired 2026-09-01**, ADR-0025. No convention exists for a bug log file: the tracker holds open defects, the changelog holds fixed ones, and the failing-test rule moved to `CONTRIBUTING.md`
- [x] ~~`docs/ACTIVITY.md`: the journal~~ — **removed 2026-08-31**, ADR-0024. A journal records how the work was made, not what was built; it continues in the team's private notes
- [x] ~~`CITATION.cff`~~ — **deferred** 2026-08-30. Purely additive, nothing depends on it, and nothing later assumes it. Add later if CLI wants it.

### F. Environment and Stage 0

- [x] Isolated working tree at `Final\Fieldbook` — *done 2026-08-29*
- [x] `mise run setup`: Python 3.13.15, locked dependencies, git hooks — *done 2026-08-29*
- [x] `mise run verify` green on the clean tree — *done 2026-08-29*
- [x] `uv tool install claude-code-tools`, 18 executables installed — *done 2026-08-30*
- [x] Plugin marketplace `cctools-plugins` and all ten plugins, via `claude plugin` in the terminal — *done 2026-08-30*

### G. Proving it works (the deliverable is the demonstration, not the files)

- [x] A trivial pull request shows the gate and goes green — **done 2026-08-30**
- [x] A file under `src/` with no docstring fails on `D100` — **done 2026-08-30**
- [x] A test private key is blocked by the pre-commit hook — **done 2026-08-30**
- [x] ~~`main` cannot be merged to without a green check and one approval~~ — **not being added**, ADR-0021. This demonstrated a requirement that was dropped. What `main` does enforce, a pull request for every change and no force-push or deletion, is already live

### Deliberately deferred, recorded so they are not lost

| Item | Goes to | Source |
|---|---|---|
| `datapackage.json` | PR 8, once fields are settled | the original plan |
| `docs/runbook.md`, `docs/reference.md` | PR 16 | ADR-0011 |
| Documentation introspection test | Grows with each PR that adds fields | ADR-0011 |
| Golden-input fixtures, AI readiness note | PR 3 and PR 9 | ADR-0010 |
| Extraction on the scheduled run | After PR 9 and the readiness note | ADR-0010 |
