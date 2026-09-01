# ADR-0016 — One activity log replaces the WORKLOG folder [decision]
**Status:** Accepted (2026-08-30). **Owner:** build.
**Context.** The original plan specified a journal at `WORKLOG/YYYYMMDD.md`, one file per day. A single running file was requested instead.
**Decision.** `docs/ACTIVITY.md` takes the journal role, newest day first. The `WORKLOG/` folder is not created. The Stage 11 instruction to record what happened after each pull request is unchanged; only the location changes.
**Consequences.** One journal rather than two competing for the same attention. Fading maintainer attention is the most likely cause of this project's death, and a duplicated log is the first thing to go stale. Departs from the original plan, recorded so the departure is deliberate and visible.
