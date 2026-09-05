# PR 3a — the record shape, and reading a captured page

**Date:** 2026-09-04 · **Status:** ready to propose · **Owner:** build
**Branch:** `feat/extract-read-a-page` · **Commit type:** `feat(extract): turn a captured page into the text a model reads`

## Goal

**One captured page becomes one readable string, and the shapes a funding call
is made of exist.**

A captured page is markup: tags, escaped characters, invisible characters, menus
and footers. Something has to turn that into the words a person would read, and
that same string is later what every quote is checked against. If it is wrong,
everything after it inherits the wrongness and no later check can catch it.

No model, no command line, no checks. Those are the two parts that follow.

## Why

This is the only part where being wrong is invisible. A quote check compares two
strings; if the string it compares against is not what the page says, the check
passes and the record is wrong anyway.

It is also the part that can be judged without knowing anything else. Take a real
funder page, find a sentence with your own eyes, and confirm it is findable in
what comes out.

## Requirements (EARS)

*The numbers run on from the part before. The three are one design read in three sittings, so a number means the same thing in all of them.*

### The record shape


1. THE SYSTEM SHALL define the record in `models.py` alongside the shapes already
   there, as a title, a type drawn from a fixed list of ten, a funder, a timing, a
   budget, a summary, an eligibility, an area, a list of topics and a source link.
2. THE SYSTEM SHALL express a claim drawn from the source's own prose as a value
   paired with the quote it rests on. **Five fields carry a stored quote:** budget,
   summary, eligibility, area, and timing.
3. THE SYSTEM SHALL express a timing as either a closing date with the quote it was
   read from, or one of `rolling`, `ongoing` and `eoi` with the quote that supports
   it, so that carrying both or neither cannot be expressed. See ADR-0031.
4. THE SYSTEM SHALL allow four fields to be absent: funder, budget, eligibility and
   area. Title, type, timing and summary SHALL always be present. That marking in
   the shape is the whole list of what may be absent. See ADR-0033.
5. THE SYSTEM SHALL NOT add the prompt version, the model name or the builder
   version to the record. Those three travel beside it, and the slice that writes
   the card decides where they come to rest.
6. THE SYSTEM SHALL NOT add the project-report shape here. It arrives with the
   reports slice.


### The text the model reads


7. THE SYSTEM SHALL derive one readable string from a captured item, and that same
   string SHALL be both what the model reads and what every quote is checked
   against. See ADR-0034.
8. THE SYSTEM SHALL derive that string using the standard library only, by removing
   markup, decoding character references, dropping script and style content, turning
   block boundaries into line breaks, replacing a non-breaking space with a plain
   space, and removing zero-width and soft-hyphen characters.
9. WHEN a captured item cannot be decoded as text, THE SYSTEM SHALL replace the
   unreadable characters rather than fail, because a source serving broken bytes is
   a source problem and not a reason to stop.
10. THE SYSTEM SHALL record the version of this derivation on every extraction, so
    a stored value is attributable to the logic that produced it. A change to it
    that alters behaviour earns a decision record and a rebuild.
11. THE SYSTEM SHALL NOT narrow the source text to part of a page in this slice.
    The production input is a feed entry, which carries no navigation, and any rule
    for selecting an article's own region can silently select nothing. See the
    note under **Two things measured while writing this**.


## Files touched

- `src/field_monitoring_pipeline/models.py` (the record shapes join the source and
  raw-item shapes already there)
- `src/field_monitoring_pipeline/extract.py` (new: the text derivation only)
- `.gitattributes` (the archive and the frozen pages are never rewritten by git)
- `tests/test_extract.py` (new), `tests/test_models.py`, `tests/test_gitattributes.py` (new)
- `tests/fixtures/cipesa/` and `tests/fixtures/pulitzer/` (the two frozen pages
  and where each came from)
- `scripts/refresh_fixture.py` (new: refetches a frozen page through the real fetcher)
- `docs/decisions/` (ADR-0034 and ADR-0036, and their index lines)
- `docs/BUGS.md` (BUG-018), `docs/ARCHITECTURE.md`, `CHANGELOG.md`

## Out of scope

The command line and every check on a claim, which is part 3b. The model, the
instruction and the run by hand, which is part 3c. Everything the whole step
leaves out is listed in 3c.

## The end-to-end check that proves it works

1. `mise run verify` passes on a clean tree, with no network and no model key.
2. The two frozen pages are real funder pages, fetched through the production
   fetch function, and stored byte for byte as the servers sent them.
3. For each, a sentence you can read on the funder's own page in a browser is
   findable in the text this part produces. That is the whole claim.
4. Nothing appears anywhere in `data/`.


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

- The derivation turns a captured page into text where every real quote is found,

## What was measured while writing this

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
