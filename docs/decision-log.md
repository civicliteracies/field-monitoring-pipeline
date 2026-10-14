# Decision log

How Fieldbook handles what it collects, organised by topic. Each entry documents a choice that
affects what the tool does, and records only what a reader could not work out from the code.

The first section, **Pending decisions**, lists choices that are open. Each one names the situation,
the question, what happens in the meantime and what that wait costs, and the technical detail of what
would unblock it, so a reader knows what is compromised. When a pending decision resolves it moves
into the section it belongs to as an ordinary entry, and the pending entry is deleted. Every change
that decides something adds its entry here, in the same pull request.

## 0. Pending decisions

### Which source goes on the watch list first?

**Situation.** Fieldbook reads only the sources named on its watch list, and the list carried from
earlier work holds one source that publishes essays and announcements rather than funding calls.

**Question.** Which source is first, and does it publish its calls as feed entries or only as web
pages?

**Status quo.** No source is on the list. A run over the source carried from earlier work would reach
it, store what it served and produce no cards, which proves the plumbing and nothing about the
reading. The cost of waiting is that the reading step can only be tried on pages fetched by hand, so
the one uncertain part of the tool stays unproven against a real source.

**Technical detail.** CLI names the source. If it publishes a feed or a public data service, the
collecting change reads that; if it publishes calls only on web pages, the collecting change also
keeps each page and takes its text from it.

### When is the key for the reading step set?

**Situation.** The reading step sends the text of a stored item to a language model, and that request
needs a key.

**Question.** Is the key set before the reading step is built, or after the first card has been
produced by hand?

**Status quo.** No key is set, and no step that would use one is built yet. Collecting and storing
never need a key. The cost arrives with the daily run: it will collect and store without reading, so
the archive will grow while the cards do not.

**Technical detail.** The key is never written into a file of this repository. A run reads it from
the repository's settings, in a form chosen when the key is set.

### Who builds the page that searches the whole archive?

**Situation.** The cards are plain files with a stable shape, which a searchable page can read
directly.

**Question.** Is that page built here, or elsewhere by whoever wants it?

**Status quo.** There is no such page, and no archive to search yet. Once cards exist they are
browsed as folders on github.com and searched with the search built into the site. The cost is that
finding an old call will mean knowing roughly where to look.

**Technical detail.** Whoever builds it reads the card files and builds an index outside this
repository. Nothing here changes for that, provided the card keeps its shape.

### When are urgent calls floated to the top of the feed?

**Situation.** The feed carries new cards in the order they are found.

**Question.** When should a call that closes soon be ordered above one that closes later?

**Status quo.** No ordering by urgency. While the feed holds less than a screen of open calls,
ordering changes nothing a reader would notice. The cost is that once the feed is longer than a
screen, a call closing this week can sit below one closing in six months.

**Technical detail.** The decision is taken when the feed change is planned, and it needs the
deadline, which every dated call carries.

### When does the reading step move to a paid model?

**Situation.** The reading step is the only part of the tool that uses a model, and like everything
else the tool uses, the model runs on a free tier.

**Question.** At what point is a paid model worth what it costs?

**Status quo.** A free tier model reads every item and nothing is paid. The condition for paying is
that the model is shown to be what holds the tool back. The cost of waiting is that a free tier's
limits and terms can change without notice.

**Technical detail.** When the reading step is built, it names its model in one place and every card
records which model read it, so a move to a paid model changes one setting.

## 1. The goal

Keep CLI current with its own sector without anyone tending it. What arrives each week is read once
and lost, so the system is built around memory: everything collected is kept, and everything shown is
derived from what was kept.

## 2. The shape of a run

A run takes each item through seven steps, in order. Reach the sources on the watch list and bring
back what they published. Write down what came back, once and unchanged, together with where it came from.
Give each item a stable name of its own. Read the facts the item states, with one language model
call. Check what was read against what was stored. Write the card. Save the cards and build the feed.

Three things stay apart inside every step: the data, declared in files a person can read; the
behaviour, plain functions that act on it; and the coordination, a single command that calls the
steps in order and holds no rules of its own.

## 3. Storage

### Where does everything the tool collects live?

**Situation.** The system has to keep every item it collects, for years, on free services, and stay
readable without specialist tools.

**Decision.** One plain file per item in this repository. No server, no database engine, no committed
index. Anything derived is rebuilt from the files and never stored beside them.

**Rationale.** The history of the repository becomes the audit log, its permissions become the access
control, and nothing in it can be withdrawn by a supplier. What it gives up is querying: there is no
way to ask the store a question except by reading files, which is why searching the whole archive
belongs to a separate page that reads the same files.

**Technical detail.** Collected items and cards live on the `data` branch, which shares no history
with the code. The storing change writes them, through one function that owns every path under the
data folder.

### Is a page read before or after it is stored?

**Situation.** The one uncertain step is reading a funder's page. If reading and collecting happen
together, a change to the reading means going back to the source, and the source may have changed or
gone.

**Decision.** Write what a source served to disk before anything reads it: one file per item, holding
what the source served together with where it came from, its link and the time it was collected.
Every later step works from that copy.

**Rationale.** Any step can be run again over the same text, a card can be checked against what was
really served, and a source is never asked twice for the same item. What it gives up is space, and it
means the stored copy may hold contact details that a page published. Those stay in the copy, where
they are useful for applying, and never appear on a card.

**Technical detail.** An item is written only when its file does not exist yet, so a second run over
the same item changes nothing, and the time of collection never makes a new commit. BUG-002 in the bug
history is where that rule came from.

## 4. Reading with a model

### How many steps use a language model?

**Situation.** Turning a page of prose into fields needs judgement that plain rules cannot supply.
Everything else the system does is mechanical.

**Decision.** One language model call, in the reading step. No second call, no agent framework, and
no model anywhere else, including the tagging of cards and the quarterly reading.

**Rationale.** One call is cheap, repeatable and easy to reason about, and every other step then
gives the same answer every time it runs. What it gives up is convenience: the places where a model
would be quicker, such as sorting items into topics, are done by rules instead.

**Technical detail.** The call sends one stored item as plain text under one fixed instruction, kept
in its own file and versioned, and the card records which version and which model read it.

### What has to travel with a value read from a page?

**Situation.** A model can produce a plausible fact that the page never stated, and a wrong deadline
on a funding card is worse than no card at all.

**Decision.** Each value read from the prose travels with the sentence it was read from, and that
sentence must appear word for word in the stored copy. A value whose sentence cannot be found is
refused rather than repaired: the reason goes back once, and a second failure writes nothing.

**Rationale.** It makes a card checkable in seconds by a person who has never seen the tool. What it
gives up: the title and the funder's name are taken as the page gives them, because they are not read
out of a sentence, and the check proves that a sentence is present. It cannot prove that the sentence
supports the value beside it.

No check yet requires a figure in the budget to appear in the budget's own sentence. A check of that
kind, tried in earlier work, refused honest summaries on real pages, and the only fault it ever caught
had been typed in by hand. It returns, in that narrow form, once a card is seen whose budget states a
figure its sentence does not.

**Technical detail.** The comparison is made after whitespace is collapsed, against the text taken
from the stored copy rather than the live page, so a page edited after collection cannot change the
result.
