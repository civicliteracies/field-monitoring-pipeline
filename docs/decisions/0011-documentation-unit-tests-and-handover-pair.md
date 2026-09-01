# ADR-0011 — Documentation unit tests and a Diátaxis handover pair [decision]
**Status:** Accepted (2026-08-29). **Owner:** build.
**Context.** Docs drift, and the handover after the internship needs the right two documents.
**Decision.** Add a documentation test that fails the build if a field or option is undocumented (stronger than a file-touch check), and keep a `docs/runbook.md` (what breaks, how to fix) and `docs/reference.md` (what each field means, where secrets live).
**Consequences.** Follows Simon Willison's documentation unit tests and the Diátaxis how-to/reference split; the runbook is the tool's lifeline for its maintainers.
