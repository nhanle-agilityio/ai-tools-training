---
name: issue-fix
description: >-
  The TaskBoard team's workflow for fixing a GitHub issue end to end: read the
  issue, branch, reproduce, commit a failing test, commit the minimal fix, verify,
  and draft the PR description. Use this skill whenever the user asks to fix,
  work on, pick up, or plan a fix for an issue (e.g. "fix #12", "work on issue
  14", "plan a fix for #9"), even if they only name the issue number. Do not use it
  for questions that only explain code or an issue without changing anything.
---

# Fixing an issue (TaskBoard)

The rules live in `CLAUDE.md` (layers, conventions, "Never" list). This skill is
the order of work. Follow the steps in order and stop at each **checkpoint**.

## 1. Read the issue

- Read GitHub issue `#<N>` with the GitHub MCP (`issue_read`), and its spec in
  `docs/specs/` if the issue links one. The issue is the source of truth for
  expected behavior, not the current code.
- If the user names a legacy `TB-xxx` ticket from `docs/tickets/`, ask for the
  matching GitHub issue number before going on.
- List the acceptance criteria. Each one needs at least one test.
- Write down anything the issue leaves open (timezones, empty input, limits).

## 2. Reproduce before planning

Show the bug with real output, not by reading code alone: a failing assertion,
a `curl` against `make run`, or a short Python snippet in the app context.
Record the exact input and the wrong output; they go into the PR.

## 3. Plan

State in a few lines:

- the root cause, as `file:line`
- every caller or endpoint the fix affects
- the tests you will add
- related problems you found outside the issue, which you will only mention

**Checkpoint:** if an ambiguity changes the fix, ask before writing code.
Otherwise state it as an assumption and continue.

## 4. Branch

```bash
git switch -c fix/<N>-<short-desc> feature/example_taskboard
```

## 5. Failing test first

- Add tests in `tests/` through the HTTP layer with the `client`, `project` and
  `make_task` fixtures.
- Time-dependent behavior: freeze `datetime` with `monkeypatch` (a `datetime`
  subclass whose `now()` returns a fixed value). Never use `date.today()` in a
  test assertion.
- Run `.venv/bin/pytest -k <keyword>` and confirm the new tests fail **for the
  reason in the issue**, not because of a typo or an import error.
- Commit only the test files, staged by name:
  `test(#<N>): <what the tests assert>`

## 6. Minimal fix

- Change the smallest amount of code in the correct layer.
- Re-run the narrow tests, then the full suite and lint:

```bash
make test
.venv/bin/ruff check . && .venv/bin/ruff format --check .
```

- Commit only the source files: `fix(#<N>): <effect for the user>`

**Checkpoint:** show `git log --oneline feature/example_taskboard..HEAD` and the
test result. There must be exactly two commits, test then fix, unless the user
agreed otherwise.

## 7. PR description

Draft it in English with this structure, or run `/pr-description <N>`:

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

Closes #<N>
```

## Stop here

Do not push, open a PR, or merge. Hand the branch and the description to the
user. No `Co-Authored-By` or AI attribution in commits or the PR.
