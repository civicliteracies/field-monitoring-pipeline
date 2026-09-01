# ADR-0006 — A Constitution of non-negotiables fences the agent [decision]
**Status:** Accepted (2026-08-29). **Owner:** build.
**Context.** An agent can "helpfully" add a database, a paid API, or a second AI call, breaking the project's core constraints.
**Decision.** A short `constitution.md` holds the hard box (free tier, repo-is-the-database, exactly one AI step, no new dependency without approval, one small PR, boring technology); the agent stops and asks rather than crossing it.
**Consequences.** Follows GitHub Spec Kit's `constitution.md`; the strongest single guard against scope creep.
