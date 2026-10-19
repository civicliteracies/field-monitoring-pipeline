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
- [x] **2. `chore(hooks): run every hook from the project environment`**
      Outside the run, in the quality gate. Every check git runs by itself uses the copy of the tool
      the project installed, rather than fetching a second copy of its own, so no version number is
      written in the hook settings.
- [x] **3. `chore(hooks): run the whole quality gate from the pre-push hook`**
      Outside the run, in the quality gate. One read-only task holds the four checks, and sending code
      runs it over the whole project: linting, formatting checked, the strict type check and the
      tests. A value that cannot be what the code says it is stops here.
- [x] **4. `feat(fetch): fetch the open calls of the source on the watch list`**
      Fetch (ingestion). A plain text file names each source Fieldbook reads, its address and the
      words it searches for, and Fieldbook asks that source for the grant topics it has open or has
      announced, leaving out any whose closing date has already passed, and can bring back a call's
      web page.
- [x] **5. `feat(store): store each call once`**
      Store the raw (raw storage with provenance) and Identify (stable identifiers). Each call is
      written down once: its web page exactly as downloaded, and the source's record of it with
      every value as sent. Both go in the source's folder, and both are named by a code made from
      the call's identifier. One log records where each call came from, when it was collected, and
      whether it was saved or failed and why. It also records how each run ended for each source:
      successful, failed or nothing new. A call already saved is left alone, and one that
      failed is tried again by the next run. One command now runs the steps in order.
- [x] **6. `ci(schedule): run the command every morning`**
      Fetch (ingestion) and Publish (publishing). GitHub runs that command every morning and commits
      what it stored to the `data` branch, which holds the archive and shares no history with the
      code. It commits what was stored even when the run stopped with an error, and only when
      something has changed. This change also adds a rules file to that branch, which tells git to
      leave stored pages exactly as they arrived, and rewrites the branch's front page.
- [x] **7. `feat(models): define what a funding call is made of`**
      Validate (validation). One template names the fields of a card: the title, the type, the
      funder, the opening date, the deadline, the budget, the summary, who can apply and where, and
      the link. A call with no deadline stays open. Both dates, the budget, the summary, who can
      apply and where each carry a sentence beside the value, or for a date or the budget the
      source's own field written out as one line, so a person can check it. The template refuses a
      record that does not fit.
- [x] **8. `feat(extract): read one stored call into a call record`**
      Read the stated facts (extraction). The project's own code copies the title, the two dates and
      the budget from the source's own record, each date and the budget with its field written out
      as one line. A language model reads the stored call under fixed instructions. It names the
      type, the funder, the summary, who can apply and where, the last three each with the sentence
      it rests on. The code turns both into a record, which notes which instructions and which model
      read it. It was run by hand until item 10.
- [x] **9. `feat(validate): check each quote against the stored text`**
      Validate (validation). Every quoted sentence is looked for word for word in the stored text,
      and the record marks each one found or not found. When a sentence is not found, or the model's
      answer cannot be used, the model is asked once more, with a message the code writes naming
      each problem. A sentence still not found stays on the record, marked. The code writes a note
      for it, and one for each problem and each empty field.
- [x] **10. `feat(serialize): write each new record as a card`**
      Write the card (serialisation), with the coordination that sits on top of the steps. The daily
      run now reads every stored call that has no card. One record becomes one Markdown file that
      GitHub shows as a page: the fields on top for machines, and each fact below them. The funder's
      own sentence sits under the summary, who can apply and where, a line from the source's own
      record under the dates and the budget, and a warning under a sentence not found. The log gains
      a row for each call read, `card written` with its notes or `failed` with its reason. A call
      that has a card is not read again, and one whose reading failed is read again the next
      morning.
- [ ] **11. `feat(publish): build the feed from the cards`**
      Publish (publishing). An RSS file is written from the cards, one entry per card, so a new
      funding call arrives in a feed reader the day it is found.

## After this version

Topics on each card, the remaining call sources one at a time, the project reports on their own
weekly run, the quarterly reading of where the sector is going, the proposals of funders not yet
followed, and a guide to adding a source.
