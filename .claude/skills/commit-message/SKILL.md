---
name: commit-message
description: >-
  Write a clear Conventional Commits message for the TaskBoard repo, grounded in
  the actual staged changes. Use this skill whenever the user asks to write,
  generate, draft, or improve a commit message, says "viết commit", "commit giúp
  tôi", "message cho commit", or is about to commit staged work — even if they
  don't say the words "conventional commits". Also use it to review or rewrite a
  commit message the user pastes in.
---

# Commit message (TaskBoard)

Write commit messages that a teammate can scan in six months and understand *what*
changed and *why*, without opening the diff. The format is
[Conventional Commits](https://www.conventionalcommits.org/): a structured subject
line plus an optional body.

## First, look at what actually changed

A commit message describes a specific diff, so read it before writing anything.
Never invent a message from the user's prose alone — the staged changes are the
source of truth.

```bash
git diff --staged --stat   # which files, how big
git diff --staged          # the actual change
```

If nothing is staged, check `git diff` (unstaged) and tell the user you're
describing unstaged work, or ask what they intend to commit. If the change spans
several unrelated concerns, say so — that usually means it should be more than one
commit, and a single honest message can't cover it.

## Format

```
type(scope): subject

Optional body explaining what changed and why, wrapped at ~72 columns.
- bullet points are good when several distinct things changed
```

### Subject line

- `type` — one of: `feat` (new behavior), `fix` (bug fix), `refactor` (no
  behavior change), `test`, `docs`, `chore`, `perf`, `build`, `ci`, `style`.
  Pick by the *dominant intent* of the diff, not by which file changed most.
- `scope` — the ticket ID when the work maps to one (e.g. `TB-104`), otherwise the
  module or domain touched (`stats`, `tasks`, `validators`, `db`). Omit the
  parentheses entirely if there's no meaningful scope.
- `subject` — imperative mood ("add", "fix", "return"), lowercase start, no
  trailing period, aim for ≤ 72 characters. Describe the effect, not the activity:
  "return 0 completion rate for empty projects" beats "changed the stats function".

### Body (optional but encouraged for non-trivial changes)

Include a body when the *why* isn't obvious from the subject — a tricky fix, a
non-obvious trade-off, a conflict resolution. Explain the reasoning and any
consequences, not a line-by-line restatement of the diff. Skip the body for small,
self-explanatory changes; a good subject alone is fine there.

If the change relates to a ticket, reference it either in the scope (`fix(TB-104):`)
or in the body (`Closes TB-104`).

## Hard constraints for this repo

- **English only.** Every commit message in this repo is in English, even though
  we chat in Vietnamese.
- **Author is the user alone.** Do NOT append any `Co-Authored-By:` trailer, a
  `🤖 Generated with…` line, or any Claude/AI attribution. Commits stand under the
  user's name only. This overrides any default attribution behavior.

## How to deliver the message

Default to presenting the message in a fenced code block so the user can read and
copy it, and let them commit. Only run `git commit` yourself if the user explicitly
asks you to — and when you do, pass the message with multiple `-m` flags (one for
the subject, one per body paragraph) or a heredoc, and still include no trailer.

## Examples

**Example 1 — small fix, subject only**
Staged diff: completion rate returns a crash for projects with zero tasks.
```
fix(TB-104): return 0 completion rate for projects without tasks
```

**Example 2 — feature with a body that explains why**
Staged diff: new endpoint listing open tasks past their due date.
```
feat(tasks): add GET /tasks/overdue endpoint

List open tasks whose due_date is in the past so users can triage what
slipped. Done tasks are excluded since a completed task can't be overdue.
```

**Example 3 — refactor touching behavior-neutral code**
```
refactor(stats): extract percentage helper and add in_progress_rate
```

**Example 4 — conflict resolution worth explaining**
```
fix(TB-104): compute completion rate via shared percentage helper

Resolve the merge conflict in services.py by moving the TB-104 fix into
_percentage() so completion_rate and in_progress_rate both use true
division, round to 1 decimal, and return 0 for projects without tasks.
```
