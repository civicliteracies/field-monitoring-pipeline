# Decisions

Numbered Architecture Decision Records: **why** Fieldbook is built the way it is.
Each record carries a Title, Status, Context, Decision, Consequences, and an Owner.

**Records are immutable and additive.** An accepted record is never rewritten. If a
decision changes, a new record supersedes it and the two are linked, so the
reasoning behind the old choice survives beside the new one.

**Threshold.** A full record is required when a change touches the item schema, the
extraction step, a source route, or the cron cadence, or when a founder makes a
call with real alternatives. Ordinary slices need only a line in
`docs/ACTIVITY.md`.

**Bugs live in [`docs/BUGS.md`](BUGS.md), not here.** When fixing a bug also
establishes a lasting rule, the incident is recorded there and the rule here, and
the two link to each other. Records 0001 and 0002 predate that split and stay
here unchanged, because accepted records are never rewritten; `BUGS.md` carries
their incident history and points back to them.

## Index

| # | Type | Title |
|---|---|---|
| ADR-0001 | `[correctness]` | Deadline validates as a *valid* date, not a *future* date |
| ADR-0002 | `[correctness]` | Heartbeat proves liveness, not emptiness |
| ADR-0003 | `[decision]` | Adopt numbered ADRs for the decision log |
| ADR-0004 | `[decision]` | Clean-as-You-Code machine gate with added thresholds |
| ADR-0005 | `[decision]` | Spec-first: an approved EARS spec is the primary human gate |
| ADR-0006 | `[decision]` | A Constitution of non-negotiables fences the agent |
| ADR-0007 | `[decision]` | AGENTS.md as the canonical context file |
| ADR-0008 | `[decision]` | Free supply-chain stack on the public repo |
| ADR-0009 | `[decision]` | Second-opinion review agent and a deterministic Stop hook |
| ADR-0010 | `[decision]` | AI-step readiness gate; fetched text is a prompt-injection surface |
| ADR-0011 | `[decision]` | Documentation unit tests and a Diátaxis handover pair |
| ADR-0012 | `[decision]` | The dashboard front end is built by the team, not the agent |
| ADR-0013 | `[decision]` | The repository is public from the start of the build |
| ADR-0014 | `[decision]` | No CODEOWNERS file |
| ADR-0015 | `[decision]` | The agent configuration is committed, and treated as a dangerous path |
| ADR-0016 | `[decision]` | One activity log replaces the WORKLOG folder |
| ADR-0017 | `[decision]` | The bug history is a separate file from the decision log |

---

## ADR-0001 — Deadline validates as a *valid* date, not a *future* date [correctness]
**Status:** Accepted (2026-08-26). **Owner:** build.
**Context.** Validation required a dated call's deadline to parse as a *future* date and re-ran on every push, so the day a deadline passed the retained call would fail the check and the rebuild step would reject every expired call. This breaks a stated goal: keep closed calls (find the January report in July; count past activity in the quarterly read).
**Decision.** Whether a deadline still lies ahead is a *derived, surfacing* property, used to order and flag calls, not a stored-record invariant. The permanent checks are: required fields present, each value's quote a real substring of the source, and the deadline parses as a *valid* date. Open-versus-closed is computed from the date at display time.
**Consequences.** Standard temporal-data practice (Hiflylabs, *Temporal Data Validity Management*); matches Cédric's framing of timeliness as "is the deadline still open?". Applied in Technical Blueprint (Parts 3, 4, 5, 8, 11), Build Plan (Step 5), Technology Assessment (Parts 1, 4, 5), the decisions ledger (§2).

## ADR-0002 — Heartbeat proves liveness, not emptiness [correctness]
**Status:** Accepted (2026-08-26). **Owner:** build.
**Context.** The heartbeat was described as written "each run" in some places and "only after a run that produced data" in others, and was said to make an empty run visible. Neither version works.
**Decision.** The heartbeat proves *liveness*: written on every run that executes, so a silently dropped run goes stale (the real alarm). A run that fired but scraped nothing is a *separate* check, the per-source item-count baseline.
**Consequences.** The standard cron-monitoring split (watchflow, *Why Cron Jobs Fail Silently*); completes Cédric's stated volume check. Applied in Technical Blueprint (Parts 7, 8, 9), Build Plan (Step 7, Part 4), Technology Assessment (Parts 1, 4, 5), RISKS.md (risk 5), the decisions ledger (§6).

## ADR-0003 — Adopt numbered ADRs for the decision log [decision]
**Status:** Accepted (2026-08-29). **Owner:** build.
**Context.** The decision and bug log needs a durable, handover-proof format for a two-person non-engineer team maintaining a public repo.
**Decision.** Use numbered ADRs (Title/Status/Context/Decision/Consequences/Owner), immutable and additive, superseded rather than deleted, kept in git as `docs/DECISIONS.md`, with the threshold rule above.
**Consequences.** Follows ThoughtWorks' "adopt"-tier lightweight ADRs and AWS's immutable/supersede/owner rules; raises the bus factor by preserving the reasoning a departing person would otherwise take away.

## ADR-0004 — Clean-as-You-Code machine gate with added thresholds [decision]
**Status:** Accepted (2026-08-29). **Owner:** build.
**Context.** For non-engineers reviewing AI-written code, correctness must be automatic and must judge only the change.
**Decision.** The gate judges new code only ("Clean as You Code") and adds a new-code coverage floor (~80%), a complexity cap (ruff `C901`), no bare `except` (`BLE`/`E722`), a dependency vulnerability gate (`pip-audit`), and a file-size budget (150–500 lines), on top of the existing ruff/basedpyright-strict/pytest/`D100` gate.
**Consequences.** Mirrors SonarQube's default gate; the founders review intent and green CI, not the diff.

## ADR-0005 — Spec-first: an approved EARS spec is the primary human gate [decision]
**Status:** Accepted (2026-08-29). **Owner:** build.
**Context.** Two non-engineer maintainers cannot review diffs line by line, and an agent that jumps to code can solve the wrong problem.
**Decision.** Each PR begins with a short plain-English spec in EARS form ("WHEN… THE SYSTEM SHALL…"), naming files touched, out-of-scope, and the end-to-end check; a founder approves the spec before code is written.
**Consequences.** Follows Anthropic's explore-plan-code-commit and Amazon Kiro's spec-as-unit-of-work; the readable spec becomes the review lever.

## ADR-0006 — A Constitution of non-negotiables fences the agent [decision]
**Status:** Accepted (2026-08-29). **Owner:** build.
**Context.** An agent can "helpfully" add a database, a paid API, or a second AI call, breaking the project's core constraints.
**Decision.** A short `constitution.md` holds the hard box (free tier, repo-is-the-database, exactly one AI step, no new dependency without approval, one small PR, boring technology); the agent stops and asks rather than crossing it.
**Consequences.** Follows GitHub Spec Kit's `constitution.md`; the strongest single guard against scope creep.

## ADR-0007 — AGENTS.md as the canonical context file [decision]
**Status:** Accepted (2026-08-29). **Owner:** build.
**Context.** A durable civic project should avoid single-vendor lock-in in its agent instructions.
**Decision.** Adopt the open, tool-neutral `AGENTS.md` standard as the canonical context file, with `CLAUDE.md` importing it (`@AGENTS.md`); keep both short (real rules only).
**Consequences.** Read by Codex/Copilot/Cursor and others should the team ever switch tools; the "keep it short" rule prevents the agent ignoring a bloated file.

## ADR-0008 — Free supply-chain stack on the public repo [decision]
**Status:** Accepted (2026-08-29). **Owner:** build.
**Context.** A public repo that is also the database, running GitHub Actions with one API key, has a supply-chain and secrets surface.
**Decision.** Stand up (all free) the OpenSSF Scorecard Action, Dependabot (alerts + delayed updates), secret scanning with push protection, SHA-pinned Actions, least-privilege `GITHUB_TOKEN`, and the `detect-private-key` and `check-added-large-files` pre-commit hooks; adopt the slopsquatting rule (no new dependency without approval, CI installs only from the lockfile).
**Consequences.** Targets OpenSSF Scorecard's critical/high checks and OWASP CI/CD risks; free artifact attestations reach SLSA build level 1 to 2.

## ADR-0009 — Second-opinion review agent and a deterministic Stop hook [decision]
**Status:** Accepted (2026-08-29). **Owner:** build.
**Context.** "Looks done" is the only signal an agent has without a check it can run, and non-engineers need a first-line reviewer.
**Decision.** A local Stop hook runs `mise run check` and refuses to end a turn on a red gate; each PR gets a fresh-context second-opinion review (the `/code-review` skill) scoped to correctness and requirement gaps before the founder looks.
**Consequences.** Follows Anthropic's "give the agent a check it can run" and the writer/reviewer pattern; catches CI-gaming and hallucinated correctness.

## ADR-0010 — AI-step readiness gate; fetched text is a prompt-injection surface [decision]
**Status:** Accepted (2026-08-29). **Owner:** build.
**Context.** Extraction is the one non-deterministic step and it ingests attacker-influenced web content (OWASP LLM01).
**Decision.** Extraction does not run unattended until a one-page readiness note passes (enable/disable, failure behaviour, monitoring, golden-fixture test plan). Fetched text is strictly data: never executed, never into a shell line, always schema-validated, quarantined on invalid.
**Consequences.** Follows Kubernetes production-readiness reviews and OWASP LLM01; a bad extraction fails safe instead of corrupting the git-as-database.

## ADR-0011 — Documentation unit tests and a Diátaxis handover pair [decision]
**Status:** Accepted (2026-08-29). **Owner:** build.
**Context.** Docs drift, and the handover to non-engineers after the internship needs the right two documents.
**Decision.** Add a documentation test that fails the build if a field or option is undocumented (stronger than a file-touch check), and keep a `docs/runbook.md` (what breaks, how to fix) and `docs/reference.md` (what each field means, where secrets live).
**Consequences.** Follows Simon Willison's documentation unit tests and the Diátaxis how-to/reference split; the runbook is the tool's lifeline for its maintainers.

## ADR-0012 — The dashboard front end is built by the team, not the agent [decision]
**Status:** Accepted (2026-08-29). **Owner:** build.
**Context.** The founders and intern want to own the look and feel of the public-facing dashboard, and the store is plain card files that any front end can read directly.
**Decision.** Claude Code builds the data pipeline, the RSS feed, and everything except the dashboard front end (PR 12); the dashboard (`site/`) is built by the team, reading `data/calls/<id>.md` client-side and following the CLI Brand Guide. Claude Code builds through PR 11, pauses while the team builds PR 12, then continues at PR 13 — the step is built by a human, not skipped — and keeps the card files and the feed a stable contract for the front end.
**Consequences.** The front end decouples cleanly from the pipeline (files-as-store makes this free); the agent's surface work ends at the feed, and the team owns the dashboard. Recorded so the split is unambiguous.

## ADR-0013 - The repository is public from the start of the build [decision]
**Status:** Accepted (2026-08-29). **Owner:** Cedric Lombion.
**Context.** The build began with the repository private on a free-plan organisation. Verified against the API: rulesets returned `403 Upgrade to GitHub Pro or make this repository public`, so branch protection, secret scanning with push protection, the OpenSSF Scorecard, GitHub Pages, and CODEOWNERS were all unavailable. PR 1 exists to make the quality gate binding, and none of the binding mechanisms were available.
**Decision.** Make the repository public immediately rather than at launch. The design's end state was public in any case, and GitHub Pages is needed for the dashboard at PR 12, well before launch.
**Consequences.** The gate can enforce rather than only report. Actions minutes become unlimited. All collected data is public activity from organisations' own publications, and the one model key is an encrypted secret that never enters the repository. The full history was scanned before the change: eleven files, no credential ever committed.

## ADR-0014 - No CODEOWNERS file [decision]
**Status:** Accepted (2026-08-29). **Owner:** Cedric Lombion.
**Context.** The Build Prompt calls for `.github/CODEOWNERS` placing the workflow YAML, the extraction prompt, and the data contracts behind a named founder. Three people work on this repository.
**Decision.** No CODEOWNERS file. In the founder's words, this kind of process is useful in a larger team, and here the collaborators can talk to each other.
**Consequences.** Enforcement is unaffected: branch protection still requires a green gate and one approving review on every path. What is given up is the automatic routing of a review request to a named owner when a specific path changes, which at this team size solves a problem that does not exist. Supersedes the CODEOWNERS requirement in the Build Prompt's PR 1.

## ADR-0015 - The agent configuration is committed, and treated as a dangerous path [decision]
**Status:** Accepted (2026-08-29). **Owner:** build.
**Context.** The Rulebook's Stage 0 asks for a `.claude/` Stop hook that refuses to end a turn on a failing gate, but `.gitignore` ignored `.claude/` entirely, making a committed hook impossible. Researched against the Claude Code documentation.
**Decision.** Commit `.claude/settings.json`. It is the documented shared project scope, explicitly intended to be committed, hooks included. `.gitignore` ignores `.claude/settings.local.json` alone.
**Consequences.** Committed `deny` rules bind immediately on any clone with no workspace-trust step, which is the only mechanism that makes the Constitution's limits mechanical rather than remembered, and so serves ADR-0006. The residual risk is real and narrow: hooks in settings files run even in the two untrusted situations the documentation names, so the file is executable content in a public repository. It is mitigated by keeping the hook to one fixed command, admitting no secret to the file, and requiring a reviewed pull request for any change. A path-specific owner was the original mitigation; see ADR-0014.

## ADR-0016 - One activity log replaces the WORKLOG folder [decision]
**Status:** Accepted (2026-08-30). **Owner:** Rezhyar Fakhir.
**Context.** The Build Prompt and Rulebook specify a journal at `WORKLOG/YYYYMMDD.md`, one file per day. A single running file was requested instead.
**Decision.** `docs/ACTIVITY.md` takes the journal role, newest day first. The `WORKLOG/` folder is not created. The Stage 11 instruction to record what happened after each pull request is unchanged; only the location changes.
**Consequences.** One journal rather than two competing for the same attention. RISK 3 names fading maintainer attention as the most likely cause of this project's death, and a duplicated log is the first thing to go stale. Departs from the Build Prompt, recorded so the departure is deliberate and visible.

## ADR-0017 - The bug history is a separate file from the decision log [decision]
**Status:** Accepted (2026-08-30). **Owner:** Rezhyar Fakhir.
**Context.** The Build Prompt treats `docs/DECISIONS.md` as the decision log and bug history together, one file carrying both, distinguished by a `[correctness]` or `[decision]` tag. In practice the two answer different questions, for different readers, at different moments: why is it built this way, against what broke and how was it fixed. A founder diagnosing a problem should not have to filter a list of architecture records.
**Decision.** Split them. `docs/DECISIONS.md` holds design decisions. `docs/BUGS.md` holds defects, each with symptom, cause, fix, and the test that now guards it. Where fixing a bug also establishes a lasting rule, the incident is recorded in `BUGS.md` and the rule in `DECISIONS.md`, and the two link to each other, so neither file is incomplete and nothing is written twice.
**Consequences.** Each file answers one question completely. Records 0001 and 0002 stay in this file unchanged, because accepted records are never rewritten, and `BUGS.md` carries their incident history with a link back. Departs from the Build Prompt; to be confirmed with Cedric.

---

*Records 0001 to 0012 were made during the document phase and are carried here verbatim. Sources: watchflow, "Why Cron Jobs Fail Silently"; Hiflylabs, "Temporal Data Validity Management"; and the study "How Other Organizations Do It" (ThoughtWorks and AWS on ADRs; SonarQube Clean-as-You-Code; Anthropic and Amazon Kiro on agent process; GitHub Spec Kit; the AGENTS.md standard; OpenSSF, SLSA, and OWASP; Kubernetes production-readiness; Simon Willison and Diataxis).*
