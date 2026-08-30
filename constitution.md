# Constitution

The hard box. These six hold through every pull request and every phase of
Fieldbook. **If a task seems to require breaking one, stop and ask a founder.**
Do not work around it, and do not solve the problem a different way without
saying so first.

Changing anything here needs a founder's explicit written approval, recorded as a
decision in `docs/DECISIONS.md`.

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

**4. No new dependency without a founder's approval.**
Every dependency must be real, current, widely used, and pinned in `uv.lock`. CI
installs only from the lockfile. Models invent plausible but fake package names,
so a human confirms every addition.

**5. One small pull request at a time.**
One self-contained change, a few hundred lines at most. Never batch. Never leave
a half-built feature on `main`.

**6. Boring technology.**
Python, GitHub Actions, Markdown in git, one model call. Every new moving part
spends an innovation token a two-person team cannot afford. Treat the stack as
frozen unless a founder agrees to change it.

---

## Why this file exists

Fieldbook is maintained by two people who are not full-time engineers, after the
person who built it has gone. Everything above protects that. An agent, or a
contributor in a hurry, can reasonably think that adding a small database, a
second model call, or one convenient library makes the system better. Each of
those makes it harder to keep alive, and the evidence is that projects like this
one die from neglect rather than from missing features.

The rules are few and blunt on purpose. A long list gets skimmed.
