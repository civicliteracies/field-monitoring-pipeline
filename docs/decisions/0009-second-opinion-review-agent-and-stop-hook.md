# ADR-0009 — Second-opinion review agent and a deterministic Stop hook [decision]
**Status:** Accepted (2026-08-29). Superseded in part by ADR-0019, which replaced the command the hook runs with the read-only `mise run verify`. **Owner:** build.
**Context.** "Looks done" is the only signal an agent has without a check it can run, and a first-line reviewer is needed before a person looks.
**Decision.** A local Stop hook runs `mise run check` and refuses to end a turn on a red gate; each PR gets a fresh-context second-opinion review (the `/code-review` skill) scoped to correctness and requirement gaps before a member of CLI looks.
**Consequences.** Follows Anthropic's "give the agent a check it can run" and the writer/reviewer pattern; catches CI-gaming and hallucinated correctness.
