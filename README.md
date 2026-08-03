# Field Monitoring Pipeline

## Setup

```sh
mise run setup
```

Installs dependencies and git hooks (pre-commit lint/format, pre-push tests, commit-msg linting).

## Common tasks

| Command | Description |
| --- | --- |
| `mise run check` | Quality gate: format + lint + typecheck + test |
| `mise run lint` | Lint and auto-fix with ruff |
| `mise run format` | Format with ruff |
| `mise run typecheck` | Type-check with basedpyright |
| `mise run test` | Run the test suite |

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/) (enforced by commitizen).
