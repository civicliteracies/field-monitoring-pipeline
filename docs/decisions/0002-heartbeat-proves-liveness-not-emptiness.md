# ADR-0002 — Heartbeat proves liveness, not emptiness [correctness]
**Status:** Accepted (2026-08-26). **Owner:** build.
**Context.** The heartbeat was described as written "each run" in some places and "only after a run that produced data" in others, and was said to make an empty run visible. Neither version works.
**Decision.** The heartbeat proves *liveness*: written on every run that executes, so a silently dropped run goes stale (the real alarm). A run that fired but scraped nothing is a *separate* check, the per-source item-count baseline.
**Consequences.** The standard cron-monitoring split (watchflow, *Why Cron Jobs Fail Silently*); completes the agreed volume check.
