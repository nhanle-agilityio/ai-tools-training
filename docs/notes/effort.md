# Day 6 — Effort levels on one bug

## Setup

Same bug (TB-103, "tasks due today are reported as overdue"), same prompt, three fresh sessions in plan mode, plans not approved. The prompt asked for: root cause, every path that uses `is_overdue`, ambiguous requirements, time-independent tests, files to change.

| Run | Setting | Time | Context after plan |
| --- | --- | --- | --- |
| A | `/effort low` | 35s | 49.1k |
| B | `/effort high` | 1m22s | 64.9k |
| C | `/effort medium` (default) + `ultrathink` | 1m16s | 57.6k |

About 28k of each context total is fixed overhead (system tools, skills, memory; see `compaction.md`). The work itself was roughly **A ≈ 21k, B ≈ 37k, C ≈ 30k**. The three ran in parallel, so the times are indicative only.

## Answer key

1. **Root cause:** `services.py:72` compares the date string `"2026-10-21"` with `datetime.now().isoformat()` (`"2026-10-21T00:01:00"`). The shorter string is a prefix, so it is always "less", and a task due today is overdue all day.
2. **Easy-to-miss path:** `list_overdue_tasks(db, now)` filters with the `now` it receives, but `_serialize_tasks` calls `is_overdue(task)` without `now`, so the `is_overdue` flag always uses the real clock. The list and the flag can disagree.
3. **Ambiguity to raise, not decide:** whose "today" (server local, UTC, or the user's timezone).
4. **Time-independent tests:** freeze the clock at 00:01 and 23:59 instead of using `date.today()` in tests.
5. **Minimal scope:** the fix is one or two lines in `is_overdue`; the `now` mismatch is a separate issue to mention.

## Scores (0–2 per criterion)

| Criterion | A (low) | B (high) | C (medium + ultrathink) |
| --- | --- | --- | --- |
| Root cause | 2 · correct, not reproduced | 2 · reproduced at 00:00, 00:01, 23:59 | 2 · reproduced |
| All paths, incl. the `now` mismatch | 2 | 2 · most complete map, endpoint by endpoint | 2 |
| Ambiguity | 1.5 · timezone; also asked about a boundary the ticket already defines | 2 · timezone, plus "does the reminder email read this API or compute its own?" | 2 · timezone, plus MR target mismatch between `docs/tickets/README.md` and `CLAUDE.md` |
| Time-independent tests | 1.5 · fixed `now`, but needs a new clock hook in production code | 2 · `datetime` subclass via monkeypatch, no new dependency, all endpoints checked | 2 · same technique, explains the midnight race of `date.today()` |
| Scope | 1 · wants to change 3 things, including the `now` mismatch | 2 · 2 lines, mismatch only mentioned | 2 · 1 line, mismatch only mentioned |
| **Total** | **8 / 10** | **10 / 10** | **10 / 10** |

C also noticed that the prompt's glob `TB-103-*.md` matched nothing (the file is `TB-103.md`) and said so. A and B found the file silently.

## Takeaways

- **Low effort found the right root cause in 35s.** It's fine for triage and "explain this code".
- **Low effort widened the scope.** It treated a side issue as part of the fix and suggested adding production code only to make tests easier. The higher settings kept the fix to one or two lines and only mentioned the side issue, as `CLAUDE.md` asks.
- **High and ultrathink checked their claims.** Both ran the code to reproduce the bug before planning; low effort reasoned from reading only.
- **Medium + `ultrathink` gave the same quality as `/effort high` with ~20% less work** on this bug. It applies to one prompt only, so it's a cheap way to go deep on a single hard step without raising effort for the whole session.
- Rule of thumb: low for triage and questions, high or `ultrathink` for a plan that will be merged.

## Caveats

- One run per setting. The differences between B and C are within normal run-to-run variation.
- TB-103 is a small bug; the gap between settings should grow on bugs that span more files.

## Plan-tier availability

- `/effort low`, `medium` and `high` all worked on my plan; medium is the default.
- `ultrathink` worked as a prompt keyword on this plan, with no setting change.
