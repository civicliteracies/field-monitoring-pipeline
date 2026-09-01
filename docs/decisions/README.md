# Decisions

Numbered Architecture Decision Records: **why** Fieldbook is built the way it is.
One record per file, each carrying a Title, Status, Context, Decision,
Consequences, and an Owner.

Filenames follow the usual convention, `NNNN-title-with-dashes.md`, so a new
record is a commit that adds one file and touches nothing else.

**Records are immutable and additive.** An accepted record is never rewritten. If
a decision changes, a new record supersedes it and the two are linked, so the
reasoning behind the old choice survives beside the new one. **Status is the one
field that moves**, because that is what it is for: it says whether a record still
holds, and it names the record that replaced it.

**Filenames are permanent too.** Renaming one breaks every link to it, and links
between records are how the supersession chain is read.

**Threshold.** A full record is required when a change touches the item schema,
the extraction step, a source route, or the cron cadence, or when a member of CLI
makes a call with real alternatives. An ordinary slice needs no record; its commit
is the history.

**Defects.** An open defect belongs in the repository's issue tracker, and a fixed
one gets a line under `Fixed` in [`CHANGELOG.md`](../../CHANGELOG.md). A defect
whose fix establishes a lasting rule earns a record here, like
[ADR-0001](0001-deadline-validates-as-a-valid-date.md) and
[ADR-0002](0002-heartbeat-proves-liveness-not-emptiness.md). See
[ADR-0025](0025-conventional-file-layout.md).

**One editorial pass, on 2026-08-31.** Wording across every record was standardised
on "CLI" and "a member of CLI", and phrases describing anyone's professional
background were removed, since this repository is public and nothing here should
characterise a person. **No decision, context, or consequence was altered.** The
pass is recorded because editing accepted records at all is worth declaring.

**A second pass, on 2026-09-01.** One record named an internal document, and
the name was replaced with a description of what it said. **No decision,
context, or consequence was altered.** Recorded on the same reasoning.

## Index

| # | Type | Title |
|---|---|---|
| [ADR-0001](0001-deadline-validates-as-a-valid-date.md) | `[correctness]` | Deadline validates as a *valid* date, not a *future* date |
| [ADR-0002](0002-heartbeat-proves-liveness-not-emptiness.md) | `[correctness]` | Heartbeat proves liveness, not emptiness |
| [ADR-0003](0003-adopt-numbered-adrs-for-the-decision-log.md) | `[decision]` | Adopt numbered ADRs for the decision log |
| [ADR-0004](0004-clean-as-you-code-machine-gate.md) | `[decision]` | Clean-as-You-Code machine gate with added thresholds |
| [ADR-0005](0005-spec-first-approved-spec-is-the-human-gate.md) | `[decision]` | Spec-first: an approved EARS spec is the primary human gate |
| [ADR-0006](0006-a-constitution-of-non-negotiables.md) | `[decision]` | A Constitution of non-negotiables fences the agent |
| [ADR-0007](0007-agents-md-as-the-canonical-context-file.md) | `[decision]` | AGENTS.md as the canonical context file |
| [ADR-0008](0008-free-supply-chain-stack-on-the-public-repo.md) | `[decision]` | Free supply-chain stack on the public repo |
| [ADR-0009](0009-second-opinion-review-agent-and-stop-hook.md) | `[decision]` | Second-opinion review agent and a deterministic Stop hook |
| [ADR-0010](0010-ai-step-readiness-gate.md) | `[decision]` | AI-step readiness gate; fetched text is a prompt-injection surface |
| [ADR-0011](0011-documentation-unit-tests-and-handover-pair.md) | `[decision]` | Documentation unit tests and a Diátaxis handover pair |
| [ADR-0012](0012-dashboard-front-end-is-built-by-the-team.md) | `[decision]` | The dashboard front end is built by the team, not the agent |
| [ADR-0013](0013-repository-is-public-from-the-start.md) | `[decision]` | The repository is public from the start of the build |
| [ADR-0014](0014-no-codeowners-file.md) | `[decision]` | No CODEOWNERS file |
| [ADR-0015](0015-agent-configuration-is-committed.md) | `[decision]` | The agent configuration is committed, and treated as a dangerous path |
| [ADR-0016](0016-one-activity-log-replaces-the-worklog-folder.md) | `[decision]` | One activity log replaces the WORKLOG folder |
| [ADR-0017](0017-bug-history-is-a-separate-file.md) | `[decision]` | The bug history is a separate file from the decision log |
| [ADR-0018](0018-scheduled-run-commits-to-its-own-branch.md) | `[decision]` | The scheduled run commits to its own branch, not to `main` |
| [ADR-0019](0019-quality-gate-runs-in-the-push-hook.md) | `[decision]` | The quality gate runs in the push hook, and `verify` is its read-only form |
| [ADR-0020](0020-ci-runs-the-gate-and-reports.md) | `[decision]` | CI runs the gate and reports; nothing is required to merge |
| [ADR-0021](0021-every-check-runs-on-the-maintainers-machine.md) | `[decision]` | Every check runs on the maintainer's machine; GitHub runs only the scheduled job |
| [ADR-0022](0022-the-gate-is-the-four-standard-checks.md) | `[decision]` | The gate is the four standard checks; the rest was over-engineering |
| [ADR-0023](0023-one-advisory-linux-run.md) | `[decision]` | One advisory Linux run, not required to merge |
| [ADR-0024](0024-build-journal-is-not-published.md) | `[decision]` | The build journal is not published; it lives with the team |
| [ADR-0025](0025-conventional-file-layout.md) | `[decision]` | The conventional layout for decision records and specifications |

---

*Records 0001 to 0012 were made before any code existed and are carried here verbatim. Every source behind them is published and can be read by anyone: watchflow, "Why Cron Jobs Fail Silently"; Hiflylabs, "Temporal Data Validity Management"; ThoughtWorks and AWS on decision records; SonarQube on Clean as You Code; Anthropic and Amazon Kiro on agent process; GitHub Spec Kit; the AGENTS.md standard; OpenSSF, SLSA, and OWASP; Kubernetes production-readiness reviews; Simon Willison on documentation tests; and Diátaxis.*
