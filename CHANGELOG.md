# Changelog

Everything notable that changes in Fieldbook is recorded here, newest first.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

An entry says what changed for someone using or maintaining Fieldbook, in plain
language. **Why** a choice was made, and what it cost, belongs in
[`docs/decisions/`](docs/decisions/) instead.

## [Unreleased]

### Added

- A quality gate as one command, `mise run verify`: formatting checked, ruff
  lint, a strict type-check with basedpyright, and the test suite. It reports
  rather than repairs, and the pre-push hook runs it, so nothing failing leaves
  the machine without someone deliberately overriding the hook.
- `mise run check`, the same four checks with fixing turned on, for use while
  working.
- Working rules for any AI coding agent in [`AGENTS.md`](AGENTS.md), loaded by
  [`CLAUDE.md`](CLAUDE.md), sitting under the six non-negotiables in
  [`constitution.md`](constitution.md).
- A plain-language map of every file in
  [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).
- Numbered decision records in [`docs/decisions/`](docs/decisions/), ADR-0001 to
  ADR-0025, one file per record with an index.
- One specification per pull request in [`specs/`](specs/), written and approved
  before any code exists.
- An advisory run of the gate on Linux for every pull request. It reports and
  does not block, and it exists for the one thing a gate on a Windows machine
  cannot see, which is a fault that only appears on the operating system the
  scheduled run uses.
- Git hooks that refuse a commit carrying a private key or an oversized file, and
  check every commit message against
  [Conventional Commits](https://www.conventionalcommits.org/).
- This changelog.
- Capture of funding calls from one source: the run reaches it, cleans the link,
  gives each item a permanent name, and writes the body and a record of where it
  came from into `data/raw/`. An item already captured is recognised and not
  written twice, and a source's first look archives its backlog without
  announcing it as new.
- A scheduled run each morning, which can also be started by hand. It commits to
  the `data` branch and never to `main`.
- `config/sources.toml`, the watch list. It decides what the system looks at, and
  changing that is a text edit rather than a code change.
- A bug history in [`docs/BUGS.md`](docs/BUGS.md): what broke, what caused it,
  what fixed it, and the test that now guards it, one entry per defect.
- Each captured item is named for the source that captured it, so two sources
  carrying one funding call each keep their own copy and neither is lost.
- A day on which nothing at a source changed leaves the archive untouched, so its
  history shows when items actually changed rather than when the run last looked.
- What a source served is archived whole, before anything reads it, so nothing a
  later step needs can have been thrown away by an earlier one.
- The run reaches only addresses on the open internet, including where a source
  redirects it, and refuses anything on a private or local network.
- A source behind a gate is reported as skipped rather than as quiet, and keeps
  no bookmark, so the next run looks again instead of believing it.

### Changed

- Every development tool is pinned to an exact version rather than a range, so a
  version moves only when a person moves it and that change arrives as a pull
  request where it can be questioned.
