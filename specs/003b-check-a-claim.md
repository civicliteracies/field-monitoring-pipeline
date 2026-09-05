# PR 3b — reading a command line, and checking every claim

**Date:** 2026-09-04 · **Status:** ready to propose · **Owner:** build
**Branch:** `feat/extract-check-a-claim` · **Commit type:** `feat(extract): build a checked record from a flagged command`

## Goal

**One line of flags becomes one record, or a named refusal saying why not.**

Every check in the system lives here. A quote must really appear in the page. A
deadline must be readable back out of its own sentence and match. A budget's
figures must be in the sentence carrying them. A quote must not carry somebody's
telephone number. An absent field must be said out loud rather than left blank.

No model. The command line is handed in, so every one of these can be judged by
writing a line by hand and watching what is accepted and refused.

## Why

This is where a mistake ships a wrong deadline to a reader who acts on it.

It is also the part with the most in it, and the part every review of this work
has found something in. Reading it on its own, without a model or a page reader
in the way, is the point of splitting.

## Requirements (EARS)

*The numbers run on from the part before. The three are one design read in three sittings, so a number means the same thing in all of them.*

### Finding and reading the command


17. WHEN the model replies, THE SYSTEM SHALL take the one line beginning with the
    marker word followed by a space or the end of the line. Two such lines or none
    is a malformed command.
18. THE SYSTEM SHALL refuse a reply longer than a stated length, and a command line
    longer than a stated length.
19. THE SYSTEM SHALL read a free-text value as a JSON string, so a quotation mark,
    a comma or a backslash inside a funder's own words cannot break the parse.
20. THE SYSTEM SHALL refuse a flag it does not know, a flag given twice, a
    free-text flag whose value is not quoted, and a plain flag with no value.
21. THE SYSTEM SHALL accept an absence as its own flag, one per field that may be
    absent, carrying no value.
22. WHEN a field that may be absent carries neither a value nor its absence flag,
    THE SYSTEM SHALL treat the command as malformed. Leaving a field out is not the
    same as saying the source does not state it, and only the second is honest.
23. WHEN a field carries both a value and its absence flag, THE SYSTEM SHALL treat
    the command as malformed.
24. WHEN a value is given for a quote-carrying field without its quote, or a quote
    without its value, THE SYSTEM SHALL treat the command as malformed.
25. THE SYSTEM SHALL NOT accept a flag for the topics or the source link. Topics
    are assigned deterministically at the tagging slice, and the link is already
    known from the capture.
26. THE SYSTEM SHALL take the source link from the item's canonical link where the
    capture recorded one, and otherwise from the address it was fetched from.


### Checking a claim


27. THE SYSTEM SHALL confirm that every stored quote appears in the source text
    word for word, comparing after collapsing runs of whitespace and normalising
    characters, and applying the same treatment to both sides.
28. THE SYSTEM SHALL refuse a quote shorter or longer than a stated range. A single
    word satisfies a substring test and proves nothing.
29. THE SYSTEM SHALL refuse a stored quote containing an email address or a
    telephone number, and SHALL NOT alter the quote to remove one, because an
    altered quote is no longer a substring of the source. The field is then grounded
    on another sentence or recorded as not stated. See ADR-0031.
30. THE SYSTEM SHALL confirm that every number of two or more digits in a budget
    appears in the budget's own quote, because a budget is the figure itself.
    For the other quoted fields THE SYSTEM SHALL confirm the number appears
    somewhere in the source text, because those are prose that may honestly name
    a year or a count the page discusses elsewhere. Both still refuse a figure the
    page never states. See ADR-0032 and **What the first real runs showed**.
31. WHEN a timing is a closing date, THE SYSTEM SHALL read a date back out of the
    quoted sentence and confirm it matches the date the model typed.
32. THE SYSTEM SHALL read a date only in a written form it recognises, and SHALL
    treat a relative phrase as unreadable.
33. WHEN a quoted sentence carries more than one date, THE SYSTEM SHALL refuse it
    and ask for a narrower span naming only the closing date, because a sentence
    stating when applications open and when they close supports either reading.
34. THE SYSTEM SHALL confirm the title is a whole line of the source text rather
    than any substring of it, so a title cannot be assembled from scattered words.
35. THE SYSTEM SHALL confirm the type is one of the ten and the open basis one of
    the three, and SHALL say so in its own words rather than passing on a library's
    message, because that message is read by the model on its next attempt.
36. **THE SYSTEM SHALL NOT claim these checks confirm a value is correct.** They
    confirm a quote was copied rather than invented. A real sentence attached to a
    value it does not support is caught for the timing, the budget, the type and the
    topics, and is not caught for the summary, the eligibility and the area. See
    ADR-0032 and the guard pass at PR 9.


## Files touched

- `src/field_monitoring_pipeline/extract.py` (the command reader and every check
  join the text derivation already there)
- `tests/test_extract.py`
- `docs/decisions/` (ADR-0031, ADR-0032 and ADR-0033, and their index lines)
- `AGENTS.md` (the quote rule corrected, and an honest statement of what the
  checks catch)
- `docs/ARCHITECTURE.md`, `CHANGELOG.md`

## Out of scope

The model, the instruction, the retry when an answer comes back broken, and the
run by hand, which is part 3c. Everything the whole step leaves out is listed
there.

## The end-to-end check that proves it works

1. `mise run verify` passes on a clean tree, with no network and no model key.
2. Write a command line by hand against one of the frozen pages, and watch a
   complete record come out with every claim carrying the sentence it rests on.
3. Change one thing in that line and watch it refused, with a reason that names
   the flag and the rule. A quote that is not on the page, a deadline that
   disagrees with its own sentence, a budget stating a figure its sentence does
   not, a quote carrying an email address, a field left silently out.
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
- The command is found among prose, and a lookalike line, two lines, none, an
- An unknown flag, a repeated flag, an unquoted value, a plain flag with no value
- A quote not on the page, a quote of one word, a quote carrying a contact detail,
- An open call builds and stores its quote, and an open basis with no quote is
- A broken command triggers exactly one retry, and a second failure raises the named
- A transport failure consumes no attempt and is not reported as a malformed command.
