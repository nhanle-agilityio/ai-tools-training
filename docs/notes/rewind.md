# Day 5 — Checkpoint / rewind experiment

## Setup

Ask Claude for a deliberately bad change, check `git diff --stat`, then rewind (`Esc Esc` → restore code and conversation) to the point before the prompt and check `git diff --stat` again.

## Results

| Run | Prompt | How Claude changed files | Code restored by rewind? |
| --- | --- | --- | --- |
| 1 | Rename `paginate` to `p`, remove docstrings (auto mode) | `sed -i` via Bash | ❌ Only the conversation rewound; files stayed changed |
| 2 | Same, with "use the Edit tool, no shell commands" | `Edit` tool | ✅ `git diff` clean after rewind |
| 3 | Delete `docs/tickets/TB-106.md` with `rm` | `rm` via Bash | ❌ File not restored; recovered with `git checkout --` |

Run 1 was found by reading the session transcript: there were no `Edit`/`Write` calls, only `Bash` with `sed -i`.

## Why

Checkpoints only track changes made through Claude's file-editing tools (`Edit` / `Write`). Anything done in the shell (`sed`, `rm`, `mv`, `git`, scripts, migrations) is outside the checkpoint system.

In **auto mode**, Claude may prefer shell commands for quick mechanical edits (bulk renames, deletions), so rewind silently stops covering them.

## Takeaways

1. Rewind is reliable only for `Edit` / `Write` changes. Don't assume it covers everything in auto mode.
2. Git is the real safety net: commit or stash before letting an agent make large changes, and check `git status` after a rewind instead of trusting it.
3. When rewind matters, say so in the prompt ("use the Edit tool, no shell commands to modify files") or work in normal / accept-edits mode.
4. "Restore conversation only" leaves the edits in place while Claude forgets making them. Only use it when you want to keep the code and retry the discussion.
