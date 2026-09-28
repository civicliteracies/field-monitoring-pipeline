# Architecture

What every file in this repository is, and what it does. One entry per file. A change adds an entry
for each file it adds, and updates the entry of any file whose job it changes, so this map grows with
the code rather than ahead of it.

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
| `config/sources.toml` | The watch list: each source Fieldbook reads, with its name, its search address and the words it searches for. |

## The code

| File | What it is and does |
|---|---|
| `src/field_monitoring_pipeline/__init__.py` | Marks the folder as the package the run lives in. The file itself is empty. |
| `src/field_monitoring_pipeline/fetch.py` | Asks the EU Funding and Tenders Portal for the calls that match each search word, in English, open or announced, reading every page, and keeps each call once as the portal sent it, leaving out those already closed. It also fetches a call's web page as the portal serves it. |
| `tests/__init__.py` | Marks the tests folder as part of the project. |
| `tests/test_placeholder.py` | One passing test, from the project's first setup. |
| `tests/test_fetch.py` | Checks the fetch against recorded portal replies, so no test needs the internet: the watch list's shape, one call per identifier, closed calls left out, every page read, what the request asks for, a web page kept whole, and a redirect that stops the fetch. |
| `tests/replies/democracy.json` | A recorded reply for "democracy", cut down to four calls: two closed ones, one marked open and one marked announced, and two current ones, one in two stages. |
| `tests/replies/civil_society.json` | A recorded reply for "civil society", cut down to two calls, one of them also in the democracy reply. |
| `tests/replies/digital_page_1.json` | The first of two recorded pages for "digital", cut down to one call. Its total is set to 150 by hand, so the fetch reads exactly two pages. |
| `tests/replies/digital_page_2.json` | The second recorded page for "digital", cut down to one call. |
| `tests/replies/page.html` | A small hand-written web page that points to one other file, for the test that a page is kept whole and the file it points to is not fetched. |
