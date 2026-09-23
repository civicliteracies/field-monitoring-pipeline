# Field Monitoring Pipeline

Most of what the Civic Literacy Initiative (CLI) needs to know already reaches it. A funder opens a call, a peer publishes a report, a newsletter carries a link. It is read once and then lost, or found after the deadline has passed. Fieldbook is the memory that stops that happening.

Every morning it visits the sources CLI has chosen, keeps a copy of what they published, and turns each funding call into a card: what the call is, who can apply, how much it offers, when it closes. Under each fact read from the page sits the funder's own sentence, so it can be checked against the funder's words in seconds. The cards are plain files on the `data` branch of this repository, and an RSS feed carries each new one into a feed reader. It is built to run on GitHub, on free services, with no one tending it.

None of this runs yet. The code arrives one change at a time, in the order [`docs/plan.md`](docs/plan.md) sets out, and this page describes Fieldbook as it will work once those changes are in.

## What it does

It finds the opportunities CLI can act on, for funding and for paid work: grants, tenders, requests for proposals, expressions of interest, framework agreements, fellowships, prizes, and training and teaching posts. Each becomes a card. Later versions add the project reports peer organisations publish, a quarterly reading of where the sector is going, and proposals of funders to follow; [`docs/plan.md`](docs/plan.md) lists them.

## How a run works

Fieldbook watches a named list of sources and never searches the open web. Each morning it reaches every source by the route that source publishes, and writes down what came back, once, before reading a word of it, together with where it came from. Then it reads: one language model call per item, asked for what the page states and nothing else, with the sentence each fact rests on. Every quoted sentence is checked word for word against the stored copy, and an item that fails twice produces nothing. What survives becomes a Markdown card, saved to the `data` branch, which holds the archive and shares no history with the code, and carried into the RSS feed.

Everything collected and everything written stays in this repository as plain files, one per item, on the `data` branch.

## What it does not promise

The checks prove that a quoted sentence is on the page, word for word. They do not prove that the sentence supports the fact printed beside it. That is why every card is built to be read next to its source, with the funder's own words under each fact.

## This version

The first version will carry one funding call, from one source, the whole way: collected, kept, read, checked, written as a card and delivered to a feed reader, every morning. Topics on each card, more sources, the project reports, the quarterly reading, the proposals of funders to watch and a guide to adding a source follow it. [`docs/plan.md`](docs/plan.md) lists them in order.

## The records

[`docs/plan.md`](docs/plan.md) says what is being built and in what order, [`docs/decision-log.md`](docs/decision-log.md) says why Fieldbook is built this way, [`docs/bug-history.md`](docs/bug-history.md) keeps each serious fault, the open ones first, with its cause and its fix, and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) says what every file in this repository is for.

## Setup

```sh
mise run setup
```

Installs dependencies and git hooks (pre-commit lint/format, pre-push tests, commit-msg linting). See [CONTRIBUTING.md](CONTRIBUTING.md) for details on the dependency setup, pre-commit hooks, and commit conventions.

## Common tasks

| Command | Description |
| --- | --- |
| `mise run check` | Quality gate: format + lint + typecheck + test |
| `mise run lint` | Lint and auto-fix with ruff |
| `mise run format` | Format with ruff |
| `mise run typecheck` | Type-check with basedpyright |
| `mise run test` | Run the test suite |

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/) (enforced by commitizen).
