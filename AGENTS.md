# AGENTS.md

Instructions for any AI coding agent working in this repository. Written to the
open `AGENTS.md` standard so Claude Code, Codex, Copilot, Cursor and others read
one shared source.

[`constitution.md`](constitution.md) holds six rules that never bend, and this
file holds the working rules that sit under them. Claude Code loads both, because
`CLAUDE.md` imports them. Read it first if your tool has not already.

## Before you write code

**Write the specification first, and get it approved.** Every pull request begins
with a short plain-English spec in `specs/NNN-short-title.md`, written as
testable statements ("WHEN this happens THE SYSTEM SHALL do that"), naming the
files it touches, what is out of scope, and the end-to-end check that proves it
works. A member of CLI approves the spec before any code exists. This is the main
review lever: CLI judges a readable spec, and the machine judges the code.

**One pull request is one thin vertical slice** that runs and shows a visible
result. A few hundred changed lines at most. If it grows past that, split it.

## The store

- **Files are the store.** One item is one file. The repository tree is the data.
- **Capture, then derive.** The raw fetched body is committed to `data/raw/`
  **before** anything reads it. The archive is the source of truth; cards are
  derived from it and can be rebuilt at any time.
- **The stable key is the filename. It is always a hash, and it always carries
  the source.** `item_id` hashes the source together with, in order of
  preference, the source's own id for the item, else the canonical link, else
  the body. It always hashes, because one of those is text from the open web and
  the name becomes a file path: hashing means a name can never contain a
  separator (ADR-0026). It always carries the source, because a name identifies
  one source's capture, so nothing can overwrite what another source captured,
  whichever rule applied (ADR-0028). Deduplication within a source is done by
  the filesystem, not by an index.
- **A name cannot say that two captures are the same call, and does not try.**
  A source republishing a call links to its own page, and canonicalisation
  resolves no redirects, so two sources do not produce one address for one call.
  The canonical link is recorded un-namespaced as the evidence, and matching
  happens at the card, where the funder, the title and the deadline are better
  evidence than two strings being equal. See ADR-0028.
- **People write `config/`, the run writes `data/`, and neither writes the
  other's.** Every write in the run goes through one function rooted at `data/`,
  so a hand edit and a scheduled run can never collide. See ADR-0027.
- Never commit a database, a query index, or a derived cache.

## The one AI step

Extraction, and nothing else.

- **The model writes a command with flags**, and a deterministic builder we own
  turns that command into the record. The record's shape lives in our builder,
  never in the provider.
- **Forbidden:** provider structured outputs, function calling, `Instructor` or
  any schema-constrained decoding wrapper, and raw JSON emitted by the model.
- **Every field is a value and a quote.** A value cannot be stored without a
  supporting quote, and the quote must be a real substring of the source text,
  checked deterministically. Anything absent is the first-class value
  **"not stated"**, never invented.
- Free-text flag values are JSON-encoded, so a stray quote or comma cannot break
  parsing.
- **Fail safe.** A malformed command returns an error the model reads and
  retries. Anything failing twice is held and logged, never published as a guess.
  Every record stores its `prompt_version` and `model_id`.
- **The model is untrusted.** It reads attacker-influenced web text. Its output is
  never executed, never reaches a shell, and is always validated against the
  schema. Route any scraped value through an `env:` variable, never a `run:` line.

## Two correctness rules already settled

- **A deadline validates as a *valid* date, not a *future* one.** Whether a call
  is still open is derived at display time, never stored. The archive keeps closed
  calls, and `rebuild.py` must never reject one. See ADR-0001.
- **The heartbeat proves liveness, not emptiness.** It is written on every run
  that executes, so a silently dropped run goes stale. A run that fired but found
  nothing is a separate check, the per-source item-count baseline. See ADR-0002.

## Documentation moves with the code

- Every file under `src/` opens with a plain-language module docstring: three or
  four jargon-free sentences saying what the file is, what it does, and how it
  fits, written so it can be understood without reading the code. Enforced by ruff
  `D100`.
  **Known limit:** ruff treats an underscore-prefixed module such as
  `_helpers.py` as private and does not apply `D100` to it. Do not name modules
  that way here. The rule still stands for every file; only the automatic check
  stops seeing it.
- **When a change makes a file's entry in `docs/ARCHITECTURE.md` wrong, fix the
  entry in the same change.** No automatic check enforces this, deliberately. A
  rule that fires on every edit to a covered file also fires on changes below the
  level the entry describes, and a check that cries wolf gets ignored. Judgement
  and a review pass before pushing do this better than a pattern match.
- A change that leaves its explanation wrong is not done.

## The records

| File | What goes in it |
|---|---|
| `docs/decisions/` | Why a choice was made, and what it costs. One numbered file per record, immutable, superseded rather than rewritten. |
| `docs/BUGS.md` | What broke, what caused it, what fixed it, and the test that now guards it. One entry per defect, newest first. |
| `CHANGELOG.md` | What changed for anyone using Fieldbook, grouped under `Added`, `Changed`, `Fixed` and the rest. |

A full decision record is required when a change touches the item schema, the
extraction step, a source route, or the cron cadence, or when a member of CLI makes a
call with real alternatives. An ordinary slice needs no record; its commit is the
history. A journal of how the work was done is not published: see ADR-0024.

**Defects.** An open one belongs in the repository's issue tracker. A fixed one
gets an entry in `docs/BUGS.md` carrying its symptom, its cause, its fix and its
guarding test, plus a line under `Fixed` in the changelog when someone using
Fieldbook would notice the difference. A defect whose fix establishes a lasting
rule earns a decision record as well, and the two link to each other rather than
repeating each other. The history records defects in behaviour, not corrections
to wording and not the removal of code nothing used. See ADR-0025.

**A bug fix must add a test that fails on the pre-change behaviour.** Without it,
"fixed" is a claim rather than a fact.

## Conventions

- **Environment:** `uv` and `mise`, Python 3.13. Code under
  `src/field_monitoring_pipeline/`, tests mirroring it under `tests/`.
- **The gate:** `mise run verify` is format checked, lint, strict type-check, and
  tests, and it fixes nothing. The pre-push hook runs it, so it must pass before
  anything leaves the machine. `mise run check` is the same four with fixing
  turned on, for use while working.
- **Types:** basedpyright runs in strict mode. Fully type every function. No
  untyped `dict` at a module boundary; the contracts are Pydantic models for
  exactly this reason.
- **Dependencies:** `uv add` for runtime, `uv add --dev` for tooling, then pin
  the result to an exact version rather than a range, so a version changes only
  when someone changes it. Commit `pyproject.toml` and `uv.lock` together. Never
  hand-edit the lockfile.
- **Commits:** Conventional Commits, enforced by commitizen. Types: `feat`, `fix`,
  `chore`, `docs`, `refactor`, `test`, `ci`. Example:
  `feat(fetch): reach one source by its freshest route`.
- **Actions:** every GitHub Action pinned to an exact commit SHA, never a tag.
- **Secrets:** never commit anything matching the `.gitignore` secret patterns.
  The model key is a GitHub Actions secret.

## Never write about people in this repository

This repository is public and permanent. **Do not name any individual in any file
here, in any commit message, or in any pull request description.** Not to credit
them, not to attribute a decision to them, not to describe their access or their
role.

That includes all of:

- who has access to what, and whether they should
- anyone's role, contribution, performance, or whether they work on this project
- attributing a decision or an opinion to a named person, including quoting them
- credit, attribution, or authorship discussions
- personal email addresses or contact details

**Record what was decided and why. Never who said it.** Use roles, not names:
"CLI" for a client decision, "the build" for an engineering one.

| Write this | Not this |
|---|---|
| A code owners file was declined as too much process for a team of this size | A named person said it was too much process |
| **Owner:** CLI | **Owner:** a person's name |
| The repository was made public on this date | A named person made it public |

The one exception is git's own author field, which must identify a real account
because that is what attribution of authorship requires. That is metadata, not
prose about a person.

These discussions belong in the team's private notes, outside this repository.
**A closed pull request stays readable, and its commits stay reachable**, so
anything published here cannot reliably be taken back. Check before writing, not
after.

## Never write about access or permissions in this repository

A sentence can name nobody and still be a disclosure. "The only team with write
access is X" identifies a way in without using anyone's name, so this is a
separate rule from the one above and it catches what that one misses.

**Do not write who can reach this repository, what they can do there, or any plan
to change it.** That covers who holds read, write, or admin, which teams have
access and by what route, and any intention to grant or remove it.

**What may be written:** a workflow token's own permissions, because that is the
code's configuration and it sits in the file regardless. A workflow running with
`contents: read` is a fact about the system. Who may approve its merge is a fact
about people.

| Write this | Not this |
|---|---|
| These settings need a repository admin to apply | Naming who holds admin, or who does not |
| The workflow token is `contents: read` | The team with write access is X |
| The branch rules require a pull request for every change | A plan to change who can write |

Published standards treat this as a security category rather than a privacy one.
Access questions belong in the team's private notes.

## Never name this project's internal documents

Internal documents live with the team, outside this repository. This repository
does not name them, describe what they contain, record that a decision departed
from one, or record that one was edited.

Keep the substance and drop the pointer. "The original plan called for a code
owners file" rather than naming the document it came from. "Fading attention is
the most likely cause of this project's death" rather than citing the risk
register it is written in.

**Published sources may be cited.** A paper, a standard, a vendor's documentation:
anyone can read those, and citing them makes the reasoning checkable. An internal
citation is the opposite. It only tells a reader that something they cannot see
exists.

| Write this | Not this |
|---|---|
| The original plan called for X | Naming the internal document it came from |
| The original design had the run committing to `main` | Naming the internal document that said so |
| Fading attention is the most likely cause of failure | Citing an internal risk register by item number |
| *ADR-0008* | *Internal document, section 4; ADR-0008* |

## The one test that covers all three of these rules

People, access, and internal documents are the same rule seen three ways. Before
writing anything here, ask: **does this sentence describe the published thing, or
does it describe how we made it?** If the second, it belongs in the team's private
notes and not in this repository.

## House style for all prose

Commit messages, pull request descriptions, `README`, and everything in `docs/`:
plain English, short declaratives, no em-dash used as a mid-sentence aside, no
"X, not Y" constructions,
"use" rather than "leverage", no hype and no exclamation marks. Documentation
style, not marketing. Acknowledge trade-offs rather than papering over them.

## Two stops, and both are mandatory

There are two separate places to stop and wait. Passing the first does not carry
you through the second, and neither may be skipped because the other was
satisfied.

### Stop 1: before anything leaves the machine

**Building and shipping are separate steps, and an instruction to build does not
authorise shipping.** Finish the work locally, run the gate, commit if useful,
then stop, say what would be pushed, and ask.

Wait for an explicit yes before `git push`, before `gh pr create`, and before any
other outward send. **A draft pull request counts as shipping**, because it is
visible to CLI the moment it exists.

When an instruction is ambiguous between building and shipping, read it as
building only.

### Stop 2: at the merge line

Once a pull request is open, stop again. A member of CLI reviews and merges, and that
merge is the deployment. **Never merge your own pull request.**

Do not start the next slice's code on `main` before the current one is approved.
Branch the next slice instead.

## Deliberately not built in phase one

Entity resolution or any alias file. Relevance ranking or any score. Semantic
search. A committed query engine. The public-facing layer.

## Must never appear

A third-party uptime monitor. Email delivery or any email service. A chatbot on
Telegram, Slack, WhatsApp, Discord, or Signal. Phone push. GitHub Issue Forms for
administration. A private repository, a hard run-time timeout, or a scheduled
discovery job.
