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
