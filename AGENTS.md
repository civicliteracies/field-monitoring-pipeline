# AGENTS.md

Instructions for any AI coding agent working in this repository. Written to the
open `AGENTS.md` standard so Claude Code, Codex, Copilot, Cursor and others read
one shared source.

Read [`constitution.md`](constitution.md) first. It holds six rules that never
bend. This file holds the working rules that sit under them.

## Before you write code

**Write the specification first, and get it approved.** Every pull request begins
with a short plain-English spec in `issues/YYYYMMDD-pr-NN-*.md`, written as
testable statements ("WHEN this happens THE SYSTEM SHALL do that"), naming the
files it touches, what is out of scope, and the end-to-end check that proves it
works. A founder approves the spec before any code exists. This is the main
review lever: the founders judge a readable spec, and the machine judges the code.

**One pull request is one thin vertical slice** that runs and shows a visible
result. A few hundred changed lines at most. If it grows past that, split it.

## The store

- **Files are the store.** One item is one file. The repository tree is the data.
- **Capture, then derive.** The raw fetched body is committed to `data/raw/`
  **before** anything reads it. The archive is the source of truth; cards are
  derived from it and can be rebuilt at any time.
- **The stable key is the filename.** `item_id` is the source's own id if it has
  one, else the SHA of the canonical link, else a hash of the normalised body.
  Deduplication is done by the filesystem, not by an index.
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
  fits, written so a non-technical reader understands it. Enforced by ruff `D100`.
  **Known limit:** ruff treats an underscore-prefixed module such as
  `_helpers.py` as private and does not apply `D100` to it. Do not name modules
  that way here. The rule still stands for every file; only the automatic check
  stops seeing it.
- **A pull request that changes anything under `src/` must update that file's
  entry in `docs/ARCHITECTURE.md` in the same pull request.** CI enforces this.
  A genuinely doc-irrelevant change may opt out with a `docs: n/a` line in the
  pull request body, used sparingly.
- A pull request that changes code without updating its explanation is not done.

## The records

| File | What goes in it |
|---|---|
| `docs/ACTIVITY.md` | What was done, and when. Every action. |
| `docs/DECISIONS.md` | Why a choice was made, and what it costs. Numbered, immutable, superseded rather than rewritten. |
| `docs/BUGS.md` | What broke, why, how it was fixed, and the test that now guards it. |

A full decision record is required when a change touches the item schema, the
extraction step, a source route, or the cron cadence, or when a founder makes a
call with real alternatives. Ordinary slices need only an activity line.

**A bug fix must add a test that fails on the pre-change behaviour.** Without it,
"fixed" is a claim rather than a fact.

## Conventions

- **Environment:** `uv` and `mise`, Python 3.13. Code under
  `src/field_monitoring_pipeline/`, tests mirroring it under `tests/`.
- **The gate:** `mise run check` is format, lint, strict type-check, and tests.
  It must pass before a pull request is opened.
- **Types:** basedpyright runs in strict mode. Fully type every function. No
  untyped `dict` at a module boundary; the contracts are Pydantic models for
  exactly this reason.
- **Dependencies:** `uv add` for runtime, `uv add --dev` for tooling. Commit
  `pyproject.toml` and `uv.lock` together. Never hand-edit the lockfile.
- **Commits:** Conventional Commits, enforced by commitizen. Types: `feat`, `fix`,
  `chore`, `docs`, `refactor`, `test`. Example:
  `feat(fetch): reach one source by its freshest route`.
- **Actions:** every GitHub Action pinned to an exact commit SHA, never a tag.
- **Secrets:** never commit anything matching the `.gitignore` secret patterns.
  The model key is a GitHub Actions secret.

## House style for all prose

Commit messages, pull request descriptions, `README`, and everything in `docs/`:
plain English, short declaratives, no em-dashes, no "X, not Y" constructions,
"use" rather than "leverage", no hype and no exclamation marks. Documentation
style, not marketing. Acknowledge trade-offs rather than papering over them.

## Stop at the merge line

Open the pull request, then wait. A founder reviews and merges, and that merge is
the deployment. **Never merge your own pull request.** Do not start the next
slice's code on `main` before the current one is approved; branch the next slice
instead.

## Deliberately not built in phase one

Entity resolution or any alias file. Relevance ranking or any score. Semantic
search. A committed query engine. The public-facing layer.

## Must never appear

A third-party uptime monitor. Email delivery or any email service. A chatbot on
Telegram, Slack, WhatsApp, Discord, or Signal. Phone push. GitHub Issue Forms for
administration. A private repository, a hard run-time timeout, or a scheduled
discovery job.
