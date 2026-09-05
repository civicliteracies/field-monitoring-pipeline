# Changelog

Everything notable that changes in Fieldbook is recorded here, newest first.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

An entry says what changed for someone using or maintaining Fieldbook, in plain
language. **Why** a choice was made, and what it cost, belongs in
[`docs/decisions/`](docs/decisions/) instead.

## [Unreleased]

### Fixed

- A stored value cannot carry an invisible character. The rule said nothing but
  words and the check meant only the characters below the ASCII range, so a line
  separator, a zero width space or a direction override reached a card.
- A range of years written with a slash is read as a range of years again.
- A quote can no longer be stitched together from two blocks of text. This was
  recorded as fixed once and was not: the end of a block was written as a single
  line break, which a page wrapping its own source also produces, so the two could
  not be told apart. Both frozen pages were affected.
- The cells of a table row are separated. They used to run together with nothing
  between them.
- A page that nests a menu inside a menu no longer has the rest of its menu read
  as the article.
- A telephone number or an email address can no longer reach a card through the
  title, the funder, or any stored value. The rule that keeps contact details out
  of a published record ran on the quoted sentence and on nothing else, so five
  of the six published fields had no guard at all.
- A telephone number is caught when a currency word sits anywhere near it. One
  currency word used to clear every number sharing a run of digits with it,
  whichever end it sat at, including a number written one plain space from an
  amount. A figure grouped for reading is still read as a figure, so an amount in
  the millions or billions is unaffected.
- A telephone number is caught when it is written with a dash, a slash, a middle
  dot, an invisible joiner, or wide digits, none of which the rule could see
  before.
- Two telephone numbers written side by side are caught. They used to merge into
  one run and be discarded for being longer than any number anybody can ring.
- An address written to defeat a machine reading the page is caught, in the four
  forms a site uses when it means to hide one.
- A closing date is no longer published from the wrong date. A sentence naming
  when a call opens in words and when it closes in figures produced a card whose
  deadline was the opening date, with that sentence stored beside it as evidence.
- What a source served is protected from having its line endings rewritten, which
  only the older archive folder was.
- A telephone number is caught even when something else with digits sits beside
  it. A number followed by its opening hours, or two numbers side by side, used to
  merge into one run that the check read as too long for anyone to ring, and the
  quote was published.
- A telephone number written without separators is caught. Any solid run of seven
  or eight digits used to be assumed to be an amount, which made every number
  written that way invisible. The cost is that an amount written solid with no
  currency beside it is now refused, which naming the currency clears.
- A figure in a value must be a number the page actually states. It was enough
  for the digits to appear anywhere, so a claimed 87 was accepted on a page whose
  only number is the year 1987.
- A quote can no longer be padded with spaces to reach the length the rule asks
  for. The length was measured on the raw text and the grounding on the collapsed
  text, so whitespace counted towards a floor that exists to make a quote mean
  something.
- A stored value may not carry a line break or a tab. One hidden inside passed
  the check, because the check collapses whitespace, and still reached the card,
  where a title has to be one whole line of the page and the printed record puts
  one field on one line.
- A telephone number written as two groups of four digits is caught. The
  exemption that lets a range of years through was matching any eight digits with
  a dash in the middle, which is how much of the world writes a local number.
- An amount with the currency written after it is read as money. The rule looked
  only before the figure, so an honest budget written the ordinary European way
  was refused as carrying a contact detail.
- A quote can no longer be stitched together from two unrelated paragraphs. The
  end of a block of text was being treated as an ordinary space when a quote was
  checked against the page, so a sentence from one paragraph joined to a sentence
  from the next read as one real quote and passed. That check is what every
  stored value rests on.
- A page's own menu can no longer reach the text a quote is checked against by
  closing a tag it never opened. A menu lists the funder's other programmes, and
  a sentence from one of those would otherwise pass while describing a different
  grant.
- A page served with Windows line endings now reads exactly as the same page
  written the plain way. A stray carriage return was letting a page write its own
  copy of the delimiter that separates the instruction from the text it is meant
  to read.
- A record refuses a field it does not know, rather than loading and dropping it
  in silence. A card is read back on every push and again on every rebuild, so a
  mistyped or renamed field is worth stopping for.
- The archive and the frozen test fixtures are no longer rewritten by git. A page
  served with Windows line endings was stored one way and read back another, which
  would have made a quote verify on the machine that captured it and fail
  everywhere else.
- A damaged bookmark file no longer ends the whole scheduled run before anything
  is fetched. It costs one unconditional fetch of one source and is repaired.
- A typo in the watch list is reported instead of producing a run that quietly
  looks at nothing and reports success.
- The gate refuses a lockfile that disagrees with the project file. It said it
  did and did not: the flag in use installed from the lockfile and ignored the
  disagreement, and the local gate rewrote the lockfile to agree rather than
  reporting it.

### Added

- The words a model will read. A captured page becomes one readable string, with
  markup removed and a sentence kept whole across a link or a bold word. That same
  string is what every quote will later be checked against.
- A record built from one line of flags, with every claim checked against the page
  it came from. Five fields on a call carry the sentence that supports them, a
  closing date is read back out of its own sentence rather than trusted, and a
  claim the page does not support is refused with a reason.
- The one AI step, proven on a single real item. A model reads a captured item,
  reasons in the open, then writes one command line naming what it found. A broken
  answer is sent back once with the reason. Nothing is written to disk yet.
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
  ADR-0036, one file per record with an index.
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
