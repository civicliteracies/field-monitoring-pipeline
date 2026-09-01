# ADR-0004 — Clean-as-You-Code machine gate with added thresholds [decision]
**Status:** Accepted (2026-08-29). **Owner:** build.
**Context.** When reviewing AI-written code, correctness has to be automatic, and it has to judge only the change.
**Decision.** The gate judges new code only ("Clean as You Code") and adds a new-code coverage floor (~80%), a complexity cap (ruff `C901`), no bare `except` (`BLE`/`E722`), a dependency vulnerability gate (`pip-audit`), and a file-size budget (150–500 lines), on top of the existing ruff/basedpyright-strict/pytest/`D100` gate.
**Consequences.** Mirrors SonarQube's default gate; CLI reviews intent and green CI, not the diff.
