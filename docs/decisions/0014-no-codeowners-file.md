# ADR-0014 — No CODEOWNERS file [decision]
**Status:** Accepted (2026-08-29). **Owner:** CLI.
**Context.** The original plan called for `.github/CODEOWNERS` placing the workflow YAML, the extraction prompt, and the data contracts behind a named person. Three people work on this repository.
**Decision.** No CODEOWNERS file. The pattern earns its place in a larger team where nobody knows who owns which directory, and that is not the situation here.
**Consequences.** Enforcement is unaffected: branch protection still requires a green gate and one approving review on every path. What is given up is the automatic routing of a review request to a named owner when a specific path changes, which at this team size solves a problem that does not exist. Supersedes the code owners requirement in the original plan.
