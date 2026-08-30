# PR 1 — CI quality gate and one-time project guardrails

**Date:** 2026-08-29 · **Status:** awaiting founder approval · **Owner:** build
**Branch:** `ci/quality-gate` · **Commit type:** `ci: run mise check on every pull request`

## Goal

Make the quality bar that already runs on a contributor's machine also run, and
where possible bind, on GitHub. After this PR, nothing broken and nothing
undocumented can reach `main` without someone deliberately overriding it.

## Why

The scaffold already carries the toolchain: ruff, basedpyright strict, pytest,
commitizen, and git hooks. What is missing is the layer above it. A gate that
only runs locally is a gate the two founders have to remember; a gate that runs
in CI is one they can trust. This PR adds no pipeline code at all.

## Requirements (EARS)

### The CI gate

1. WHEN a pull request is opened or updated against `main`, THE SYSTEM SHALL run
   `mise run check` (format, lint, strict type-check, tests) and report a single
   pass or fail status on the pull request.
2. WHEN a commit is pushed to `main`, THE SYSTEM SHALL run the same check.
3. WHEN the CI workflow runs, THE SYSTEM SHALL install dependencies only from the
   committed `uv.lock`, and SHALL NOT resolve or upgrade a dependency at run time.
4. WHEN the CI workflow references any GitHub Action, THE SYSTEM SHALL pin that
   action to an exact commit SHA rather than a tag or branch.
5. WHEN the CI workflow runs, THE SYSTEM SHALL grant the workflow token
   `contents: read` and no other permission.

### The documentation guards

6. WHEN a file under `src/` has no module docstring, THE SYSTEM SHALL fail the
   lint step (ruff `D100`).
7. WHEN a pull request changes any file under `src/` and does not change
   `docs/ARCHITECTURE.md`, THE SYSTEM SHALL fail the documentation guard.
8. WHEN a pull request body contains the line `docs: n/a`, THE SYSTEM SHALL skip
   the guard in requirement 7 for that pull request.

### The added machine-gate thresholds

9. WHEN a function's cyclomatic complexity exceeds the configured cap, THE SYSTEM
   SHALL fail the lint step (ruff `C901`).
10. WHEN code uses a bare `except` or catches a blind exception, THE SYSTEM SHALL
    fail the lint step (ruff `E722`, `BLE`).
11. WHEN the test suite runs in CI, THE SYSTEM SHALL measure coverage and SHALL
    fail if coverage of the code changed in this pull request falls below 80 per
    cent.
12. WHEN a dependency in `uv.lock` has a known published vulnerability, THE SYSTEM
    SHALL fail the dependency audit step.

### The governance files

13. WHEN the repository is checked out, THE SYSTEM SHALL carry `AGENTS.md` as the
    canonical agent-instructions file, `CLAUDE.md` importing it via `@AGENTS.md`,
    and `constitution.md` holding the six non-negotiables.
14. WHEN a pull request is merged to `main`, THE SYSTEM SHALL require a green
    CI gate and at least one approving review, with bypassing disabled.
    (Founder declined a `CODEOWNERS` file on 2026-08-29: too much process for a
    team of three. Branch protection supplies the enforcement; only the automatic
    routing of reviews to a named path owner is given up.)
15. WHEN the repository is checked out, THE SYSTEM SHALL carry a seeded
    `docs/ARCHITECTURE.md`, a seeded `docs/DECISIONS.md` in ADR form carrying
    ADR-0001 through ADR-0017, a seeded `docs/BUGS.md` carrying BUG-001 and
    BUG-002, and `docs/ACTIVITY.md`.

### The supply chain

16. WHEN a commit is attempted that contains a private key, THE SYSTEM SHALL block
    it (`detect-private-key` pre-commit hook).
17. WHEN a commit is attempted that adds a file above the configured size budget,
    THE SYSTEM SHALL block it (`check-added-large-files` pre-commit hook).
18. WHEN a dependency has a newer version, THE SYSTEM SHALL raise it as a delayed
    Dependabot update rather than applying it automatically
    (`.github/dependabot.yml`).

### The records

Requirements 19 to 21 are stated in the Stop-hook section below, and 22 in the
activity-log section. These two complete the set.

23. WHEN a bug is fixed, THE SYSTEM SHALL record it in `docs/BUGS.md` with its
    symptom, cause, fix, and the test that now guards it, and SHALL NOT accept
    the fix without a test that fails on the pre-change behaviour (RISK 11).
24. WHEN fixing a bug also establishes a lasting rule, THE SYSTEM SHALL record
    the incident in `docs/BUGS.md` and the rule in `docs/DECISIONS.md`, and link
    the two, so neither file is incomplete and nothing is written twice.

## Files touched

- `.github/workflows/ci.yml` (new)
- `.github/workflows/docs-guard.yml` (new, or a job inside `ci.yml`)
- `.github/dependabot.yml` (new)
- `pyproject.toml` (ruff `D100`, `C901`, `BLE`/`E722`; coverage config)
- `.pre-commit-config.yaml` (add `detect-private-key`, `check-added-large-files`)
- `AGENTS.md`, `CLAUDE.md`, `constitution.md` (new, repository root)
- `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/BUGS.md`, `docs/ACTIVITY.md` (new, seeded)
- `uv.lock` + `pyproject.toml` dev group (two new dev dependencies, see below)

## New dependencies requiring founder approval

The Constitution forbids adding a dependency without written approval. Two are
needed to satisfy requirements 11 and 12:

- `pytest-cov` (dev) — measures coverage for the new-code floor.
- `pip-audit` (dev) — the dependency vulnerability gate.

Both are current, widely used, and will be pinned in `uv.lock`.

**Approved by the founder on 2026-08-29.** Requirements 11 and 12 stay in scope.

## Out of scope

- Any pipeline code. No `fetch.py`, no `models.py`, no `config/`, no `data/`.
- `datapackage.json` (proposed for PR 8, once the fields are settled).
- `docs/runbook.md` and `docs/reference.md` (proposed for PR 16).
- The full documentation introspection test. There are no fields or config
  options yet to introspect, so it grows with the PRs that add them.
- The dashboard and anything under `site/` (PR 12, built by the team).

## Resolved: the repository is public

**Cédric made the repository public on 2026-08-29.** Verified: rulesets now return
`[]` rather than `403`. The three items previously blocked are back in scope and
ship in this PR:

- Branch protection on `main`: required CI check, one approving review,
  conversation resolution, linear history, and bypassing disabled.
- Secret scanning with push protection.
- `.github/workflows/scorecard.yml` (OpenSSF Scorecard).

Dependabot alerts are enabled alongside them. GitHub Pages is now available for
the dashboard at PR 12. The repository's full history was scanned before this
change took effect: eleven files, no secret ever committed.

All three settings need a repository admin. The builder holds `push` and not
`admin`, so a founder applies them, or grants admin.

## The end-to-end check that proves it works

1. Open a trivial pull request. The `mise run check` status appears and goes green.
2. Add a file under `src/` with no module docstring. CI fails on `D100`.
3. Change a file under `src/` without touching `docs/ARCHITECTURE.md`. The
   documentation guard fails. Add the `ARCHITECTURE.md` entry; it passes.
4. Attempt to commit a test private key locally. The pre-commit hook blocks it.
5. If public: confirm `main` cannot be merged to without a green check and one
   approval, and that the Scorecard and secret-scanning checks are live.

## Open questions for the founder

1. **Repository visibility.** Resolved 2026-08-29: public. No longer open.
2. **`pytest-cov` and `pip-audit`.** Approved 2026-08-29. No longer open.
3. **The `.claude/` Stop hook.** Researched and settled; see the section below.
   Confirm the approach.
4. **CODEOWNERS.** Declined by the founder on 2026-08-29. No longer open.
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
- An ignored hook must be recreated by hand on every machine. RISK 3 names
  fading maintainer attention as the most likely cause of this project's death,
  so anything that depends on being remembered will eventually be forgotten.

**The guards that answer the residual risk.**

- A change under `.claude/` reaches `main` only as a reviewed pull request with a
  green gate, the same as any other path, since branch protection applies
  repository-wide. This is weaker than a path-specific owner but adequate at this
  team size, and it is the founder's call.
- The Stop hook runs one fixed command, `mise run check`, with nothing dynamic
  and nothing interpolated.
- No secret ever enters the file, since the `env` block is also used before trust.
- `.gitignore` drops the blanket `.claude/` line and ignores
  `.claude/settings.local.json` explicitly, which is what the documentation
  instructs when that file is created by hand.

**Additional requirements this adds to PR 1.**

19. WHEN a Claude Code session attempts to end while `mise run check` fails, THE
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

## Addition: a single activity log replaces the WORKLOG folder

**Requested by the founder on 2026-08-29.**

22. WHEN any action is taken on the project, THE SYSTEM SHALL record it in
    `docs/ACTIVITY.md` as a dated, plain-language entry naming what was done and
    what came of it.

The Build Prompt and the Rulebook specify a journal at `WORKLOG/YYYYMMDD.md`, one
file per day. `docs/ACTIVITY.md` does the same job in one running file, newest day
first. Keeping both would leave two journals competing for the same attention, and
RISK 3 names fading maintainer attention as this project's most likely cause of
death, so the less convenient one would go stale and neither could then be
trusted.

**Proposal:** `docs/ACTIVITY.md` takes the journal role and the `WORKLOG/` folder
is not created. This is a deliberate departure from the Build Prompt, so it needs
founder confirmation and an ADR. The Stage 11 instruction to write a journal entry
after each pull request is unchanged; only the location changes.

The division between the three records stays as the Rulebook describes it:
`ACTIVITY.md` is what happened, `DECISIONS.md` is why and at what cost, and
`ARCHITECTURE.md` is what each file is.

---

## Build checklist

Every item PR 1 must produce, derived from the Build Prompt's PR 1 entry, the
Rulebook's Book B and Stage 0, ADR-0004, and the decisions taken during this
build. Each line names its source so the list is auditable. Tick as built.

**State as of 2026-08-30: 33 of 39 done. PR 1 is open as a draft at pull request #1 with both CI jobs green.**

### A. Repository settings (a founder with admin applies these; the builder has push only)

- [ ] Branch protection on `main`: required CI check, one approving review, conversation resolution, linear history, bypassing disabled — *Build Prompt PR 1; ADR-0014 makes this the sole enforcement*
- [ ] Secret scanning with push protection enabled — *Build Prompt PR 1; ADR-0008*
- [ ] Dependabot alerts enabled — *ADR-0008*
- [ ] Access fix: grant `rezhyarfakhir` direct write, grant `@civicliteracies/admin` write, then remove this repository from the `interns` team, in that order — *least privilege; raised 2026-08-29, still open*

### B. CI workflows

- [x] `.github/workflows/ci.yml`: runs `mise run check` on pull request and push, installs from `uv.lock` only, every action pinned to a commit SHA, token `contents: read` — *Build Prompt PR 1; requirements 1 to 5* — **done 2026-08-30**
- [x] Documentation guard: fails a pull request that changes `src/` without changing `docs/ARCHITECTURE.md`, with a `docs: n/a` opt-out. A job inside `ci.yml` — *Build Prompt section 2; requirements 7 and 8* — **done 2026-08-30**
- [x] `pip-audit` step in CI — *ADR-0004; requirement 12* — **done 2026-08-30**
- [x] `.github/workflows/scorecard.yml`: OpenSSF Scorecard — *ADR-0008* — **done 2026-08-30**

### C. Configuration edits

- [x] `pyproject.toml`: enable ruff `D100`, module docstring required under `src/` — *Build Prompt section 2 and 3; requirement 6* — **done 2026-08-30**
- [x] `pyproject.toml`: complexity cap, ruff `C901` — *ADR-0004; requirement 9* — **done 2026-08-30**
- [x] `pyproject.toml`: no bare or blind except, ruff `E722` and `BLE` — *ADR-0004; requirement 10* — **done 2026-08-30**
- [x] `pyproject.toml`: coverage configuration and the 80 per cent new-code floor — *ADR-0004; requirement 11* — **done 2026-08-30**
- [x] `pyproject.toml` and `uv.lock`: add `pytest-cov` — *approved by founder 2026-08-29* — **done 2026-08-30**
- [x] `pyproject.toml` and `uv.lock`: add `pip-audit` — *approved by founder 2026-08-29* — **done 2026-08-30**
- [x] File-size budget, Python files 150 to 500 lines, split into a package near 500 — *ADR-0004. Not expressible in ruff; needs a small CI check or a pre-commit hook* — **done 2026-08-30**
- [x] `.pre-commit-config.yaml`: add `detect-private-key` — *Build Prompt PR 1; requirement 16* — **done 2026-08-30**
- [x] `.pre-commit-config.yaml`: add `check-added-large-files` — *Build Prompt PR 1; requirement 17* — **done 2026-08-30**
- [x] `.gitignore`: replace the blanket `.claude/` with `.claude/settings.local.json` — *ADR-0015* — **done 2026-08-30**

### D. Governance files

- [x] `constitution.md`: the six non-negotiables — *ADR-0006* — **done 2026-08-30**
- [x] `AGENTS.md`: the canonical, tool-neutral agent instructions — *ADR-0007* — **done 2026-08-30**
- [x] `CLAUDE.md`: the Build Prompt committed, importing `@AGENTS.md`, with build-machine paths stripped — *Build Prompt, start-here box* — **done 2026-08-30**
- [x] `.claude/settings.json`: the Stop hook running `mise run check`, plus deny rules — *ADR-0009, ADR-0015; requirements 19 to 21* — **done 2026-08-30**
- [x] `.github/dependabot.yml`: delayed version updates — *ADR-0008; requirement 18* — **done 2026-08-30**
- [x] ~~`.github/CODEOWNERS`~~ — **declined by the founder**, ADR-0014

### E. The records

- [x] `docs/ARCHITECTURE.md`: the living plain-language map, seeded — *Build Prompt section 2; the docs guard has nothing to check without it* — **done 2026-08-30**
- [x] `docs/DECISIONS.md`: seeded, ADR-0001 to ADR-0017 with an index — *done 2026-08-30*
- [x] `docs/BUGS.md`: seeded, BUG-001 and BUG-002 with the failing-test rule — *done 2026-08-30, ADR-0017*
- [x] `docs/ACTIVITY.md`: the journal — *done 2026-08-29, ADR-0016*
- [x] ~~`CITATION.cff`~~ — **deferred** 2026-08-30. Purely additive, nothing depends on it, and it is not in the Build Prompt's ship list. Add later if CLI wants it.

### F. Environment and Stage 0

- [x] Isolated working tree at `Final\Fieldbook` — *done 2026-08-29*
- [x] `mise run setup`: Python 3.13.15, locked dependencies, git hooks — *done 2026-08-29*
- [x] `mise run check` green on the clean tree — *done 2026-08-29*
- [x] `uv tool install claude-code-tools`, 18 executables installed — *done 2026-08-30*
- [x] Plugin marketplace `cctools-plugins` and all ten plugins, via `claude plugin` in the terminal — *done 2026-08-30*

### G. Proving it works (the deliverable is the demonstration, not the files)

- [x] A trivial pull request shows the gate and goes green — **done 2026-08-30**
- [x] A file under `src/` with no docstring fails on `D100` — **done 2026-08-30**
- [ ] A change under `src/` without an `ARCHITECTURE.md` update fails the docs guard, then passes once the entry is added
- [x] A test private key is blocked by the pre-commit hook — **done 2026-08-30**
- [ ] `main` cannot be merged to without a green check and one approval

### Deliberately deferred, recorded so they are not lost

| Item | Goes to | Source |
|---|---|---|
| `datapackage.json` | PR 8, once fields are settled | Blueprint Parts 3 and 4 |
| `docs/runbook.md`, `docs/reference.md` | PR 16 | ADR-0011 |
| Documentation introspection test | Grows with each PR that adds fields | ADR-0011 |
| Golden-input fixtures, AI readiness note | PR 3 and PR 9 | ADR-0010 |
| Extraction on the scheduled run | After PR 9 and the readiness note | ADR-0010 |
