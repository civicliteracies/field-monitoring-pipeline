# ADR-0010 — AI-step readiness gate; fetched text is a prompt-injection surface [decision]
**Status:** Accepted (2026-08-29). **Owner:** build.
**Context.** Extraction is the one non-deterministic step and it ingests attacker-influenced web content (OWASP LLM01).
**Decision.** Extraction does not run unattended until a one-page readiness note passes (enable/disable, failure behaviour, monitoring, golden-fixture test plan). Fetched text is strictly data: never executed, never into a shell line, always schema-validated, quarantined on invalid.
**Consequences.** Follows Kubernetes production-readiness reviews and OWASP LLM01; a bad extraction fails safe instead of corrupting the git-as-database.
