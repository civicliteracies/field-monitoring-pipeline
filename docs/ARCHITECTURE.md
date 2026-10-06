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
| `.github/workflows/calls.yml` | The daily run. Every morning, or when started by hand from the Actions tab, GitHub runs the one command and commits what it stored to the `data` branch. What was stored before an error is still committed, and a morning with nothing to add leaves no commit. |

## The code

| File | What it is and does |
|---|---|
| `src/field_monitoring_pipeline/__init__.py` | Marks the folder as the package the run lives in. The file itself is empty. |
| `src/field_monitoring_pipeline/fetch.py` | Asks the EU Funding and Tenders Portal for the grant topics that match each search word, in English, open or announced, reading every page, and keeps each call once as the portal sent it, with its identifier, its link and its title, leaving out those already closed. It also fetches a call's web page as the portal serves it. |
| `src/field_monitoring_pipeline/store.py` | Writes everything under the data folder. For each saved call it writes two files in the source's folder: the call's web page as downloaded and the source's record of it. Both are named by a code made from the call's identifier. In one log beside the folders it adds a row for each call the run tried, saved or failed, and for a search that failed. It also tells the run which calls are already saved. |
| `src/field_monitoring_pipeline/calls.py` | The one command. It reads the watch list, fetches each source's calls, skips those already saved, and downloads and stores the rest. When a call's page or a search fails, it has the store write that in the log. It prints what it did. |
| `tests/__init__.py` | Marks the tests folder as part of the project. |
| `tests/test_placeholder.py` | One passing test, from the project's first setup. |
| `tests/test_fetch.py` | Checks the fetch against recorded portal replies, so no test needs the internet: the watch list's shape, one call per identifier, each call's title and whole record, closed calls left out, every page read, what the request asks for, a web page kept whole, the client's own settings, and a redirect that stops the fetch. |
| `tests/test_store.py` | Checks the store in a temporary folder: the code that names a call's files, the page kept byte for byte, the record written with every value as sent, the files written before the log row, the log's rows and its first line, and a failed call's row. |
| `tests/test_calls.py` | Checks the command against recorded portal replies, so no test needs the internet: a first run that saves every call, a second that changes nothing, closed calls left out by the run's clock, a call whose page fails, every failed call counted, a search that fails, any other error stopping the run with no row written for it, two sources kept apart, a watch list with a field missing, the command ending with a failure when a call has failed, and the file run as the command. |
| `tests/replies/democracy.json` | A recorded reply for "democracy", cut down to four calls: two closed ones, one marked open and one marked announced, and two current ones, one in two stages. |
| `tests/replies/civil_society.json` | A recorded reply for "civil society", cut down to two calls, one of them also in the democracy reply. |
| `tests/replies/digital_page_1.json` | The first of two recorded pages for "digital", cut down to one call. Its total is set to 150 by hand, so the fetch reads exactly two pages. |
| `tests/replies/digital_page_2.json` | The second recorded page for "digital", cut down to one call. Its record keeps one key beside its metadata, so a test can tell the whole record from a part of it. |
| `tests/replies/page.html` | A small hand-written web page that points to one other file, for the test that a page is kept whole and the file it points to is not fetched. The command's tests also serve it as a call's page. It holds one byte that is not UTF-8, so a page changed on its way would not match. |

## The archive, on the `data` branch

The `data` branch holds the archive and shares no history with the code. The log appears with the
first run, and a call's two files once that call is saved.

| File | What it is and does |
|---|---|
| `.gitattributes` | Tells git to convert no line endings on this branch, so a stored page is the same bytes on every machine. |
| `README.md` | The branch's front page: what the branch is for. |
| `data/raw/log.csv` | The log of calls: one row for each call a run tried, saved or failed, and for a search that failed. |
| `data/raw/<source ID>/<code>.html` | A saved call's web page, exactly as downloaded. |
| `data/raw/<source ID>/<code>.json` | The source's record of the same call, every value as sent. |
