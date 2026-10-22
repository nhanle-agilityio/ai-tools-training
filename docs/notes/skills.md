# Day 7 — Team skill and slash command

What we shipped in `.claude/`: the `ticket-fix` skill and the `/mr-description` command (MR !12).

## Which tool for which job

| Tool | Holds | Runs when |
| --- | --- | --- |
| `CLAUDE.md` | Rules that always apply (layers, conventions, "Never") | Every session, always in context |
| Skill (`.claude/skills/<name>/SKILL.md`) | A procedure for one kind of task | Claude loads it when the request matches its `description` |
| Slash command (`.claude/commands/<name>.md`) | A task you start on purpose, with arguments | Only when you type `/<name>` |

- The skill points to `CLAUDE.md` for rules instead of copying them; it only adds the order of work,
  checkpoints and the MR template.
- `/mr-description` is a command, not a skill: it takes an argument, and it should run only when asked
  (`disable-model-invocation: true`).

## Skill: testing the trigger

Each prompt in a fresh session (skills load at start-up):

| Prompt | Expected | Result |
| --- | --- | --- |
| "Plan a fix for TB-102. Don't change any files yet." | trigger | triggered |
| "lên kế hoạch sửa ticket TB-104, chưa sửa file nào" | trigger | not triggered |
| "Explain how search works in services.py." | no trigger | not triggered |

- The `description` is the whole trigger. Vietnamese keywords in it did not make the Vietnamese prompt
  trigger, so we removed them and kept the description in English, like the rest of the repo.
- The negative case ("do not use it for questions that only explain code") matters as much as the
  positive one.

## Command: two iterations

Tested on `fix/TB-103-due-today-not-overdue`, which has a test commit and a fix commit.

1. **First version.** The description was accurate and every acceptance criterion was mapped to a test.
   It also noticed the commit scope `fix(tasks): … (TB-103)` breaks the `CLAUDE.md` convention. But:
   - "Out of scope" said "None". The rule said "problems visible in the diff", and the latent `now`
     mismatch in `_serialize_tasks` is not in the one-line diff. The rule was too narrow, not the model.
   - The note about commits appeared below the block in one run and was missing in the other.
2. **Second version.** A mandatory "Checks" list (commit order, commit scope) printed before the block,
   and "Out of scope" now reads the changed functions and their callers. Both fresh runs passed: both
   flagged the scope and found the `now` mismatch; the run without an argument took `TB-103` from the
   branch name.

We did not put the `now` mismatch in the command as an example, so the second run had to find it alone.

## Lessons

- Test a skill or command in a **fresh session**. Re-running in the same session reuses the earlier
  answer; our first "no argument" test was identical word for word and proved nothing.
- `!`-backtick context (`git diff`, `git log`) puts the facts in the prompt before the model starts, so
  the output is grounded in the real diff.
- Phrase checks as a fixed list that always prints. "Say so if …" gets skipped when nothing seems wrong.
- Scope rules like "only what the diff shows" are good for describing the change, and bad for finding
  what the change missed.
