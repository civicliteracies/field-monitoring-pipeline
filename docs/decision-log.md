# Decision log

How Fieldbook handles what it collects, organised by topic. Each entry documents a choice that
affects what the tool does, and records only what a reader could not work out from the code.

The first section, **Pending decisions**, lists choices that are open. Each one names the situation,
the question, what happens in the meantime and what that wait costs, and the technical detail of what
would unblock it, so a reader knows what is compromised. When a pending decision resolves it moves
into the section it belongs to as an ordinary entry, and the pending entry is deleted. Every change
that decides something adds its entry here, in the same pull request.

## 0. Pending decisions

### Who builds the page that searches the whole archive?

**Situation.** The cards are plain files with a stable shape, which a searchable page can read
directly.

**Question.** Is that page built here, or elsewhere by whoever wants it?

**Status quo.** There is no such page. Stored calls are browsed as folders on github.com, on the
`data` branch, and cards are browsed the same way. The cost is that finding an old call means
knowing roughly where to look.

**Technical detail.** Whoever builds it reads the card files and builds an index outside this
repository. Nothing here changes for that, provided the card keeps its shape.

### When are urgent calls floated to the top of the feed?

**Situation.** The feed carries every card, in the order of the cards' names: by the day each call
was found, then by title.

**Question.** When should a call that closes soon be ordered above one that closes later?

**Status quo.** No ordering by urgency. While the feed holds less than a screen of open calls,
ordering changes nothing a reader would notice. The cost is that once the feed is longer than a
screen, a call closing this week can sit below one closing in six months.

**Technical detail.** The feed is built with its entries in the order of the cards' names, and no
ordering by urgency. Ordering by urgency needs only the deadline, which every dated call carries.

### When does the reading step move to a paid model?

**Situation.** The reading step is the only part of the tool that uses a model, and like everything
else the tool uses, the model runs on a free tier.

**Question.** At what point is a paid model worth what it costs?

**Status quo.** The reading step uses Gemini 3.5 Flash-Lite on its free tier, the model its
instructions were tried on. The plan is a free tier model for every item, with nothing paid. The
condition for paying is that the model is shown to be what holds the tool back. The cost of waiting
is that a free tier's limits and terms can change without notice.

**Technical detail.** The reading step names its model in one place and every record notes which
model read it, so a move to a paid model changes one setting.

## 1. The goal

Keep CLI current with its own sector without anyone tending it. What arrives each week is read once
and lost, so the system is built around memory: everything collected is kept, and everything shown is
derived from what was kept.

## 2. The shape of a run

A run takes each item through seven steps, in order. Reach the sources on the watch list and bring
back what they published. Write down each item collected, once and whole, together with where it
came from. Give each item a stable name of its own. Read the facts the item states: copy those the
source gives in its own fields, and name the rest with a language model. The model is asked once
more when its answer cannot be used or a sentence it quotes is not found. Check what was read
against what was stored. Write the card. Save the cards and build the feed.

Three things stay apart inside every step: the data, declared in files a person can read; the
behaviour, plain functions that act on it; and the coordination, a single command that calls the
steps in order. The command decides what to skip and what to do when a step fails, and holds no rule
about the items themselves.

## 3. Sources

### Which source goes on the watch list first?

**Situation.** Fieldbook reads only the sources named on its watch list, and the first had to
publish funding calls in a form a program can read.

**Decision.** The EU Funding and Tenders Portal, reached through its public search service, which
answers in JSON. Fieldbook asks it, in English, for the grant topics that match each search word,
open or announced, and leaves out any call whose last closing date has passed. Each call's web page
is fetched as the portal serves it.

**Rationale.** Of the sources on CLI's list, it is the one that publishes open and announced calls a
program can read, each with its full text; the others publish news and essays, or grants already
given. Only grant topics are read for now, because the portal's other kinds each need their own
design: EU aid calls keep their details in attached documents, and cascade calls share identifiers
with other calls. Announced calls are kept because an application takes months to prepare; each is
captured once, as it stood on the day it was saved, and not updated. Closed calls are left out by
their dates rather than by the portal's status, because the portal still marks some old calls as
open or forthcoming. A failed request is not tried again in the same run. The failures seen are the
portal redirecting a call's page to a page that no longer exists, and its search timing out and then
answering with an error. When asked again, the portal served the page normally, so the next run asks
again. A call whose page fails is skipped and written in the log of calls with the error. Its record
is not kept without its page, because the search sends the record again on the next run. The other
calls are saved, and the run ends with a failure. A search that fails is written in the log too, and
stops the run. Nothing more is built for a failure until the log shows what is needed. The page is
kept whole, so the stored copy is the page itself and not a reading of it. For this portal the page
is a frame that the browser fills from the record, so the record carries the text. What it gives up:
a call published only in a language other than English is not seen. A call whose page fails on every
run until it closes is never saved.

**Technical detail.** Each search word is its own search, because the portal's search mishandles
several phrases in one query.

## 4. Storage

### Where does everything the tool collects live?

**Situation.** The system has to keep every item it collects, for years, on free services, and stay
readable without specialist tools.

**Decision.** Plain files in this repository. Each source has a folder, which holds every call's web
page and the source's record of it, and one folder holds a card for each call read. One log beside
the folders has a row for each call the run tried and for each call it read. It also has a row for
each source, saying how the run ended for it. No server, no database engine, no committed index. The
cards are derived from the stored files and kept beside them, because a reading costs a request to
the model and may not come out the same twice. The feed is rebuilt from the cards on every run and
kept beside them, so a feed reader can fetch it. Nothing else derived is kept.

**Rationale.** The history of the repository becomes the audit log, its permissions become the
access control, and nothing in it can be withdrawn by a supplier. The log of calls is one table,
written as it happens: where each call came from, when it was collected, whether it was saved and,
once read, whether its card was written. It takes the place of a note beside each call. It is not a
derived index. The identifier, title and link it repeats are copied from the source's record when a
row is written, and never updated. The run's row for a source holds one of three words:
`successful`, `failed` or `nothing new`. It also holds the numbers the run counted: how many calls
were fetched, how many were new and how many failed. When the search itself failed, the row holds
the error. The store writes it once, when the run is done with that source, and never updates it.
The log is never rebuilt from the files. A call's files are named by a code made from its
identifier, not by the identifier itself. Some identifiers cannot be file names (web addresses, or
names that carry slashes), and a name cannot change once a call is saved. The log pairs each code
with the call's identifier, title and link, so a person can find a call's files there. What plain
files give up is querying: there is no way to ask the store a question except by reading files,
which is why searching the whole archive belongs to a separate page that reads the same files. A row
for every finished run gives up one thing. The log grows on a day that brought no new call, so the
archive's history does not show by itself which days brought one. The numbers in the run's row show
it.

**Technical detail.** Collected items, cards and the feed live on the `data` branch, which shares no
history with the code. One module writes everything under the data folder and owns every path there.

### Is a page read before or after it is stored?

**Situation.** The one uncertain step is reading a funder's page. If reading and collecting happen
together, a change to the reading means going back to the source, and the source may have changed or
gone.

**Decision.** Write what a source served to disk before the reading step sees it: the call's web
page, exactly as downloaded, and the source's record of the call, every value as sent. Every later
step works from that copy. The log holds where each call came from, its link and the time it was
collected.

**Rationale.** Any step can be run again over the same text, a card can be checked against what was
really served, and once a call is saved its page is never asked for again. What it gives up is
space, and it means the stored copy may hold contact details that a page published. Those stay in
the copy, where they are useful for applying, and never appear on a card.

**Technical detail.** A call's files are written first and its row in the log last, and a call
counts as stored once it has a `saved` row. A run that stops partway therefore never leaves a call
marked as saved with a file missing, and the next run does that call again. A run stores a call only
when it has no `saved` row, and reads it only when it has no card. So a run with nothing new,
nothing failing and nothing left to read rewrites nothing but the feed, which comes out byte for
byte the same. It adds the run's row for each source, and every other stored byte stays as it was.
BUG-002 in the bug history is where that rule came from. A call that keeps failing adds one row each
run. That is deliberate: recording each try, and how each run ended, is what the log is for. The
fetch may leave out a whole call, by its identifier or its closing date, but never changes one: each
saved call is stored whole, as the source served it. The record is its own file because, for the
first source, the page holds none of the call's text. It is not kept inside the log. The records of
33 calls came to 1.2 MB, and GitHub shows a log as a table only up to 512 KB.

### What does a card hold, and how is it named?

**Situation.** A card has two readers: a person on github.com, and the code that reads cards back.

**Decision.** A card is one Markdown file. On top, between two `---` lines, sits the record, one
field per line, each value written in JSON. A field that holds a sentence is written over several
lines, its parts indented under it. Below is the half for people: the title, then each fact. The
funder's own sentence sits under the summary, who can apply and where, and the source's own line
under the dates and the budget. A sentence not found has a warning under it, and an empty field says
"not stated". The link and the model and instructions that read it come last. A card is named by the
day the call was saved, its title made into a short name, and the first ten characters of the call's
code. All cards sit in one folder, and a call with a card is never read again.

**Rationale.** The block on top is what GitHub shows as a table and what the code reads back.
Written in JSON, a colon or a quotation mark in a value cannot break it. The day saved puts the
cards in the order the calls were found. The title gives a name a person can recognise, and the code
keeps two calls with the same title apart. What it gives up: a card is never updated. A call changed
at its source keeps the card of the day it was read, as its stored copy keeps the page of the day it
was saved.

**Technical detail.** Each fact and its line are set apart by a blank line, because github.com joins
lines that touch and takes a line after a quote into the quote. A card counts as written once its
file exists, and its row in the log follows it. Only small letters, digits and hyphens reach a
card's name.

### How is the feed built?

**Situation.** A feed reader collects a feed by itself, and shows as new any entry it has not seen
before.

**Decision.** One RSS 2.0 file, `data/feed.xml`, rebuilt from every card on each run, with one entry
per card in the order of the cards' names. Each entry holds the title and the closing date, a link
to the card on github.com, the summary, and the call's code as its identity. The feed holds no date
of the build, and no entry is marked closed. A reader fetches it from its raw address on the `data`
branch.

**Rationale.** With no date of the build and a fixed order, the same cards give the same file, so a
morning with no new card changes nothing. The code never changes, so a reader shows each call once.
If a reader refuses the raw address, GitHub's own page hosting can serve the same file. What it
gives up: a closed call stays in the feed, and urgent calls are not floated to the top. An entry
shows the summary without its sentence or its warning; the card it links to shows both.

**Technical detail.** The feed is built last, so a run stopped by an error leaves it as it was until
the next run that reaches its end. Python's own XML tree writer writes the file. The project's
checker refuses that module by name, because its readers are unsafe on XML from outside; one line
allows it in the module that only writes.

## 5. Reading with a model

### How many steps use a language model?

**Situation.** Turning a page of prose into fields needs judgement that plain rules cannot supply.
Everything else the system does is mechanical.

**Decision.** One step uses a language model: the reading. It asks the model once, and once more
when the answer cannot be used or a sentence it quotes is not in the stored text. No agent
framework, and no model anywhere else, including the tagging of cards and the quarterly reading.

**Rationale.** One step with at most two requests is cheap and easy to reason about, and every other
step then gives the same answer every time it runs. The second request is the same conversation: the
instructions and the text, the model's first answer, and a message the code writes naming each
problem and its rule. The message holds no text of the call, so the model's job does not change: it
answers the same instructions again. What it gives up is convenience: the places where a model would
be quicker, such as sorting items into topics, are done by rules instead.

**Technical detail.** The first request sends one stored item as plain text under fixed
instructions, kept in their own file and versioned, and the record notes which version and which
model read it. A request the model service turns away is raised as it is and not sent again. A
request that fails in the daily run is written in the log as a failed reading, and the call is read
again the next morning. Nothing tries a failed request again within a run; that is brought back once
the log shows readings lost to a dropped connection.

### When is the key for the reading step set?

**Situation.** The reading step sends the text of a stored item to a language model, and that
request needs a key.

**Decision.** The key is saved as a repository secret after the first card has been made by hand,
and the daily run reads from then on.

**Rationale.** A card made by hand shows the reading works on a real call before the daily run sends
requests for the whole archive. What it gives up: until the secret is saved, every reading in the
daily run fails and is written in the log, and the morning ends with a failure. Collecting and
storing go on.

**Technical detail.** The key is never written into a file of this repository. The daily run hands
it to the command from the secret `GEMINI_API_KEY`, in the step that runs the command, and nowhere
else.

### What has to travel with a value read from a page?

**Situation.** A model can produce a plausible fact that the page never stated, and a wrong deadline
on a funding card is worse than no card at all.

**Decision.** Each value read from the prose travels with the sentence it was read from, and that
sentence is looked for word for word in the stored copy. A sentence that cannot be found goes back
to the model once. If it is still not found, it stays with its value, marked as not found, and is
never repaired. A date or the budget that the source gives in a labelled field is copied rather than
read, and its sentence is that field written out as one line.

**Rationale.** It makes a card checkable in seconds by a person who has never seen the tool. What it
gives up: the title, the type, the funder's name and the link are taken as given, because they are
not read out of a sentence. The check shows whether a sentence is present. It cannot show that the
sentence supports the value beside it.

No check yet requires a figure in the budget to appear in the budget's own sentence. A check of that
kind, tried in earlier work, refused honest summaries on real pages, and the only fault it ever caught
had been typed in by hand. It returns, in that narrow form, once a card is seen whose budget states a
figure its sentence does not. Where the source gives the budget in a field, the budget and its line
are written together from that field.

**Technical detail.** The comparison is made after whitespace is collapsed, against the text taken
from the stored copy rather than the live page, so a page edited after collection cannot change the
result.

### What happens when the reading meets a fault?

**Situation.** A model can quote a sentence that is not in the stored text, write an answer the code
cannot read, or leave a field empty. Refusing such a record would hide the fault: nothing would
reach the card, and nobody would see what went wrong.

**Decision.** A fault is marked and noted, never hidden by refusing the record. A sentence not found
after the second try stays on the record, marked as not found. The reading writes a note for each
problem in either answer and for each sentence not found. Each empty field among the funder, who can
apply and where gets a note saying what the answer did: the model marked it not stated, or did not
mention it. Only two faults make no record: an answer that cannot be used on either try, and a
request the model service turns away. The error then names the problems of each answer already
received.

**Rationale.** A marked fault can be seen and judged by the person reading the card; a refused
record cannot. What it gives up: a card can carry a sentence the source never wrote, with its
warning beside it. The notes say only what the code saw, never why the model chose it.

**Technical detail.** Each sentence carries a mark, `found`. The notes are plain lines written by
the code. Each problem note names the answer it came from, first or second, so a fault the second
answer put right reads differently from one kept on the record.

### How does a card hold the dates of a call?

**Situation.** A funding call opens on one date and closes on another, its deadline. Some calls have
no deadline and stay open. A reader has to tell a call that has not opened yet from one that takes
applications now.

**Decision.** A card holds one opening date and one deadline. The opening date is empty when the
source gives none, and the deadline is empty when the call stays open. Each of the two dates carries
a sentence beside it. A call in two stages keeps its first deadline, and the line beside it names
both stages with their dates.

**Rationale.** With one deadline that may be empty, every card says exactly one of two things: the
call closes on a date, or it stays open. What it gives up: only the sentence says in what way a call
stays open, and a call with several deadlines keeps one of them as its date. The opening date
carries a sentence for the same reason as the deadline: a person can check each date against its
sentence.

**Technical detail.** The deadline and its sentence are one block that every card has. A second
block holds the opening date and its sentence. Every card names that block too, and leaves the whole
block empty when the source gives no opening date.

### Which facts are copied from the source, and which does the model name?

**Situation.** The EU portal gives each call's title, opening date, deadlines and budget in labelled
fields of its own record, and states them in a sentence only now and then: of 33 calls the portal
served, the prose states an opening date in 5, a deadline in 6 and the call's own budget in none.
In trials, a model asked to name these facts copied them wrongly or wrote flags its instructions
never offered.

**Decision.** The code copies the title, the two dates and the budget from the record's fields, and
writes each date and the budget out as one plain line that serves as its sentence. The model names
the rest: the type, the funder, the summary, who can apply and where. Where the prose also states a
date, the field's value and line are kept. The budget names the call's whole amount, then in
brackets what one winning project can get, with the euro sign after each amount. Where the topics
of one call share one amount, the portal gives each topic's line the whole of it, and the budget
says it is shared and by how many topics.

**Rationale.** A fact the source already gives in a field needs no judgement, so copying it cannot
misread it. What it gives up: where the prose and the field disagree, the card shows the field and
says nothing of the prose. The euro sign is not in the stored record: the portal's own page prints
it beside each amount. It is the one thing on a card that is not derived from what was kept.

**Technical detail.** The four lines come first in the text the model reads. The three that carry a
sentence, the two dates and the budget, are checked like any other sentence, and are always found.

### Why does the model answer with one command line?

**Situation.** A model can be asked to fill a shape the provider enforces, or to write its answer
as text that the code reads.

**Decision.** The model writes its reasoning, then one line that begins with a fixed word and names
each fact with a flag. The code finds that line, reads its flags, and builds the record through the
template.

**Rationale.** The record's shape lives in this repository, so any model that can write a line can
be used. What it gives up: the code reads that one line and nothing else, and a line it cannot read
goes back to the model once, with the rule it broke, and is never repaired by the code.

**Technical detail.** Each free-text value is written as a JSON string, so a funder's own quotation
marks reach the record unbroken. A flag the instructions never offered, a flag given twice and a flag
with no value are refused.
