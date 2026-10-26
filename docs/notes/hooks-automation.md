# Day 9 — Hooks and the automation ladder

## Hooks

| Hook | Event | Where | Purpose |
| --- | --- | --- | --- |
| format-on-edit | `PostToolUse` on `Write\|Edit` | `.claude/settings.json` (already there) | `ruff format` every edited `.py` file |
| block-forbidden-command | `PreToolUse` on `Bash` | `.claude/settings.json` + `.claude/hooks/block_git_add_all.py` | Block `git add -A`, `--all` and `.` |
| notify-on-finish | `Stop` | `~/.claude/settings.json` (personal) | macOS notification when Claude finishes |

The team hooks live in the repo; notify-on-finish is a personal preference, so it stays in user settings.

### block-forbidden-command

`CLAUDE.md` says "never `git add -A` / `git add .`". As text, that is a request; the hook makes it a
boundary. It reads the Bash command from the hook input and exits 2 with a reason when a `git add` would
stage the whole tree; Claude gets the reason and retries with explicit paths.

It went through four versions:

1. **Bash + regex**, 20 local test cases. Our own commit was blocked because the message mentioned
   `git add -A`, so we stripped quoted strings before matching.
2. **Review round 1** found three bypasses: `git add -Av`, `git add "."` (quote-stripping removed the
   argument too), and global options like `git -c k=v add -A`. Rewritten in Python with `shlex`, so
   arguments are un-quoted like the shell does. Tests committed.
3. **Review round 2** found that a parse error blocked every command with an unbalanced quote, such as a
   heredoc containing `it's`. "Fail closed" sounded safe, but on a hook that sees every Bash call, false
   positives hurt too. Parse errors now fall back to a regex on the raw text. Wrappers (`env`, `sudo`,
   `bash -c`) are looked through.
4. **Review round 3** found only deliberate evasions (`sudo -u root git add .`) and one claim that did not
   reproduce. We stopped and listed the gaps in the docstring and the PR.

The hook guards against habit, not evasion. Known gaps: `$(...)` in double quotes, `eval`, wrapper flags
that take a value, `bash -lc`. Known false positive: a heredoc body line that is itself `git add .`.

Run its tests with `.venv/bin/pytest .claude/hooks/test_block_git_add_all.py` (43 cases, outside
`make test`).

## Automation ladder

| Rung | What | Runs where | Approval |
| --- | --- | --- | --- |
| `/goal` | Keep working in a session until a condition is true | Your session | As usual |
| Desktop scheduled task | Prompt on a schedule, Local | Your machine, sandboxed | None while it runs |
| Cloud routine | Prompt on a schedule or other trigger | Anthropic's cloud, needs a GitHub repo | None (Auto mode) |
| GitHub Actions `@claude` | Review on PR open; answer `@claude` mentions | GitHub runners | None |

### `/goal`

Goal: the hook tests pass and the hook also blocks `sudo -u root git add .` and `nice -n 5 git add -A`.

- **Done in 49s, one turn, 3.1k tokens.** It reproduced first, found the cause, stayed in scope and did
  not commit.
- **It introduced a regression and called it a "known gap".** It added one set of value-taking flags
  shared by all wrappers. For `sudo`, `-s` and `-P` take no value, so `sudo -s git add .` and
  `sudo -P git add .`, blocked before the change, passed after it. We found this by running the hook
  before and after on the same commands.
- **`/goal` is only as good as its stop condition.** The condition said "tests pass and these two are
  blocked". No test covered `sudo -s`, so the goal could not see the break. Add "nothing that was blocked
  before is allowed now" to the condition, or a before/after check.
- The change was an exercise and was reverted.

### Desktop scheduled task: morning briefing

Weekdays at 8:30, Local, read-only prompt: sync state of both remotes, open GitHub PRs, tickets without a
fix branch.

- **It runs sandboxed.** `git fetch` failed on both remotes: the proxy refused SSH to GitLab, and GitHub
  SSH failed host key verification. A scheduled task does not have your terminal's network access.
- **It handled the failure well.** It used the GitHub MCP for live GitHub state, said the GitLab state was
  a stale local copy instead of claiming the remotes were in sync, stayed read-only, and sent a push
  notification about the failed fetch.
- **The prompt asked the wrong question.** "Tickets without a fix branch" returned "None" because local
  branches exist for all six; it says nothing about what is merged. Ask for "tickets with no fix merged
  into `feature/example_taskboard`".

### Cloud routines

From the `claude.ai/code/routines` form (not created):

- Triggers: a schedule (daily at a time), and more can be added.
- Runs in **Auto mode: "Claude will work and use connectors without pausing for approval."**
- Picking a repository makes it a Claude Code task; without one it is a chat task. Repositories are GitHub
  ones, so our GitLab remote can't be used directly.
- Connectors and notifications are set per routine.

Since nothing pauses for approval, the limits must come from what the routine can reach: connector
scopes, token permissions, a read-only prompt. Same lesson as Day 8's one-repo PAT.

### GitHub Actions `@claude`

`/install-github-app` failed with *"Failed to access repository :"*: it reads the repo from `origin`
(GitLab here) and needs the `gh` CLI, which isn't installed. Manual setup worked: install the Claude
GitHub App on this repo only, add `CLAUDE_CODE_OAUTH_TOKEN` (from `claude setup-token`) as a secret, and
add two workflows (PR #3):

- `claude.yml` answers `@claude` in issues, PR comments and reviews.
- `claude-code-review.yml` reviews PRs, with `CLAUDE.md` as the review rules.

The review workflow does not run on the PR that adds or changes it (it must match the default branch), so
the first real review was on the next PR (#4, the hook).

#### Exercise: evaluating its comments

| Round | Found | Accurate | Value |
| --- | --- | --- | --- |
| 1 | 3 bypasses + missing tests | 4 / 4 | High: commands Claude could type by habit |
| 2 | False positive on unbalanced quotes + wrapper bypasses | 2 / 2 | High: the false positive would have blocked heredocs all the time |
| 3 | Value-taking wrapper flags + heredoc false positive | 2 of 3 claims | Low: deliberate evasions; one claim did not reproduce |

- **It found what our own tests missed, twice.** We wrote tests for the cases we had thought of; the
  review looked for ways around the guard. Round 2 found a bug that our round-1 fix introduced.
- **It read `CLAUDE.md`** and said which rules did not apply (layers, tickets) instead of inventing
  problems. It never approved; posting as the token owner, it can't approve its own PR.
- **It said when it had not run something** ("I read this from the code and did not run it"). Its one
  wrong claim was a regex case it reasoned about without running.
- **Value drops each round.** Every push triggered a new review that found something new, while the
  findings got smaller and less accurate.
- **Noise:** each review event also started the `@claude` workflow, which skipped. Six skipped checks per
  round.

#### Fixing the noise (PR #5)

Eight threads across three rounds made it hard to see what was resolved. The workflow now reviews once
when the PR is opened (`@claude review again` for another round), keeps one sticky summary, and reads the
existing threads first so it does not repeat answered points.

The bot does not resolve threads. The author replies to each thread with the fixing commit or the
won't-fix reason, then resolves it. On PR #4 we replied through the GitHub MCP and resolved by hand.

## Workflow change

From Day 9, PRs are reviewed and merged on GitHub, where `@claude` runs. GitLab gets the result by a
fast-forward push of `feature/example_taskboard`, without an MR.

## Takeaways

- **A hook turns a rule into a boundary.** It is the place for "never" rules that can be checked
  mechanically. Keep the rest in `CLAUDE.md`.
- **A hook that sees every call must avoid false positives as much as bypasses.** Ours blocked our own
  commit, then our own tests, then a heredoc. Test with the commands Claude really runs.
- **Stop patching evasions.** Each layer of parsing added new edge cases; `/goal` showed how a fix for one
  can break another. Document the gaps.
- **The higher the rung, the less approval.** `/goal` runs in a session you watch; routines and Actions run
  with no one approving each step. Scope tokens and connectors to match.
- **Automated review is worth one or two rounds, not more.** After that, review on demand.
