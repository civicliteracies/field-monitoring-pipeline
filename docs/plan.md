# The plan

What is being built, in the order it is built. Each line carries the title the change will be made
under and a short plain description of what it does, and is ticked by the change that completes it.

The run has seven steps, and each line below says which one it belongs to: Fetch (ingestion), Store
the raw (raw storage with provenance), Identify (stable identifiers), Read the stated facts
(extraction), Validate (validation), Write the card (serialisation), Publish (publishing). Three
changes sit outside the run, in the records and in the checks that guard the code.

## This version: one funding call, from one source, to a card and into a feed reader

- [x] **1. `docs: add README overview, decision log, bug history and architecture map`**
      Outside the run. The front page says what Fieldbook is, and `docs` gains this plan, the
      decision log, the bug history and the map of every file.
- [ ] **2. `chore(hooks): run every hook from the project environment`**
      Outside the run, in the quality gate. Every check git runs by itself uses the copy of the tool
      the project installed, rather than fetching a second copy of its own, so no version number is
      written in the hook settings.
- [ ] **3. `chore(hooks): run the whole quality gate from the pre-push hook`**
      Outside the run, in the quality gate. One read-only task holds the four checks, and sending code
      runs it over the whole project: linting, formatting checked, the strict type check and the
      tests. A value that cannot be what the code says it is stops here.
- [ ] **4. `feat(fetch): fetch the open calls of the source on the watch list`**
      Fetch (ingestion). A plain text file names each source Fieldbook reads and its address, and
      Fieldbook asks that source for the calls it has open, leaving out any whose closing date has
      already passed.
- [ ] **5. `feat(store): store each call once`**
      Store the raw (raw storage with provenance) and Identify (stable identifiers). Each call is
      written down once, exactly as it arrived, in one file named by a code made from the source's
      own identifier, together with where it came from and when it was collected. A call already
      stored is left alone. One command now runs the steps in order.
- [ ] **6. `ci(schedule): run the command every morning`**
      Fetch (ingestion) and Publish (publishing). GitHub runs that command every morning and commits
      what it stored to the `data` branch, which holds the archive and shares no history with the
      code. It commits what was stored even when the run stopped with an error, and only when
      something has changed.
- [ ] **7. `feat(models): define what a funding call is made of`**
      Validate (validation). One template names the fields of a card: the title, the type, the
      funder, the budget, the summary, who can apply and where, and the closing date, which is empty
      when the call stays open. Each value read from a page's prose carries the sentence it came
      from.
- [ ] **8. `feat(extract): read one stored call into a call record`**
      Read the stated facts (extraction). One language model call reads a stored call under a fixed
      instruction and answers with the facts it states, each with the sentence it rests on. The
      project's own code turns that answer into a record, which notes which instruction and which
      model read it.
- [ ] **9. `feat(validate): refuse a record whose quotes are not in the stored text`**
      Validate (validation). Every quoted sentence is checked word for word against the stored text.
      A failure goes back to the model once; a second failure writes nothing.
- [ ] **10. `feat(serialize): write each new record as a card`**
      Write the card (serialisation), with the coordination that sits on top of the steps. One
      record becomes one Markdown file that GitHub shows as a page: the fields on top for machines,
      and below them each quoted fact with the funder's own sentence under it. A call that already
      has a card is not read again.
- [ ] **11. `feat(publish): build the feed from the cards`**
      Publish (publishing). An RSS file is written from the cards, one entry per card, so a new
      funding call arrives in a feed reader the day it is found.

## After this version

Topics on each card, the remaining call sources one at a time, the project reports on their own
weekly run, the quarterly reading of where the sector is going, the proposals of funders not yet
followed, and a guide to adding a source.
