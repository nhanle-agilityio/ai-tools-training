# CLAUDE.md — TaskBoard

Flask + SQLite task API used for Claude training. Not client code. It contains
intentional bugs tracked in `docs/tickets/` (TB-xxx) — the ticket is the source
of truth for expected behavior, not the current code.

## Commands

```bash
make setup | make test | make seed | make run    # run serves http://127.0.0.1:5050
.venv/bin/pytest -k <keyword>                     # narrow test loop
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

## Architecture (one-way, never skip a layer)

routes.py (HTTP only) → services.py (logic, calls validators) → repository.py (all SQL) → db.py

- Raise `ValidationError` / `NotFoundError`; handlers in `__init__.py` map them to 400 / 404.
- Tasks returned to clients go through `services._serialize_tasks` (adds tags + is_overdue).

## Conventions

- Everything committed is in English: code, docs, commits, MR descriptions.
- Conventional Commits, scope = ticket id: `fix(TB-101): ...`, `test(TB-101): ...`.
- Bug fixes: failing-test commit first, then the fix, as separate small commits.
- Branches: `fix/TB-xxx-short-desc` from `feature/example_taskboard`; MRs target it.
- Tests go through the HTTP layer with the `client` / `project` / `make_task` fixtures.
- A hook runs `ruff format` (line length 110) on every edited .py file — don't fight its output.

## Never

- Never `git add -A` / `git add .` — stage the files you changed by name.
- Never fix or refactor outside the ticket you were asked about; mention it instead.
- Never edit a ticket's acceptance criteria to make a test pass.
- Never decide an ambiguous requirement silently — ask, or state it as an assumption in the MR.
