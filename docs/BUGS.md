# Bug history

Every defect found in Fieldbook, what caused it, what fixed it, and the test that
now guards it. Newest first.

**Why this file exists.** So the same problem is not rediscovered later, and so
anyone maintaining Fieldbook can see how it behaves under stress without having
to open closed issues one at a time. A changelog line says what changed for
someone using Fieldbook. This says what broke, and why.

**What goes in it.** A defect in how the system behaves: wrong output, a crash, a
requirement with nothing behind it, a check that could never fire. Not a wording
correction to a document, and not the removal of code nothing used. Those are
ordinary work, and a history that carries everything stops being read.

**How it sits with the other records.** A defect lives in the repository's issue
tracker while it is open and comes here once it is fixed. It also gets a line
under `Fixed` in [`CHANGELOG.md`](../CHANGELOG.md) when someone using Fieldbook
would notice the difference. When a fix establishes a lasting rule, that rule
becomes a numbered record in [`docs/decisions/`](decisions/), and the two link to
each other so neither has to repeat the other. See
[ADR-0025](decisions/0025-conventional-file-layout.md).

**A fix is not accepted without a test that fails on the pre-change behaviour.**
Every entry below names its test. Where a defect was found in the specification
before the code it concerns existed, the entry says which slice brings the test.

---

## BUG-037 — A currency word cleared a telephone number written one space away from an amount

**Found** 2026-09-07, by a skeptic checking the fix for BUG-030, and the last of
the leaks in this function.

**Symptom.** "Contact 20 41 23 45 250 000 EUR" published the number, and so did a
Danish office number written beside an amount in the same way. The run holds
fourteen digits, which is fewer than any number anybody can ring, so nothing
about its length was suspicious.

**Cause.** A plain single space is not a place a run of digits can be broken,
and it must not become one: an ordinary telephone number is written with plain
spaces inside it, so breaking on one would take every real number apart and hide
it. A number and an amount joined only by single spaces therefore stayed one run,
and the currency word at the far end cleared the whole of it.

**Fix.** The run is read from the currency word inwards. Every shorter piece of
it that could stand alone is weighed, and a piece long enough to ring that is not
itself written the way a figure is written means the currency word was clearing
more than the amount. A figure grouped for reading has a first group of one to
three digits and then nothing but groups of exactly three; a telephone number
does not, because its groups are whatever the country writes. Without that
distinction the fix would refuse every amount past a million, since the first
seven digits of one are as long as a number somebody could ring.

**Test.** `tests/test_extract.py`, three leaking shapes and three large figures
that must still be read as figures, including one in the billions. See ADR-0038.

---

## BUG-036 — The gate said it refused a lockfile that disagreed, and did not

**Found** 2026-09-07, by an audit running the tooling rather than reading it.

**Symptom.** Four places stated that uv refuses to run when `uv.lock` and
`pyproject.toml` disagree, and that this is why the gate carries no separate
check for it. Neither half held. A dependency added to `pyproject.toml` by hand
and never locked passed the Linux install step, and the local gate rewrote the
lockfile to agree rather than reporting the difference.

**Cause.** Two different flags. `--frozen` means install from the lockfile
without updating it, so a disagreement is ignored rather than refused. Plain
`uv run` resolves and quietly rewrites the lockfile. The flag that asserts the
two agree is `--locked`, and nothing used it. Measured both ways in a copy of the
project outside the repository.

**Fix.** The Linux install step uses `--locked`. Every command in the gate passes
`--locked`, so the assertion holds on the machine the push comes from as well as
on the one that reports afterwards. The four claims are corrected to describe the
tool as it behaves.

**Test.** None that runs in the suite. This is a property of the task runner and
the workflow rather than of the code, and a test that shells out to uv to install
a deliberately broken project would be slower than the whole suite. The gate
itself now fails if the two files disagree, which is the check.

---

## BUG-035 — A typo in the watch list made the whole run do nothing and report success

**Found** 2026-09-07, by a completeness pass reading files no other reading had opened.

**Symptom.** Writing the watch list's table name wrongly, `[[sources]]` for
`[[source]]`, produced a list of no sources. Every source was skipped without
being mentioned, and the run reported that it had succeeded.

**Cause.** The reader asked the parsed file for its `source` blocks and accepted
whatever came back, including nothing. A typo inside a block was already reported
by name. A typo in the block's own name was not, because there was then no block
to report.

**Fix.** A watch list naming nothing to watch stops the run and says which keys
the file does contain, so the typo is visible in the message. This is the one
kind of failure that stops a run outright, because it is a mistake in the
repository rather than a website having a bad day.

**Test.** `tests/test_models.py`, two shapes: the table name mis-spelt, and a
watch list with nothing in it at all.

---

## BUG-034 — A damaged bookmark ended the whole scheduled run before anything was fetched

**Found** 2026-09-07, by an audit reading how the run behaves when its own files are wrong.

**Symptom.** A half-written or hand-damaged file under `data/state/` ended the
entire run with an unhandled error, before a single source had been reached.

**Cause.** The bookmark is read at the top of the loop, outside the error
handling that keeps one failing source from stopping the others. A file recorded
as a disposable cache was therefore the one thing able to stop every source at
once.

**Fix.** Unreadable now means the same as absent. The source is fetched
unconditionally, which is the cost that decision already accepted, and the file
is rewritten correctly on the same run.

**Test.** `tests/test_calls.py`, a damaged bookmark: no source is skipped and the
file is repaired in passing. See ADR-0027.

---
## BUG-033 — A deadline was published from the wrong date when the other one was written in figures

**Found** 2026-09-07, by an audit attacking the checks by running them.

**Symptom.** A sentence saying when a call opens in words and when it closes in
figures produced a card whose deadline was the **opening** date, with that same
sentence stored beside it as its evidence. The card contradicted its own quote.

**Cause.** The date reader knows three written forms. A date written 30/09/2026
is not one of them, so the sentence read as naming a single date and the guard
against a quote naming two dates never fired.

**Fix.** A date written in figures in a form this project refuses to guess at is
now noticed, which is not the same as read. 30/09/2026 means one thing in most of
the world and nothing in the United States, and a reader that guessed would agree
with whatever the model guessed. Noticing it is enough to ask for a narrower
quote.

**Test.** `tests/test_extract.py`, three shapes: slashes, dots, and the year
written first.

---

## BUG-032 — A separator the pattern did not know hid a telephone number completely

**Found** 2026-09-07, by an audit probing the gate with code rather than reading it.

**Symptom.** A number written with an en dash, a non-breaking hyphen, a minus
sign, a solidus, a middle dot, a word joiner, a figure space, wide digits, or
this project's own paragraph boundary character was published. No currency word
was needed anywhere in the sentence.

**Cause.** The pattern that finds a candidate accepted only the plain ASCII
separators. Anything else broke the run into pieces shorter than the shortest
number anybody can ring, and each piece was skipped. The boundary character is
the worst of these, because the collapsing step turns it back into a space
afterwards, so a quote written with it still matched the page word for word.

**Fix.** Every character that is one of these written another way is read as the
plain one before the rule looks at the sentence. Each stands for exactly one
character, so a number's position in the plainly written text is its position in
the sentence the page wrote, which the currency rule depends on.

**Test.** `tests/test_extract.py`, nine shapes, one per separator.

---

## BUG-031 — Two numbers written side by side were discarded for being too long to ring

**Found** 2026-09-07, by an audit, and the shape needs no currency word at all.

**Symptom.** "Call 020 7123 4567 020 7123 4568 with any questions." published both
numbers. So did a number written solid beside an amount, and a number beside a
reference number.

**Cause.** Nothing splits two numbers written one plain space apart, and nothing
should, because an ordinary number is written with single spaces inside it. The
merged run therefore passed the longest number anybody has, and a run that long
was skipped as too long to ring. The rule was at its weakest exactly where a page
puts a number, which is a contact line listing two of them.

**Fix.** A run still holding more digits than anybody's number, with nothing
inside it that a single number can carry on across, is refused rather than
skipped.

**Test.** `tests/test_extract.py`, four shapes.

---

## BUG-030 — The contact rule ran on the quote and on nothing else

**Found** 2026-09-07, by an audit of fourteen independent readings, and the most
serious thing any of them found.

**Symptom.** A telephone number or an email address written into the title, the
funder, or any of the four stored values reached the record untouched. Reproduced
end to end: a funder of "Example Trust (grants team, tel +45 20 41 23 45)" and a
title of "Call the grants team on 020 7123 4567" both built a record.

**Cause.** The rule was called in exactly one place, inside the quote check. The
guard on stored values looked only for control characters. The funder is the
widest way through, because it is deliberately ungrounded in phase one, so the
model's own words become a stored value with nothing reading them.

**Fix.** The rule runs in the one function every stored value passes through on
its way into the record. This is a different kind of fix from the four that came
before it: those made the rule stronger, and a stronger rule applied in one place
out of six still publishes a number in the other five.

**Test.** `tests/test_extract.py`, two end-to-end tests carrying a real contact
line through the whole step, one on the funder and one on the title. See ADR-0038.

---

## BUG-019 — A quote could be stitched together from two unrelated paragraphs

**Found** 2026-09-05, by an audit, before any record had been built.

**Symptom.** A quote made by joining the last sentence of one paragraph to the
first sentence of the next, with an ordinary space between them, was accepted as
a real substring of the page. The string was not on the page. Reproduced on a
two paragraph page with no trickery of any kind: a budget belonging to a
different programme was attached to a call and passed every check, including the
rule that a stated figure must appear in the budget's own sentence.

**Cause.** The derivation marks the end of a block of text with a blank line.
The comparison then collapsed every run of whitespace to a single space, which
erased that mark. Once erased, the gap between two paragraphs was indistinguishable
from the space between two words, so a quote could cross from one to the other.
This was the check every stored value rests on, so it was the worst place in the
system for the two halves to disagree about what the page says.

**Fix.** The end of a block is turned into a character a quote cannot cross,
rather than into a space. A quote that really does span two blocks, copied whole,
still carries the boundary and still matches. Any copy of that character arriving
in the text becomes a space first, so nothing can imitate a boundary. The
character is from the private use area, chosen after the obvious one, the record
separator, turned out to be counted as whitespace by Python and to be collapsed
away by the very step it had to survive.

**Test.** `tests/test_extract.py`, five tests: the splice is refused, three
honest quotes still match including one copied whole across the break, the marker
cannot be smuggled in, and the marker is not whitespace. Reverting the change
turns the first red.

---

## BUG-020 — A page could still forge the fence by ending a line the Windows way

**Found** 2026-09-05, by an audit, before the step had ever run unattended.

**Symptom.** The instruction sent to the model wraps the page's text in a fence
and rewrites anything inside it that looks like a fence delimiter, so a page
cannot end the quoted section and speak as though it were the instruction. A page
whose lines end with a carriage return slipped past that rewrite: the delimiter
reached the model intact, and the prompt carried two closing fences instead of
one. One of the two frozen pages is served with those endings, so this was
ordinary input rather than a contrived one.

**Cause.** The rewrite matches a delimiter alone on its line, and the end of a
line is matched only immediately before a newline. A carriage return sits between
the delimiter and that newline, so the pattern never lined up and the line was
left as the page wrote it.

**Fix.** Line endings are settled in the derivation, once, before anything reads
the text. The same page served either way now gives the same string to the model
and to every check.

**Test.** `tests/test_extract.py`, three cases: a carriage return inside a
paragraph, between two paragraphs, and alone. Each asserts none survives and that
the page reads the same as the same page written the plain way.

---

## BUG-043 — An error handed back to the model carried the page's own words

**Found** 2026-09-07, by a second opinion reading the slice against its own
specification, and it was introduced by the fix for BUG-033 the same day.

**Symptom.** The refusal raised when a deadline quote names a second date written
in figures said which date it was. That message travels into the next request, so
the page's own words were sent to the model a second time.

**Cause.** The message interpolated the matched text rather than counting it. The
rule against this is written down: an error handed back must carry no text read
from the source.

**Fix.** The message says how many were found and not what they are, which is
enough for the model to quote a narrower span.

**Test.** `tests/test_extract.py`, the same three shapes as BUG-033, now matching
a message that names no date.

---

## BUG-042 — A range of years written with a slash was refused as a telephone number

**Found** 2026-09-07, by a second opinion, and introduced by the widening of the
separators the day before.

**Symptom.** "The fellowship covers 2026/2027 in full." was refused as carrying a
telephone number. The academic year is written that way and a funding page is
full of them.

**Cause.** Reading a solidus as a separator inside a run of digits made the year
range eight digits joined by one, and the shapes known not to be numbers to ring
knew the dash forms only.

**Fix.** The slash joins the dashes in that exemption. Written with a plain space
it stays refused, because two groups of four digits with a space between them is
also exactly how a Danish local number is written, which is the defect BUG-025
was about.

**Test.** `tests/test_extract.py`, three shapes: a plain hyphen, an en dash and a
slash.

---

## BUG-041 — A stored value could carry an invisible character that is a line break by another name

**Found** 2026-09-07, by a second opinion reading the requirement rather than the
code.

**Symptom.** The rule is that a stored value carries nothing but words. The check
meant only the characters below the ASCII range, so a line separator, a paragraph
separator, a zero width space, a byte order mark, a soft hyphen or a direction
override passed into the title, the funder or any value, and reached the card.

**Cause.** The pattern was written when the concern was a tab or a line break
typed by a model. The same idea has a much wider membership in Unicode, and two
of them are line breaks under another name while the direction overrides make a
stored value read on the page as something other than what it says.

**Fix.** The pattern covers the format and separator characters as well. The cost
is that a script using a zero width joiner as ordinary writing would be refused,
which costs one further attempt.

**Test.** `tests/test_extract.py`, seven characters, one per shape.

---

## BUG-040 — Closing a furniture tag closed the outermost one of that name, not the innermost

**Found** 2026-09-07, by a second opinion, in the fix for BUG-021.

**Symptom.** A page that nests the same furniture tag, which a template does
whenever a menu holds a submenu, ended the whole filter at the inner closing tag.
Everything after it, the rest of the menu included, was read as the article.

**Cause.** The list of open furniture tags was searched from the front. Matching
by name was introduced so that a stray closing tag changes nothing, and it
searched from the wrong end.

**Fix.** The innermost tag of that name is the one that closes.

**Test.** `tests/test_extract.py`, a menu inside a menu and an aside inside an
aside. The existing test named for nesting used two different tag names, which is
the one nesting shape that already worked.

---

## BUG-039 — The cells of one row were run together with nothing between them

**Found** 2026-09-07, by a second opinion.

**Symptom.** A table row derived to its cells with no separator at all, so a label
in one column and a figure in another read as a single sentence a quote could be
built from.

**Cause.** A row was a block boundary and a cell was not.

**Fix.** A cell is its own block.

**Test.** `tests/test_extract.py`, two cells of one row, among the ten block
shapes a quote may not cross.

---

## BUG-038 — The end of a block was one line break, and one is not enough

**Found** 2026-09-07, by a second opinion, and the most serious thing found in
this project so far: BUG-019 was recorded as fixed and was not.

**Symptom.** A quote could still be stitched together from two unrelated blocks.
Reproduced through the whole gate: a sentence that is not on the page was
accepted as a budget's own evidence. It happens on both frozen pages, in markup
they really use, and the same page written `<br>` spliced while written `<br/>`
did not.

**Cause.** The end of a block was written as a single line break. A single line
break also arrives inside a block, from a page that wraps its own source, and the
collapsing step cannot tell those apart. It treated both as ordinary space, so
the boundary was lost for every shape that produced only one: a line break inside
a paragraph, and a block followed by loose text. Only two adjacent blocks
produced the blank line the fence actually required, and that is the only shape
the guarding test used.

**Fix.** The end of a block is written as a blank line, always. A line break
inside a block is still collapsed, so a sentence broken by a page wrapping its
source still matches itself.

**Test.** `tests/test_extract.py`, ten block shapes that must fence and three
continuous shapes that must not, plus the whole gate on the sentence that started
it. The old test asserted a single line break between two paragraphs, which was
the defect written down as an expectation.
## BUG-029 — A telephone number beside anything else with digits in it was published

**Found** 2026-09-05, by a skeptic set on refuting an audit's own research, and the
worst of the ten found that day.

**Symptom.** A quote carrying a real telephone number was published whenever
anything else with digits in it sat beside the number. Five of six ordinary
sentence shapes leaked, among them "Call CIPESA on +256 414 289 502 (8.00-17.00)
East Africa Time", built from this project's own first funder's contact line, and
a Danish funder's two office numbers written side by side. Reproduced against the
real code.

**Cause.** A run of digits does not stop where a telephone number stops. The
pattern that finds a candidate continues through a bracket, a second number, or a
set of opening hours, because a space, a bracket, a dot and a dash are all things
that appear inside one number. The merged run then held nineteen or twenty
digits, the length test said no number anybody can ring is that long, and the
whole run was cleared. The rule was therefore at its weakest exactly where a page
puts a number: in a contact line, next to other figures.

**Fix.** A run short enough to be one number is weighed whole, as before. A run
longer than that is broken at the places one number cannot continue across, which
are a bracket, a gap of more than one space, a dash with space on both sides, and
a plus starting a second number. Each part is then weighed on its own. This
removes a case the rule used to give up on rather than adding a guard.

**Test.** `tests/test_extract.py`, four shapes: a number then its opening hours, a
number then another in brackets, two numbers either side of a dash, and hours
written with a dot. Reverting the change turns all four red.

---

## BUG-022 — A line break hidden in a value passed the check and reached the record

**Found** 2026-09-05, by an audit, before any record had been built.

**Symptom.** A title given as `Civic\nData Grants 2026` was accepted as a whole
line of the page and stored with the line break in it. The same held for any
stored quote or value. Reproduced for a title and for a quote.

**Cause.** A value is compared with its whitespace collapsed and stored exactly
as the model wrote it. A line break or a tab therefore vanished for the
comparison and survived into the record. Two things depend on that not happening.
A title is required to be one whole line of the source, and a title spanning two
lines is not. And the printed record puts one field on one line so a person can
read it beside the page, which is where the checks stop and the human check takes
over.

**Fix.** A stored value may carry no control character. One rule, applied to the
title, to every quote, to every field value and to the funder.

**Test.** `tests/test_extract.py`, three cases through the builder: a line break
in the title, a tab in a value, and a line break in a quote.

---

## BUG-023 — A fabricated number was grounded on part of a larger one

**Found** 2026-09-05, by an audit, before any record had been built.

**Symptom.** A claimed reach of 87 countries was accepted on a page whose only
number is the year 1987. The page states nothing about 87 of anything.

**Cause.** The rule that every number of two or more digits in a value must be
supported was written as a search for those characters anywhere in the page. The
digits of 87 sit inside 1987, so the search succeeded. Every number in the page
was therefore a hiding place for any number whose digits it happened to contain,
which includes years, identifiers and every larger figure.

**Fix.** The numbers the evidence states are read out with the same rule used to
read them out of the value, and the two are compared as numbers. A figure now has
to be one the page actually states.

**Test.** `tests/test_extract.py`, two tests: the fabricated 87 is refused on a
page that says 1987, and a claim resting on 1987 itself is still accepted.

---

## BUG-024 — Four spaces bought a one word quote past the length floor

**Found** 2026-09-05, by an audit, before any record had been built.

**Symptom.** The quote `Africa` was refused as too short to prove anything, which
is what the floor exists for. The quote `Africa    ` was accepted.

**Cause.** The length was measured on the raw string and the grounding on the
collapsed one, so whitespace counted towards the floor while adding nothing that
could be checked. The suite's own test for this rule was named for a one word
quote proving nothing, and a one word quote could pass.

**Fix.** Both are measured on the same form, the one the comparison uses.

**Test.** `tests/test_extract.py`, the padded quote is refused and the reported
length is the real one. A second test covers the ceiling, which had none: the two
bounds are one chained comparison, so either half failing satisfied a coverage
report the same way and the ceiling could have been removed with nothing turning
red.

---

## BUG-025 — A local telephone number written as two groups of four was exempt

**Found** 2026-09-05, by an audit, before any record had been built.

**Symptom.** `Call our office at 2345-6789 for details` was reported as carrying
no contact detail. A real telephone number could therefore reach a quote stored
in a public repository that keeps its history.

**Cause.** An exemption added so that a range of years such as 2024-2025 would
not be read as a telephone number. It was written as any four digits, a dash and
any four digits, which is also how a great many countries write an ordinary local
number.

**Fix.** A range has to look like years for the exemption to apply.

**Test.** `tests/test_extract.py`, the local number is caught, and a recent and
an older range of years are both still allowed.

---

## BUG-026 — An amount with the currency written after it was read as a telephone number

**Found** 2026-09-05, by an audit, before any record had been built.

**Symptom.** `grants of up to 12.345.678 EUR` was refused as carrying a contact
detail. The same amount written `EUR 12.345.678` was accepted.

**Cause.** The rule that a currency marker makes a run of digits money looked
only at the text before the run. Writing the currency after the figure is
ordinary in much of Europe, and grouping thousands with periods is ordinary with
it.

**Fix.** The rule looks on both sides of the run.

**Test.** `tests/test_extract.py`, two shapes: the currency code after the figure,
and thousands grouped with spaces.

---

## BUG-021 — A stray closing tag let a page's menu through as though it were the article

**Found** 2026-09-05, by an audit, before any record had been built.

**Symptom.** The derivation drops a page's own furniture, its menus, footers and
forms, because a menu lists the funder's other programmes and a sentence from one
of those is a real substring of this page. It would pass the quote check while
describing a different grant. A page that closed a tag it never opened unwound
that filter partway through, and the rest of the menu was read as though it were
the article.

**Cause.** One shared count of how many furniture tags were open, incremented on
any opening tag and decremented on any closing one, whichever tag it was. A
closing tag with no opening partner therefore reduced the count while the page
was still inside a menu. Pages built by a template drop tags this way in ordinary
use.

**Fix.** The names of the open furniture tags are kept instead of a count, and a
closing tag matches by name. A stray one now changes nothing, and closing an
outer tag closes whatever was opened inside it.

**Test.** `tests/test_extract.py`, one test for the stray closing tag and three
for the ordinary shapes: nested and both closed, never closed, and opened and
closed normally. Reverting the change turns the first red.

---

## BUG-018 — Git rewrote the archive, so a quote verified on one machine and failed on every other

**Found** 2026-09-03, by measurement, before any item had been archived.

**Symptom.** A capture of 54 bytes was stored by git as 52 and came back from a
fresh clone as 52. A quote spanning a line break was found in the original
capture and was not found in the clone. Nothing had gone wrong yet only because
the archive was still empty. As soon as it held anything, the check that runs on
every push and again on rebuild would have refused honest quotes, on the machines
that did not capture them, for a reason nothing in the output would explain.

**Cause.** `.gitattributes` told git to normalise line endings across every file
in the repository. That was written when this repository held only code, where it
prevents a whole class of works-on-my-machine trouble, and it is right for code.
It became wrong when the repository started holding evidence. A source serving
Windows line endings gave one string during the run and a different string after
a clone, and the quote check compares character by character.

**Fix.** Two lines excluding the archive and the frozen test fixtures from that
rule, so both come back exactly as the server sent them. It also makes true a
decision already taken, that the raw stays perfectly verbatim so anything can be
re-derived from it. See
[ADR-0034](decisions/0034-the-derived-text-and-the-builder-version.md).

**Test.** `tests/test_gitattributes.py`. It drives git rather than trusting it:
it writes a capture with Windows line endings into a throwaway repository using
this project's own `.gitattributes`, commits it, clones it, and asserts the bytes
are unchanged and that a quote spanning the line break still matches. Removing
the two lines turns all three cases red.

## BUG-017 — A source could send the run to an address the watch list never chose

**Found** 2026-09-02, by probing, before release.

**Symptom.** The fetch step's own opening paragraph said reaching somewhere off
the watch list could not be expressed. It could. Five private addresses placed
on a watch list were all fetched and read. Worse, redirects were followed
without question, so an ordinary public source answering with a redirect to a
link-local address was followed there and its body captured, and the run commits
what it captures to a public repository.

**Cause.** The claim was true of the function's shape, which takes a source
rather than an address, and false at run time, where nothing checked what the
address actually was and redirects were handled by the network library rather
than by us.

**Fix.** Every address is checked before it is reached, including each redirect
hop, which is why redirects are now followed by the fetch step rather than by
the library. Loopback, private, link-local, reserved, multicast and unspecified
addresses are refused, as are names that mean a machine on this network. A
refusal is permanent and not retried, because the address will be just as
private on the third attempt. A name that resolves to a private address is not
caught, which is stated in the code rather than left to be discovered.

**Test.** `test_an_address_off_the_open_internet_is_refused`,
`test_a_redirect_off_the_open_internet_is_refused`,
`test_an_ordinary_redirect_is_still_followed` and
`test_a_source_that_redirects_in_circles_gives_up` in `tests/test_fetch.py`.

## BUG-016 — What the source served was thrown away before it was archived

**Found** 2026-09-02, by probing, before release.

**Symptom.** Capture before derive is the rule the whole design rests on, and
the code did the opposite. A response was parsed, filtered, reduced to three
joined fields per item, and only that was written. A feed carrying a publication
date, an author and a category archived none of them, and the response itself
was nowhere: not on disk, and not in git, because it had never been written.

**Cause.** Reading the response happened inside the fetch, so by the time
anything could have been written down there was nothing left but the result.

**Fix.** The fetch returns the response unread. The run writes it down, then
reads items out of it. Responses are kept per source, named by a hash of their
own bytes, and each item's record names the response it came from.

**Rule this established.**
[ADR-0030](decisions/0030-the-response-is-the-capture.md).

**Test.** `test_the_response_comes_back_exactly_as_served` in
`tests/test_fetch.py`; `test_what_the_source_served_is_written_down_whole`,
`test_an_item_names_the_response_it_was_read_out_of` and
`test_a_source_serving_the_same_response_does_not_churn` in
`tests/test_calls.py`.

## BUG-015 — A blocked source looked healthy, and then healthy for ever

**Found** 2026-09-02, by probing, before release.

**Symptom.** A source behind a gate answers with a holding page rather than a
feed. The run reported it as a healthy source with nothing new, **saved the
holding page's bookmark**, and every run afterwards reported it unchanged. A
dead source and a quiet one were indistinguishable, permanently. With one source
on the watch list the whole system could be dead and reporting success.

**Cause.** A holding page and an empty feed both yield no items, and nothing
told them apart.

**Worth knowing.** The obvious signal was the wrong one. The feed reader's
complaint flag is not raised for a holding page at all, so a check on it would
have looked right and caught nothing. What separates them is that a feed always
names its own format and a holding page never does. That was found by trying six
kinds of response and reading what came back, rather than by reasoning about it.

**Fix.** A response that names no feed format is refused. The source is skipped
with the reason, its bookmark is not saved, so the next run looks again instead
of believing it, and the page itself is kept as the evidence. An empty but valid
feed is still healthy and keeps its bookmark.

**Test.** `test_a_response_that_is_not_a_feed_is_refused` and
`test_an_empty_but_valid_feed_is_not_refused` in `tests/test_fetch.py`;
`test_a_blocked_source_is_skipped_and_keeps_no_bookmark` and
`test_an_empty_feed_is_not_mistaken_for_a_blocked_one` in `tests/test_calls.py`.

## BUG-014 — Every day committed to the archive, even when nothing had changed

**Found** 2026-09-02, by rehearsing a whole scheduled run twice, before release.

**Symptom.** The workflow has a step that says "nothing new to commit" and stops
early. It could never run. A day on which the source published nothing new still
produced a commit. Over a year of quiet that is several hundred commits recording
nothing, and the archive's history stops answering what it exists for: when did
this item actually change.

**Cause.** Each item's record stored the moment it was fetched, taken fresh every
run. The bodies never churned, because writing identical bytes is not a change,
but the records did, on that timestamp alone. The record was describing the run
rather than the item.

**Worth knowing.** Every test passed throughout and a single live run looked
perfect. The fault only appears on the second day, and only when the result is
committed, which is why nothing local had caught it. The missing test was not a
grand one: capturing the same item twice should write the same bytes.

**Fix.** Every field in the record is now a fact about the item. The time it
carries is when the item first entered the archive, and it does not move
afterwards. When the run last looked belongs with the run's bookmarks, which do
not churn.

**Rule this established.**
[ADR-0029](decisions/0029-the-archive-records-the-item-not-the-run.md).

**Test.** `test_capturing_the_same_item_again_writes_the_same_bytes`,
`test_the_first_capture_is_the_one_the_record_keeps` and
`test_an_unreadable_record_does_not_stop_the_next_run` in `tests/test_archive.py`.

## BUG-013 — Two sources carrying one call would have overwritten each other

**Found** 2026-09-02, by the pre-push audit, before release.

**Symptom.** Three rules name a captured item, and only the first carried the
source. Two sources that both carried a funding call, an aggregator and the
funder itself, would have produced one name under the second rule. The second
capture would have overwritten the first: its body, and the record of where it
came from, gone. The run log would have reported two new items where the archive
held one.

**Cause.** The name was doing two jobs it cannot both do. Naming one source's
capture needs the source in it. Deciding that two captures are the same call
needs the source left out. One string cannot be both, and the rules were
inconsistent about which job they were doing.

**Worth knowing.** Which rule applies depends on what a publisher includes, so
the same two sources would have collided or not depending on which software a
funder happens to run. Nine feeds in this sector were fetched to check: every one
of the five that answered publishes a per-item identifier, so the collision was
the rare path and would have surfaced late and inconsistently.

**Fix.** Every rule carries the source, so a name identifies one source's
capture and nothing can overwrite anything. The canonical link stays recorded
un-namespaced, because it is the evidence for deciding later whether two
captures are one call. That decision moves to the card, where the funder, the
title and the deadline are better evidence than two links being equal.

**Rule this established.**
[ADR-0028](decisions/0028-a-name-identifies-one-sources-capture.md).

**Test.** `test_every_rule_names_one_source_capture` and
`test_the_same_source_reporting_again_keeps_one_file` in `tests/test_archive.py`,
`test_two_sources_carrying_one_call_each_keep_their_capture` and
`test_the_log_count_matches_what_the_archive_holds` in `tests/test_calls.py`.

## BUG-012 — A run cut short between an item's two files stranded it for ever

**Found** 2026-09-02, by the pre-push audit, before release.

**Symptom.** Each captured item is two files: the body and the origin record
beside it. They were written body first. Whether an item is already known is read
from the bodies alone, so a run that died between the two writes left a body with
no origin beside it, and every run after that took the item for known and never
wrote it again. The origin record for that item was lost permanently.

**Cause.** The order of the two writes was arbitrary, and the arbitrary order was
the unsafe one. A scheduled run on a shared machine can be cut short at any
point, so the gap between two writes is real rather than theoretical.

**Fix.** The origin record goes down first and the body second. A run cut short
now leaves no body, the item still counts as unseen, and the next run writes both.
This is the same reasoning that already sets the order of writing against
checking: leave the state that repairs itself, not the state that strands.

**Test.** `test_the_origin_record_is_written_before_the_body` in
`tests/test_archive.py`.

## BUG-011 — A failed source reported the name of the fault and threw away what it said

**Found** 2026-09-02, by the pre-push audit, before release.

**Symptom.** When a source could not be reached, the run recorded only the class
of the fault, so the log read `hewlett: ConnectTimeout` and nothing more. Which
address, which timeout, and what the machine actually reported were all
discarded. There is no log file and no stored trace, so that one line is the
whole account of the failure.

**Cause.** The line built its text from the fault's type name alone and never
included the fault itself.

**Fix.** The message is kept alongside the name. The watch-list reader already
did this correctly, and the fetcher now matches it.

**Test.** `test_a_failed_source_reports_the_message_not_just_the_name` in
`tests/test_fetch.py`.

## BUG-010 — A run that fell over threw away everything it had already captured

**Found** 2026-09-02, by the pre-push audit, before release.

**Symptom.** The scheduled run archives each source's items as it goes, then
commits everything at the end. The commit step was skipped whenever the capture
step failed. So a run that reached three sources and fell over on the fourth
discarded all three sources' captured items when the machine was torn down, and
the next day fetched them all again.

**Cause.** A step in a scheduled job does not run by default once an earlier step
has failed. Nothing said this one should.

**Fix.** The commit step now runs whatever happened before it. Work already
written down is committed even when the run did not finish.

**Test.** None. This is one line of workflow configuration and the test suite
does not run workflows. It is proved by triggering the run by hand, which is part
of the end-to-end check for this slice.

## BUG-009 — A feed that could not be read stopped the whole run

**Found** 2026-09-02, by the pre-push audit, before release.

**Symptom.** The rule is that one broken website never stops the others, and that
held for every way a site can fail to answer. It did not hold for a site that
answered with something unreadable. A feed carrying an impossible date, for
instance the thirty-first of a thirty-day month, raised while its items were
being read, and nothing caught it. The run stopped there, every later source went
unread, and no line was printed to say why.

**Cause.** Turning a fetched body into items happened inside the part of the code
that catches network faults, but the catch named network faults only. A fault
from reading the body was a different kind and passed straight through.

**Fix.** A body that cannot be read now fails that source alone, with the reason,
and the run carries on. It is not retried, because reading it again would fail in
exactly the same way.

**Test.** `test_a_feed_that_cannot_be_read_skips_its_source` in
`tests/test_fetch.py`.

## BUG-008 — The same source listed twice was accepted and confused itself

**Found** 2026-09-02, by the pre-push audit, before release.

**Symptom.** Nothing stopped two entries in the watch list from carrying the same
identifier. A run then processed the first, saved its bookmark under that
identifier, reached the second, and read back the bookmark the first had just
written. The second was therefore treated as a source already seen rather than a
first look, so its whole backlog was announced as new activity. That is exactly
the symptom BUG-005 was written to remove, reached by a different route.

**Cause.** The identifier is the name under which a source's bookmark is filed,
which only works if it is unique, and nothing checked that it was. A watch list
is edited by hand, so a copy and paste that keeps the old identifier is an
ordinary mistake rather than a far-fetched one.

**Fix.** A repeated identifier is refused when the watch list is read, before any
network request, naming the identifier that was repeated. The check spans every
entry rather than one kind, because a bookmark is filed under the identifier
alone. This follows BUG-006, which established that a broken watch list must say
which entry is broken.

**Test.** `test_the_same_id_twice_is_refused_by_name` and
`test_a_repeat_across_kinds_is_refused_too` in `tests/test_models.py`.

## BUG-007 — A source that sent its response slowly was never abandoned

**Found** 2026-09-01, in review, before release.

**Symptom.** A source is supposed to be abandoned when its response passes the
size or the time cap. Only the size cap existed. A source that answered promptly
and then sent its body a few bytes at a time, never pausing long enough to trip
the per-read limit, would be read for as long as it cared to keep sending.

**Cause.** The only limit in the fetcher was the network timeout, which bounds a
single connection attempt or a single read, not the total time spent reading a
body. The reading loop counted bytes and nothing else. Worse, a read that did
eventually time out was fed into the retry path, so a stalling source was tried
three times rather than dropped, which is the opposite of what a cap means.

**Fix.** The reading loop takes a deadline when it starts and abandons the body if
it passes, exactly as it abandons a body that grows too large. Passing either cap
skips the source with no retry.

**Test.** `test_a_stalling_response_is_abandoned` in `tests/test_fetch.py`.

## BUG-006 — A broken watch list did not say which entry was broken

**Found** 2026-09-01, in review, before release.

**Symptom.** A source entry with a missing field, or a route the system does not
implement, correctly stopped the run before any network request. But the error
named only the offending value. With several sources in the file, nobody could
tell which entry it came from.

**Cause.** The whole list was checked in one expression, so a failure carried the
field that failed and nothing about the entry around it.

**Fix.** Each entry is checked on its own, and a failure is reported naming that
source's identifier, or its position in the file when the identifier is itself
the missing field.

**Test.** `test_a_route_nobody_implements_is_named_with_its_block` and
`test_a_block_missing_its_id_is_named_by_its_position` in `tests/test_models.py`.

## BUG-005 — A source's first look announced its whole backlog as new activity

**Found** 2026-09-01, in review, before release.

**Symptom.** The first look at a source archives everything it publishes back to
that source's cutoff date. Every one of those items was counted and reported as
new activity, so adding a source would produce a burst of false news. The
requirement says a first run must not be treated as new activity worth
reporting.

**Cause.** The run asked only whether an item was absent from the archive before
the run started. On a first look everything is absent, so everything counted.
Nothing in the run told a first look apart from any later one.

**Fix.** A first look is recognised by the absence of a stored bookmark for that
source. The run labels it a first look, archives everything as before, and counts
none of it as new, because those items are new to the archive rather than new in
the world.

**Worth knowing.** Two tests asserted the wrong behaviour as the expected answer,
so the gate was green over this the whole time. Both were corrected with the fix.

**Test.** `test_a_run_captures_from_every_call_source` and
`test_a_later_run_counts_only_the_genuinely_new` in `tests/test_calls.py`.

## BUG-004 — The check for "nothing has changed" could never fire

**Found** 2026-09-01, while building, before release.

**Symptom.** A source that answers that nothing has changed should be noted and
skipped without reading a body. The comparison that detects that answer was
always false, so every unchanged source would have had its whole body fetched,
parsed and re-archived on every run, for ever.

**Cause.** The code compared the response against a named value taken from the
network library. In the pinned version of that library the value is a pair rather
than a single number, so the comparison could never match.

**Fix.** The response is compared against the number itself, named once at the top
of the file so it still reads as a name rather than a bare figure.

**Worth knowing.** The strict type check in the gate found this. No test would
have: the tests would have kept passing while the system quietly did the
expensive thing every time.

**Test.** `test_an_unchanged_source_is_read_no_further` in `tests/test_fetch.py`.

## BUG-003 — An item's name could have addressed a file outside the archive

**Found** 2026-09-01, while writing the specification, before the code existed.

**Symptom.** An item's name becomes its filename. The first naming rule used the
identifier the source published for that item, taken as given. A source
publishing an identifier of `../../config/sources.toml` would have written
outside the archive and over the watch list.

**Cause.** The naming rule treated a value from the open web as a safe name. The
existing rule that fetched text is untrusted covered text reaching the model, and
nobody had extended it to fetched text that becomes a path.

**Fix.** Every naming rule hashes its input, so a name is always a fixed-length
hexadecimal string and cannot contain a path separator. The three rules and their
order of preference are unchanged. This removes the possibility rather than
checking for it.

**Rule this established.**
[ADR-0026](decisions/0026-item-names-are-always-hashed.md).

**Test.** `test_a_hostile_identifier_cannot_escape_the_archive` in
`tests/test_archive.py`.

## BUG-002 — The heartbeat was described two ways and worked as neither

**Found** 2026-08-26, in the specification, before the code existed.

**Symptom.** The heartbeat was described in some places as written on every run
and in others as written only after a run that produced data, and was said to
make an empty run visible. Neither version does that.

**Cause.** One mechanism was being asked to prove two different things: that a run
happened at all, and that a run found something.

**Fix.** The heartbeat proves liveness only. It is written on every run that
executes, so a run that is silently dropped goes stale, which is the real alarm.
Whether a run found anything is a separate check, the per-source item count
baseline.

**Rule this established.**
[ADR-0002](decisions/0002-heartbeat-proves-liveness-not-emptiness.md).

**Test.** Arrives with the health page and the heartbeat at PR 7 and PR 14, where
this behaviour is built.

## BUG-001 — A passing deadline would have made a stored call fail validation

**Found** 2026-08-26, in the specification, before the code existed.

**Symptom.** Validation required a dated call's deadline to parse as a date in the
future, and validation re-runs on every push. The day a deadline passed, the
stored call would fail its check and the rebuild step would reject every expired
call. Keeping closed calls is a stated goal: finding the January report in July,
and counting past activity in the quarterly read.

**Cause.** Whether a call is still open was treated as a property of the stored
record rather than as something worked out when the call is shown.

**Fix.** The permanent check is that the deadline parses as a valid date. Open
against closed is derived from today's date at the moment of display, and the
archive keeps closed calls.

**Rule this established.**
[ADR-0001](decisions/0001-deadline-validates-as-a-valid-date.md).

**Test.** Arrives with validation at PR 4, where this rule is implemented.
