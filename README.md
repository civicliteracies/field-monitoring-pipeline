# Field Monitoring Pipeline

Fieldbook: a near-zero-cost, self-running monitor of the transparency and
accountability funding sector, built for the Civic Literacy Initiative.

It watches the funders and organisations CLI follows, captures every funding call
and project report as a plain text file in this repository, reads the stated facts
out of each with one bounded AI step, and publishes the calls as an RSS feed and a
searchable dashboard. Once a quarter it derives a plain-figures read of where the
sector is heading, with no AI at all.

**The repository is the database.** One item is one text file. There is no server,
no database engine, and no paid service: git holds the data, GitHub Actions runs
the schedule, and the whole thing sits inside the free tier.

Everything collected here is public activity, drawn from organisations' own
publications.

## Setup

```sh
mise run setup
```

Installs dependencies and git hooks (pre-commit lint/format, pre-push quality
gate, commit-msg linting). See [CONTRIBUTING.md](CONTRIBUTING.md) for details on
the dependency setup, pre-commit hooks, and commit conventions.

## Common tasks

| Command | Description |
| --- | --- |
| `mise run verify` | The quality gate, read-only. The pre-push hook runs this |
| `mise run check` | The same four checks with fixing turned on, for use while working |
| `mise run lint` | Lint and auto-fix with ruff |
| `mise run format` | Format with ruff |
| `mise run typecheck` | Type-check with basedpyright |
| `mise run test` | Run the test suite |

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/) (enforced by commitizen).

## How it is built

| File | What it holds |
| --- | --- |
| [`constitution.md`](constitution.md) | Six rules that never bend |
| [`AGENTS.md`](AGENTS.md) | The working rules, for any AI coding agent |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | What every file is and how it works, in plain language |
| [`docs/decisions/`](docs/decisions/) | Why each choice was made, and what it costs |
| [`CHANGELOG.md`](CHANGELOG.md) | What changed, release by release |
| [`specs/`](specs/) | One specification per pull request, approved before any code |
