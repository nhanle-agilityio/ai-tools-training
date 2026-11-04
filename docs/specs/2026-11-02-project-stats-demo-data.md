# Project stats and demo data

- **Status:** draft
- **Date:** 2026-11-02
- **Slug:** `project-stats-demo-data`

## Problem

A client that wants a dashboard cannot get one from TaskBoard. `GET /projects/<id>/stats` returns
`project_id`, `total`, `by_status`, `completion_rate` and `in_progress_rate`, but not how many tasks are
overdue or how work splits by priority. There is no endpoint that summarises all projects at once, so a
client has to call every project and merge the numbers itself. The demo data loaded by `make seed` has no
comments and no soft-deleted task, so the comment endpoints and the soft-delete rules show nothing right
after seeding. The README documents neither the stats fields nor a global summary.

Today the overdue rule lives in `services.is_overdue`: a live task is overdue when its status is not
`done`, it has a `due_date`, and `due_date` is before today (a task due today is not overdue).

## Goals

- `GET /projects/<id>/stats` also returns `overdue` and `by_priority`.
- A new `GET /stats` returns a summary across active projects: project count, task total, tasks by
  status, overdue count and the 5 most used tags.
- `make seed` loads comments (one of them soft-deleted), one soft-deleted task and more varied tags.
- The README documents both stats endpoints with example responses.

## Non-goals

- A per-project breakdown, `by_priority` or rates in `GET /stats`. Deferred: not requested.
- Query parameters on `GET /stats` (filters, top-N size). Deferred: not requested.
- Fixing other stale README rows (PATCH/DELETE project, tag and comment endpoints, `?tag=`). Out of
  scope; noted under Risks.
- Schema changes. Every number can be computed from existing tables.
- Browser verification. TaskBoard is an HTTP API with no UI.

## Decisions

| Question | Decision | Why |
| --- | --- | --- |
| Overdue rule | Same as `services.is_overdue`: live task, `status != 'done'`, `due_date` set and `due_date < today` | One rule for `is_overdue`, `GET /tasks/overdue` and stats |
| `overdue` type | Integer count | A dashboard number |
| `by_priority` shape | `{"low": n, "medium": n, "high": n}`, all keys always present; live tasks of any status. Key order is not a requirement (Flask sorts JSON keys) | Mirrors `by_status` |
| Existing project stats fields | `project_id`, `total`, `by_status`, `completion_rate`, `in_progress_rate` unchanged | Additive change; no client breaks |
| "Active project" | `projects.deleted_at IS NULL`; there is no other project state | Only state the model has |
| What `GET /stats` counts | Live tasks in active projects | Deleted rows behave as if they do not exist |
| `GET /stats` shape | `{"projects", "total", "by_status", "overdue", "top_tags"}` | Exactly the requested summary |
| `projects` in `GET /stats` | Count of active projects, including projects without tasks | It counts projects, not tasks |
| `top_tags` counting | Number of live tasks in active projects carrying the tag, any status | Same counting as `GET /projects/<id>/tags` |
| `top_tags` order and size | `task_count` descending, then `tag` ascending; at most 5; fewer when fewer tags exist; `[]` when none | Most used first; deterministic ties |
| `top_tags` item shape | `{"tag": "<tag>", "task_count": n}` | Same as `GET /projects/<id>/tags` |
| `GET /stats` parameters and errors | No parameters (unknown ones ignored); no error case; empty database returns `200` with zeros, full `by_status` and `top_tags: []` | Read-only global summary |
| How overdue is counted | In SQL (`status != 'done' AND due_date IS NOT NULL AND due_date < ?`), today's ISO date passed in by `services` | Avoids loading tasks; same rule as `is_overdue` |
| Seed comments | 5-8 comments with real author names on tasks in both projects; one comment soft-deleted | Shows the comment endpoints and `comment_count` |
| Seed soft-deleted task | Exactly one task, deleted through `services.delete_task`, that has tags and a comment | Shows that deleted tasks are not counted |
| Seed tags | More tasks and more varied tags in Website; adding new tasks is allowed | Makes `top_tags` meaningful |
| Seed dates | Stay relative to today; `make seed` still resets the database | Demo stays current |
| Seed test | Smoke test runs `seed()` on the temporary database and checks over HTTP; no exact counts asserted | Keeps the seed easy to change |
| Seed test and `GET /stats` | The smoke test uses `GET /projects/<id>/stats` (not `GET /stats`) to show the deleted task is not counted | T3 does not depend on T2 |
| README scope | Update the `/projects/<id>/stats` row, add a `/stats` row, add example JSON responses for both | Only the endpoints in this spec |
| Verification | `needs-e2e = no`; HTTP checks only | No UI |
| Baseline for existing project stats fields | Today's behaviour: empty project gives rates `0` (int); 4 tasks with 1 `done` and 1 `in_progress` give `25.0`; rounding to 1 decimal | Concrete oracle for "unchanged" |
| Seed comment and task deletion | The soft-deleted comment is on a live task. At least 5 comments are visible on live tasks; comments on the deleted task do not count | Each deletion is observable on its own |
| Checking hidden seed state | Tests may read `tasks`, `task_tags` and `task_comments` through `get_db()` in the `app` fixture's context: to count soft-deleted tasks and comments (`deleted_at IS NOT NULL`) and to confirm the deleted task had tags and a comment | Hidden from HTTP once deleted; a comment on the deleted task also returns 404 |
| Seed minimums | Website: more than 5 tasks. "Relative dates": at least one live task is overdue and at least one has `due_date >= today`; no frozen clock. `author` only needs to be non-blank. "Tasks listed" means `pagination.total` | Measurable without exact counts |
| T4 verification | README criteria are a manual review checklist, not pytest. Example JSON must match the real response keys; numbers are illustrative | Docs only |
| Project soft-deleted but its tasks not | Its tasks are not overdue for any endpoint: excluded from `GET /stats` and from `GET /tasks/overdue`, whether the project was deleted through the API or by setting `projects.deleted_at` directly. T2 has one DB-level test that sets `projects.deleted_at` without touching tasks; #73 adds the matching parity test for `GET /tasks/overdue` | The API cascade hides a missing project join |
| "Today" | Server-local date, as `is_overdue`. Tests use `date.today() ± n`, like existing tests; a run across midnight may flake | Same as the current suite |
| Edge HTTP cases | Non-integer id, trailing slash, `POST /stats`: Flask defaults (404 / 405); no dedicated tests required | App-wide behaviour |
| `top_tags` tie order | `tag` ascending in SQLite `BINARY` order | Deterministic without collation |
| Invalid stored `due_date`, performance | Ignored: the API cannot store an invalid date; no response-time target | Out of scope |
| `seed()` on a non-empty database | Not supported; `make seed` resets with `init_db()` first | Current behaviour |
| `is_overdue` in README | Not mentioned | Not requested |

- 2026-11-04 (#73, Q1): Accept the fix commits' change to the QA test `tests/test_overdue_soft_deleted_project.py` as the G1.1 test, or have QA rewrite it? → Accepted: the change (`892e834`) is a ruff line wrap only.
- 2026-11-04 (#73, Q2): Is a task of a soft-deleted project not overdue for any endpoint? → Confirmed: a task of a soft-deleted project is not overdue for any endpoint.

## Design

### API contracts

**`GET /projects/<id>/stats`** (changed, additive)

```json
{
  "project_id": 1,
  "total": 4,
  "by_status": {"todo": 2, "in_progress": 1, "done": 1},
  "by_priority": {"low": 1, "medium": 1, "high": 2},
  "overdue": 1,
  "completion_rate": 25.0,
  "in_progress_rate": 25.0
}
```

- `by_priority`: live tasks of the project grouped by priority; all three keys present, zero when empty.
- `overdue`: live tasks of the project with `status != 'done'`, a `due_date`, and `due_date < today`.
- Missing or soft-deleted project: `404 {"error": "project <id> not found"}` (unchanged).

**`GET /stats`** (new)

```json
{
  "projects": 3,
  "total": 30,
  "by_status": {"todo": 18, "in_progress": 6, "done": 6},
  "overdue": 3,
  "top_tags": [
    {"tag": "feature", "task_count": 10},
    {"tag": "bug", "task_count": 8},
    {"tag": "ui", "task_count": 7},
    {"tag": "auth", "task_count": 6},
    {"tag": "tech-debt", "task_count": 3}
  ]
}
```

- `projects`: active projects (`deleted_at IS NULL`), including those without tasks.
- `total`, `by_status`, `overdue`: over live tasks in active projects; same rules as project stats.
- `top_tags`: at most 5, `task_count` desc then `tag` asc.
- Always `200`. Empty database: `{"projects": 0, "total": 0, "by_status": {"todo": 0, "in_progress": 0, "done": 0}, "overdue": 0, "top_tags": []}`.

### Data model

No change. Uses `projects`, `tasks`, `task_tags`, `task_comments` as they are.

### Other areas

- Layering: routes → services → repository. New SQL lives in `repository.py`; `services.py` passes
  today's date (`date.today().isoformat()` or equivalent) into the overdue count.
- Seed (`taskboard/seed.py`) uses services only (`create_project`, `create_task`, `create_comment`,
  `delete_comment`, `delete_task`), as it does today.

## Risks and unknowns

- Overdue in SQL and in `is_overdue` could drift. Mitigation: tests compare stats `overdue` against
  `GET /tasks/overdue` for the same data, including a task due today.
- Tests that depend on "today" use relative dates (`date.today() ± n`), as existing tests do; a run that crosses midnight may flake.
- README has other stale rows (PATCH/DELETE project, tag and comment endpoints, `?tag=` filter). Not
  fixed here; worth a separate docs issue.

## Tasks

| Id | Title | Type | Area | Depends on | Size | Needs e2e | Risk | Risk reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T1 | Add overdue and by_priority to project stats | feat | backend | - | S | no | low | Additive response fields; read-only; no schema change |
| T2 | Add GET /stats summary across active projects | feat | backend | - | M | no | low | New read-only endpoint; no schema or stored data change |
| T3 | Richer demo seed data with comments and a soft-deleted task | chore | data | - | S | no | low | Demo data only; `make seed` resets a local database |
| T4 | Document project stats and GET /stats in the README | docs | docs | T1, T2 | S | no | low | Documentation only |

### T1: Add overdue and by_priority to project stats

- **Type:** feat
- **Area:** backend
- **Depends on:** none
- **Size:** S
- **Needs e2e:** no
- **Risk:** low - additive response fields; read-only; no schema change
- **Hotspot files:** `taskboard/services.py`, `taskboard/repository.py`

**Acceptance criteria**

- [ ] With live tasks priority `high` x2, `medium` x1, `low` x0: `GET /projects/<id>/stats` returns `by_priority == {"low": 0, "medium": 1, "high": 2}`.
- [ ] A project without tasks returns `by_priority == {"low": 0, "medium": 0, "high": 0}` and `overdue == 0`.
- [ ] With tasks: `todo` due yesterday, `in_progress` due 3 days ago, `done` due yesterday, `todo` due today, `todo` due tomorrow, `todo` without due date: `overdue == 2`.
- [ ] For the same data, `overdue` equals the number of this project's items in `GET /tasks/overdue`.
- [ ] A soft-deleted task (overdue, `high`) is counted in neither `overdue` nor `by_priority`.
- [ ] Existing fields keep their current values: 4 tasks (`todo` x2, `in_progress` x1, `done` x1) give `total == 4`, `by_status == {"todo": 2, "in_progress": 1, "done": 1}`, `completion_rate == 25.0`, `in_progress_rate == 25.0`; an empty project gives `completion_rate == 0` and `in_progress_rate == 0`.
- [ ] Missing or soft-deleted project returns `404 {"error": "project <id> not found"}`.

**Scope** (files and areas this task may touch)

- `taskboard/services.py` (`project_stats`), `taskboard/repository.py` (new count queries), `tests/test_projects.py`

**Test plan**

Test cases: T1.1-T1.26 (see Test matrix). Tests go through the HTTP layer with `client` / `project` / `make_task`; dates relative to `date.today()`.

### T2: Add GET /stats summary across active projects

- **Type:** feat
- **Area:** backend
- **Depends on:** none
- **Size:** M
- **Needs e2e:** no
- **Risk:** low - new read-only endpoint; no schema or stored data change
- **Hotspot files:** `taskboard/routes.py`, `taskboard/services.py`, `taskboard/repository.py`

**Acceptance criteria**

- [ ] Empty database: `GET /stats` returns `200 {"projects": 0, "total": 0, "by_status": {"todo": 0, "in_progress": 0, "done": 0}, "overdue": 0, "top_tags": []}`.
- [ ] The response has exactly the keys `projects`, `total`, `by_status`, `overdue`, `top_tags`.
- [ ] `projects` counts active projects, including a project without tasks; a soft-deleted project is not counted.
- [ ] `total` and `by_status` count live tasks across all active projects; soft-deleted tasks and tasks of a soft-deleted project are excluded.
- [ ] `overdue` uses the same rule as project stats (not `done`, `due_date < today`; due today is not overdue) and equals the number of items in `GET /tasks/overdue` for the same data.
- [ ] `top_tags` lists `{"tag", "task_count"}` counting live tasks in active projects, any status, summed across projects (tag `bug` on 2 tasks in project A and 1 in project B gives `task_count: 3`).
- [ ] `top_tags` is ordered by `task_count` desc then `tag` asc, and holds at most 5 items; with 7 distinct tags only the top 5 are returned; with 2 tags, 2 are returned.
- [ ] Tags only on soft-deleted tasks or in soft-deleted projects do not appear in `top_tags`.
- [ ] A project whose `deleted_at` is set directly in the database while its tasks stay live contributes nothing to `projects`, `total`, `by_status`, `overdue` or `top_tags`.
- [ ] Query parameters are ignored: `GET /stats?foo=bar` returns the same body as `GET /stats`.

**Scope** (files and areas this task may touch)

- `taskboard/routes.py` (new route), `taskboard/services.py` (new function), `taskboard/repository.py` (new queries), new `tests/test_stats.py`

**Test plan**

Test cases: T2.1-T2.31 (see Test matrix). Extra projects via `client.post("/projects", ...)`; deletions through the API, except T2.29 (direct database write).

### T3: Richer demo seed data with comments and a soft-deleted task

- **Type:** chore
- **Area:** data
- **Depends on:** none
- **Size:** S
- **Needs e2e:** no
- **Risk:** low - demo data only; `make seed` resets a local database
- **Hotspot files:** none

**Acceptance criteria**

- [ ] After `seed()`, at least 5 comments with non-blank `author` are visible through `GET /tasks/<id>/comments` on live tasks, in at least 2 projects.
- [ ] Exactly one seeded comment on a live task is soft-deleted: `GET /comments/<id>` returns 404, it is not in its task's comment list, and that task's `comment_count` excludes it.
- [ ] Exactly one seeded task is soft-deleted: `GET /tasks/<id>` returns 404 and it does not appear in `GET /tasks`. Read through the database, it has at least one `task_tags` row and at least one `task_comments` row.
- [ ] `GET /projects/<id>/stats` `total` for that task's project equals the number of its tasks listed by `GET /tasks?project_id=<id>` (the deleted task is not counted).
- [ ] The Website project has more than 5 live tasks (`pagination.total`), and the seeded live tasks use at least 8 distinct tags in total.
- [ ] Running the seed on a fresh database succeeds; at least one live task has `is_overdue == true` and at least one has `due_date >= today`.

**Scope** (files and areas this task may touch)

- `taskboard/seed.py`, new `tests/test_seed.py`

**Test plan**

Test cases: T3.1-T3.11 (see Test matrix). The smoke test calls `taskboard.seed.seed(get_db())` inside the `app` fixture's app context, then checks over HTTP and, for hidden state, through `get_db()`. No exact counts beyond the minimums above.

### T4: Document project stats and GET /stats in the README

- **Type:** docs
- **Area:** docs
- **Depends on:** T1, T2
- **Size:** S
- **Needs e2e:** no
- **Risk:** low - documentation only
- **Hotspot files:** `README.md`

**Acceptance criteria**

- [ ] The API table row for `GET /projects/<id>/stats` lists `by_status`, `by_priority`, `overdue`, `completion_rate` and `in_progress_rate`.
- [ ] The API table has a row for `GET /stats` describing the summary across active projects.
- [ ] A section shows an example JSON response for each endpoint whose keys match the actual responses.
- [ ] The overdue rule (not `done`, `due_date` before today) and the `top_tags` order and limit are stated.
- [ ] No other README rows are changed.

**Scope** (files and areas this task may touch)

- `README.md`

**Test plan**

Test cases: T4.1-T4.6 (see Test matrix), a manual review checklist (no pytest): compare the example keys with `curl localhost:5050/stats` and `/projects/1/stats` after `make seed`; check `git diff` touches only the two rows and the new example section.

## Test matrix

Tests are named `test_t<task>_<n>_<description>` (e.g. `test_t1_2_any_status_counts`) or carry a comment `# T1.2`. T4 rows are a review checklist, referenced by id in the PR. "Today" is `date.today()`; `D-n` / `D+n` are ISO dates relative to it.

| Id | Task | Criterion | Case | Given / When / Then | Level | Priority |
| --- | --- | --- | --- | --- | --- | --- |
| T1.1 | T1 | by_priority high x2, medium x1, low x0 | happy | Given live tasks with priority `high`, `high`, `medium` / When `GET /projects/<id>/stats` / Then 200 and `by_priority == {"low": 0, "medium": 1, "high": 2}` | http | must |
| T1.2 | T1 | by_priority high x2, medium x1, low x0 | edge | Given tasks `low`/`done`, `medium`/`in_progress`, `high`/`todo` / When GET stats / Then `by_priority == {"low": 1, "medium": 1, "high": 1}` (any status counts) | http | must |
| T1.3 | T1 | by_priority high x2, medium x1, low x0 | edge | Given project A with 2 `high` tasks and project B with 1 `low` task / When GET stats for A / Then `by_priority == {"low": 0, "medium": 0, "high": 2}` (no leak from B) | http | must |
| T1.4 | T1 | by_priority high x2, medium x1, low x0 | edge | Given a task created without `priority` / When GET stats / Then `by_priority["medium"] == 1` (default priority) | http | should |
| T1.5 | T1 | by_priority high x2, medium x1, low x0 | edge | Given a task created `low` then `PATCH`ed to `high` / When GET stats / Then `{"low": 0, "medium": 0, "high": 1}` | http | should |
| T1.6 | T1 | by_priority high x2, medium x1, low x0 | boundary | Given any data / When GET stats / Then `set(by_priority) == {"low", "medium", "high"}`, values are ints and `sum(by_priority.values()) == total` | http | should |
| T1.7 | T1 | Project without tasks: zeros | happy | Given the `project` fixture with no tasks / When GET stats / Then `by_priority == {"low": 0, "medium": 0, "high": 0}` and `overdue == 0` | http | must |
| T1.8 | T1 | Project without tasks: zeros | edge | Given a project whose only task (`high`, `todo`, D-1) was deleted / When GET stats / Then all `by_priority` values 0, `overdue == 0`, `total == 0` | http | should |
| T1.9 | T1 | overdue == 2 for the 6-task fixture | happy | Given tasks `todo` D-1, `in_progress` D-3, `done` D-1, `todo` D+0, `todo` D+1, `todo` no due date / When GET stats / Then `overdue == 2` | http | must |
| T1.10 | T1 | overdue == 2 for the 6-task fixture | boundary | Given only a `todo` task due D+0 / When GET stats / Then `overdue == 0` | http | must |
| T1.11 | T1 | overdue == 2 for the 6-task fixture | boundary | Given only a `todo` task due D-1 / When GET stats / Then `overdue == 1` | http | must |
| T1.12 | T1 | overdue == 2 for the 6-task fixture | edge | Given only a `done` task due D-30 / When GET stats / Then `overdue == 0` | http | must |
| T1.13 | T1 | overdue == 2 for the 6-task fixture | edge | Given an overdue task in project B / When GET stats for project A / Then A's `overdue` excludes it | http | must |
| T1.14 | T1 | overdue == 2 for the 6-task fixture | edge | Given a `todo` task due D-1 then `PATCH`ed to `done` / When GET stats / Then `overdue == 0` | http | should |
| T1.15 | T1 | overdue == 2 for the 6-task fixture | edge | Given a `todo` task due D-400 / When GET stats / Then `overdue == 1` | http | should |
| T1.16 | T1 | overdue equals the project's items in GET /tasks/overdue | happy | Given the T1.9 fixture / When GET stats and `GET /tasks/overdue` / Then `overdue ==` number of overdue items with `project_id == <id>` (2) | http | must |
| T1.17 | T1 | overdue equals the project's items in GET /tasks/overdue | edge | Given the T1.9 fixture in A plus 1 overdue task in B / When both calls / Then A's `overdue` equals the count of A's items only (2) | http | must |
| T1.18 | T1 | overdue equals the project's items in GET /tasks/overdue | edge | Given a task due D+0 and a deleted overdue task / When both calls / Then both report 0 for the project | http | should |
| T1.19 | T1 | Soft-deleted task (overdue, high) not counted | happy | Given a live `medium` task and a `high`/`todo`/D-1 task that is then deleted / When GET stats / Then `overdue == 0` and `by_priority == {"low": 0, "medium": 1, "high": 0}` | http | must |
| T1.20 | T1 | Soft-deleted task (overdue, high) not counted | edge | Same data as T1.19 / Then `total == 1` and `by_status["todo"] == 0` | http | should |
| T1.21 | T1 | Existing fields keep their values | happy | Given 4 tasks `todo` x2, `in_progress` x1, `done` x1 / When GET stats / Then `project_id == <id>`, `total == 4`, `by_status == {"todo": 2, "in_progress": 1, "done": 1}`, `completion_rate == 25.0`, `in_progress_rate == 25.0` | http | must |
| T1.22 | T1 | Existing fields keep their values | boundary | Given an empty project / When GET stats / Then `completion_rate == 0` and `in_progress_rate == 0`, both int | http | must |
| T1.23 | T1 | Existing fields keep their values | boundary | Given 3 tasks `done` x1, `todo` x2 / When GET stats / Then `completion_rate == 33.3` | http | should |
| T1.24 | T1 | Existing fields keep their values | edge | Given any data / When GET stats / Then key set is exactly `{project_id, total, by_status, by_priority, overdue, completion_rate, in_progress_rate}` | http | should |
| T1.25 | T1 | Missing or soft-deleted project returns 404 | error | Given no project 9999 / When `GET /projects/9999/stats` / Then 404 `{"error": "project 9999 not found"}` | http | must |
| T1.26 | T1 | Missing or soft-deleted project returns 404 | error | Given a project with an overdue `high` task, then `DELETE /projects/<id>` / When GET stats / Then 404 `{"error": "project <id> not found"}` | http | must |
| T2.1 | T2 | Empty database: 200 with zeros | happy | Given a fresh DB, no `project` fixture / When `GET /stats` / Then 200 and body `== {"projects": 0, "total": 0, "by_status": {"todo": 0, "in_progress": 0, "done": 0}, "overdue": 0, "top_tags": []}` | http | must |
| T2.2 | T2 | Empty database: 200 with zeros | edge | Given 1 project with tasks, then `DELETE /projects/<id>` / When `GET /stats` / Then body equals the empty-database body | http | should |
| T2.3 | T2 | Exactly the 5 keys | happy | Given 1 project with 1 tagged task / When `GET /stats` / Then `set(body) == {"projects", "total", "by_status", "overdue", "top_tags"}` | http | must |
| T2.4 | T2 | Exactly the 5 keys | boundary | Given any data / When `GET /stats` / Then `set(by_status) == {"todo", "in_progress", "done"}`, values ints | http | should |
| T2.5 | T2 | projects counts active projects | happy | Given projects A (2 tasks), B (0 tasks), C (deleted through the API) / When `GET /stats` / Then `projects == 2` | http | must |
| T2.6 | T2 | projects counts active projects | edge | Given only the `project` fixture, no tasks / When `GET /stats` / Then `projects == 1` and `total == 0` | http | must |
| T2.7 | T2 | projects counts active projects | edge | Given B deleted, then a new project created with B's name / When `GET /stats` / Then the new project is counted once | http | should |
| T2.8 | T2 | total and by_status over live tasks | happy | Given A: `todo` x2, `done` x1; B: `in_progress` x1, `todo` x1 / When `GET /stats` / Then `total == 5` and `by_status == {"todo": 3, "in_progress": 1, "done": 1}` | http | must |
| T2.9 | T2 | total and by_status over live tasks | edge | Given the T2.8 data plus 1 deleted `todo` task in A / When `GET /stats` / Then `total == 5` and `by_status["todo"] == 3` | http | must |
| T2.10 | T2 | total and by_status over live tasks | edge | Given the T2.8 data, then `DELETE /projects/<B>` / When `GET /stats` / Then `total == 3` and `by_status == {"todo": 2, "in_progress": 0, "done": 1}` | http | must |
| T2.11 | T2 | total and by_status over live tasks | boundary | Given A and B with tasks / When `GET /stats` and each project's stats / Then global `total` and each `by_status` value equal the sums; `sum(by_status.values()) == total` | http | should |
| T2.12 | T2 | overdue: same rule; equals GET /tasks/overdue | happy | Given the T1.9 fixture in A plus a `todo` task due D-2 in B / When `GET /stats` / Then `overdue == 3` | http | must |
| T2.13 | T2 | overdue: same rule; equals GET /tasks/overdue | boundary | Given only a `todo` task due D+0 / When `GET /stats` / Then `overdue == 0` | http | must |
| T2.14 | T2 | overdue: same rule; equals GET /tasks/overdue | happy | Given the T2.12 data plus 1 deleted overdue task and 1 overdue task in a project deleted through the API / When `GET /stats` and `GET /tasks/overdue` / Then `overdue ==` item count of `/tasks/overdue` (3) | http | must |
| T2.15 | T2 | overdue: same rule; equals GET /tasks/overdue | edge | Given `done` D-5 and `in_progress` D-5 / When `GET /stats` / Then `overdue == 1` | http | should |
| T2.16 | T2 | top_tags sums across projects, any status | happy | Given `bug` on 2 tasks in A and 1 task in B / When `GET /stats` / Then `top_tags` contains `{"tag": "bug", "task_count": 3}` | http | must |
| T2.17 | T2 | top_tags sums across projects, any status | edge | Given `bug` on a `todo`, a `done` and an `in_progress` task / When `GET /stats` / Then `bug` has `task_count == 3` | http | must |
| T2.18 | T2 | top_tags sums across projects, any status | boundary | Given any tagged data / When `GET /stats` / Then each item has exactly keys `{"tag", "task_count"}`, `tag` str, `task_count` int >= 1 | http | must |
| T2.19 | T2 | top_tags sums across projects, any status | edge | Given a task created with `tags: ["Bug", "bug "]` / When `GET /stats` / Then `top_tags` contains `{"tag": "bug", "task_count": 1}` | http | should |
| T2.20 | T2 | top_tags sums across projects, any status | edge | Given a task tagged `["bug"]` then `PATCH`ed to `tags: ["ui"]` / When `GET /stats` / Then `ui` has count 1 and `bug` is absent | http | should |
| T2.21 | T2 | top_tags order desc/asc, at most 5 | happy | Given tag counts a=4, b=3, c=3, d=2, e=1 / When `GET /stats` / Then tags in order `["a", "b", "c", "d", "e"]` | http | must |
| T2.22 | T2 | top_tags order desc/asc, at most 5 | boundary | Given 7 tags with counts 7..1 / When `GET /stats` / Then `len(top_tags) == 5` and counts `[7, 6, 5, 4, 3]` | http | must |
| T2.23 | T2 | top_tags order desc/asc, at most 5 | boundary | Given exactly 2 tags / When `GET /stats` / Then `len(top_tags) == 2` | http | must |
| T2.24 | T2 | top_tags order desc/asc, at most 5 | boundary | Given 6 tags each on 1 task: `alpha`, `bravo`, `charlie`, `delta`, `echo`, `zulu` / When `GET /stats` / Then tags `["alpha", "bravo", "charlie", "delta", "echo"]` | http | must |
| T2.25 | T2 | top_tags order desc/asc, at most 5 | edge | Given projects with tasks but no tags / When `GET /stats` / Then `top_tags == []` | http | should |
| T2.26 | T2 | Tags only on deleted tasks or projects excluded | happy | Given `ghost` only on a deleted task, `legacy` only in a project deleted through the API, `live` on 1 live task / When `GET /stats` / Then `top_tags == [{"tag": "live", "task_count": 1}]` | http | must |
| T2.27 | T2 | Tags only on deleted tasks or projects excluded | edge | Given `bug` on 2 live tasks and 1 deleted task / When `GET /stats` / Then `bug` has `task_count == 2` | http | must |
| T2.28 | T2 | Tags only on deleted tasks or projects excluded | edge | Given 5 tags on deleted tasks only (3 tasks each) and `x` on 1 live task / When `GET /stats` / Then `top_tags == [{"tag": "x", "task_count": 1}]` | http | should |
| T2.29 | T2 | Project soft-deleted in DB, tasks live, contributes nothing | edge | Given A (live `todo` D-1, tag `a`) and B (live `todo` D-1, tag `b`); then `UPDATE projects SET deleted_at = <now> WHERE id = <B>` through `get_db()`, tasks untouched / When `GET /stats` / Then `projects == 1`, `total == 1`, `by_status["todo"] == 1`, `overdue == 1`, `top_tags == [{"tag": "a", "task_count": 1}]` | integration | must |
| T2.30 | T2 | Query parameters ignored | happy | Given mixed data / When `GET /stats?foo=bar` and `GET /stats` / Then both 200 with equal bodies | http | must |
| T2.31 | T2 | Query parameters ignored | edge | Given mixed data / When `GET /stats?project_id=1&tag=bug&page=abc&per_page=0` / Then 200, same body as `GET /stats` | http | should |
| T3.1 | T3 | >= 5 visible comments, non-blank author, >= 2 projects | happy | Given `seed(get_db())` in the app context / When each project's tasks are listed and `GET /tasks/<id>/comments` is called for each / Then >= 5 comments, each `author.strip() != ""`, on tasks of >= 2 distinct `project_id`s | http | must |
| T3.2 | T3 | >= 5 visible comments, non-blank author, >= 2 projects | edge | Same seed / Then each listed task's `comment_count == len(GET /tasks/<id>/comments)` | http | should |
| T3.3 | T3 | Exactly one comment on a live task soft-deleted | happy | Given the seed / When `task_comments` rows with `deleted_at IS NOT NULL` are read through `get_db()` / Then exactly 1 row; its task returns 200; `GET /comments/<cid>` returns 404; `cid` not in the task's comment list; `comment_count` equals the list length | integration | must |
| T3.4 | T3 | Exactly one seeded task soft-deleted, with tags and a comment | happy | Given the seed / When `tasks` rows with `deleted_at IS NOT NULL` are read through `get_db()` / Then exactly 1 row; `GET /tasks/<id>` 404; absent from `GET /tasks`; it has >= 1 `task_tags` row and >= 1 `task_comments` row | integration | must |
| T3.5 | T3 | Exactly one seeded task soft-deleted, with tags and a comment | edge | Same seed / Then comments of the deleted task are not counted toward T3.1's 5, and T3.1 still passes | http | should |
| T3.6 | T3 | stats total equals pagination.total for the deleted task's project | happy | Given the seed / When `GET /projects/<pid>/stats` and `GET /tasks?project_id=<pid>` / Then `stats.total == pagination.total` | http | must |
| T3.7 | T3 | stats total equals pagination.total for the deleted task's project | edge | Same check for every active seeded project, including the 0-task `Game Prototype` | http | should |
| T3.8 | T3 | Website > 5 live tasks; >= 8 distinct tags | happy | Given the seed / When `Website` is found in `GET /projects` and `GET /tasks?project_id=<id>` / Then `pagination.total > 5` | http | must |
| T3.9 | T3 | Website > 5 live tasks; >= 8 distinct tags | happy | Given the seed / When all live tasks are listed / Then >= 8 distinct tags across them | http | must |
| T3.10 | T3 | Fresh DB seed succeeds; one overdue, one due >= today | happy | Given the fresh temp DB from the `app` fixture / When `seed(get_db())` / Then no exception and `GET /projects` lists >= 2 projects | integration | must |
| T3.11 | T3 | Fresh DB seed succeeds; one overdue, one due >= today | happy | Given the seed / When all live tasks are listed / Then >= 1 has `is_overdue == true` and >= 1 has `due_date >= date.today().isoformat()` | http | must |
| T4.1 | T4 | Stats row lists the 5 fields | happy | Review checklist: the README row `GET /projects/<id>/stats` names `by_status`, `by_priority`, `overdue`, `completion_rate`, `in_progress_rate` | unit | must |
| T4.2 | T4 | Row for GET /stats | happy | Review checklist: the API table has a `GET` `/stats` row describing a summary across active projects | unit | must |
| T4.3 | T4 | Example JSON keys match actual responses | happy | Review checklist: after `make seed` + `make run`, `curl localhost:5050/stats` and `/projects/1/stats` have the same top-level and nested keys as the README examples; numbers illustrative | unit | must |
| T4.4 | T4 | Example JSON keys match actual responses | edge | Review checklist: each example block parses as valid JSON | unit | should |
| T4.5 | T4 | Overdue rule and top_tags order and limit stated | happy | Review checklist: README states not `done`, `due_date` before today (due today not overdue), `top_tags` by `task_count` desc then `tag` asc, at most 5 | unit | must |
| T4.6 | T4 | No other README rows changed | happy | Review checklist: `git diff <base> -- README.md` changes only the stats row, adds the `/stats` row and the example section | unit | must |
