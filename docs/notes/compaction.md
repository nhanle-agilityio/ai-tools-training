# Day 5 — Compaction experiment

## Setup

One fresh Claude Code session: explain `is_overdue` → analyse TB-103 → plan a fix (plan mode, not approved). Then four check questions were asked before and after `/compact`.

## Token usage (`/context`)

| Category | Before | After | Change |
| --- | --- | --- | --- |
| Messages | 34.2k | 8.3k | −76% |
| System tools | 15.9k | 14.6k | ~ |
| Skills (52) | 8.5k | 8.5k | — |
| Memory files (3) | 1.2k | 1.2k | — |
| **Total** | **63.5k** | **36.3k** | **−43%** |

## What survived

| Question | After compact |
| --- | --- |
| Q1: TB-103 root cause file:line | ✅ Identical (`services.py:71-72`), verified against the code |
| Q2: timezone decision and scope | 🟡 Decision and out-of-scope items kept; plan file path and "plan rejected" status dropped |
| Q3: files the plan would change | ✅ Same 3 files, more detail |
| Q4: commit conventions | ✅ All 9 rules, reloaded from `CLAUDE.md` |

## Caveats

- **Session was short** (34k tokens of messages, ~3% of the window), so the summary had room to keep almost everything.
- **The plan was saved to a file**, so plan details didn't depend on chat history.
- **Claude may have re-read the code** to answer Q1/Q3 after compacting. Check for tool calls before calling it "memory".

## Takeaways

1. Compaction is cheap and keeps decisions and conclusions; it drops secondary details and transient state.
2. Anything that must survive belongs outside the chat: `CLAUDE.md`, memory, or a file (plan, ticket).
3. Fixed per-session cost is ~28k tokens. Skills (8.5k) cost 7× more than all memory files (1.2k), so pruning unused skills saves more than trimming `CLAUDE.md`.

## Next time

Add facts that exist **only in the chat** (e.g. "reviewer is Lan, deadline Thursday 15:00") and long tool output (`make test -v`), then check them after `/compact`.
