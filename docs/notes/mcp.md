# Day 8 — MCP servers: GitHub and Playwright

## Setup

| Server | How | Tools | Scope |
| --- | --- | --- | --- |
| GitHub (`https://api.githubcopilot.com/mcp/`) | claude.ai custom connector, PAT in a request header | 47 | Synced into Claude Code as `claude.ai github` |
| Playwright (`npx -y @playwright/mcp@latest`) | `claude mcp add playwright -- ...` | 25 | `local` (this repo, this user; nothing written to the repo) |

The repo lives on GitLab. For the exercise it was also pushed to GitHub
(`nhanle-agilityio/ai-tools-training`, branches `main` and `feature/example_taskboard`). GitLab stays the
source of truth; GitHub is only updated by a manual push.

### Getting the GitHub server connected

1. `claude mcp add --transport http github https://api.githubcopilot.com/mcp/` failed:
   *"Incompatible auth server: does not support dynamic client registration"*. Claude Code's OAuth flow
   registers a client on the fly, and GitHub's OAuth server does not support that.
2. The claude.ai **GitHub integration** is not an MCP server. It adds repo files to chats and projects,
   has no PR or issue tools, and does not show up in Claude Code.
3. A claude.ai custom connector with **"Use your own OAuth client"** needs a GitHub OAuth App. It worked,
   but the consent screen asked for all public and private repos, gists and org read access, and it
   could not be limited per organization: one org with no OAuth restrictions was granted automatically.
   Too broad for an exercise; cancelled.
4. **What worked:** a claude.ai custom connector with *No sign-in* and the header
   `Authorization: Bearer <fine-grained PAT>`. The PAT is limited to this one repo, with Contents, Pull
   requests and Issues set to read and write, and it expires in 30 days. Connectors added on claude.ai
   appear in Claude Code after a session restart.

Adding the same PAT header with `claude mcp add ... -H "Authorization: Bearer ..."` also works, and
keeps the token in `~/.claude.json` instead of claude.ai.

## Exercise: GitHub MCP end to end

One prompt, in a fresh session, using only the GitHub MCP tools, asking before each write:

1. Create issue #1.
2. Create branch `docs/mcp-exercise`, commit a placeholder file, open PR #2 that closes #1.
3. List open PRs; read the PR's files, commits and mergeable state.
4. Post a review on the PR.
5. Read the PR back and return the URLs.

| Check | Result |
| --- | --- |
| Asked before every write | Yes, three confirmations (step 2's three writes as one) |
| Used only MCP | Yes, 12 GitHub calls, no `git` or Bash |
| Followed `CLAUDE.md` | No `Co-Authored-By`; PR body says `Closes #1` |
| Read real state | It noticed the local git context said `main` while GitHub's default is `feature/example_taskboard` |

- **It knew a GitHub rule we didn't mention:** you can't approve your own PR, so it posted a `COMMENT`
  review and said why before posting.
- **Everything is done as you.** The token is yours, so the issue, the commit and the "review" all show
  under your account. A Claude review on your own PR looks like a self-review.
- The branch and commit exist only on GitHub until you fetch.

## Bonus: Playwright against the running app

`make seed && make run`, then one prompt: read `/tasks` and `/tasks/overdue` through the browser and check
TB-103's fix in the live app. No data changes.

- **The fix holds on live data.** All 28 tasks have an `is_overdue` flag that matches their due date.
  The three tasks due today are not overdue; `/tasks/overdue` returns only the two past-due open tasks;
  past-due `done` tasks and tasks without a due date are left out.
- It paged through `/tasks` (10 per page) on its own to see all 28 tasks.
- The one console error was a missing `/favicon.ico` (404), not an app bug.
- It reported where it did not follow the prompt: it used Bash once to read the ticket, and Playwright
  can only save screenshots inside the repo, not in the scratchpad.
- **Playwright writes to `.playwright-mcp/`** in the repo (screenshots, page snapshots, console logs).
  It is now in `.gitignore`.

TaskBoard is a JSON API, so this used Playwright as a JSON reader. It is the wrong tool for that; `curl`
or the test client does the same with less. It pays off on apps with a UI: clicking through a flow and
checking what the user actually sees.

## Context cost

MCP tools are loaded on demand: at start Claude sees only tool names, and a tool's full schema is added
when it is first used.

| Moment | MCP tools | MCP server instructions |
| --- | --- | --- |
| Fresh session, 123 tools (GitHub, Playwright, Gmail, Docs) | 1.2k | 1.3k |
| After the GitHub exercise (~10 tools used) | 6.2k | 1.3k |
| Playwright session, 77 tools | 1.1k | 0.7k |

For comparison, built-in system tools take 15.1k and skills 8.6k. Adding servers costs almost nothing
until their tools are used, about 0.5k per tool used.

## Takeaways

- **MCP replaces guesses with state.** Claude read the real default branch and PR status instead of
  inferring them from the local clone. That is what we lack on GitLab, where `glab` login is blocked.
- **Auth is the hard part, not the tools.** It took four attempts to connect GitHub; the exercise itself
  took one prompt.
- **Scope the token, not the prompt.** A one-repo PAT limits what any prompt can do. "Ask before each
  write" worked here, but it is a request, not a permission boundary.
- **Pick the server for the job.** GitHub MCP for PRs and issues; Playwright for UIs. For a JSON API,
  plain HTTP is simpler.

## Cleanup

- PR #2 and issue #1 are exercise artifacts on GitHub; close them, don't merge.
- Revoke the PAT when training ends (it expires on its own after 30 days).
