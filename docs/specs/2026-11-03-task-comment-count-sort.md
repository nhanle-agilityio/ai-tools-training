# Task comment counts: sort by comments and lint/format make targets

- **Status:** draft
- **Date:** 2026-11-03
- **Slug:** `task-comment-count-sort`

## Problem

Clients can see how many comments a task has (`comment_count`, added by the
[task comments spec](2026-10-29-task-comments.md)), but they cannot ask `GET /tasks` for the most
discussed tasks first. To find the busiest tasks they must fetch every page and sort on their side.
Separately, developers run lint and format checks by typing the raw `ruff` commands; the Makefile has
`setup`, `test`, `seed`, `run` and `clean` but no `lint` or `fmt` target.

Current behaviour: every task object returned by the API has `comment_count`, the number of its comments
whose `deleted_at` is null. Comments are flat (no replies or threads). `GET /tasks` accepts
`sort` = `created_at` (default) | `due_date` | `priority`; any other value returns
`400 {"error": "sort must be one of created_at, due_date, priority"}`.

## Goals

- `GET /tasks?sort=comments` returns tasks with the most live comments first.
- `make lint` runs the same lint and format checks as CI; `make fmt` fixes what can be fixed.
- The README documents the new sort value and the new make targets.

## Non-goals

- Changing `comment_count`. It already counts only the task's own live comments ("direct" comments);
  there are no threaded replies to exclude. No code task is created for it.
- An ascending comment sort (`sort=-comments` or similar).
- Documenting the existing comment endpoints and `comment_count` in the README. Missing today, but outside
  this idea; noted as a follow-up.
- Changing CI to call the make targets.

## Decisions

| Question | Decision | Why |
| --- | --- | --- |
| Does `comment_count` need work? | No. "Direct comments" = live comments on the task itself, which is the current behaviour. No task. | Comments are flat; the field and its tests already ship |
| Count used by `sort=comments` | Same as `comment_count`: comments with `deleted_at` null. A task with no live comments counts 0 and sorts last | Order must agree with the number the client sees |
| Tie-break | `comment_count DESC, t.created_at DESC, t.id DESC` | Within equal counts, same order as the default sort; `id` makes pages stable |
| Combination with filters | Works with `project_id`, `status`, `tag`, `q`, `page`, `per_page`; `total` is unchanged, only the order changes | No special rules |
| Invalid sort error | Existing message, now listing the new value: `sort must be one of created_at, due_date, priority, comments` | The message is built from `SORT_CLAUSES` |
| `make lint` | `$(BIN)/ruff check . && $(BIN)/ruff format --check .`; check only, never writes | Same commands as CI |
| `make fmt` | `$(BIN)/ruff check --fix --exit-zero . && $(BIN)/ruff format . && $(BIN)/ruff check .`; writes files; no unsafe fixes; exits non-zero when an unfixable lint error remains; fixable fixes are still applied | Fix first, then format, so a removed import cannot leave unformatted output; formatting always runs (verified with ruff 0.17.1) |
| `.PHONY` | Both targets added | Makefile convention |
| README scope | Only the new `sort` value and the two make targets | Keep scope to this idea |
| Testing the tie-break | One test may write `created_at` directly in the database to separate `created_at` from `id`; all other tests go through HTTP | Through HTTP both always rise together (precedent: project-stats T2.29) |
| Query count for `sort=comments` | The number of `SELECT`s touching `task_comments` does not depend on the number of tasks (no N+1) | Same concern as the batched `comment_count` |
| Query-count test setup | Both runs use the default `per_page` (10); count every `SELECT` whose text contains `task_comments` | Settled during QA |
| `make lint` output | `&&` stops after the first failing check, same as CI | Matches CI |
| Existing behaviour kept | Empty, unknown or differently cased `sort` values return 400; a repeated `sort` uses the first value; a page past the last returns `400 page N is out of range (1-M)`; per_page cap unchanged | No change to request parsing |
| Task split | T1 sort (with its README line), T2 Makefile (with its README lines); independent | Small, separately reviewable |

## Design

### API contracts

**`GET /tasks?sort=comments`** (changed: new `sort` value)

Response `200`: the usual `{"items": [...], "pagination": {...}}`. Items are ordered by the number of
live comments of each task, descending; ties by `created_at` descending, then `id` descending. Each item's
`comment_count` equals the count used for ordering, so `comment_count` values are non-increasing across
the full result set (across pages too).

| Case | Status | Body |
| --- | --- | --- |
| `sort=comments` with any combination of existing filters | 200 | filtered tasks in the order above |
| `sort=title` (or any unknown value) | 400 | `{"error": "sort must be one of created_at, due_date, priority, comments"}` |

Only live tasks are listed (unchanged). A soft-deleted comment does not count.

### Data model

No change. The order uses a count of `task_comments` rows with `deleted_at IS NULL` per task, computed in
the list query (for example a correlated subquery in the `ORDER BY`). The existing index
`idx_task_comments_task` covers the lookup.

### Other areas

Makefile:

```make
.PHONY: setup test run seed clean lint fmt

lint:
	$(BIN)/ruff check . && $(BIN)/ruff format --check .

fmt:
	$(BIN)/ruff check --fix --exit-zero . && $(BIN)/ruff format . && $(BIN)/ruff check .
```

README: add `comments` to the `sort` values in the API table; add `make lint` and `make fmt` to the
Quick start block.

## Risks and unknowns

- `tests/test_comments.py::test_list_tasks_loads_comment_counts_in_one_query` asserts that a default
  `GET /tasks` runs exactly one `SELECT` touching `task_comments`. The comment-count expression must only
  be in the `comments` sort clause, not in the shared list query, or that test breaks.
- `created_at` has one-second resolution, so tasks created in one test often share it; the `id DESC`
  tie-break keeps the order deterministic.
- Both tasks edit `README.md` in different sections; a trivial merge conflict is possible.
- Follow-up (not in this spec): the README does not document the comment endpoints or `comment_count`.

## Tasks

| Id | Title | Type | Area | Depends on | Size | Needs e2e | Risk | Risk reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T1 | Add sort=comments to GET /tasks | feat | backend | - | S | no | low | Additive query value; read-only; no schema change |
| T2 | Add make lint and make fmt targets | chore | infra | - | S | no | low | Developer tooling only; no app or CI change |

### T1: Add sort=comments to GET /tasks

- **Type:** feat
- **Area:** backend
- **Depends on:** none
- **Size:** S
- **Needs e2e:** no
- **Risk:** low - additive query value; read-only; no schema change
- **Hotspot files:** `taskboard/repository.py`, `README.md`

**Acceptance criteria**

- [ ] Tasks A (0 comments), B (2 comments), C (1 comment): `GET /tasks?sort=comments` returns `200` with items in order B, C, A and `comment_count` values `[2, 1, 0]`.
- [ ] A soft-deleted comment does not count: B has 3 comments with 2 deleted, C has 2 live comments: C comes before B.
- [ ] Ties: tasks with the same number of live comments are ordered by `created_at` descending, then `id` descending (with equal `created_at`, the higher `id` comes first). To separate the two keys, one test may set `created_at` directly in the database: a lower-`id` task with a later `created_at` comes first.
- [ ] Combined with filters: `GET /tasks?sort=comments&project_id=<p>&status=todo&tag=bug&q=x` returns only the matching tasks, in comment order; `pagination.total` equals the filtered count.
- [ ] Pagination: with 5 tasks of distinct comment counts and `per_page=2`, pages 1-3 together list every task exactly once, and `comment_count` is non-increasing across the pages.
- [ ] `GET /tasks?sort=title` returns `400 {"error": "sort must be one of created_at, due_date, priority, comments"}`.
- [ ] Each item's `comment_count` under `sort=comments` equals `comment_count` from `GET /tasks/<id>` for the same task.
- [ ] Soft-deleted tasks are not listed under `sort=comments`, whatever their comment count.
- [ ] Existing sorts are unchanged (existing sort tests pass), and a default `GET /tasks` still runs exactly one `SELECT` touching `task_comments`.
- [ ] With `sort=comments`, the number of `SELECT`s touching `task_comments` is the same for 3 tasks as for 10 tasks.
- [ ] README API table lists `comments` among the `sort` values.

**Scope** (files and areas this task may touch)

- `taskboard/repository.py` (`SORT_CLAUSES`), `tests/test_tasks.py`, `README.md` (API table row for `GET /tasks`)

**Test plan**

Test cases: T1.1-T1.20 (see Test matrix). HTTP tests in `tests/test_tasks.py` with `client` / `project` / `make_task`; comments via `POST /tasks/<id>/comments`, deleted via `DELETE /comments/<id>`; T1.7 is the only direct database write. Tests are named `test_t1_<n>_<description>`.

### T2: Add make lint and make fmt targets

- **Type:** chore
- **Area:** infra
- **Depends on:** none
- **Size:** S
- **Needs e2e:** no
- **Risk:** low - developer tooling only; no app or CI change
- **Hotspot files:** `Makefile`, `README.md`

**Acceptance criteria**

- [ ] On the base branch with `git status` empty (it passes ruff today), `make lint` runs `.venv/bin/ruff check .` and `.venv/bin/ruff format --check .` and exits 0.
- [ ] With a lint error or an unformatted file present, `make lint` exits non-zero and `git status` / file contents are unchanged (`.ruff_cache/` carries its own `.gitignore`).
- [ ] With a file `import os\nx=1\n` (unused import at the top, unformatted), `make fmt` exits 0 and leaves `x = 1\n`; a following `make lint` exits 0.
- [ ] With an unfixable lint error (F821 undefined name) in an unformatted file, `make fmt` still formats the file and exits non-zero.
- [ ] `lint` and `fmt` are listed in `.PHONY`.
- [ ] README Quick start lists `make lint` and `make fmt`, each with an inline `# ...` comment like the existing lines.

**Scope** (files and areas this task may touch)

- `Makefile`, `README.md` (Quick start block)

**Test plan**

Test cases: T2.1-T2.9 (see Test matrix). Manual shell checks recorded in the PR description with `# T2.<n>` comments (no pytest for Makefile targets); scratch files are removed afterwards and never committed.

## Test matrix

| Id | Task | Criterion | Case | Given / When / Then | Level | Priority |
| --- | --- | --- | --- | --- | --- | --- |
| T1.1 | T1 | Order B, C, A with counts [2,1,0] | happy | Given A (0 comments), B (2 via `POST /tasks/<id>/comments`), C (1), created in order A, B, C. When `GET /tasks?sort=comments`. Then 200, item ids `[B, C, A]`, `comment_count` `[2, 1, 0]` | http | must |
| T1.2 | T1 | Order B, C, A with counts [2,1,0] | edge | Given only tasks with 0 comments (X, then Y). When `GET /tasks?sort=comments`. Then 200, order `[Y, X]` (same as the default sort), all `comment_count` 0 | http | should |
| T1.3 | T1 | Order B, C, A with counts [2,1,0] | boundary | Given no tasks. When `GET /tasks?sort=comments`. Then 200, `items == []`, `pagination.total == 0` | http | should |
| T1.4 | T1 | Soft-deleted comment does not count | happy | Given C with 2 live comments, then B with 3 comments, 2 deleted via `DELETE /comments/<id>`. When `GET /tasks?sort=comments`. Then 200, C before B, counts `[2, 1]` | http | must |
| T1.5 | T1 | Soft-deleted comment does not count | edge | Given E (0 comments), then D with 2 comments, both deleted. When `GET /tasks?sort=comments`. Then D has `comment_count` 0, ties with E and comes first (higher `id`) | http | should |
| T1.6 | T1 | Ties by created_at DESC, then id DESC | happy | Given P, Q, R each with 1 comment, created in that order through HTTP (same-second `created_at`). When `GET /tasks?sort=comments`. Then order `[R, Q, P]` | http | must |
| T1.7 | T1 | Ties by created_at DESC, then id DESC | edge | Given P (lower id) and Q (higher id), each with 1 comment; set P.`created_at` = `2099-01-01T00:00:00` directly in the DB (the only direct DB write). When `GET /tasks?sort=comments`. Then P before Q | integration | must |
| T1.8 | T1 | Combined with filters | happy | Given a second project p2. Matching M1 (p1, todo, tag bug, title "fix x", 1 comment) and M2 (same, 3 comments); non-matching tasks with 5 comments each: in p2; `status=done`; no `bug` tag; title without "x". When `GET /tasks?sort=comments&project_id=<p1>&status=todo&tag=bug&q=x`. Then 200, ids `[M2, M1]`, `pagination.total == 2` | http | must |
| T1.9 | T1 | Combined with filters | edge | Given the same data. When `sort=comments&status=todo`. Then `total` equals `total` of `GET /tasks?status=todo`, same id set, in comment order | http | should |
| T1.10 | T1 | Pagination across pages | happy | Given 5 tasks with 0, 1, 2, 3, 4 comments. When `GET /tasks?sort=comments&per_page=2&page=1..3`. Then pages have 2, 2, 1 items, union is all 5 ids without duplicates, concatenated `comment_count` `[4,3,2,1,0]`, `total == 5` on every page | http | must |
| T1.11 | T1 | Pagination across pages | boundary | Given the same 5 tasks. When `GET /tasks?sort=comments&per_page=2&page=4`. Then `400 {"error": "page 4 is out of range (1-3)"}` | http | should |
| T1.12 | T1 | Unknown sort returns 400 with new message | error | When `GET /tasks?sort=title`. Then `400 {"error": "sort must be one of created_at, due_date, priority, comments"}` | http | must |
| T1.13 | T1 | Unknown sort returns 400 with new message | edge | When `sort=Comments`, `sort=` (empty), `sort=-comments`, `sort=comment`. Then each returns 400 with the same message | http | should |
| T1.14 | T1 | Unknown sort returns 400 with new message | edge | When `sort=comments&sort=title`. Then 200 in comment order. When `sort=title&sort=comments`. Then 400 | http | should |
| T1.15 | T1 | List comment_count equals GET /tasks/<id> | happy | Given 3 tasks with 0, 2 (plus 1 deleted) and 1 comments. When `GET /tasks?sort=comments` and `GET /tasks/<id>` for each item. Then each item's `comment_count` equals the detail value | http | must |
| T1.16 | T1 | Soft-deleted tasks not listed | happy | Given T with 5 comments, then `DELETE /tasks/<T>`, and U with 1 comment. When `GET /tasks?sort=comments`. Then T absent, U first, `total == 1` | http | must |
| T1.17 | T1 | Existing sorts unchanged; default = one task_comments SELECT | happy | When the existing suite runs (`tests/test_tasks.py` sort tests, `tests/test_comments.py::test_list_tasks_loads_comment_counts_in_one_query`). Then all pass unchanged | http | must |
| T1.18 | T1 | Existing sorts unchanged; default = one task_comments SELECT | edge | Given 3 tasks with comments and a SQL trace. When `GET /tasks`, `?sort=due_date`, `?sort=priority`. Then each runs exactly 1 `SELECT` touching `task_comments` | http | should |
| T1.19 | T1 | No N+1 under sort=comments | happy | Given a SQL trace and default `per_page`. When `GET /tasks?sort=comments` with 3 tasks (1 comment each), then on a fresh DB with 10 tasks (1 comment each). Then the number of `SELECT`s containing `task_comments` is equal in both runs | http | must |
| T1.20 | T1 | README lists `comments` sort value | happy | When reading the README API row for `GET /tasks`. Then its `sort` values include `comments` (`` `priority` \| `comments` ``) | integration | must |
| T2.1 | T2 | make lint passes on clean base | happy | Given a clean tree on the base branch. When `make lint`. Then the echoed commands are `.venv/bin/ruff check . && .venv/bin/ruff format --check .`, exit 0 | integration | must |
| T2.2 | T2 | make lint fails without writing | error | Given scratch `scratch_bad.py` = `import os\n` (F401). When `make lint`. Then exit ≠ 0, file checksum unchanged, `git status --porcelain` shows only the scratch file | integration | must |
| T2.3 | T2 | make lint fails without writing | error | Given scratch `scratch_fmt.py` = `x=1\n` (lint-clean, unformatted). When `make lint`. Then exit ≠ 0, file unchanged | integration | must |
| T2.4 | T2 | make fmt fixes; lint then passes | happy | Given scratch `scratch_fix.py` = `import os\nx=1\n`. When `make fmt`, then `make lint`. Then fmt exits 0, file is `x = 1\n`, lint exits 0 | integration | must |
| T2.5 | T2 | make fmt with unfixable error | error | Given scratch `scratch_f821.py` = `def g( ):\n    return y\n`. When `make fmt`. Then file becomes `def g():\n    return y\n`, exit ≠ 0 | integration | must |
| T2.6 | T2 | make fmt (no unsafe fixes) | edge | Given scratch = `def f():\n    x = 1\n    return 0\n` (F841, unsafe fix only). When `make fmt`. Then `x = 1` remains, exit ≠ 0 | integration | should |
| T2.7 | T2 | make fmt (clean tree) | edge | Given a clean tree. When `make fmt`. Then exit 0, `git status --porcelain` empty | integration | should |
| T2.8 | T2 | lint and fmt in .PHONY | happy | When `grep '^.PHONY' Makefile`. Then it includes `lint` and `fmt` (and the existing targets); with an empty file named `lint` in the root, `make lint` still runs ruff (remove it after) | integration | must |
| T2.9 | T2 | README Quick start lists the targets | happy | When reading the README Quick start block. Then it has `make lint    # ...` and `make fmt     # ...` lines, with each `#` in the same column as the existing lines (column 14) | integration | must |
