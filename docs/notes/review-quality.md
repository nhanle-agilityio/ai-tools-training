# Day 10 — Review and quality

Three questions: how good is local `/code-review`, when is ultrareview worth it, and what do the security
tools catch. To measure instead of guess, we reviewed one real branch and one branch with known, seeded
bugs.

## CI first

Until today a green PR only meant the Claude review job finished. PR #8 adds `ci.yml`: app tests, the
hook tests and ruff on every PR. "PR green" now means tests and lint pass.

## `/code-review` on a real branch (PR #9)

The branch closed the wrapper gaps in the `git add` hook: one test commit and one fix commit using
per-wrapper option tables.

| # | Finding | Real? |
| --- | --- | --- |
| 1 | BSD `xargs -J` slips through (macOS) | Yes; `man xargs` lists `-J`, `-R`, `-S` |
| 2 | `sudo -R` slips through | Yes; in `sudo -h` |
| 3 | `bash -c -- '...'` slips through | Yes |
| 4 | `env -S 'git add .'` slips through | Yes; our table treated the command string as an option value |
| 5 | `bash script.sh -c '...'` is a false positive of the hook | Yes |
| 6 | Option tables are fragile; look for `git`/shell tokens after the wrapper instead | Yes, and a better design |
| 7 | Use `frozenset` | Style nit |

7 of 7 useful, no false positives, 1m19s. The agent ran the hook to confirm each bypass before
reporting. It could not run pytest (the system `python3` has none) and said so.

We took the redesign in #6: the per-wrapper tables are gone, and the hook checks every later `git` or
shell token. It is shorter and doesn't depend on GNU vs BSD options. Fixed as a second test/fix commit
pair. On the PR, CI was green, and `@claude` found two minor, non-blocking points, both real (`bash
--rcfile f -c ...` slips through; `sudo echo git add .` is blocked). Merged.

## Comparing signal on a seeded branch

`review/seeded-bugs` added two small features: `GET /tasks?tag=` and `POST /projects/<id>/complete`.
All 57 tests passed and ruff was clean, but seven bugs were planted. The answer key stayed outside the
repo, so reviewers could not see it.

| ID | Seeded bug |
| --- | --- |
| S1 | SQL injection: `tag` formatted into SQL with an f-string |
| S2 | Tag filter not normalized; tags are stored lowercase and stripped |
| S3 | SQL in `routes.py`, skipping services and repository (CLAUDE.md layer rule) |
| S4 | No `db.commit()`: the bulk update is rolled back, yet the response says `completed: 2` |
| S5 | Fake-green test: checks only the response, never re-reads the tasks |
| S6 | Missing project returns 200 instead of 404 |
| S7 | `updated_at` not bumped |

S1, S2, S4 and S6 were proven against the running app before any review. `?tag=x' OR '1'='1` returned
another project's task.

| | `/code-review` (run 1) | `/code-review` (run 2) | Ultrareview |
| --- | --- | --- | --- |
| S1 to S4, S6, S7 | all | all | all |
| S5 fake-green test | partly (no re-read, no 404 case) | yes, including uppercase tags | **missed** |
| **Recall** | 7 / 7 | 7 / 7 | 6 / 7 |
| Real issues outside the key | `?tag=%20` returns nothing; commit convention | commit convention | 5 real bugs in existing code |
| False positives | 0 | 0 | 0 among those checked |
| Time | 31s | 32s | about 4 min, in the cloud |
| Scope | 1 commit, 5 files | 1 commit, 5 files | 43 files, branch vs `main` |

- **On a small, focused diff, `/code-review` was enough.** It caught everything, including the
  fake-green test, in about 30 seconds. Two runs gave the same findings.
- **Ultrareview missed the test-quality bug.** S5 breaks nothing at runtime, and runtime behaviour is
  what it hunted for.
- **Ultrareview reviewed the wrong scope, and that is where it paid off.** With no argument it compared
  the branch with `main`, which only has the initial commit, so it reviewed the whole repository. It
  found five real bugs in existing code that no one had flagged (below). Use it for a deep pass over a
  large or risky area, not for a five-file diff.
- **None of the reviewers ran the code.** All said so. Findings are well-argued claims until someone
  reproduces them; we did, for every finding we kept.

### Real bugs found in existing code (proposed tickets)

Outside every ticket, so not fixed (CLAUDE.md: mention, don't fix). Verified with the test client:

| Proposed ticket | Bug | Result |
| --- | --- | --- |
| A | `PATCH /tasks/<id>` with `"description": null` or a list | 500 (`IntegrityError` / `ProgrammingError`) instead of 400 |
| B | `"project_id": true` accepted as `1` (`bool` is an `int`) | 201, task created in project 1 |
| C | Integers too large for SQLite in `?page=` or a path id | 500 (`OverflowError`) instead of 400/404 |
| D | Two `POST /projects` with the same name at once | 500 instead of 400 (race on the unique name); not reproduced |
| E | `GET /tasks/overdue` has no limit | Unbounded response on large data; design point, not reproduced |

## Security tools

| Tool | When it runs | Result on S1 (SQL injection) |
| --- | --- | --- |
| `/security-review` | On demand, one pass over the branch | Caught: High, confidence 9/10, two exploit paths, 0 false positives |
| `security-guidance` plugin | Automatically while Claude edits | Missed (see below) |
| `claude-security` plugin | On demand, multi-agent deep scan with patches | Read the docs, not run |

### `/security-review`

It reported only S1 and correctly ignored S2 to S7, which are not security bugs. It traced the input
from route to service to repository, showed a filter bypass and blind data extraction through
`pagination.total`, and noted that SQLite rejects stacked statements and that a `--` payload returns 500.
A second agent verified the finding before the report.

That verifier was stopped by the Opus 5.5 safeguards (`[cyber]`), a false flag on legitimate security
review. The report still completed because the verdict arrived first. If it happens again, switch with
`/model sonnet` before scanning.

### `security-guidance` plugin

It is built on hooks: a pattern match on each Edit/Write, a model review of the turn's diff when Claude
stops, and a deeper review on `git commit` or `git push`. It never blocks.

1. **A plainly dangerous request** (let the client pass a raw `ORDER BY`): Claude refused at the design
   step and proposed an allow-list of columns. No file changed, so the plugin had nothing to review.
2. **A refactor carrying the existing vulnerability** (move the tag filter into `_tag_filter`, "keep the
   behaviour exactly the same", and add a comment to a workflow file):
   - The end-of-turn review read both changed files and reported "no vulnerabilities found" (3.7s,
     ~$0.08 on Opus). **False negative.** The f-string was moved, not written, and the diff doesn't show
     that `tag` comes from the query string.
   - The workflow edit should trigger the per-edit pattern warning, but Claude used `sed` through Bash,
     and that layer only watches Edit and Write. **No warning.**
   - Claude itself flagged the injection, kept to the "pure refactor" request, and proposed a separate
     ticket with a failing test first.

The plugin is one layer, as its docs say ("the review model can miss issues"). Here the model was the
stronger layer both times.

### `claude-security` plugin

From the docs: `/plugin install claude-security@claude-plugins-official`, then `/claude-security`. A
multi-agent scan that maps the architecture, builds a threat model, hunts, and has independent agents
verify each finding. It scans a whole repository or a diff at low, medium or high effort and writes
Markdown, JSONL and SARIF. It can draft patches but never applies them. A separate managed product with
the same name is Enterprise-only.

## For the retro

**False positives from reviewers: none that survived checking.** Every finding we kept reproduced. Two
were nits (commit convention, `frozenset`).

**Inaccurate claims and misses:**

- Ultrareview missed the fake-green test (S5).
- `security-guidance` missed S1 in a refactor, and its per-edit check was sidestepped by `sed`.
- Day 9's third `@claude` round had one claim that did not reproduce (regex false positive).

**False positives from our own tooling** (the hook, not a reviewer):

- `bash script.sh -c 'git add .'` was blocked (fixed in PR #9).
- `sudo echo git add .` (unquoted) is blocked by the new design; accepted.

**Process notes:**

- `/ultrareview` with no argument diffs against `main`. In this repo that is the initial commit; pass the
  real base or a PR number when you want a diff review.
- Reviewers read code; they don't run it. Reproduce before fixing, and before believing a "no issues".
- Review tools are layered: in-session plugin, `/code-review` and `/security-review` on demand,
  ultrareview or `claude-security` for deep scans, `@claude` and CI on the PR. Each missed something
  another caught.

## When to use which

| Situation | Tool |
| --- | --- |
| Before every PR, small diff | `/code-review` (seconds, free) |
| Diff touches input handling, SQL, auth | add `/security-review` |
| Large or risky area, or code no one has reviewed in a while | ultrareview or `claude-security` (minutes, paid) |
| On the PR | CI for tests, `@claude` for one review |
