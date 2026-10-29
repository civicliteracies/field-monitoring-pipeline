# The plan

This plan lists everything we are building, in the order it will be built. Each item includes its
pull request title and a plain-English explanation of what it does. Items are checked off as each
update is completed.

Our daily automated run follows seven steps in order:

1. Fetch: Finding new funding opportunities.
2. Store the raw: Saving exact, untouched copies of the original pages.
3. Identify: Giving each opportunity a permanent ID to avoid duplicates.
4. Read the stated facts: Extracting key information, partly using artificial intelligence.
5. Validate: Checking that all quoted proof sentences actually appear in the original text.
6. Write the card: Saving clean, structured summary sheets to our archive.
7. Publish: Delivering new cards to subscribers through a news feed.

Some tasks sit outside this daily run, including project documentation, code quality checks, tools
run by hand, and quarterly reports.

## The first version: the funding calls of one source, each to a card and into a feed reader

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
- [x] **11. `feat(publish): build the feed from the cards`**
      Publish (publishing). An RSS file is rebuilt from the cards each morning, one entry per card,
      so a new funding call arrives in a feed reader the day it is found. Each entry carries the title
      with the closing date, a link to the card, the summary, and the call's code as its identity.

## The second version: topics, more sources, the project reports and the sector's direction

- [x] **12. `feat(extract): log each model response`**
      Whenever the artificial intelligence reads a funding call, Fieldbook saves the model's exact,
      raw response directly into a log file before generating the final card. This gives us a
      permanent audit trail, allowing anyone to review the model's original words and verify how it
      arrived at each extracted fact.
- [x] **13. `feat(tags): tag cards with topics from the topic list`**
      We maintain a plain text list of relevant topics, classifying each topic as either primary
      (areas where our organization actively works) or secondary (areas we simply monitor). Instead
      of relying on the artificial intelligence, Fieldbook's own code automatically matches the labels
      the source put on each call against this list and attaches the matching topics to its card,
      making it easy to group and filter cards by topic.
- [x] **14. `feat(sources): add a second source of calls`**
      Fieldbook adds a second funding website to its monitoring watch list after we manually verify
      that the website regularly publishes open calls. Any calls gathered from this new
      source are converted into standard cards, stored in the same archive directory, and published
      through the same RSS feed.
- [ ] **15. `feat(reports): ingest project reports as cards`**
      Once a week, Fieldbook runs a separate background workflow dedicated to reading completed
      project reports rather than funding calls. It turns each report into its own card inside a
      dedicated folder, extracting the organization name alongside five key details: the target
      audience, the research methodology, the final results, the project duration, and the
      geographic area, with each detail accompanied by its exact supporting quote from the report.
- [ ] **16. `feat(direction): generate the quarterly sector report`**
      Once every quarter, Fieldbook runs a completely offline script without using artificial
      intelligence. The code analyzes all stored cards by funder and by topic, producing a quarterly
      summary with statistics and charts. This report highlights topics that attracted interest from
      three or more funders, shows which topics grew or declined compared to the previous quarter,
      and lists any newly detected funding organizations.
- [ ] **17. `feat(discover): suggest new funders to watch`**
      This introduces an on-demand tool that a person can run by hand. The script compares our
      existing archive against a public registry to find funding organizations we have not
      encountered yet. It produces a list of suggested funders along with an explanation for why
      each one might be relevant, without altering the active watch list automatically.
- [ ] **18. `docs: add a guide for adding a source`**
      A new, straightforward guide added to the project documentation explains step by step how to
      add a new funding portal to the watch list, along with the specific quality checks to perform
      before adding it.

## Looking ahead: Ideas after version two

Future updates may focus on smarter filtering and a public interface. Ideas under consideration
include ranking grants by how closely they match our team's mission, creating a dedicated reader
view for project reports, automatically linking related past and present grants, enabling
concept-based semantic search, and launching a public web portal for anyone to browse our findings.
