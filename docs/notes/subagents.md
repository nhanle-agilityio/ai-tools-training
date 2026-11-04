# Day 6 follow-up — Subagents

## What a subagent is

- A separate Claude with its own context window. It gets a prompt, does the work with its own tools and
  returns one final report. The main session sees only that report, not the files it read.
- Built-in types: `Explore` (read-only search), `Plan` (read-only design), `general-purpose` (all tools).
  Project agents live in `.claude/agents/<name>.md`; this repo uses `code-reviewer` (read-only review).
- The model can be set per call. Our rule: Opus plans and reviews, Sonnet implements, Haiku searches and
  runs tests.

## Run 1: TB-103 (Day 6)

The plan for TB-103 was prepared in the `tb-103` worktree with `Explore` (find every caller of
`is_overdue`) and `code-reviewer` (review the plan against the code). The fix was then committed as a test
and a fix commit (`7f07507`, `9e1e146`) and merged. No transcript of the subagent calls was kept, which is
why this note was written later.

## Run 2: two investigations in parallel (Day 15, 2026-11-04)

While the main session created gap issue #73 and drafted release notes, two Sonnet subagents ran in the
background:

| Subagent | Task | Tool calls | Tokens | Time | Result |
| --- | --- | --- | --- | --- | --- |
| QA coverage review | Check every `must` row of two specs against the tests, run the suite | 12 | ~79k | 1m41s | 93 must rows: 85 covered, 3 weak, 5 manual; 323 tests pass. The 3 weak rows became issue #74 |
| Checkpoint audit | Read the session transcripts of Day 3, 6 and 11 and match each item to evidence | 26 | ~106k | 2m34s | `checklist-audit.md` (this PR) |

The main session's context grew only by the two reports, about 2k tokens, instead of the ~185k the
subagents read.

## When to use one

| Use a subagent | Stay in the main session |
| --- | --- |
| A bounded question with a clear answer ("which rows lack a test?") | Work that needs the conversation so far |
| Reading a lot to return a little (transcripts, a large diff) | Small lookups (one file, one grep) |
| Independent tasks that can run in parallel | Edits that must be reviewed as one change |

## Lessons

- **Write the prompt as a brief.** The subagent starts cold: give it paths, the exact output format and
  what not to do ("read-only, do not commit").
- **Ask for evidence.** Both prompts asked for file:line, commit or session timestamp, so the reports could
  be checked. One claim (a date in the audit) was flagged by the subagent itself as weakly sourced and was
  corrected before commit.
- **Verify before acting.** A report is model output: the weak-assert finding was checked against the test
  code before the issue was created.
