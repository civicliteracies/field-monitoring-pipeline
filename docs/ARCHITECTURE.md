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
cap, a ban on catching errors blindly, and a check that a function does not
return a value on one path and fall off the end on another. Test files are
exempted from the rules
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

### `docs/decisions/`, `docs/BUGS.md` and `CHANGELOG.md`

The three records. `docs/decisions/` answers why the system is built this way, one
numbered file per record, never rewritten, only superseded, with a `README.md`
beside them as the index. The filenames follow the usual `NNNN-title-with-dashes`
convention, and they are permanent, because the links between records are how the
supersession chain is read. `docs/BUGS.md` answers what broke and how it was
fixed, one entry per defect with its symptom, its cause, its fix and the test
that now guards it, so the same problem is not rediscovered later and a
maintainer can see how the system behaves under stress without opening closed
issues one at a time. `CHANGELOG.md` answers what changed for anyone using
Fieldbook, in the Keep a Changelog format, opening with an `Unreleased` section
that fills up between releases.

All three are prose rather than mechanism, so they get no entry of their own
here, but they are covered by the same discipline: written as the work happens,
not reconstructed later. A defect sits in the repository's issue tracker while it
is open and moves to the history once it is fixed; where its fix also sets a
lasting rule, the rule becomes a decision record and the two link to each other.
See ADR-0025. There is deliberately no fourth record of what was done and when:
the commit history is that, and a journal of how the work was made is not
published. See ADR-0024.

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

### `config/sources.toml`

**What it is.** The watch list: which sources the run reaches, and how.

**What the code inside does.** It is data rather than code. One block per source,
each carrying a short identifier, a name, whether it publishes funding calls or
project reports, how it is reached, its address, and a first-run cutoff date.

**How it does it.** The run reads it and never writes to it. That separation is
the point: people edit this file by hand, in the web editor or through a pull
request, and the run owns `data/`. Neither touches the other's files, so a hand
edit and a scheduled run can never collide.

**In and out.** In: edited by CLI. Out: read at the start of every run.

**How it fits.** It is the only place that decides what the system watches.
Changing what is monitored is a text edit here, never a code change.

**What a reviewer must know.** A malformed block stops the run before any network
request, and the error names the block it sits in, so a typo is reported rather
than half a run being carried out. The
`since` date bounds the first look at a source, so adding one does not pull in
years of back catalogue. Only `feed` is implemented so far; page and PDF routes
arrive with the libraries that read them.

### `src/field_monitoring_pipeline/models.py`

**What it is.** The typed shapes each step of the run hands to the next.

**What the code inside does.** Defines a source on the watch list and one
captured item, and reads the watch list from disk.

**How it does it.** Both are Pydantic models, so a malformed watch list is
rejected where it is read rather than failing somewhere further down.

**In and out.** In: the watch-list file. Out: typed objects every other module
takes as arguments.

**How it fits.** It sits under everything else in the run. Keeping the shapes in
one file means no step has to guess what another gives it.

**What a reviewer must know.** `source_item_id` is the identifier a source
published for an item. It is text from the open web and is only ever hashed,
never used as a name. See ADR-0026. A source identifier used twice in the watch
list is refused by name, because that identifier is what a source's bookmark is
filed under and two entries sharing one would read each other's.

### `src/field_monitoring_pipeline/normalize.py`

**What it is.** The step that reduces a link to one canonical form.

**What the code inside does.** Lowercases the scheme and host, drops the
fragment, removes tracking parameters, and sorts what remains.

**How it does it.** By splitting the address, filtering the query parameters
against a list of tracking names and prefixes, and reassembling it.

**In and out.** In: a link as the source published it. Out: the form used to
recognise the same page again.

**How it fits.** It runs before an item is named, because the name is derived
from this address.

**What a reviewer must know.** Without it, the same call arriving from one
source by a newsletter link, a shared link and a direct link would be captured
three times. It works within a source and cannot work across them: a source that
republishes a call links to its own page, so two sources do not produce one
address for one call. See ADR-0028.
It works on the text of a link and makes no network request, so a link that
redirects is left pointing at the redirector. Resolving those costs one request
per item on every run, and a feed almost always publishes its own identifier
for an item, which takes precedence over the link when naming it, so that work
is deferred to the slice that hardens canonicalisation.

### `src/field_monitoring_pipeline/fetch.py`

**What it is.** The only part of the system that reaches the open internet.

**What the code inside does.** Reaches one source and brings back what it served,
unread. Handles it being slow, down, unchanged, too large, or at an address the
watch list never chose. Reading a response into items is a separate function in
the same file, which runs after the response has been written down.

**How it does it.** It sends back the validator the source gave last time, so an
unchanged source can answer in one short exchange. Every address is checked
before it is reached, and redirects are followed here rather than by the network
library, so each hop is checked too. A timeout or a fault at the far end is
retried three times with a widening pause. An answer that the request was wrong
is permanent and is not retried, and so is an address off the open internet. The
body is read in chunks and abandoned if it passes the size cap or the reading
deadline.

**In and out.** In: a source from the watch list and its stored validator. Out:
exactly one of three things, unchanged, fetched, or failed. A fetch carries the
response exactly as served, not items, because the run writes it down before
anything reads it.

**How it fits.** It is the first step of the run and the only one that can be
affected by anything outside the repository.

**What a reviewer must know.** It takes a source drawn from the watch list and
never a bare address, so reaching somewhere not on the list cannot be expressed
in the code. Items published before the source's cutoff are dropped here. A
source that fails is reported and the run carries on: one broken website must
never stop the others, and that now covers a site that answers with something
unreadable as well as one that does not answer. An unreadable body skips its
own source without a retry, because reading it again would fail the same way.
Not every server honours a conditional request; the item-name gate is what
actually prevents a second capture.

Two things here are load bearing and easy to undo by accident. **A response that
names no feed format is refused**, which is what tells a source behind a gate
apart from a source that is merely quiet: both give no items, and only a real
feed announces its format. Without it a blocked source keeps its bookmark and
reports unchanged for ever, so a dead source looks healthy. And **every address
is checked, including each redirect**, which is why the client is told not to
follow them: a redirect names an address the watch list never chose, and the run
commits what it captures to a public repository. A name that resolves to a
private address is not caught; catching that means intercepting the connection
rather than reading the address, which is more machinery than this project needs
against something nobody here has faced. See ADR-0030.

### `src/field_monitoring_pipeline/store.py`

**What it is.** The `data/` directory, and the only way anything writes into it.

**What the code inside does.** Two jobs. It writes every file, and it answers
whether an item was already captured.

**How it does it.** Every write joins a path onto a fixed root and refuses
anything that would land outside it. The names already captured are read once
when the store is opened.

**In and out.** In: bytes and a path inside the store. Out: files on disk, and
the answer to whether a name is new. Three folders live under it: `raw/` for the
items, `responses/` for what each source actually served, and `state/` for the
bookmarks the run keeps for itself.

**How it fits.** Everything the run writes goes through here.

**What a reviewer must know.** Reading the existing names once, at opening, is
what makes the ordering rule safe: the raw body is written before anything asks
whether the item was known, and the answer still reflects the state before the
run began. Writing an item cannot change the answer for that item.

### `src/field_monitoring_pipeline/archive.py`

**What it is.** The step that writes down what a source served, and names and
writes each item read out of it.

**What the code inside does.** Works out an item's permanent name, then writes
the body and a companion record of where it came from.

**How it does it.** The name is a hash of the source together with one of three
things, in order of preference: the source's own identifier for the item, the
canonical link, or the body. Every one of them is hashed, and every one of them
carries the source.

**In and out.** In: one item and the store. Out: two files, and the name the item
now has for good. Capturing the same item again writes the same bytes, so a day
when nothing changed leaves the archive untouched and there is nothing to commit.
The time the record carries is when the item first entered the archive, not when
the run last looked, because a value that changes every run would make the
archive's history meaningless. See ADR-0029.

**How it fits.** It runs before anything asks whether the item was already known,
which is the rule the whole archive rests on.

**What a reviewer must know.** Hashing is not decoration. One of the three inputs
is an identifier a source published, which is text from the open web, and the
name becomes part of a file path. Hashing means a name can never contain a
separator and so can never address anything outside the archive. See ADR-0026.
Every rule also carries the source, so a name identifies one source's capture
and nothing can overwrite what another source captured. Which rule applies
depends on what a publisher includes, so leaving any of them without the source
would make that protection depend on a publisher's habits. A name therefore
cannot say that two captures are the same call, and does not try: the canonical
link is recorded un-namespaced as the evidence for deciding that at the card.
See ADR-0028. Writing before checking means the worst case is a duplicate rather
than an item lost with no record that it was ever seen. The order of the two files follows
the same reasoning: the origin record first and the body second, because
whether an item is known is read from the bodies, so a run cut short between
them leaves an item that will be written again rather than one taken for known
for ever.

### `src/field_monitoring_pipeline/calls.py`

**What it is.** One run of the funding-call capture. This is what the workflow
executes.

**What the code inside does.** Reads the watch list, and for each call source
fetches, writes down what came back, reads items out of it, archives those, and
counts what was new.

**How it does it.** It sequences the other modules and does nothing else itself,
so the order of the run reads in one place.

**In and out.** In: the watch-list path, the store, and a network client. Out: a
report of what happened to each source, printed for the run log.

**How it fits.** It is the top of the run. Every other module is called from
here.

**What a reviewer must know.** The order in this file is the design's central
rule made literal: the response is written down before anything reads it, so a
later slice can re-derive from what the source actually said rather than from
what one version of one function made of it. See ADR-0030. A source whose
response cannot be read is skipped and keeps no bookmark, so tomorrow looks
again rather than believing a holding page. A source that fails is reported and
the run continues. The run only fails as a whole if the watch list itself cannot be read,
because that is a mistake in the repository rather than a website having a bad
day. The first successful look at a source, recognised by the absence of a
stored validator, archives the backlog without counting it as new: those items
are new to the archive rather than new in the world. `FIELDBOOK_DATA` says
where the archive is, because on GitHub it is checked out from its own branch
rather than sitting beside the code.

### `.github/workflows/calls.yml`

**What it is.** The scheduled run that captures funding calls each morning.

**What the code inside does.** Checks out the code and the archive separately,
installs the project, runs the capture, and commits anything new.

**How it does it.** The archive lives on the `data` branch and is checked out
into its own folder, so code and data never share a working tree.

**In and out.** In: fires on a schedule and on demand. Out: commits to the `data`
branch.

**How it fits.** It is the only thing that runs unattended.

**What a reviewer must know.** It commits to `data` and never to `main`. The
branch rules require a pull request for every change to `main` and that binds
automation as well as people, so routing the run to its own branch means it never
has to get past those rules and no bypass or extra credential is needed. See
ADR-0018. The token is read-only except on the job that commits. The schedule
runs a few minutes past the hour, because jobs scheduled on the hour are the ones
most often delayed. The commit step runs whatever happened before it, so a run
that falls over partway down the watch list still commits what the earlier
sources gave it instead of discarding that work.

### `tests/__init__.py` and the test files

**What they are.** The test package marker, and one test file beside each
module under `src/`.

**What the code inside does.** Each file protects the behaviour its module
promises: a link reduced to one canonical form, a write that cannot leave the
store, a name that is always a hash, a broken source that does not stop the
run, and the whole run from feed body to files on disk.

**How it does it.** A test that needs a website gets a stand-in one: a client
whose answers the test itself decides. No test touches the network.

**In and out.** In: nothing. Out: a pass or a failure, and the coverage figure
the gate's floor is measured against.

**How it fits.** The gate runs the suite before every push, and the advisory
Linux run repeats it on the operating system the schedule uses.

**What a reviewer must know.** Because the tests decide every answer the
network would give, the suite proves the code's behaviour rather than any
website's availability, and it cannot fail because a site had a bad day. The
placeholder test from the first slice is gone: it protected no behaviour and
existed only so the gate had something to run before real code arrived. Tests
are explained by the behaviour they protect, and each module's entry above
carries that behaviour.

---

## Still to come

Named so the shape of the finished system is visible from the start. Each moves
into the sections above, with a full entry, in the pull request that creates it.

| File | What it will do | Arrives at |
|---|---|---|
| `models.py` additions | The call and report shapes join the source and raw-item shapes already there | PR 3 |
| `extract.py` | The one AI step: the model writes a command, a deterministic builder makes the record | PR 3 |
| `validate.py` | Checks a record against its rules before filing, holding anything that fails twice | PR 4 |
| `write.py` | Writes the record as a Markdown card that renders on github.com | PR 4 |
| `publish.py` | Rebuilds the feed and index from the filed cards, urgent calls first | PR 11 |
| `health.py` | Renders the status page and writes the heartbeat proving a run happened | PR 7, 14 |
| `rebuild.py` | Re-derives every card from the raw archive. Recovery and migration | PR 10 |
| `sandbox.py` | Runs a real fetch and extract on one pasted link, storing nothing | PR 15 |
| `direction.py` | The quarterly rollup, by plain counting, with no AI | PR 19 |
| `config/sources.toml` additions | The full source list, once the pipeline is proven on one | PR 5 |
| `config/tags.toml` | The fixed topic list, each marked primary or secondary | PR 8 |
| `config/strings.toml` | The card and feed wording, so changing copy needs no code | PR 11 |
| **A card file** | One funding call as a text file: typed fields at the top, the source quotes below. Explained once as a type, never one entry per card | PR 4 |
| `datapackage.json` | Describes the collected data: its fields, licence, and provenance | PR 8 |
| `site/` | The dashboard. Built by the CLI team, not the build agent | PR 12 |
