# Contributing

## Prerequisites

* [uv](https://docs.astral.sh/uv/getting-started/) — manages the Python environment and dependencies
* [mise](https://mise.jdx.dev/getting-started.html) (recommended) — runs project tasks and pins the Python version for you
* Python ≥3.13 (mise installs this automatically if you don't have it)

## Setup

```sh
git clone https://github.com/civicliteracies/field-monitoring-pipeline.git
cd field-monitoring-pipeline
mise run setup
```

`mise run setup` does two things:

1. `uv sync` — creates `.venv` and installs both the project's runtime dependencies and its `dev` dependency group (ruff, basedpyright, pytest, commitizen).
2. `uvx pre-commit install` — wires up the git hooks described below.

Without mise, run the same two steps by hand:

```sh
uv sync
uvx pre-commit install --hook-type pre-commit --hook-type pre-push --hook-type commit-msg
```

## Project layout & dependency scaffolding

```
pyproject.toml   # project metadata, runtime deps, dev deps, and every tool's config
uv.lock          # exact resolved versions — committed, never hand-edited
src/field_monitoring_pipeline/   # the package
tests/           # pytest suite, mirrors src/
mise.toml        # task runner: setup, check, lint, format, typecheck, test
.pre-commit-config.yaml   # git hook definitions
```

Everything lives in one `pyproject.toml`:

* **`[project.dependencies]`** — runtime dependencies. Add with `uv add <package>`.
* **`[dependency-groups.dev]`** — tools only developers need (ruff, basedpyright, pytest, commitizen), never shipped. Add with `uv add --dev <package>`.
* **`[tool.basedpyright]`**, **`[tool.ruff]`**, **`[tool.pytest.ini_options]`** — each tool's config lives next to the dependency that needs it, instead of a separate `ruff.toml` / `pytest.ini`.

`uv.lock` is the source of truth for exact versions; it's regenerated automatically whenever you `uv add`/`uv remove` or run `uv sync`, and should always be committed alongside a `pyproject.toml` change.

The package uses a `src/` layout: code lives under `src/field_monitoring_pipeline/`, not at the repo root. This is what `basedpyright`'s `extraPaths = ["src"]` and the package's install metadata (`tool.hatch.build.targets.wheel`) point at — if you add a new top-level module, it goes under `src/field_monitoring_pipeline/`, not next to `pyproject.toml`.

## Common tasks

| Command | Description |
| --- | --- |
| `mise run check` | Quality gate: format + lint + typecheck + test. Fixes as it goes — run this while working |
| `mise run verify` | The whole gate, read-only: reports rather than fixes. This is what the push hook runs |
| `mise run lint` | Lint and auto-fix with ruff |
| `mise run format` | Format with ruff |
| `mise run typecheck` | Type-check with basedpyright (strict mode) |
| `mise run test` | Run the test suite |

Without mise, the underlying commands are `uv run ruff check . --fix`, `uv run ruff format .`, `uv run basedpyright src tests`, `uv run pytest -n auto`.

## Pre-commit hooks

`mise run setup` installs three hooks, so most of this happens automatically:

* **On `git commit`** — `ruff check --fix` and `ruff format` run against the files you're committing. If either one modifies a file, the commit is aborted so you can review the change and re-stage it.
* **On `git commit` (commit-msg)** — `commitizen` checks your commit message matches [Conventional Commits](https://www.conventionalcommits.org/) (`type(scope): summary`, e.g. `feat(pipeline): add CSV ingest step`). Common types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`.
* **On `git push`** — the whole quality gate runs, via `mise run verify`: formatting is checked, ruff lints, basedpyright type-checks in strict mode, and the tests run. Anything failing blocks the push. It reports rather than fixes, so pushing never rewrites your files under you.

Run any of them by hand without committing/pushing:

```sh
uvx pre-commit run --all-files          # lint + format hooks only
uvx pre-commit run --all-files --hook-stage pre-push   # the full gate
```

Writing a commit message interactively (handles the Conventional Commits format for you):

```sh
uvx --from commitizen cz commit
```

## Fixing a bug

**A fix must come with a test that fails on the old behaviour.** Write the test
first, watch it fail, then change the code and watch it pass. Without that step
"fixed" is a claim rather than a fact, and nothing stops the bug coming back
later.

Where the record of it goes:

* **While it is open** — the repository's issue tracker.
* **Once it is fixed** — an entry in [`docs/BUGS.md`](docs/BUGS.md) with the
  symptom, the cause, the fix, and the test that now guards it.
* **If a user would notice the difference** — a line under `### Fixed` in
  [`CHANGELOG.md`](CHANGELOG.md).
* **If the fix settles a lasting rule** — a numbered record in
  [`docs/decisions/`](docs/decisions/), linked to and from the bug entry, so the
  reasoning survives beyond the incident.

## FAQ

**The pre-commit hooks aren't running when I commit.**
They're probably not installed. Run `mise run setup` again (or the `uvx pre-commit install ...` command above) — it's safe to re-run.

**My commit was rejected for message formatting.**
Use `uvx --from commitizen cz commit` to build a compliant message interactively, or match the pattern by hand: `type(optional-scope): summary`.

**Ruff or basedpyright complains about something in `tests/`.**
Test files are intentionally exempt from a few rules (`S` security checks, unused-argument checks, private-member access, magic values) via `[tool.ruff.lint.per-file-ignores]` in `pyproject.toml` — those patterns are normal in test code. If you're seeing something else, it's a real finding.

**How do I add a dependency?**
`uv add <package>` for runtime code, `uv add --dev <package>` for a tool you only need locally (linters, test libraries). Either way, commit the resulting `pyproject.toml` and `uv.lock` changes together.
