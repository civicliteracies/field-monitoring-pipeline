# ADR-0003 — Adopt numbered ADRs for the decision log [decision]
**Status:** Accepted (2026-08-29). Superseded in part by [ADR-0025](0025-conventional-file-layout.md), which moved the records from one file to one file per record under `docs/decisions/`. The format, the immutability rule and the threshold are unchanged. **Owner:** build.
**Context.** The decision and bug log needs a durable, handover-proof format that survives the handover of a public repository.
**Decision.** Use numbered ADRs (Title/Status/Context/Decision/Consequences/Owner), immutable and additive, superseded rather than deleted, kept in git as `docs/DECISIONS.md`, with the threshold rule above.
**Consequences.** Follows ThoughtWorks' "adopt"-tier lightweight ADRs and AWS's immutable/supersede/owner rules; raises the bus factor by preserving the reasoning a departing person would otherwise take away.
