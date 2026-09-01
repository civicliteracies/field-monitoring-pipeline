# Architecture

The plain-language map of Fieldbook as it exists right now. Every file that is
part of this project is explained here: what it is, what it does, how it does it,
and what a reviewer needs to know. Written so a reader who does not write code can
understand the system, and a reviewer can judge a change, without reading the code.

This is not a design document and not a changelog. The design and the deeper
reasoning live with the team, outside this repository. This file describes what is
actually here.

## What Fieldbook is

A near-zero-cost, self-running monitor of the transparency and accountability
funding sector, built for the Civic Literacy Initiative. It watches the funders
CLI follows, captures every funding call and project report as a plain text file
in this repository, reads the stated facts out of each with one bounded AI step,
and publishes the calls as an RSS feed and a searchable dashboard.

**This repository is the database.** No server, no database engine. One item is
one file, and `github.com` renders it directly.

```
fetch -> normalize -> archive -> store -> extract -> validate -> write -> publish
 [det]     [det]       [det]     [det]   [AI+det]     [det]      [det]     [det]
                         |                    |
                  capture happens here   the only AI step
```

`[det]` marks a deterministic step: a plain rule, the same every time. The raw
fetched text is committed **before** anything reads it, so every card can be
rebuilt from the archive at any time.

---

## How to keep this file

**The deal.** Every file carrying code, behaviour, configuration, or a contract is
explained here in plain language, and every time one ships or changes, its
explanation ships with it. Merging is the
deployment, so every deployment updates this map. **If a file changed and its
explanation did not, the work is not done.**

**What is covered.** Every file carrying code, behaviour, configuration, or a
contract. Not only the Python modules: the workflows, the hooks, the build and
tool configuration, the schema and data contracts, the site files, and the tests.
The test is simple. If a reader would wonder "what is this and why is it here",
it gets an entry.

**Two limits, so the map stays useful.** Generated data is explained once as a
category, never per file: one entry describes what a card file is, not one entry
per card. Lockfiles and pure records get a single sentence. Prose files that
explain themselves get no entry at all: `README.md`, `CONTRIBUTING.md`, and this
file.

**Every entry has seven parts.** No code, no function signatures. Prose about the
code, not the code.

1. **File** — the path.
2. **What it is** — one sentence naming its job in the system.
3. **What the code inside does** — the main parts, and what each is for.
4. **How it does it** — the approach, the steps, the order, the decisions it
   makes. Enough that a reviewer understands the mechanism.
5. **In and out** — what it takes, what it produces.
6. **How it fits** — where it sits, what calls it, what it calls.
7. **What a reviewer must know** — assumptions, edge cases, failure behaviour,
   side effects, cost, security notes, and any trap. Whatever a careful reviewer
   would otherwise have to ask.

**Kept current by judgement, not by a rule.** When a change makes an entry here
wrong, the same change fixes the entry. There is no automatic check, and that is
deliberate: a rule firing on every edit to a covered file also fires on changes
below the level an entry describes, and a check that cries wolf trains people to
ignore it. A review pass before pushing catches the real cases, which are the ones
where the map now says something untrue.

**Keep the entry and the docstring in agreement.** Each code file under `src/`
opens with three or four jargon-free sentences, required by ruff `D100`. That is
the short local copy; the entry here is the fuller explanation. Neither may
contradict the other.

**Style.** Short declaratives. Spell out an acronym once. No em-dashes. Say what
the code does, how, and why. Never skip the how or the reviewer notes to save
space, because those are what a reviewer needs most.

---

# The files

## Automation and workflows

Enforcement lives on the maintainer's machine, in the pre-push hook. GitHub runs
two things and only two: one advisory check on each pull request, and from PR 2
the scheduled scraping job. See ADR-0021 and ADR-0023.

### `.github/workflows/ci.yml`

**What it is.** One advisory run of the quality gate on Linux, for every pull
request. It reports; it never blocks a merge.

**What the code inside does.** Checks out the code, installs the pinned Python and
uv, installs the libraries from the lockfile only, and runs `mise run verify`.

**How it does it.** GitHub starts a clean Ubuntu machine on each pull request.
`uv sync --frozen` fails outright if the lockfile and `pyproject.toml` disagree,
which is the same refusal uv makes locally. Then it runs `mise run verify`, the
same task the pre-push hook runs, so a green tick here means what a clean push
means. Every action is pinned to an exact commit SHA rather than a tag, because a
tag can be moved to point at different code and a commit SHA cannot. The token is
`contents: read` and nothing more.

**In and out.** In: a pull request. Out: a pass or a fail, visible on the pull
request and binding on nothing.

**How it fits.** It sits beside the pre-push hook rather than above it. The hook
is the gate; this is a second opinion from a different operating system.

**What a reviewer must know.** **Its entire purpose is the operating system.**
Every check it runs has already run on the maintainer's machine, so on Windows it
would tell you nothing new. The build machine is Windows and the scheduled run
executes on Linux, and that gap has already produced two real faults: the line
endings that made `.gitattributes` necessary, and a shell script written with
Windows line endings that could not execute. Nothing else belongs in this file. A
dependency scan, a file-size check and a documentation guard were all considered
and removed, and adding one back here would rebuild what ADR-0022 took out.

### `.claude/hooks/check-gate.sh`

**What it is.** A small script that stops an AI coding session from ending while
the quality gate is failing.

**What the code inside does.** Reads the information the agent passes it, decides
whether the session may end, and blocks it if the gate is red.

**How it does it.** It first checks whether it has already blocked once in this
turn. If so it allows the stop, because otherwise a gate that cannot be fixed
would loop forever. Otherwise it moves to the project folder, confirms the tooling
is present, and runs `mise run verify`, the read-only gate, so a hook that judges
the work cannot quietly repair it first. If the gate passes it exits quietly. If the
gate fails it prints an explanation and the last forty lines of the failure, then
exits with the code that means "block", which the agent reads as a reason to keep
working.

**In and out.** In: session details on standard input. Out: an exit code, and the
failure text when it blocks.

**How it fits.** It is the local counterpart to CI. CI catches a bad change after
it is pushed; this catches it before the agent believes it is finished.

**What a reviewer must know.** "Looks done" is the only signal an agent has
without a check it can run, so this gives it one. **The loop guard matters**: 
without it a persistently failing gate would trap the session. It exits quietly
and allows the stop whenever the tooling is missing, so it can never block someone
who simply has not run setup. It is written to run under Git Bash on Windows and
under Linux, which is why the repository stores it with Unix line endings; with
Windows line endings it would fail on Linux with a confusing interpreter error.

## Build and tool configuration

### `pyproject.toml`

**What it is.** The project's definition, and the settings for every tool that
checks the code.

**What the code inside does.** Names the project and the Python version it needs,
lists the libraries, and configures the linter, the type checker, the test runner,
coverage, and the commit-message checker.

**How it does it.** Dependencies are declared loosely here, for example "at least
this version", and resolved into exact versions in the lockfile. The linter runs
with a wide default rule set plus rules chosen for this project: security
anti-patterns, unused arguments, boolean traps, private-member access, import
hygiene, naming, a required explanation at the top of every file, a complexity
cap, and a ban on catching errors blindly. Test files are exempted from the rules
that only make sense for production code. The type checker runs in strict mode.
Tests run with coverage measured, and the run fails if coverage falls below eighty
per cent.

**In and out.** In: read by uv, ruff, basedpyright, pytest, coverage, and
commitizen. Out: the rules those tools enforce.

**How it fits.** It is the single place the machine gate is configured. Changing a
threshold here changes what the gate demands of every future change.

**What a reviewer must know.** **The coverage floor measures the whole project,
not only the lines changed in a pull request.** ADR-0004 asks for a new-code
floor, and true diff coverage would need another dependency, so this is the
boring approximation until it proves inadequate. Coverage warnings about workers
collecting no data are silenced, because tests run in parallel and most workers
legitimately measure nothing; silencing that one message keeps real failures
visible. **Ruff does not apply the docstring rule to a file whose name starts with
an underscore**, treating it as private, so do not name modules that way here. The
complexity cap is set at ten: past that, a function is doing too much to review in
one sitting.

### `mise.toml`

**What it is.** Which Python version this project runs on, and the named commands
everyone uses.

**What the code inside does.** Pins the Python version and defines the tasks:
`setup` prepares a fresh clone, `check` is the quality gate, `verify` is the same
gate read-only, and `test`, `lint`, `format`, and `typecheck` are their parts.

**How it does it.** When you are inside this folder, mise makes the pinned Python
the active one, and steps back outside it when you leave. `setup` installs the
locked libraries and the git hooks. `check` runs the four sub-tasks and fixes what
it can, which is what you want while working. `verify` runs the same four and
fixes nothing, because a gate that edits the code it is judging can pass by
repairing the fault it should have reported. Nothing else is bolted on: uv already
refuses to run when the dependency files disagree, so there is no separate check
for that.

**In and out.** In: `mise run <task>`. Out: the installed toolchain and the
result of the checks.

**How it fits.** It is the one entry point. The pre-push hook runs
`mise run verify`, so the gate has a single definition rather than one on a
machine and another on a server.

**What a reviewer must know.** The build machine has a different system Python
from the one this project needs, and mise is what keeps them apart. **`mise run
verify` is the contract.** A check added there runs before every push, and
again on Linux for every pull request, because both the hook and the advisory
workflow call this one task. See ADR-0021 and ADR-0023. A check added to `check`
but not to `verify` would never guard anything.

### `.pre-commit-config.yaml`

**What it is.** The checks that run on a contributor's own machine, before a
commit or a push exists.

**What the code inside does.** Four groups: blocks private keys and oversized
files, formats and lints the changed code, checks the commit message format, and
runs the full test suite before a push.

**How it does it.** Git calls these automatically at three moments. On commit it
scans the staged files for anything resembling a private key and for files above
one megabyte, then formats and lints. On the commit message it checks the
Conventional Commit format. On push it runs every test, so a failing test cannot
leave the machine.

**In and out.** In: the staged files, the commit message. Out: a pass, or a
blocked commit or push with the reason.

**How it fits.** It is the first line, catching problems seconds after they are
made rather than minutes later in CI.

**What a reviewer must know.** **The private-key check is the one that cannot be
undone if it fails.** A key committed to a public repository is public
permanently, even after deletion, so blocking it before the commit exists is the
only real protection. The size limit exists because this repository is the
database and must stay quick to clone; the store is plain text, so a large binary
is almost always a mistake. The pre-push hook runs `mise run verify`, so it
needs both mise and uv on the PATH; a terminal opened before either was installed
fails here with "Executable ... not found". Open a new terminal.

### `.gitattributes`

**What it is.** The rule that stores every text file with Unix line endings.

**What the code inside does.** Normalises all text, and names the file types that
must always use Unix endings and the binary types git must not touch.

**How it does it.** Git converts on the way in, so whatever a Windows or Mac
machine writes locally is stored the same way in the repository.

**In and out.** In: files as written locally. Out: files stored consistently.

**How it fits.** It sits under everything: the stored cards, the scripts, the
configuration.

**What a reviewer must know.** The build machine is Windows and CI is Linux.
Without this, a shell script committed from Windows carries Windows line endings
and fails on Linux with a confusing "bad interpreter" error. It matters more here
than in most projects **because the repository is the database**: the stored cards
are text, and their differences should be clean and comparable whatever machine
wrote them.

### `.gitignore`

**What it is.** What git deliberately does not track.

**What the code inside does.** Excludes build output, virtual environments,
editor settings, logs, and the secret file patterns.

**How it does it.** Pattern matching on paths.

**In and out.** In: paths. Out: whether git sees them.

**How it fits.** It is the passive half of secret protection; the pre-commit hook
is the active half.

**What a reviewer must know.** **The shared agent configuration at
`.claude/settings.json` is deliberately tracked**, and only the personal override
file is ignored. That is a change from the original scaffold and is recorded as
ADR-0015. The reason is that permission restrictions in that file take effect on
any clone immediately, so committing it is what makes them binding rather than
optional. The secret patterns must never be loosened.

### `.claude/settings.json`

**What it is.** The shared configuration for AI coding agents working in this
repository.

**What the code inside does.** Two things: sets what an agent may and may not do,
and registers the hook that runs the quality gate before a session may end.

**How it does it.** Refusals cover reading the secret files, merging a pull
request, and force-pushing. Two commands require a human to approve them each
time: adding or removing a dependency. The hook entry points at the gate script
and gives it five minutes.

**In and out.** In: read by the agent at session start. Out: the rules it works
under.

**How it fits.** It makes two Constitution rules mechanical instead of remembered:
no dependency added without a person approving it, and never merging your own
pull request.

**What a reviewer must know.** **Refusals and approval prompts take effect on any
clone immediately, with no trust step**, which is exactly why this file is
committed. Permission grants would wait for a trust dialog, so this file
deliberately contains none. **Hooks in a settings file do run in some untrusted
situations**, which makes this executable content in a public repository, so the
hook is kept to one fixed command and changes here deserve the same scrutiny as
changes to a workflow. No secret may ever be put in this file.

### `.python-version`

**What it is.** The Python version, in the plain format many tools read.
**What the code inside does.** Names one version. **How it does it.** A single
line. **In and out.** In: read by tools that do not read `mise.toml`. Out: the
version they select. **How it fits.** It agrees with `mise.toml`. **What a
reviewer must know.** If the two disagree, tools will disagree too. Change both
together.

### `uv.lock`

The exact version and content fingerprint of every library, so this machine, a
teammate's, and GitHub all install identically. Generated by uv, never edited by
hand, and committed with `pyproject.toml` in the same change. The fingerprints are
what make a substituted or typo-squatted package fail rather than install.

## Rules and records

### `constitution.md`

**What it is.** The six rules that never change without written approval from a member of CLI, given
approval. **What the code inside does.** States them and says why they exist.
**How it does it.** Six short statements and a closing note. **In and out.** In:
imported by `CLAUDE.md`, so it loads at the start of every session rather than
waiting to be opened. Out: the hard limits on every change. **How it fits.** It
sits above every other document here. **What a reviewer must know.** It is
short on purpose, because a long list gets skimmed. If a change appears to require
breaking one, that is a conversation with a member of CLI rather than a workaround.

### `AGENTS.md` and `CLAUDE.md`

**What they are.** The instructions any AI coding agent follows here. **What the
code inside does.** `AGENTS.md` carries the working rules in the open,
tool-neutral format. `CLAUDE.md` imports both it and `constitution.md`, and adds the
build sequence and the per-change loop. **How they do it.** The imports mean one
source rather than copies that drift, and they load the rules rather than only
pointing at them. **In and out.** In: read automatically at session start. Out: the
behaviour of the agent. **How they fit.** They sit under `constitution.md` and
above everything else. **What a reviewer must know.** The open format is
deliberate, so switching tools later does not mean rewriting the rules. All three
are kept short: real, specific rules only, not advice the linter already enforces.
Published guidance is to keep an agent context file under two hundred lines,
because a longer one is followed less reliably, and what actually loads is the
three of them together.

### `docs/decisions/` and `CHANGELOG.md`

The two records. `docs/decisions/` answers why the system is built this way, one
numbered file per record, never rewritten, only superseded, with a `README.md`
beside them as the index. The filenames follow the usual `NNNN-title-with-dashes`
convention, and they are permanent, because the links between records are how the
supersession chain is read. `CHANGELOG.md` answers what changed for anyone using
Fieldbook, in the Keep a Changelog format, opening with an `Unreleased` section
that fills up between releases.

Both are prose rather than mechanism, so they get no entry of their own here, but
they are covered by the same discipline: written as the work happens, not
reconstructed later. There is deliberately no third record of what was done and
when: the commit history is that, and a journal of how the work was made is not
published. See ADR-0024. There is no separate bug log either; an open defect goes
in the repository's issue tracker, a fixed one gets a changelog line, and a defect
whose fix sets a lasting rule earns a decision record. See ADR-0025.

### `specs/`

One short plain-English specification per pull request, numbered, written and
approved by a member of CLI before any code exists. This is the main review
lever: a readable specification is judged by a person, and the code is judged by
the machine.

## The package and its tests

### `src/field_monitoring_pipeline/__init__.py`

**What it is.** The marker that makes this folder the project's Python package.

**What the code inside does.** Nothing yet. It carries only its own explanation.

**How it does it.** Its presence is what lets the rest of the code, and the tests,
refer to this folder as one package.

**In and out.** Nothing in, nothing out.

**How it fits.** Every pipeline module will live beside it from PR 2 onward.

**What a reviewer must know.** It is deliberately empty of logic. Putting code
here would run it on every import of any module, which is a common source of
surprising behaviour. It carries a docstring because every file must, and because
without one the linter fails the build.

### `tests/__init__.py` and `tests/test_placeholder.py`

**What they are.** The test package marker, and one trivial test.

**What the code inside does.** `test_placeholder` asserts something true.

**How it does it.** It exists so the test runner has something to run.

**In and out.** In: nothing. Out: a pass.

**How it fits.** It keeps the gate meaningful before any real code exists. Without
at least one test, the test step would report nothing and the coverage floor would
have no data.

**What a reviewer must know.** It protects no behaviour and should be deleted as
soon as the first real test exists. Tests are explained here by the behaviour they
protect, so future entries will name that rather than describing the assertions.

---

## Still to come

Named so the shape of the finished system is visible from the start. Each moves
into the sections above, with a full entry, in the pull request that creates it.

| File | What it will do | Arrives at |
|---|---|---|
| `models.py` | The typed contracts every module passes: a raw item in, a call or report out | PR 3 |
| `fetch.py` | Reaches each source by its freshest route, skipping a broken one rather than failing | PR 2 |
| `normalize.py` | Cleans a link into one canonical form before it is used as a key | PR 2 |
| `archive.py` | Works out an item's stable name and commits the raw text before anything reads it | PR 2 |
| `store.py` | Skips an item already captured, so the same call arriving three ways is stored once | PR 2 |
| `extract.py` | The one AI step: the model writes a command, a deterministic builder makes the record | PR 3 |
| `validate.py` | Checks a record against its rules before filing, holding anything that fails twice | PR 4 |
| `write.py` | Writes the record as a Markdown card that renders on github.com | PR 4 |
| `publish.py` | Rebuilds the feed and index from the filed cards, urgent calls first | PR 11 |
| `health.py` | Renders the status page and writes the heartbeat proving a run happened | PR 7, 14 |
| `rebuild.py` | Re-derives every card from the raw archive. Recovery and migration | PR 10 |
| `sandbox.py` | Runs a real fetch and extract on one pasted link, storing nothing | PR 15 |
| `direction.py` | The quarterly rollup, by plain counting, with no AI | PR 19 |
| `calls.yml` | The scheduled run that fetches, extracts, and commits each morning | PR 2 |
| `config/sources.toml` | The watch-list CLI edits to change what is monitored | PR 2, 5 |
| `config/tags.toml` | The fixed topic list, each marked primary or secondary | PR 8 |
| `config/strings.toml` | The card and feed wording, so changing copy needs no code | PR 11 |
| **A card file** | One funding call as a text file: typed fields at the top, the source quotes below. Explained once as a type, never one entry per card | PR 4 |
| `datapackage.json` | Describes the collected data: its fields, licence, and provenance | PR 8 |
| `site/` | The dashboard. Built by the CLI team, not the build agent | PR 12 |
