# ADR-0007 — AGENTS.md as the canonical context file [decision]
**Status:** Accepted (2026-08-29). **Owner:** build.
**Context.** A durable civic project should avoid single-vendor lock-in in its agent instructions.
**Decision.** Adopt the open, tool-neutral `AGENTS.md` standard as the canonical context file, with `CLAUDE.md` importing it (`@AGENTS.md`); keep both short (real rules only).
**Consequences.** Read by Codex/Copilot/Cursor and others should the team ever switch tools; the "keep it short" rule prevents the agent ignoring a bloated file.
