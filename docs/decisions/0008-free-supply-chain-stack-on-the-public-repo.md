# ADR-0008 — Free supply-chain stack on the public repo [decision]
**Status:** Accepted (2026-08-29). **Owner:** build.
**Context.** A public repo that is also the database, running GitHub Actions with one API key, has a supply-chain and secrets surface.
**Decision.** Stand up (all free) the OpenSSF Scorecard Action, Dependabot (alerts + delayed updates), secret scanning with push protection, SHA-pinned Actions, least-privilege `GITHUB_TOKEN`, and the `detect-private-key` and `check-added-large-files` pre-commit hooks; adopt the slopsquatting rule (no new dependency without approval, CI installs only from the lockfile).
**Consequences.** Targets OpenSSF Scorecard's critical/high checks and OWASP CI/CD risks; free artifact attestations reach SLSA build level 1 to 2.
