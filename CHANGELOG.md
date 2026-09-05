# Changelog

Everything notable that changes in Fieldbook is recorded here, newest first.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

An entry says what changed for someone using or maintaining Fieldbook, in plain
language. **Why** a choice was made, and what it cost, belongs in
[`docs/decisions/`](docs/decisions/) instead.

## [Unreleased]

### Fixed

- The archive and the frozen test fixtures are no longer rewritten by git. A page
  served with Windows line endings was stored one way and read back another, which
  would have made a quote verify on the machine that captured it and fail
  everywhere else.

### Added

- The words a model will read. A captured page becomes one readable string, with
  markup removed and a sentence kept whole across a link or a bold word. That same
  string is what every quote will later be checked against.

### Fixed

- A damaged bookmark file no longer ends the whole scheduled run before anything
  is fetched. It costs one unconditional fetch of one source and is repaired.
- A typo in the watch list is reported instead of producing a run that quietly
  looks at nothing and reports success.
- The gate refuses a lockfile that disagrees with the project file. It said it
  did and did not: the flag in use installed from the lockfile and ignored the
  disagreement, and the local gate rewrote the lockfile to agree rather than
  reporting it.

### Changed

- Every development tool is pinned to an exact version rather than a range, so a
  version moves only when a person moves it and that change arrives as a pull
  request where it can be questioned.
