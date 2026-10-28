# Architecture

What every file in this repository is, and what it does. One entry per file where the code lives,
and one per kind of file in the archive. A change adds an entry for each file it adds, and updates
the entry of any file whose job it changes, so this map grows with the code rather than ahead of it.

## The front of the repository

| File | What it is and does |
|---|---|
| `README.md` | The front page: what Fieldbook is, what it does, how a run works, what the checks do not prove, and what this version covers. |
| `CONTRIBUTING.md` | How to set the project up and what the automatic checks do. |

## The records

| File | What it is and does |
|---|---|
| `docs/plan.md` | What is being built, in order, ticked by the change that completes each line. |
| `docs/decision-log.md` | How Fieldbook handles what it collects, by topic: the pending decisions first, then the goal, the shape of a run, and every decision the code cannot show. |
| `docs/bug-history.md` | Serious faults: the open ones first, then each fault that was fixed, with its cause, its fix and the rule it produced. |
| `docs/ARCHITECTURE.md` | This file: what each file is and does. |

## Tools and settings

| File | What it is and does |
|---|---|
| `pyproject.toml` | Names the project, the libraries the code uses and the tools it installs, and holds every tool's settings: the code checker, the type checker, the test runner and the commit message check. |
| `uv.lock` | The exact version of every tool and library, so every machine installs the same ones. |
| `.python-version` | The version of Python this project runs on. |
| `mise.toml` | The short commands: set the project up, fix what can be fixed while you work, and run the quality gate, which checks linting, formatting, types and tests without changing anything. |
| `.pre-commit-config.yaml` | The checks git runs by itself, at three moments: on commit, the code checker and then the formatter; on the commit message, its shape; on push, the whole quality gate. |
| `.gitignore` | What git leaves alone: caches, the virtual environment, local settings. |
| `config/sources.toml` | The watch list: each source Fieldbook reads, with its ID, its name, its search address and the words it searches for. The ID is the name of the source's folder in the archive, and marks its rows in the log of calls. |

## The daily run

| File | What it is and does |
|---|---|
| `.github/workflows/calls.yml` | The daily run. Every morning, or when started by hand from the Actions tab, GitHub runs the one command and commits what it stored and wrote, the feed included, to the `data` branch. The command gets the model's key from a repository secret. What was written before an error is still committed. A run adds a row to the log for each source it finishes, so a morning with no new call still leaves a commit. |

## The code

| File | What it is and does |
|---|---|
| `src/field_monitoring_pipeline/__init__.py` | Marks the folder as the package the run lives in. The file itself is empty. |
| `src/field_monitoring_pipeline/fetch.py` | Asks the EU Funding and Tenders Portal for the grant topics that match each search word, in English, open or announced, reading every page, and keeps each call once as the portal sent it, with its identifier, its link and its title, leaving out those already closed. It also fetches a call's web page as the portal serves it. |
| `src/field_monitoring_pipeline/store.py` | Writes everything under the data folder. For each saved call it writes two files in the source's folder: the call's web page as downloaded and the source's record of it. Both are named by a code made from the call's identifier. For each call read it writes a card into one folder for all sources, named by the day the call was saved, its title and the first ten characters of its code. In one log beside the folders it adds a row for each call the run tried, saved or failed; for each answer the model gave while reading a call, `first answer` or `second answer`, with the answer as it came; and for each call it read, card written or failed. For each source it adds one more, saying how the run ended for it. It also tells the run which calls are saved, which have a card, and reads a stored call's record back. It lists the cards and writes the feed beside them. |
| `src/field_monitoring_pipeline/calls.py` | The one command. It reads the watch list, fetches each source's calls, skips those already saved, and downloads and stores the rest. When a call's page cannot be downloaded, it has the store write that in the log and carries on. When a search fails or its reply is not JSON, it has the store write that and stops the run; any other error while collecting stops the run with nothing written for it. Once a source's calls are done, it has the store write how the run ended: `successful`, `failed` or `nothing new`, with the numbers it counted. Then it reads each saved call that has no card, handing the reading a function that has the store write each answer of the model as it arrives, and has the call's card written and a row added with the notes, or a `failed` row with the reason. Last, it has the feed built from every card. It prints what it did. |
| `src/field_monitoring_pipeline/models.py` | The template of a card: the fields of a funding call, the ten types a call can have, the call's identifier as the source gives it, and the names of the model and the instructions that read it. It says which fields carry a sentence, or a line written from the source's own field, and which may be empty, and refuses a record that does not fit. Each sentence carries a mark saying whether it was found in the stored text. A record cannot be changed once it is made. |
| `src/field_monitoring_pipeline/extract.py` | The reading. It makes the text a language model reads from a stored call: four lines written from the record's fields, then the call's description and conditions with the page's tags stripped. It asks the model, hands each answer on as it arrives, and reads the one command line of the answer. From the four fields and the five facts the model names it builds the record, marking each quoted sentence found or not found in the text. When the answer cannot be used or a sentence is not found, it asks once more in the same conversation, with a message naming each problem. Each record comes back with a note for each problem and each sentence not found, and for each empty field among the funder, who can apply and where, saying what the answer did. |
| `src/field_monitoring_pipeline/instructions/v3.md` | The instructions the model reads, in plain words: what the text is, the three passes, the fields and their sentences, and the one command line to write. The record notes their name. |
| `src/field_monitoring_pipeline/write.py` | The card. It writes a record as one Markdown file. The record sits on top, in a block GitHub shows as a table. Below it come the facts for people, each with its sentence or line, a warning under a sentence not found, then the link and the model that read it. The same module reads the block back into the same record. |
| `src/field_monitoring_pipeline/publish.py` | The feed. It writes RSS from the cards, one entry per card in the order of their names. Each entry holds the title with the closing date, a link to the card on github.com, the summary, and the call's code as its identity. No date of the build goes in, so the same cards give the same file. |
| `tests/__init__.py` | Marks the tests folder as part of the project. |
| `tests/test_placeholder.py` | One passing test, from the project's first setup. |
| `tests/test_fetch.py` | Checks the fetch against recorded portal replies, so no test needs the internet: the watch list's shape, one call per identifier, each call's title and whole record, closed calls left out, every page read, what the request asks for, a web page kept whole, the client's own settings, and a redirect that stops the fetch. |
| `tests/test_store.py` | Checks the store in a temporary folder: the code that names a call's files, the page kept byte for byte, the record written with every value as sent, the files written before the log row, a record that cannot be written, which calls count as saved and on which day, the log's rows and its first line, a failed call's row, the run's row in each of its three words, a card's name and its short title, cut at the last hyphen within its first 61 characters, on a long title, a curly apostrophe and a title of exactly 60 characters, with and without a word after it, a card written and found for its own call only, a stored record read back, the reading's row, an answer's row holding its word and the answer read back whole, line breaks, a lone carriage return and quotation marks included, the listing of the cards, and the feed written as UTF-8 with line feeds. |
| `tests/conftest.py` | The test watch list, written into each test's folder, for both of the command's test files. |
| `tests/test_calls.py` | Checks the command's collecting against recorded portal replies, so no test needs the internet: a first run that saves every call, a second that adds only the run's row and reads none, closed calls left out by the run's clock, a call whose page fails and is tried again, then saved and read that morning, a page that cannot be downloaded and is logged on every run, a link that cannot be read, every failed call counted, a search that fails, a search reply that is not JSON, a reply the fetch cannot read stopping the run with nothing written, any other error stopping the run with no row written for it, two sources kept apart, each with its own row for the run holding its own word and numbers, a watch list with a field missing, the command ending with a failure when a call has failed, and the file run as the command. It also holds the recorded portal, the stand-in model and the test watch list, which the reading's tests use too. |
| `tests/test_calls_reading.py` | Checks the command's reading and its feed, with the recorded portal and a stand-in model: each saved call without a card read once, by source and then identifier, each answer the model gave written in the log as it came, before the call's card and its row, the notes reaching the log, two of them in one row, a reading that fails, because the model service refuses it or both its answers cannot be used, written as failed after its answers, counted and read again the next run, its card still named by the day the call was saved, a morning with no key saving every call and failing every reading, a card that cannot be written stopping the run after the call's answer and before its card, a reply with no content leaving its empty answer row before the run stops, any other error in a reading stopping the run with what was written before it kept and no feed written, and the feed built from every card after the reading, built again when its file is missing, and holding the cards of a morning on which one reading fails. |
| `tests/test_models.py` | Checks the template: a call with a deadline is accepted with its link kept exactly as given, a call with no deadline is accepted, a deadline that is not a real date is refused, a deadline in the past is accepted, a field the template does not know is refused in each part of the template, a call with any of its fields left out is refused, a sentence whose mark is left out or empty is refused in each part that carries one, a call is accepted with an opening date in the past and with none, and an opening date that is not a real date, or whose sentence is left out, is refused. |
| `tests/test_extract.py` | Checks the reading with no network: the page's tags stripped with a sentence keeping its stop, the four lines the text begins with and the description before the conditions, each form a date or budget line takes, a pot the call's topics share, a recorded reply built into a record with every sentence found, a sentence found whatever its line breaks and spaces but only letter for letter, a sentence with words dropped or a figure changed caught and asked about once more, a sentence still missing after the second try kept and marked, the second request holding the first request, the first answer and a message with no text of the call, a usable second answer kept even when it misses more, a usable first answer kept when the second cannot be used, an answer that cannot be used on either try, a refused second request carrying the first answer's problems, an answer with no command line or two and a refused record each sent back with its rule, the notes and their order, a fact the answer leaves out, a value with no sentence refused, three malformed lines refused, what the first request to the model holds, a refused request raised, each answer handed on with its word when the first answer is clean, after a second try, when the reading fails and when the second request fails, each handed on exactly as sent, before it is judged and, for the first, before the second request goes out, a fault in keeping the second answer carrying no note of the first answer's problems, and the instructions holding the labels and marker lines the code writes, with their own example line building a record. |
| `tests/test_write.py` | Checks the card: the block on top and the half for people below, the model and the instructions in the block, the same record giving the same bytes, the block written with every character outside plain English escaped and read back as the same record, for four records: one as the recorded answer made it, one with every field that may be empty left empty, one with every sentence not found, and one whose title holds a colon and quotation marks, the warning under each sentence not found, each empty field written "not stated" and a named funder shown, each fact set apart by a blank line on all four, a day under 10 on both dates and a call with no deadline staying open, and the half for people ending with the link and the model. |
| `tests/test_publish.py` | Checks the feed: one entry per card, in the order given, one entry compared in full on a deadline whose day is under 10, on a call with no deadline, on a deadline in the past and on a title with an ampersand and an angle bracket, the channel's title, link and description, the identity the full code and not the card's name, a card whose title changed keeping its identity, the same bytes built twice, and a file that reads as RSS. |
| `tests/replies/stored_call.json` | A stored record of one call, cut down to the fields the reading uses. Its budget field keeps two lines: another call's, then the call's own. The command's tests take the reading's fields from it too. |
| `tests/replies/model_reply.txt` | The model's real reply to that call, as it was sent: its reasoning, then its one command line. |
| `tests/replies/democracy.json` | A recorded reply for "democracy", cut down to four calls: two closed ones, one marked open and one marked announced, and two current ones, one in two stages. |
| `tests/replies/civil_society.json` | A recorded reply for "civil society", cut down to two calls, one of them also in the democracy reply. |
| `tests/replies/digital_page_1.json` | The first of two recorded pages for "digital", cut down to one call. Its total is set to 150 by hand, so the fetch reads exactly two pages. |
| `tests/replies/digital_page_2.json` | The second recorded page for "digital", cut down to one call. Its record keeps one key beside its metadata, so a test can tell the whole record from a part of it. |
| `tests/replies/page.html` | A small hand-written web page that points to one other file, for the test that a page is kept whole and the file it points to is not fetched. The command's tests also serve it as a call's page. It holds one byte that is not UTF-8, so a page changed on its way would not match. |

## The archive, on the `data` branch

The `data` branch holds the archive and shares no history with the code. The log appears with the
first run, a call's two files once that call is saved, its card once it is read, and the feed once a
run reaches its end.

| File | What it is and does |
|---|---|
| `.gitattributes` | Tells git to convert no line endings on this branch, so a stored page is the same bytes on every machine. |
| `README.md` | The branch's front page: what the branch is for. |
| `data/raw/log.csv` | The log of calls: one row for each call a run tried, saved or failed, one for each answer the model gave while reading a call, with the answer as it came, one for each call it read, card written or failed, and one for each source, saying how the run ended for it. |
| `data/raw/<source ID>/<code>.html` | A saved call's web page, exactly as downloaded. |
| `data/raw/<source ID>/<code>.json` | The source's record of the same call, every value as sent. |
| `data/calls/<day saved>-<short title>-<short code>.md` | A call's card, written once when the call is read and never rewritten. Its name ends in the first ten characters of the call's code. |
| `data/feed.xml` | The RSS feed, rebuilt from every card on each run, one entry per card. A feed reader fetches it from its raw address on this branch. |
