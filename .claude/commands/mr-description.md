---
description: Draft the GitLab MR description for the current fix branch
argument-hint: "[TB-xxx]"
allowed-tools: Bash(git branch:*), Bash(git log:*), Bash(git diff:*), Read, Grep
disable-model-invocation: true
---

Draft the MR description for the current branch, in English, ready to paste into GitLab.

## Context

- Branch: !`git branch --show-current`
- Commits since base: !`git log --oneline origin/feature/example_taskboard..HEAD`
- Files changed: !`git diff --stat origin/feature/example_taskboard...HEAD`
- Diff:

!`git diff origin/feature/example_taskboard...HEAD`

## Ticket

The ticket is `$ARGUMENTS`. If it is empty, take the `TB-xxx` id from the branch name.
Read `docs/tickets/<TB-xxx>.md` and check each acceptance criterion against the tests in the diff.

## Checks

Before the description, print a short "Checks" list, always, even when everything passes:

- Commit order: one `test(...)` commit before the `fix(...)` commit.
- Commit scope: `CLAUDE.md` wants the ticket id as scope (`fix(TB-103): ...`).

Report problems only; never rewrite history.

## Output

Then print the description in one fenced `markdown` block, with these sections:

- **What:** one or two sentences on the user-visible change.
- **Root cause:** `file:line` and why it was wrong.
- **How it was fixed:** the change, and why it is the minimal one.
- **Tests:** one bullet per new test with what it proves.
- **Acceptance criteria:** each criterion from the ticket, ticked only if a test covers it.
- **Assumptions:** decisions on ambiguous requirements, or "None".
- **Out of scope:** related problems not fixed, or "None". Look beyond the diff: read the changed
  functions and their callers, and list what still behaves inconsistently with the fix.
- A final line `Closes <TB-xxx>`.

Rules:

- Describe the change only from what the diff shows. Do not claim tests pass; the reviewer sees CI.
- If there are no commits since base, say that and stop.
- No AI attribution. Do not push, open or edit an MR.
