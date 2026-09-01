# ADR-0005 — Spec-first: an approved EARS spec is the primary human gate [decision]
**Status:** Accepted (2026-08-29). **Owner:** build.
**Context.** Reviewing AI-written diffs line by line does not scale, and an agent that jumps straight to code can solve the wrong problem.
**Decision.** Each PR begins with a short plain-English spec in EARS form ("WHEN… THE SYSTEM SHALL…"), naming files touched, out-of-scope, and the end-to-end check; a member of CLI approves the spec before code is written.
**Consequences.** Follows Anthropic's explore-plan-code-commit and Amazon Kiro's spec-as-unit-of-work; the readable spec becomes the review lever.
