# Field Monitoring Pipeline

Most of what the Civic Literacy Initiative (CLI) needs to know already reaches it. A funder opens a call, a peer publishes a report, a newsletter carries a link. It is read once and then lost, or found after the deadline has passed. Fieldbook is the memory that stops that happening.

Every morning it visits the sources CLI has chosen, keeps a copy of what they published, and turns each funding call into a card: what the call is, who can apply, how much it offers, when it closes. Under the summary, who can apply and where sits the funder's own sentence, with a warning when it could not be found in what was collected. Under the dates and the budget sits a line written from the source's own record. Each can be checked against the source in seconds. The cards are plain files on the [`data` branch](https://github.com/civicliteracies/field-monitoring-pipeline/tree/data) of this repository, and an [RSS feed](https://raw.githubusercontent.com/civicliteracies/field-monitoring-pipeline/data/data/feed.xml) carries each new one into a feed reader. It is built to run on GitHub, on free services, with no one tending it.

Collecting, keeping, reading, checking, the cards and the feed run by themselves every morning. The code arrives one change at a time, in the order [`docs/plan.md`](docs/plan.md) sets out.

## What it does

It finds the opportunities CLI can act on, for funding and for paid work: grants, tenders, requests for proposals, expressions of interest, framework agreements, fellowships, prizes, and training and teaching posts. Each becomes a card. Later versions add the project reports peer organisations publish, a quarterly reading of where the sector is going, and proposals of funders to follow; [`docs/plan.md`](docs/plan.md) lists them.

## How a run works

Fieldbook watches a named list of sources and never searches the open web. Each morning it reaches every source by the route that source publishes, and writes down each item it collects, once and whole, before the reading step sees a word of it, together with where it came from. Then it reads. The title, the dates and the budget are copied from the source's own record where it gives them in fields. A language model names the rest, asked for what the text states and nothing else. For the summary, who can apply and where, it also quotes the sentence each one rests on. Every quoted sentence is checked word for word against the stored copy. When a sentence is not found, or the model's answer cannot be used, the model is asked once more. A sentence still not found stays on the card with a warning. When neither of the model's answers can be used, the item gets no card. Each item read becomes a Markdown card, saved to the `data` branch, which holds the archive and shares no history with the code, and carried into the RSS feed.

Every answer the model gives is kept, word for word, in the log of calls on the `data` branch, so anyone can read the model's own reasoning behind each fact on a card, or why a reading failed.

Everything collected and everything written stays in this repository as plain files, on the `data` branch.

## What it does not promise

The check shows whether a quoted sentence is in what was collected, word for word, and a card warns of each one it could not find. It does not show that the sentence supports the fact printed beside it. That is why every card is built to be read next to its source, with the funder's own sentence or the source's own line under each fact that has one.

## This version

The first version carries the funding calls of one source the whole way: collected, kept, read, checked, written as a card and delivered to a feed reader, every morning. Topics on each card, more sources, the project reports, the quarterly reading, the proposals of funders to watch and a guide to adding a source follow it. [`docs/plan.md`](docs/plan.md) lists them in order.

## The records

[`docs/plan.md`](docs/plan.md) says what is being built and in what order, [`docs/decision-log.md`](docs/decision-log.md) says why Fieldbook is built this way, [`docs/bug-history.md`](docs/bug-history.md) keeps each serious fault, the open ones first, with its cause and its fix, and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) says what every file in this repository is for.

## Setup

```sh
mise run setup
```

Installs dependencies and git hooks (pre-commit lint/format, pre-push quality gate, commit-msg linting). See [CONTRIBUTING.md](CONTRIBUTING.md) for details on the dependency setup, pre-commit hooks, and commit conventions.

## Common tasks

| Command | Description |
| --- | --- |
| `mise run check` | While you work: lint + format with fixes, then typecheck + test |
| `mise run verify` | Quality gate: the same four checks, read-only. The pre-push hook runs it before every push |
| `mise run lint` | Lint and auto-fix with ruff |
| `mise run format` | Format with ruff |
| `mise run typecheck` | Type-check with basedpyright |
| `mise run test` | Run the test suite |

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/) (enforced by commitizen).
