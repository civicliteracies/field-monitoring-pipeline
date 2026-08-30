# Activity log

Everything done on Fieldbook, in order, newest day first. One line or one short
block per action, with the outcome and anything it changed.

This is the project's journal. It answers "what happened, and when", in plain
language. Two other records sit beside it and do different jobs:

- `docs/DECISIONS.md` holds numbered ADRs: why a choice was made, and what it costs.
- `docs/ARCHITECTURE.md` holds the map: what each file is and does.

If an entry below records a real decision, it also has an ADR. If it records a
code change, the file's own docstring and the architecture map carry the detail.

**Convention.** Add entries as you go, not at the end of the day. Say what was
done and what came of it. Name the person or the tool. Keep it plain: someone
picking this project up in a year should be able to follow it without asking.

---

## 2026-08-29

**Read the full build documentation set.** All ten documents, in the order the
kickoff prompt gives: the Build Prompt, the Rulebook and Process, the Technical
Blueprint, the Deployment Plan, the Decision Log, RISKS, the Build Plan, the
Technology Assessment, the Design Report, and the Brand Guide. Five exist only as
Word files and `pandoc` is not installed on the build machine, so they were
converted with a short Python script reading the documents' XML directly.

**Checked the build machine.** git and the GitHub CLI present. Python 3.14.6
present. `uv`, `mise`, `pre-commit`, and `commitizen` were missing.

**Checked the repository.** `civicliteracies/field-monitoring-pipeline` exists,
default branch `main`, and holds the scaffold the Build Prompt describes:
`pyproject.toml`, `uv.lock`, `mise.toml`, `.pre-commit-config.yaml`,
`.python-version`, `CONTRIBUTING.md`, `README.md`, the package directory, and one
placeholder test.

**Found that the repository is private and the organisation is on the free plan.**
GitHub returns `403 Upgrade to GitHub Pro or make this repository public` for
rulesets. Branch protection, secret scanning with push protection, the OpenSSF
Scorecard, GitHub Pages, and CODEOWNERS are therefore all unavailable while the
repository stays private on this plan. This blocks part of PR 1 and was raised
with the founders. Still open.

**Wrote the pre-build confirmation for the founder**, restating the mission, the
invariants, the architecture, and the nineteen-pull-request sequence, and flagging
seven contradictions or gaps found across the documents.

**Toolchain installed** by Rezhyar: `uv 0.12.7` and `mise 2026.8.5`, both on the
user PATH.

**Set up the isolated working tree.** Cloned the repository to
`CLI_Design/Final/Fieldbook`, as the kickoff prompt requires. An older clone
exists elsewhere on the machine; it was checked (clean, in sync, nothing
unpushed) and left untouched.

**Ran `mise run setup`.** Installed Python 3.13.15, synced the locked
dependencies, and installed the pre-commit, pre-push, and commit-msg hooks.

**Ran `mise run check` on the clean tree. Green.** Lint passed, formatting
unchanged, basedpyright reported 0 errors in strict mode, 1 test passed.
This is the baseline before any Fieldbook code exists.

**Set the commit identity.** First to a display name and a personal address, then
corrected: the authenticated account is `rezhyarfakhir`, not `rezhyarfakhir-dev`
as the CLI label suggested. Final identity is
`rezhyarfakhir <257621542+rezhyarfakhir@users.noreply.github.com>`, set locally on
this repository only. This attributes every commit to the GitHub profile, shows
the avatar, and counts in both contributor graphs, while keeping a personal
address out of a permanently public history. It matches the form already used in
this repository by `clombion`.

**Wrote the PR 1 specification** to `issues/20260829-pr-01-ci-quality-gate.md`, in
EARS form. Covers the CI gate, the two documentation guards, the added
thresholds, the governance files, and the supply-chain hooks. Explicitly excludes
all pipeline code.

**Founder approved two new dev dependencies:** `pytest-cov` for the new-code
coverage floor, and `pip-audit` for the dependency vulnerability gate. Required
under the Constitution's no-new-dependency rule.

**Researched whether `.claude/settings.json` should be committed.** The
documentation is explicit that it is the shared project scope and should be
committed, hooks included. The commonly repeated claim that workspace trust gates
committed hooks is wrong: hooks in settings files run even in the two untrusted
situations, while `deny` and `ask` rules apply immediately with no trust step.
Decision: commit it, and guard it through CODEOWNERS like the workflow files.
Recorded in the PR 1 spec; to become an ADR.

**Researched the CODEOWNERS question.** A whole organisation is not a valid code
owner; only a user, an organisation team, or an email address. Founder chose the
`@civicliteracies/admin` team. That team currently has no access to this
repository, and GitHub requires a code-owner team to hold explicit write access,
so a founder must grant it.

**Found an access problem.** The repository has no direct collaborators at all.
Everyone reaches it through org roles and teams, and the only team with write here
is `interns`, which includes a person not working on this project. Removing that
team's access would also revoke the builder's access, so the fix has a required
order: grant direct write first, then remove the team. Raised with the founders.
Still open.

**Researched how non-code contributions are credited.** Reviewed `CITATION.cff`,
the All Contributors specification, and the CRediT taxonomy. Recommended
`CITATION.cff` plus a short hand-written roles section, and recommended against
the All Contributors bot because it adds a second writer to the repository and a
new moving part, which the Constitution's boring-technology rule discourages.
Scope question raised with the founder. Still open.

**Created this activity log**, and proposed that it take the place of the
`WORKLOG/YYYYMMDD.md` folder the Build Prompt describes, so the project keeps one
journal rather than two. Needs founder confirmation and an ADR.

**Status at end of day.** No Fieldbook code written. No commit made. No branch
cut. The PR 1 specification is written and waiting on founder approval, and three
questions are open: repository visibility, whether `CITATION.cff` is in scope, and
the access fix.

**Founder decisions received (Cédric).**

- **The repository is now public.** Verified: rulesets return `[]` rather than the
  previous `403`, so branch protection, secret scanning with push protection, the
  OpenSSF Scorecard, and GitHub Pages are all available. This unblocks PR 1.
- **No `CODEOWNERS` file.** Cédric's reasoning: too much process for three
  collaborators who can simply talk to each other, and the pattern belongs in
  larger teams. Accepted. Branch protection requiring one approving review still
  supplies the enforcement; what is given up is the automatic routing of reviews
  to a named owner for specific paths. The PR 1 spec was updated: requirements 14
  and 21 rewritten, `.github/CODEOWNERS` removed from the file list.
- **Question raised:** why does the project need repository secrets? To be
  answered before his review on Monday 2026-08-31.

**Scanned the full history before the repository went public.** Eleven files have
ever been committed, and no key or credential appears in any commit. The only
matches for secret-shaped strings are the `.gitignore` comments warning against
committing secrets. Safe to be public.

**Still needed from a founder:** the three repository settings above all require
admin, which the builder does not hold. Also outstanding: the access fix, since
Richard still reaches this repository through the `interns` team.

## 2026-08-30

**Split the bug history from the decision log.** The Build Prompt treats
`docs/DECISIONS.md` as both records in one file, separated by a `[correctness]` or
`[decision]` tag. Rezhyar argued they answer different questions for different
readers, and that is right: "why is it built this way" and "what broke and how was
it fixed" are not the same question, and a founder diagnosing a problem should not
have to filter architecture records to find real defects.

The one genuine complication is that some entries are both. BUG-001 is the proof:
a defect whose fix established a lasting design rule. That is resolved by linking
rather than merging. The incident goes in `BUGS.md`, the rule goes in
`DECISIONS.md`, and the two point at each other, so each file answers its own
question completely and nothing is written twice. Recorded as ADR-0017.

**Seeded `docs/DECISIONS.md`.** The twelve records from the document phase carried
across verbatim, since accepted records are never rewritten, plus five new ones
from this week: the repository going public, no CODEOWNERS, the committed agent
configuration, the single activity log, and this split. Seventeen records with a
scannable index.

**Seeded `docs/BUGS.md`.** BUG-001 and BUG-002 written up in full with symptom,
cause, fix, the test that guards each, and a link back to their decision records.
The file states the rule from RISK 11 that a fix is not accepted without a test
that fails on the pre-change behaviour. No build-phase defects yet.

**Checked the plugin setup and found a gap.** Step 3 of the Build Prompt's
one-time setup, installing the `pchalasani/claude-code-tools` marketplace and its
ten plugins, has not been done. Only `claude-plugins-official` is installed.
Verified before recommending: the marketplace repository is real, 1,987 stars,
updated 2026-08-29, and `claude-code-tools` on PyPI is real at version 1.25.6.
The `/plugin` commands are interactive and must be run by a person;
`uv tool install claude-code-tools` can be run from a shell. Neither blocks the
build, since the practices those skills encode are being followed by hand, but
that means the discipline rests on memory rather than tooling.

**Installed the plugin marketplace and all ten plugins, from the terminal.** The
Build Prompt gives these as interactive `/plugin` commands, and I had reported
them as something only a person could run. That was wrong: the Claude Code CLI
exposes `claude plugin marketplace add` and `claude plugin install`, so the whole
of Stage 0's tooling step can be done from a shell.

Added the `cctools-plugins` marketplace from `pchalasani/claude-code-tools`, then
installed all ten: safety-hooks, workflow, writing, aichat, tmux-cli, langroid,
voice, voxtype, msg, agent-tunnel. Two of them, `workflow` and `aichat`, failed
first time with a Windows `EPERM` on rename. The target directories were empty,
which pointed to a transient file lock rather than a real conflict, and both
installed on a straight retry. The two orphaned temp directories were removed.

Also ran `uv tool install claude-code-tools`, which the `tmux-cli` and `aichat`
plugins depend on. It installed 18 executables, including `tmux-cli`, `aichat`,
`msg`, `agent-tunnel`, `vault`, and `env-safe`, all resolving on PATH. The package
was verified as real on PyPI before installing, at version 1.25.6, per the
Constitution's rule against unverified dependencies.

**Note:** plugins load at session start, so their skills become available to the
agent in the next session rather than this one.

**Audited PR 1 against a derived checklist.** Rezhyar pointed out that
`docs/ARCHITECTURE.md` had not been created, and that work was proceeding
reactively rather than from a list. Both true. The Rulebook points at an "update
map" holding the full new-file footprint, and that document is not on this
machine, so the footprint was derived from the Build Prompt's PR 1 entry, the
Rulebook's Book B and Stage 0, and ADR-0004. The result is a 39-item checklist
written into the PR 1 spec, each item tagged to its source document. Nine done.

**Deferred `CITATION.cff` out of PR 1.** It was proposed to answer the problem that
GitHub's contributor graph counts only commits, so design and research work is
invisible there. Rezhyar's reasoning for deferring is sound: nothing in the build
reads it, no check enforces it, and no later pull request assumes it, so adding it
later costs exactly what adding it now would. It is also absent from the Build
Prompt's list of what ships, and the Constitution says not to invent scope. Under
the threshold rule this is an ordinary scope call, so it is recorded here rather
than as a decision record. Not to be confused with `CODEOWNERS`, which Cédric
declined separately (ADR-0014).

**Built PR 1 and opened it as a draft: pull request #1.** Nineteen files, both CI
jobs green on GitHub in 23 seconds.

Four things came out of building it that were not in the plan:

- **`pip-audit --strict` fails on our own package**, because a local editable
  install is not on PyPI and can never be audited. `--skip-editable` without
  `--strict` reports the skip and still fails on a real vulnerability, which is
  what was actually wanted.
- **Ruff does not apply `D100` to a module whose name starts with an
  underscore**, treating it as private. Both files used to test the rule happened
  to be named that way, so the first demonstration produced a false pass.
  Retested with a normal name and it fires correctly. Recorded as a known limit
  in `AGENTS.md` with the instruction not to name modules that way here.
- **Sixteen parallel test workers each warn that they collected no coverage
  data**, which buried the output that matters. Silenced with coverage's
  `disable_warnings` for that one slug rather than by suppressing warnings
  generally.
- **`.gitattributes` was missing and needed.** The build machine is Windows and
  CI is Linux, and the Stop hook is a shell script. Committed with CRLF endings
  it would have failed on Linux with a confusing interpreter error. Everything is
  now stored as LF, and the hook script carries its executable bit in the index.

**Proved the guards catch things**, which is the actual deliverable rather than
the files. A file under `src/` with no docstring fails linting. A file containing
a private-key header is blocked by the pre-commit hook before a commit exists,
verified with a fake key that was never committed. `pip-audit` reports the
dependency tree clean. The full gate is green locally and in CI, and the CI log
confirms every step ran rather than being skipped.

The documentation guard could not be demonstrated in this pull request, because
the only change under `src/` is adding the package docstring. It gets exercised
for real at PR 2.

**Six items remain, and four of them need a repository admin:** branch protection,
secret scanning with push protection, Dependabot alerts, and the access fix that
removes Richard's write access through the `interns` team. The exact steps are in
the pull request description. Until branch protection is on, the gate reports but
does not enforce, so PR 1 is not finished when it merges; it is finished when
those settings are applied.
