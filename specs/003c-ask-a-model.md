# PR 3c — asking a model, proven on a real page

**Date:** 2026-09-04 · **Status:** ready to propose · **Owner:** build
**Branch:** `feat/extract-ask-a-model` · **Commit type:** `feat(extract): read one real item with a model and show the record`

## Goal

**A real model reads a real funder page and produces a record a person can check
against the page beside it.**

This is the one AI step, and the only genuinely uncertain part of the three. The
first two are either correct or not. This one is a question about how a model
behaves, and it is answered by running it and looking.

## Why

The riskiest thing in the system, proven early, on one item, where being wrong
costs nothing. Everything downstream is worthless if this step invents.

It is last of the three because it needs both of the others: the text to read, and
the checks to hold its answer to.

## Requirements (EARS)

*The numbers run on from the part before. The three are one design read in three sittings, so a number means the same thing in all of them.*

### Asking the model


12. THE SYSTEM SHALL hold the instruction sent to the model in its own file under
    `src/field_monitoring_pipeline/prompts/`, named by its version, and SHALL take
    the recorded prompt version from that name so the two can never disagree.
13. THE SYSTEM SHALL enclose the item's text in a delimiter and state in the
    instruction that everything inside it is text to read and never an instruction
    to follow. Fetched text is attacker-influenced. See ADR-0010.
14. THE SYSTEM SHALL reach the model through a single named seam passed in as an
    argument, so a test can supply a stand-in and the suite runs offline.
15. THE SYSTEM SHALL set its own timeout on each model request rather than relying
    on a default. This bounds one request and is not a limit on a whole run.
16. WHEN no model key is present, THE SYSTEM SHALL say so and stop before reading
    any item, rather than discovering it partway through.


### When it fails


37. WHEN a command cannot be read or a claim cannot be grounded, THE SYSTEM SHALL
    return one plain sentence naming the flag and the rule it broke, and SHALL
    attempt the same step once more. **A retry is the same step attempted again**,
    so the rule of exactly one AI step is untouched.
38. THE SYSTEM SHALL send the same prompt version and the same model on the second
    attempt, and SHALL add nothing to the request except the error.
39. THE SYSTEM SHALL NOT put any text read from the source into an error handed
    back to the model. The error travels into the next request, and the source's own
    words would then arrive twice.
40. THE SYSTEM SHALL ask the model at most twice for one item.
41. WHEN the second attempt also fails, THE SYSTEM SHALL raise one named error
    carrying the item's name, the number of attempts and the last message, and
    SHALL return nothing partial.
42. THE SYSTEM SHALL NOT create a held directory, a quarantine folder or a run log.
    Holding a twice-failed item belongs to PR 9, and ending at one named error gives
    that slice a single place to attach to.
43. WHEN a model call produces no reply at all, THE SYSTEM SHALL treat it as a
    transport failure and not as a malformed command. It consumes none of the two
    attempts and writes nothing, so a run failing because the account is empty
    does not read as a run where the extraction is wrong.
43a. THE SYSTEM SHALL tell three kinds of transport failure apart, because they
    need different treatment.
    **A refusal for quota or rate** is permanent for this run. Asking again
    cannot make the account fuller and every later item meets the same wall, so
    it is not retried.
    **A wrong key or a wrong model name** is permanent full stop and is not
    retried.
    **A dropped connection or a fault at the far end** is neither. The request
    never reached the model, so nothing was spent, and it is sent again, up to three
    times in all, with widening pauses. This was measured rather than assumed: on the first end to end
    run of this step one page failed with a dropped connection and the same page
    succeeded immediately afterwards, so without this a single blip loses an item
    for a reason that has nothing to do with the item. Three attempts rather than
    two, also measured: three calls in a row on this provider gave two answers and
    one server error, and at that rate two attempts lose roughly one item in nine.
44. THE SYSTEM SHALL raise named error types only, so a caller catches those and
    nothing else.


### What this slice does not touch


45. THE SYSTEM SHALL write no file anywhere.
46. THE SYSTEM SHALL NOT be called by the scheduled run. Extraction joins the
    schedule after its guards and the readiness note at PR 9. See ADR-0010.
47. THE SYSTEM SHALL NOT use any value read from a model reply as a file name, a
    path segment or a key, and SHALL escape and shorten model text before it
    reaches a log.

## Files touched

- `src/field_monitoring_pipeline/extract.py` (the model client, the instruction
  loader, the retry and the whole step join what is already there)
- `src/field_monitoring_pipeline/prompts/v1.md` and `v2.md` (new)
- `scripts/run_extract.py` (new: the check done by hand)
- `env.example` (new: names the key's setting, and carries no key)
- `tests/test_extract.py`, and a recorded real reply beside each frozen page
- `docs/decisions/` (ADR-0035 and its index line)
- `CONTRIBUTING.md` (how to run the extraction by hand), `docs/ARCHITECTURE.md`,
  `CHANGELOG.md`

## Out of scope

Validating a record and writing a card, which is PR 4. The propose, challenge and
confirm pass as independent calls, holding a twice-failed item, the run log and the
readiness note, all of which are PR 9. Topic tagging, which is PR 8. Re-extraction,
which is PR 10. The try-a-link sandbox, which is PR 15. More than one item at a
time. Any measurement of extraction accuracy. Any test that calls the live model.
Narrowing a page to its article. The project-report shape.

## New dependencies requiring approval from a member of CLI

**None.** The date reader, the markup removal and the escaping are all standard
library. Measured on both fixture pages before this was written.

## The end-to-end check that proves it works

1. `mise run verify` passes on a clean tree, with no network and no model key,
   because the tests replay recorded replies.
2. Put a free model key in a `.env` file, which git already ignores.
3. Run `uv run python scripts/run_extract.py cipesa`, then the same with `pulitzer`.
4. The screen shows the model reasoning in ordinary prose, then the single command
   line it writes, then the record built from it, with each claim beside the
   sentence it rests on.
5. Open the funder's page in a browser and read the two side by side. **The check
   passes when every claim on the screen is on the page, every quote is a sentence
   that really appears there, the closing date matches the one the page states,
   and anything the page does not mention reads as not stated rather than a guess.**
6. Nothing appears anywhere in `data/` after either run.
7. **What this produced, on 2026-09-04.** Both pages, thirty checks, no failures.
   Every claim was grounded in a sentence really on its page, both headings matched
   what a person read, and both deadlines came out exactly as the pages state them.


## Why this arrives in three parts

The extraction step is one idea, and it is three separable pieces of work: what
text the model reads, whether a claim is really supported by that text, and
whether a model can produce the claims at all. Each can be wrong on its own, each
is checked a different way, and together they came to about a thousand lines of
code.

The plan says a pull request is a few hundred changed lines, and says why: review
quality falls sharply past roughly four hundred, which is what makes reviewing all
of it realistic. One piece of this size would break that, and the seam between the
three already existed in the design rather than being invented to make the number
look better.

**Neither the rule nor the reasoning is fully satisfied even split.** The three
parts are roughly 370, 373 and 428 lines of code, and no boundary anywhere in this
work gets all three under four hundred. Splitting is an improvement rather than
compliance, and saying so is better than claiming otherwise. See
[ADR-0036](../docs/decisions/0036-the-extraction-step-arrives-in-three-parts.md).

**What the three prove together, and none proves alone.** The build sequence
describes this step as the one AI step, proven on a single real item. The first
two parts do not prove that. The third does, using what the first two built.


**None.** The date reader, the markup removal and the escaping are all standard
library. Measured on both fixture pages before this was written.

## Decisions settled before writing this

- **Five fields carry a stored quote**, being budget, summary, eligibility, area
  and timing. Funder is a claim drawn from the source's prose and is deliberately
  left ungrounded in phase one. Title, type, topics and the source link are grounded
  by other means. ADR-0031 and ADR-0032.
- **Absence is spoken out loud by the model and stored as an empty field**, and the
  shape is the list of which fields may be absent. ADR-0033.
- **The propose, challenge and confirm roles are played inside one prompt** in this
  slice, because a single pass costs nothing extra on a free tier. Independent
  passes and holding a twice-failed item are PR 9.
- **A retry is the same step attempted again**, not a second AI step.
- **No new dependency.** A strict date reader built from the standard library was
  measured against both fixture pages and read both deadlines correctly.
- **The model key lives in a file git ignores**, read from the environment first so
  the scheduled run can supply a repository secret later without a code change.
  ADR-0035.
- **The deterministic side carries its own version.** Freezing the derivation would
  make it unfixable and contradicts the rebuild slice, which re-derives every record
  under current logic. ADR-0034.

## Tests

- A value carrying quotation marks, commas, semicolons, a backslash, a newline and
- A broken command triggers exactly one retry, and a second failure raises the named
- A transport failure consumes no attempt and is not reported as a malformed command.
- A dropped connection is sent once more and succeeds; one that keeps dropping

## Two things measured while writing this

**Line endings.** The repository instructs git to normalise line endings across
every file. A captured body of 54 bytes was stored as 52 and came back from a fresh
clone as 52, and a quote spanning a line break was found in the original capture and
not in the clone. That means a quote would verify on the machine that captured it
and fail on every other machine. Two lines in `.gitattributes` fix it, and both the
archive and the fixtures then return byte for byte.

**Narrowing a page to its article.** Selecting the largest article region keeps every
fact on one fixture page and loses every fact on the other, returning 353 characters
of a related-links card. Selecting the main region keeps the facts on both and removes
some of the surrounding menus. Because any rule that selects a region can select
nothing useful, and because the production input is a feed entry which carries no
menus at all, no narrowing is built here. The consequence is recorded: a quote naming
a different programme from the same organisation's menu is a genuine substring of a
whole page and would pass. Fixture B pins that case.

## What the first real runs showed

The step was run against both frozen fixtures with a real model on 2026-09-03.
Every claim on both records was grounded in a real sentence from the page, and
nothing was invented. Four things were learned that reasoning had not produced.

**The instruction needed three corrections.** Version one took the line a browser
puts in its tab as the title, which carries the organisation's name on the end and
reads badly on a card. On one page it copied a sentence and called it a summary.
On the same page it answered "not stated" for a field a sentence did support.
Version two says what to do about each, and all three were fixed on the next run.

**The same model reading the same page does not always classify it the same way.**
One page was called a grant on some runs and a request for proposals on others.
Both are on the fixed list, so both pass every check. This is why a fixed list
catches a kind nobody offers and says nothing about whether the right kind was
chosen, and it is why the fixture records the human reading separately from what
one run produced.

**The first version of the number check refused honest writing.** Requiring every
figure in a value to appear in that value's own sentence held two runs in three on
one page, each time because a summary named the year of an election that the page
discusses throughout. The year was on the page, just not in that one sentence. The
rule is now split: a budget is held to its own sentence, because a budget is the
figure itself, and every other field is held to the page. Measured after the
change, through the real path with its one retry, four runs each:

| Fixture | Built | Kind of call | Deadline |
|---|---|---|---|
| the first page | 4 of 4 | grant on some runs, request for proposals on others | 2024-02-16 every time |
| the second page | 4 of 4 | fellowship every time | 2026-07-12 every time |

The deadline, which is the field a reader acts on, was identical on every run of
both pages. The kind of call was not, which is the same finding as above seen
again.

**The model shortens a quote with dots, and that costs a retry.** Watched on a
real run: the first attempt quoted a sentence as "...scant resources to African
civil society entities...", with leading dots that are not on the page, so the
substring check refused it and the second attempt produced a clean quote. The
retry did its job and the record was built. The instruction does not yet tell the
model that a quote must be copied whole rather than shortened, and adding that
line is work for the next prompt version rather than this slice, because a
version is named by its file and two recorded fixtures cite the current one.

**A dropped connection cost an item, on the very first run.** The end to end
check was run against both pages. One failed with the connection going away
before an answer arrived, and the same page succeeded on the next attempt a
moment later. The request never reached the model, so nothing had been spent, and
the item was lost anyway. That is now the three way split in requirement 43a: a
refusal is asked once, a blip is asked twice.

**Sixty seconds was not enough for one request.** A six thousand character page
with this instruction, answered with a few thousand characters of reasoning,
passed it at least once. The limit is now three minutes. It bounds one request and
is not a limit on a whole run.

## What the last run of the check showed, and one question it raises

Run on 2026-09-04. **Both pages, thirty checks, no failures.** Every claim on both
records was grounded in a sentence really on its page, both headings matched the
human reading word for word, and both deadlines came out exactly as the pages
state them.

**The pinned model was unavailable for part of that day.** It answered with a
server error and its own explanation: this model is currently experiencing high
demand, spikes are usually temporary, try again later. A sibling on the same free
tier answered normally throughout, so it was that model rather than the account,
the key or this code. The step reported it as the provider's trouble and not as a
failure of the extraction, which is what requirement 43 exists for, and the run
above was completed against the sibling to prove the code rather than the weather.

**The question that leaves.** The build brief says to confirm the current free
tier small model at build time. The pinned one is what CLI chose, and it works,
and it was congested for several hours on the day this was finished. Whether that
is a bad afternoon or a reason to pin a different sibling is a decision for CLI
with more than one day of evidence, and nothing here should change until then. The
name is pinned exactly rather than to a moving alias, so changing it is one line
and a decision record.

## Build checklist

- [ ] The four record shapes in `models.py`, with tests
- [ ] The text derivation, with tests for markup, entities, invisible characters and
      broken input
- [ ] The prompt in its own versioned file
- [ ] The command parser, with tests for every refusal
- [ ] The checks, with tests for every refusal
- [ ] The builder, the retry and the named errors
- [ ] The small entry point for the end-to-end check
- [ ] Both fixtures frozen through the real fetch function
- [ ] Hand-written replies for the failure paths
- [ ] `.gitattributes`, `AGENTS.md`, `docs/ARCHITECTURE.md`, `CHANGELOG.md`
- [ ] ADR-0031 to ADR-0034 and their index lines
- [ ] `mise run verify` green
- [ ] The end-to-end check run by hand against both fixtures

## Still open

- **How often extraction succeeds is now measured but not settled.** The two
  fixtures do not fail at the same rate, and a page whose summary is hard to ground
  fails more often than one whose sentences are plain. The slice that runs this
  unattended needs a figure for that, and the readiness note asks for one.
- **The repository secret is not set.** It is needed only when extraction joins the
  scheduled run at PR 9, and it needs a repository admin. The local key in an
  ignored file is a separate thing and is only for the check done by hand.
- **A wrong kind of call is not caught by anything.** Checking against a fixed list
  refuses a kind nobody offers. Choosing between two real kinds is a judgement, and
  the guard pass at PR 9 is where that is addressed.
