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
| `pyproject.toml` | Names the project and the tools it installs, and holds every tool's settings: the code checker, the type checker, the test runner and the commit message check. |
| `uv.lock` | The exact version of every tool and library, so every machine installs the same ones. |
| `.python-version` | The version of Python this project runs on. |
| `mise.toml` | The short commands: set the project up, and run the quality gate of formatting, checking, type checking and tests. |
| `.pre-commit-config.yaml` | The checks git runs by itself, at three moments: on commit, the code checker and then the formatter; on the commit message, its shape; on push, the tests. |
| `.gitignore` | What git leaves alone: caches, the virtual environment, local settings. |

## The code

| File | What it is and does |
|---|---|
| `src/field_monitoring_pipeline/__init__.py` | The package the run will live in. Empty today. |
| `tests/__init__.py` | Marks the tests folder as part of the project. |
| `tests/test_placeholder.py` | One passing test, so the test command has something to run until the first real test arrives. |
