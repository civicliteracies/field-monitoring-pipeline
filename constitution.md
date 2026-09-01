# Constitution

The hard box. These six hold through every pull request and every phase of
Fieldbook. **If a task seems to require breaking one, stop and ask a member of CLI.**
Do not work around it, and do not solve the problem a different way without
saying so first.

Changing anything here needs explicit written approval from a member of CLI,
recorded as a decision in [`docs/decisions/`](docs/decisions/).

---

**1. Free tier only.**
No paid service, no server, no hosted database, no third-party SaaS. If a task
seems to need one, it is the wrong task.

**2. The repository is the database.**
One text file per item. No database engine, no committed query index, no cached
copy of derived data. Any query layer added later is rebuilt from the files and
never committed.

**3. Exactly one AI step.**
Only extraction uses a model. Never add a second model call, an agent framework,
or a model in any other step.

**4. No new dependency without approval from a member of CLI.**
Every dependency must be real, current, widely used, and pinned to an exact
version in `uv.lock`, which uv installs from and refuses to run against when it
disagrees. Models invent plausible but fake package names, so a person confirms
every addition.

**5. One small pull request at a time.**
One self-contained change, a few hundred lines at most. Never batch. Never leave
a half-built feature on `main`.

**6. Boring technology.**
Python, GitHub Actions, Markdown in git, one model call. Every new moving part
spends an innovation token a small team cannot afford. Treat the stack as
frozen unless a member of CLI agrees to change it.

---

## Why this file exists

Fieldbook has to keep working through long stretches when nobody is looking at
it. Everything above protects that. An agent, or a contributor in a hurry, can
reasonably think that adding a small database, a second model call, or one
convenient library makes the system better. Each of those is another thing that
can break while unattended, and the evidence is that projects like this one die
from neglect rather than from missing features.

The rules are few and blunt on purpose. A long list gets skimmed.

The pattern comes from [GitHub Spec Kit](https://github.com/github/spec-kit),
which keeps a project's non-negotiables in one short document an agent reads
before anything else. Spec Kit hides the file inside its own folder. Here it
sits at the root, because a rule nobody can find is no rule at all.
