---
name: ticket-fix
description: >-
  The TaskBoard team's workflow for fixing a TB-xxx ticket end to end: read the
  ticket, branch, reproduce, commit a failing test, commit the minimal fix, verify,
  and draft the MR description. Use this skill whenever the user asks to fix,
  work on, pick up, or plan a fix for a ticket (e.g. "fix TB-103", "work on
  TB-104", "plan a fix for TB-102"), even if they only name the ticket id. Do not use it
  for questions that only explain code or a ticket without changing anything.
---

# Fixing a ticket (TaskBoard)

The rules live in `CLAUDE.md` (layers, conventions, "Never" list). This skill is
the order of work. Follow the steps in order and stop at each **checkpoint**.

## 1. Read the ticket

- Open `docs/tickets/<TB-xxx>.md`. The file is named by id only (`TB-103.md`).
  The ticket is the source of truth for expected behavior, not the current code.
- List the acceptance criteria. Each one needs at least one test.
- Write down anything the ticket leaves open (timezones, empty input, limits).
- The ticket's MR target (`develop` in `docs/tickets/README.md`) is outdated.
  Follow `CLAUDE.md`: target `feature/example_taskboard`.

## 2. Reproduce before planning

Show the bug with real output, not by reading code alone: a failing assertion,
a `curl` against `make run`, or a short Python snippet in the app context.
Record the exact input and the wrong output; they go into the MR.

## 3. Plan

State in a few lines:

- the root cause, as `file:line`
- every caller or endpoint the fix affects
- the tests you will add
- related problems you found outside the ticket, which you will only mention

**Checkpoint:** if an ambiguity changes the fix, ask before writing code.
Otherwise state it as an assumption and continue.

## 4. Branch

```bash
git switch -c fix/<TB-xxx>-<short-desc> feature/example_taskboard
```

## 5. Failing test first

- Add tests in `tests/` through the HTTP layer with the `client`, `project` and
  `make_task` fixtures.
- Time-dependent behavior: freeze `datetime` with `monkeypatch` (a `datetime`
  subclass whose `now()` returns a fixed value). Never use `date.today()` in a
  test assertion.
- Run `.venv/bin/pytest -k <keyword>` and confirm the new tests fail **for the
  reason in the ticket**, not because of a typo or an import error.
- Commit only the test files, staged by name:
  `test(<TB-xxx>): <what the tests assert>`

## 6. Minimal fix

- Change the smallest amount of code in the correct layer.
- Re-run the narrow tests, then the full suite and lint:

```bash
make test
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

- Commit only the source files: `fix(<TB-xxx>): <effect for the user>`

**Checkpoint:** show `git log --oneline feature/example_taskboard..HEAD` and the
test result. There must be exactly two commits, test then fix, unless the user
agreed otherwise.

## 7. MR description

Draft it in English with this structure, or run `/mr-description <TB-xxx>`:

```markdown
## What
One or two sentences on the user-visible change.

## Root cause
`file:line` and why it was wrong.

## How it was fixed
The change, and why it is the minimal one.

## Tests
- Test name: what it proves (red before the fix, green after).

## Assumptions
Decisions made on ambiguous requirements, or "None".

## Out of scope
Related problems noticed but not fixed, or "None".

Closes <TB-xxx>
```

## Stop here

Do not push, open an MR, or merge. Hand the branch and the description to the
user. No `Co-Authored-By` or AI attribution in commits or the MR.
