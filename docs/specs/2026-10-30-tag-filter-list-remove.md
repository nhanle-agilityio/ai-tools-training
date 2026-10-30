# Filter tasks by tag, list a project's tags, remove a tag

- **Status:** draft
- **Date:** 2026-10-30
- **Slug:** `tag-filter-list-remove`

## Problem

Tasks can carry up to 10 tags, but tags can only be written, never used. A client cannot ask for
"all tasks tagged `bug`", cannot show which tags a project uses and how often, and cannot get rid of
an obsolete tag without patching every task one by one. Today `GET /tasks` filters only by
`project_id`, `status` and `q`; there is no tag endpoint at all. Tags live in
`task_tags(task_id, tag)` and are stored stripped, lower-cased and de-duplicated
(`validators.validate_tags`). Soft-deleted tasks keep their `task_tags` rows.

## Goals

- A client can filter `GET /tasks` by one or more tags; a task matches only if it has all of them.
- A client can list the tags used by a project's live tasks, with the number of tasks per tag.
- A client can remove a tag from every live task of a project in one call.

## Non-goals

- Renaming or merging tags. Deferred: no user need yet.
- A global tag list across projects. Deferred: tags are managed per project.
- Tag filter on `GET /tasks/overdue`. Deferred: not requested.
- Adding a tag to many tasks at once. Deferred: not requested.
- Touching soft-deleted tasks. They keep their tags, as decided in the project-edit-soft-delete spec.
- Schema changes. `task_tags` already holds everything needed.
- Browser verification. TaskBoard is an HTTP API with no UI, so every task is verified over HTTP only.

## Decisions

| Question | Decision | Why |
| --- | --- | --- |
| Several tags in a filter | AND: a task must have every requested tag | Filtering narrows results; matches how `status` and `q` combine |
| Filter parameter format | Repeated `tag` query param: `?tag=bug&tag=ui` | Native `request.args.getlist`; no escaping for commas |
| Filter value normalisation | Each value is `strip().lower()`ed, as on write; duplicates count once | `?tag=Bug` must match the stored `bug` |
| Empty filter value | `?tag=` or `?tag=%20` returns `400 tag must not be empty` | An empty tag can never match; silently ignoring it hides client bugs |
| Unknown tag in filter | `200` with `items: []`, `pagination.total = 0` | A filter that matches nothing is not an error |
| Filter with other params | AND with `project_id`, `status`, `q`; works with `sort` and pagination | One consistent filter model |
| Too many filter tags | More than 10 distinct tags (after normalisation) returns `400 at most 10 tags can be filtered` | A task has at most `MAX_TAGS` (10) tags, so more can never match |
| Tags in a filtered result | Each task still returns its full `tags` list | The filter selects tasks; it does not change their representation |
| Tag list endpoint | `GET /projects/<id>/tags` returns `{"items": [{"tag": ..., "task_count": n}]}` | Per-project, next to `/stats` |
| What the tag list counts | Live tasks of the project only, any status (`done` included) | Deleted tasks behave as if they do not exist |
| Tag list order | `task_count` descending, then `tag` ascending | Most used first; stable order |
| Tag list paging | None; a project without tags returns `items: []` | Few tags per project; paging can be added later without breaking clients |
| Tag list for a missing or deleted project | `404 project <id> not found` | Same as `/stats` |
| Tag removal scope | Per project: `DELETE /projects/<id>/tags/<tag>` | Symmetric with the list; one call cannot strip other projects |
| Tag removal and deleted tasks | Only live tasks lose the tag | Soft-deleted tasks keep their tags |
| `updated_at` on removal | Every task that loses the tag gets `updated_at = now`; other tasks are untouched | Same as changing tags with `PATCH /tasks/<id>` |
| Removal response | `200 {"tag": "<normalised tag>", "removed_from": n}` | The client learns how many tasks changed |
| Tag not on any live task of the project | `404 tag <tag> not found in project <id>` | The tag is treated as a resource |
| Removal check order | Missing or deleted project `404` first, then empty tag `400`, then unknown tag `404` | Same "resource first" order as `update_task` |
| Path tag normalisation | `<tag>` is URL-decoded, then `strip().lower()`ed; blank returns `400 tag must not be empty` | Same rule as the filter |
| Tags containing `/` | Route uses `<path:tag>` | Stored tags may contain `/` (e.g. `ui/ux`) and must be removable |
| Verification | `needs-e2e = no`; HTTP checks only | No UI |
| Error order on `GET /tasks` | Existing errors (`page`, `per_page`, `project_id`, `status`, `sort`) win over tag errors; among tag errors, blank before "more than 10" | New checks do not change existing responses |
| Normalisation details | Exactly `str.strip().lower()`, as on write: inner whitespace kept; `,` is an ordinary character (`?tag=a,b` looks for tag `a,b`); param name is case-sensitive (`?TAG=` is ignored); a path tag `bug/` means the tag `bug/` | One rule for read and write |
| Tag list tie order | `tag` ascending in SQLite `BINARY` order | Deterministic without extra collation |
| Order of `tags` in a task | Sorted ascending, as today (`repository.get_tags` orders by tag) | Tests compare exact lists |
| Tag list response keys | Only `items` | Decided shape; no `project_id` |
| Project `updated_at` on tag removal | Unchanged | Only tasks change |
| Filter with a missing or deleted `project_id` | `200` with `items: []`, as today | Not part of this change |
| Retried removal | Second call returns `404 tag <tag> not found in project <id>` | Keeps the tag-as-resource decision |
| `<id>` in error messages | The numeric project id, e.g. `tag bug not found in project 1` | Same as `project <id> not found` |
| Non-integer project id, empty path segment, other methods on `/tags` | Flask's default 404 / 405, as for every other route | Existing app-wide behaviour, out of scope |
| Clock in tests | Tests may monkeypatch `taskboard.services._now` to assert `updated_at` | `_now()` has second precision |
| Direct database reads in tests | Allowed through the `app` fixture only for state hidden from HTTP (soft-deleted tasks' tags) | Cannot be observed over HTTP |
| "Behaves as before" baseline | `?tag=bug&status=bogus` returns a body identical to `?status=bogus`; shape = top keys `items`, `pagination`; pagination keys `page`, `per_page`, `total`, `pages`, `has_next`; task keys include `tags`, `is_overdue`, `comment_count` | Concrete, checkable baseline |
| Page out of range with tag errors | Format errors of `page` / `per_page` win over tag errors; `page N is out of range` depends on the filtered total, so tag errors win over it (`?tag=&page=99` returns `tag must not be empty`) | The range is unknown until the filter is valid |
| Malformed input | `%ZZ`, invalid UTF-8, `%00`, `?tags=`, `?tag[]=`, `//bug`: Werkzeug / Flask defaults, no dedicated tests; NUL is accepted and matches nothing. Unencoded `/tags/ui/ux` is supported through `<path:tag>` | Out of scope; app-wide behaviour |
| Removal atomicity | No fault-injection test; the `task_tags` delete and the `updated_at` update share one `commit`, checked in review | Not observable over HTTP |

## Design

### API contracts

**`GET /tasks`** (changed)

New optional, repeatable query param `tag`.

```
GET /tasks?project_id=1&tag=bug&tag=UI&sort=priority
```

- Returns tasks that have **all** the given tags (compared after `strip().lower()`).
- Combined with `project_id`, `status`, `q`, `sort`, `page`, `per_page` as today.
- `pagination.total` counts only matching tasks.
- Response shape is unchanged; every task carries its full `tags` list.

Errors:

| Case | Status | Body `error` |
| --- | --- | --- |
| A `tag` value is empty or blank | 400 | `tag must not be empty` |
| More than 10 distinct tags after normalisation | 400 | `at most 10 tags can be filtered` |

Existing errors (`status`, `sort`, `page`, ...) are unchanged.

**`GET /projects/<id>/tags`** (new)

Response `200`:

```json
{ "items": [
    { "tag": "bug", "task_count": 3 },
    { "tag": "android", "task_count": 1 },
    { "tag": "ui", "task_count": 1 }
] }
```

- Counts live tasks of the project only; soft-deleted tasks are ignored.
- Ordered by `task_count` descending, then `tag` ascending.
- A project with no tagged live tasks returns `{"items": []}`.

Errors:

| Case | Status | Body `error` |
| --- | --- | --- |
| Project missing or deleted | 404 | `project <id> not found` |

**`DELETE /projects/<id>/tags/<path:tag>`** (new)

```
DELETE /projects/1/tags/Bug
```

Response `200`:

```json
{ "tag": "bug", "removed_from": 3 }
```

- Removes the tag from every live task of the project that has it, in one transaction.
- Sets `updated_at = now` on exactly those tasks.
- Tasks of other projects and soft-deleted tasks keep the tag.

Errors, checked in this order:

| Case | Status | Body `error` |
| --- | --- | --- |
| Project missing or deleted | 404 | `project <id> not found` |
| Tag blank after `strip()` (e.g. `/tags/%20`) | 400 | `tag must not be empty` |
| No live task of the project has the tag | 404 | `tag <tag> not found in project <id>` (normalised tag) |

### Data model

No change. `task_tags (task_id, tag)` with primary key `(task_id, tag)` is enough.

- Filter: one `EXISTS` / `IN` sub-select on `task_tags` per requested tag, or a single
  `GROUP BY task_id HAVING COUNT(DISTINCT tag) = n`, added to `repository._task_filters` so the
  count and the page query use the same clause.
- List: `task_tags` joined to live tasks of the project, grouped by `tag`.
- Remove: delete the `task_tags` rows of the project's live tasks and update their `updated_at`, then
  one `commit`.

### Other areas

- `validators.py`: a single helper normalises one tag value (`strip().lower()`, blank → 400). It is
  shared by the filter (T1) and the removal path (T3).
- Layering per `CLAUDE.md`: routes → services → repository; validation in `validators.py`.

## Risks and unknowns

- **Removal deletes stored data.** A wrong `WHERE` would strip tags from other projects or from
  soft-deleted tasks. Mitigation: T3 tests both cases explicitly; one transaction.
- **Filter and pagination drift.** If the tag clause is added to the page query but not the count,
  `pagination.total` is wrong. Mitigation: the clause lives in `_task_filters`, used by both; T1 tests
  `pagination.total`.
- **No maximum tag length.** Neither the write path nor the filter limits tag length; a very long
  `?tag=` value is accepted and simply matches nothing. Deferred: same as today's write path.
- **Removal race.** A concurrent `PATCH` that drops the tag between the existence check and the delete
  could yield `200 {"removed_from": 0}`. Accepted: single-user training app.
- **Hotspot files.** All three tasks touch `routes.py`, `services.py` and `repository.py`. Expect small
  merge conflicts if they run in parallel.

## Tasks

| Id | Title | Type | Area | Depends on | Size | Needs e2e | Risk | Risk reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T1 | Filter GET /tasks by one or more tags | feat | backend | - | M | no | low | Additive, read-only query param; no stored data changes |
| T2 | List a project's tags with task counts | feat | backend | - | S | no | low | New read-only endpoint |
| T3 | Remove a tag from all live tasks of a project | feat | backend | T1, T2 | M | no | high | Deletes stored data (`task_tags` rows) in bulk |

### T1: Filter GET /tasks by one or more tags

- **Type:** feat
- **Area:** backend
- **Depends on:** none
- **Size:** M
- **Needs e2e:** no
- **Risk:** low - additive, read-only query param; no stored data changes
- **Hotspot files:** `taskboard/routes.py`, `taskboard/services.py`, `taskboard/repository.py`, `taskboard/validators.py`

**Acceptance criteria**

- [ ] With tasks A `[bug, ui]`, B `[bug]`, C `[]`: `GET /tasks?tag=bug` returns A and B; `pagination.total` is 2.
- [ ] `GET /tasks?tag=bug&tag=ui` returns only A.
- [ ] `GET /tasks?tag=Bug` and `GET /tasks?tag=%20bug%20` return A and B.
- [ ] `GET /tasks?tag=bug&tag=BUG` returns A and B (duplicates count once).
- [ ] `GET /tasks?tag=nope` returns 200 with `items: []` and `pagination.total` 0.
- [ ] Each returned task has its full `tags` list (A returns `["bug", "ui"]` for `?tag=bug`).
- [ ] `tag` combines with `project_id`, `status` and `q` (AND), and with `sort`, `page`, `per_page`.
- [ ] Soft-deleted tasks with the tag are not returned and not counted.
- [ ] `GET /tasks?tag=` and `GET /tasks?tag=%20` return `400 tag must not be empty`.
- [ ] 11 distinct `tag` values return `400 at most 10 tags can be filtered`; 10 distinct values (even with
  extra duplicates) return 200.
- [ ] `GET /tasks?tag=bug&status=bogus` returns the existing `status` 400 error (existing errors win).
- [ ] With 1 task tagged `bug`, `GET /tasks?tag=bug&page=2` returns `400 page 2 is out of range (1-1)`;
  `GET /tasks?tag=&page=99` returns `400 tag must not be empty`.
- [ ] `GET /tasks` without `tag` behaves as before: existing tests pass unchanged and the response shape is the same.

**Scope** (files and areas this task may touch)

- `taskboard/routes.py` (`list_tasks`), `taskboard/services.py` (`list_tasks`),
  `taskboard/repository.py` (`_task_filters`, `list_tasks`), `taskboard/validators.py` (tag value
  helper), `tests/test_tasks.py`.

**Test plan**

- Test cases: T1.1-T1.45 (see Test matrix).

### T2: List a project's tags with task counts

- **Type:** feat
- **Area:** backend
- **Depends on:** none
- **Size:** S
- **Needs e2e:** no
- **Risk:** low - new read-only endpoint
- **Hotspot files:** `taskboard/routes.py`, `taskboard/services.py`, `taskboard/repository.py`

**Acceptance criteria**

- [ ] With live tasks `[bug, ui]`, `[bug]`, `[android, bug]`: `GET /projects/<id>/tags` returns 200 with
  `items` `[{"tag": "bug", "task_count": 3}, {"tag": "android", "task_count": 1}, {"tag": "ui", "task_count": 1}]`.
- [ ] Tasks with status `done` are counted.
- [ ] Tags of soft-deleted tasks are not counted; a tag used only by deleted tasks is absent.
- [ ] Tags of another project's tasks are not counted.
- [ ] A project with no tasks, or only untagged tasks, returns `{"items": []}`.
- [ ] `GET /projects/999/tags` returns `404 project 999 not found`; the same for a soft-deleted project.

**Scope** (files and areas this task may touch)

- `taskboard/routes.py`, `taskboard/services.py`, `taskboard/repository.py`, `tests/test_projects.py`.

**Test plan**

- Test cases: T2.1-T2.13 (see Test matrix).

### T3: Remove a tag from all live tasks of a project

- **Type:** feat
- **Area:** backend
- **Depends on:** T1 (shared tag value helper in `validators.py`), T2 (tests T3.2 and T3.6 read `GET /projects/<id>/tags`)
- **Size:** M
- **Needs e2e:** no
- **Risk:** high - deletes stored data (`task_tags` rows) in bulk
- **Hotspot files:** `taskboard/routes.py`, `taskboard/services.py`, `taskboard/repository.py`, `taskboard/validators.py`

**Acceptance criteria**

- [ ] With live tasks A `[bug, ui]`, B `[bug]`, C `[ui]` in project P: `DELETE /projects/P/tags/bug` returns
  `200 {"tag": "bug", "removed_from": 2}`; afterwards A has `["ui"]`, B has `[]`, C has `["ui"]`.
- [ ] A and B get `updated_at` set to the request time; C's `updated_at` is unchanged.
- [ ] A task in another project tagged `bug` keeps the tag.
- [ ] A soft-deleted task of P tagged `bug` keeps its `task_tags` row.
- [ ] `DELETE /projects/P/tags/Bug` and `DELETE /projects/P/tags/%20bug%20` remove `bug` and return `"tag": "bug"`.
- [ ] `DELETE /projects/P/tags/ui%2Fux` removes the tag `ui/ux`.
- [ ] A second `DELETE /projects/P/tags/bug` returns `404 tag bug not found in project P`.
- [ ] `DELETE /projects/P/tags/bug` when `bug` is only on deleted tasks of P returns 404 `tag bug not found in project P`.
- [ ] `DELETE /projects/P/tags/%20` returns `400 tag must not be empty`.
- [ ] `DELETE /projects/999/tags/bug` returns `404 project 999 not found`; the same for a soft-deleted project.
- [ ] `DELETE /projects/999/tags/%20` returns `404 project 999 not found` (project checked before the tag).
- [ ] The project's `updated_at` does not change.
- [ ] The `task_tags` delete and the `updated_at` update are written in one `commit` (checked in review).

**Scope** (files and areas this task may touch)

- `taskboard/routes.py`, `taskboard/services.py`, `taskboard/repository.py`, `taskboard/validators.py`
  (reuse the T1 helper), `tests/test_projects.py`.

**Test plan**

- Test cases: T3.1-T3.25 (see Test matrix). Check soft-deleted task rows via the `app` fixture's
  database connection; control the clock by monkeypatching `taskboard.services._now`.
- The one-`commit` criterion has no test row; it is checked in review.

## Test matrix

Tests are named `test_t<task>_<n>_<description>` (e.g. `test_t1_31_blank_tag_returns_400`) or carry a
comment `# T1.31`.

| Id | Task | Criterion | Case | Given / When / Then | Level | Priority |
| --- | --- | --- | --- | --- | --- | --- |
| T1.1 | T1 | `?tag=bug` returns A and B, total 2 | happy | Given A `[bug, ui]`, B `[bug]`, C `[]` / When `GET /tasks?tag=bug` / Then 200, item ids == {A, B}, `pagination.total` == 2 | http | must |
| T1.2 | T1 | `?tag=bug` returns A and B, total 2 | edge | Given A `[bug]` in P1, D `[bug]` in P2 / When `GET /tasks?tag=bug` (no `project_id`) / Then ids == {A, D}, total 2 | http | should |
| T1.3 | T1 | `?tag=bug` returns A and B, total 2 | edge | Given F `[bugfix]`, G `[debug]` / When `GET /tasks?tag=bug` / Then 200, `items: []`, total 0 (exact match, not substring) | http | should |
| T1.4 | T1 | `tag=bug&tag=ui` returns only A | happy | Given A `[bug, ui]`, B `[bug]`, C `[]` / When `GET /tasks?tag=bug&tag=ui` / Then ids == [A], total 1 | http | must |
| T1.5 | T1 | `tag=bug&tag=ui` returns only A | edge | Given A `[bug, ui]`, B `[bug]`, D `[ui]` / When `GET /tasks?tag=bug&tag=ui` / Then ids == [A] only (AND, not OR) | http | must |
| T1.6 | T1 | `tag=bug&tag=ui` returns only A | edge | Same data / When `GET /tasks?tag=ui&tag=bug` / Then ids == [A] (param order irrelevant) | http | should |
| T1.7 | T1 | `?tag=Bug` / `?tag=%20bug%20` return A and B | happy | Given A `[bug, ui]`, B `[bug]`, C `[]` / When `GET /tasks?tag=Bug` / Then ids == {A, B}, total 2 | http | must |
| T1.8 | T1 | `?tag=Bug` / `?tag=%20bug%20` return A and B | happy | Same data / When `GET /tasks?tag=%20bug%20` / Then ids == {A, B}, total 2 | http | must |
| T1.9 | T1 | `?tag=Bug` / `?tag=%20bug%20` return A and B | edge | Same data / When `GET /tasks?tag=%09BUG%0A` / Then ids == {A, B} (`strip()` removes tab/newline) | http | should |
| T1.10 | T1 | `?tag=Bug` / `?tag=%20bug%20` return A and B | edge | Given E `[foo bar]` / When `?tag=foo%20bar` then `?tag=foobar` / Then first returns [E]; second `items: []` (inner whitespace kept) | http | should |
| T1.11 | T1 | `?tag=Bug` / `?tag=%20bug%20` return A and B | edge | Given A `[bug, ui]` / When `GET /tasks?tag=bug,ui` / Then 200, `items: []`, total 0 (`,` is literal) | http | should |
| T1.12 | T1 | `?tag=Bug` / `?tag=%20bug%20` return A and B | edge | Given A, B, C as T1.1 / When `GET /tasks?TAG=bug` / Then 200, ids == {A, B, C}, total 3 (param name is case-sensitive; ignored) | http | should |
| T1.13 | T1 | `tag=bug&tag=BUG` returns A and B | happy | Given A `[bug, ui]`, B `[bug]`, C `[]` / When `GET /tasks?tag=bug&tag=BUG` / Then ids == {A, B}, total 2 | http | must |
| T1.14 | T1 | `tag=bug&tag=BUG` returns A and B | edge | Same data / When `?tag=bug&tag=%20Bug%20&tag=bug` / Then ids == {A, B}, total 2 | http | should |
| T1.15 | T1 | `?tag=nope` returns 200, `[]`, total 0 | happy | Given A, B, C as T1.1 / When `GET /tasks?tag=nope` / Then 200, `items: []`, `pagination.total` == 0 | http | must |
| T1.16 | T1 | `?tag=nope` returns 200, `[]`, total 0 | edge | Given no tasks / When `GET /tasks?tag=bug` / Then 200, `items: []`, total 0, `pages` 1, `has_next` false | http | should |
| T1.17 | T1 | `?tag=nope` returns 200, `[]`, total 0 | edge | Given A `[bug]` / When `GET /tasks?tag=bug&tag=nope` / Then 200, `items: []`, total 0 | http | should |
| T1.18 | T1 | Each task returns its full `tags` | happy | Given A `[bug, ui]`, B `[bug]` / When `GET /tasks?tag=bug` / Then A.tags == `["bug", "ui"]`, B.tags == `["bug"]` | http | must |
| T1.19 | T1 | Each task returns its full `tags` | edge | Given G created with tags `["zeta", "Alpha", "bug"]` / When `GET /tasks?tag=zeta` / Then G.tags == `["alpha", "bug", "zeta"]`; G also has `is_overdue`, `comment_count` | http | should |
| T1.20 | T1 | Combines with `project_id` (AND) | happy | Given A `[bug]` in P1, D `[bug]` in P2 / When `GET /tasks?tag=bug&project_id=<P1>` / Then ids == [A], total 1 | http | must |
| T1.21 | T1 | Combines with `project_id` (AND) | edge | Given A `[bug]` / When `GET /tasks?tag=bug&project_id=999` / Then 200, `items: []`, total 0 | http | should |
| T1.22 | T1 | Combines with `status` (AND) | happy | Given A `[bug]` todo, B `[bug]` done, C `[]` done / When `GET /tasks?tag=bug&status=done` / Then ids == [B], total 1 | http | must |
| T1.23 | T1 | Combines with `q` (AND) | happy | Given A "Login crash" `[bug]`, B "Docs" `[bug]`, C "Login form" `[]` / When `GET /tasks?tag=bug&q=login` / Then ids == [A], total 1 | http | must |
| T1.24 | T1 | Combines with `sort` | happy | Given `[bug]` tasks L (low), H (high), M (medium) plus untagged X (high) / When `GET /tasks?tag=bug&sort=priority` / Then ids in order [H, M, L] | http | must |
| T1.25 | T1 | Combines with `page`, `per_page` | happy | Given 3 `[bug]` tasks and 2 untagged / When `GET /tasks?tag=bug&per_page=2&page=2` / Then 1 item; total 3, pages 2, page 2, has_next false | http | must |
| T1.26 | T1 | Combines with `page`, `per_page` | boundary | Same data / When `GET /tasks?tag=bug&per_page=2&page=1` / Then 2 items, total 3, has_next true | http | should |
| T1.27 | T1 | Out-of-range page uses the filtered total | boundary | Given 1 `[bug]` task and 15 untagged / When `GET /tasks?tag=bug&page=2` / Then 400 `page 2 is out of range (1-1)` | http | must |
| T1.28 | T1 | Combines with all params | edge | Given a mix across P1/P2, statuses, titles / When `?tag=bug&tag=ui&project_id=<P1>&status=todo&q=login&sort=due_date&per_page=1` / Then only the intersection, in due_date order, total == intersection size | http | should |
| T1.29 | T1 | Soft-deleted tasks not returned or counted | happy | Given A `[bug]`, B `[bug]`, then `DELETE /tasks/<B>` / When `GET /tasks?tag=bug` / Then ids == [A], `pagination.total` == 1 | http | must |
| T1.30 | T1 | Soft-deleted tasks not returned or counted | edge | Given 3 `[bug]` tasks, one soft-deleted / When `GET /tasks?tag=bug&per_page=1` / Then total 2, pages 2 | http | should |
| T1.31 | T1 | `?tag=` / `?tag=%20` return 400 | error | When `GET /tasks?tag=` / Then 400 `{"error": "tag must not be empty"}` | http | must |
| T1.32 | T1 | `?tag=` / `?tag=%20` return 400 | error | When `GET /tasks?tag=%20` / Then 400 `tag must not be empty` | http | must |
| T1.33 | T1 | `?tag=` / `?tag=%20` return 400 | edge | When `GET /tasks?tag` (no `=`) / Then 400 `tag must not be empty` | http | should |
| T1.34 | T1 | `?tag=` / `?tag=%20` return 400 | edge | When `GET /tasks?tag=bug&tag=%20%09` / Then 400 `tag must not be empty` | http | should |
| T1.35 | T1 | 11 distinct → 400; 10 distinct (+dups) → 200 | boundary | When `GET /tasks?tag=t1&...&tag=t11` (11 distinct) / Then 400 `at most 10 tags can be filtered` | http | must |
| T1.36 | T1 | 11 distinct → 400; 10 distinct (+dups) → 200 | boundary | When `?tag=t1&...&tag=t10&tag=T1&tag=%20t2%20` (12 values, 10 distinct) / Then 200 | http | must |
| T1.37 | T1 | 11 distinct → 400; 10 distinct (+dups) → 200 | boundary | Given K with tags t1..t10, L with t1..t9 / When `?tag=t1&...&tag=t10` / Then 200, ids == [K], total 1 | http | should |
| T1.38 | T1 | 11 distinct → 400; 10 distinct (+dups) → 200 | edge | When 11 distinct values plus `tag=` / Then 400 `tag must not be empty` (blank checked first) | http | should |
| T1.39 | T1 | Existing errors win | error | When `GET /tasks?tag=bug&status=bogus` / Then 400, body identical to `GET /tasks?status=bogus` | http | must |
| T1.40 | T1 | Existing errors win | edge | When `GET /tasks?tag=&status=bogus` / Then the `status` 400 body, not `tag must not be empty` | http | must |
| T1.41 | T1 | Existing errors win | edge | When `?tag=&sort=bogus`, `?tag=&page=0`, `?tag=&per_page=0`, `?tag=&project_id=abc` / Then each returns the same 400 body as without `tag` | http | should |
| T1.42 | T1 | Existing errors win | edge | When 11 distinct tags plus `status=bogus` / Then the `status` 400 body | http | should |
| T1.43 | T1 | Tag errors win over out-of-range page | edge | When `GET /tasks?tag=&page=99` / Then 400 `tag must not be empty` | http | should |
| T1.44 | T1 | No `tag`: behaves as before | happy | Given A `[bug]`, C `[]` / When `GET /tasks` / Then 200, ids == {A, C}; top keys == {items, pagination}; pagination keys == {page, per_page, total, pages, has_next}; task keys include `tags`, `is_overdue`, `comment_count` | http | must |
| T1.45 | T1 | No `tag`: behaves as before | happy | Given existing `tests/test_tasks.py` with no edited test bodies / When the suite runs / Then all pass | http | must |
| T2.1 | T2 | Counts and order | happy | Given live `[bug, ui]`, `[bug]`, `[android, bug]` in P / When `GET /projects/<P>/tags` / Then 200, body == `{"items": [{"tag":"bug","task_count":3},{"tag":"android","task_count":1},{"tag":"ui","task_count":1}]}` | http | must |
| T2.2 | T2 | Counts and order | edge | Same data / Then top-level keys == {items}; item keys == {tag, task_count}; `task_count` is an int | http | should |
| T2.3 | T2 | Counts and order | boundary | Given tasks `[c]`, `[a]`, `[b]` / When list / Then order a, b, c (tie → tag ascending) | http | should |
| T2.4 | T2 | Counts and order | edge | Given tags `9`, `10`, `z`, `é` once each / When list / Then order `10`, `9`, `z`, `é` (SQLite BINARY) | http | should |
| T2.5 | T2 | Counts and order | edge | Given task `[bug]`, then `PATCH /tasks/<id>` with `tags: []` / When list / Then `{"items": []}` | http | should |
| T2.6 | T2 | `done` tasks counted | happy | Given `[bug]` todo, `[bug]` done / When list / Then `[{"tag":"bug","task_count":2}]` | http | must |
| T2.7 | T2 | Soft-deleted tasks not counted | happy | Given live `[bug]`, deleted `[bug, legacy]` / When list / Then `[{"tag":"bug","task_count":1}]`; `legacy` absent | http | must |
| T2.8 | T2 | Soft-deleted tasks not counted | edge | Given only a soft-deleted task `[bug]` / When list / Then `{"items": []}` | http | should |
| T2.9 | T2 | Other projects not counted | happy | Given P1 `[bug]`; P2 `[bug]`, `[other]` / When `GET /projects/<P1>/tags` / Then `[{"tag":"bug","task_count":1}]` | http | must |
| T2.10 | T2 | No tasks or untagged only → `[]` | happy | Given P with no tasks / When list / Then 200 `{"items": []}` | http | must |
| T2.11 | T2 | No tasks or untagged only → `[]` | happy | Given P with 2 untagged tasks / When list / Then 200 `{"items": []}` | http | must |
| T2.12 | T2 | 404 missing or deleted project | error | When `GET /projects/999/tags` / Then 404 `project 999 not found` | http | must |
| T2.13 | T2 | 404 missing or deleted project | error | Given P with a `[bug]` task, then `DELETE /projects/<P>` / When `GET /projects/<P>/tags` / Then 404 `project <P> not found` | http | must |
| T3.1 | T3 | Remove `bug`: response and remaining tags | happy | Given A `[bug, ui]`, B `[bug]`, C `[ui]` in P / When `DELETE /projects/<P>/tags/bug` / Then 200 `{"tag":"bug","removed_from":2}`; A.tags `["ui"]`, B.tags `[]`, C.tags `["ui"]` | http | must |
| T3.2 | T3 | Remove `bug`: response and remaining tags | edge | Same / Then response keys == {tag, removed_from}; `GET /projects/<P>/tags` == `[{"tag":"ui","task_count":2}]`; `GET /tasks?tag=bug&project_id=<P>` total 0 | http | should |
| T3.3 | T3 | Remove `bug`: response and remaining tags | edge | Given A `[bug]` todo, B `[bug]` done / When DELETE bug / Then `removed_from` 2; both have `[]` | http | should |
| T3.4 | T3 | A, B `updated_at` = now; C unchanged | happy | Given `_now` monkeypatched to `2026-10-30T09:00:00` while creating A, B, C, then `10:00:00` / When DELETE bug / Then A, B `updated_at` == `2026-10-30T10:00:00`; C == `09:00:00` | http | must |
| T3.5 | T3 | A, B `updated_at` = now; C unchanged | edge | Same / Then `created_at` of A, B, C unchanged | http | should |
| T3.6 | T3 | Other project's task keeps the tag | happy | Given P: A `[bug]`; Q: X `[bug]` (`_now` stepped as T3.4) / When `DELETE /projects/<P>/tags/bug` / Then X.tags == `["bug"]`, X.updated_at unchanged, `GET /projects/<Q>/tags` == `[{"tag":"bug","task_count":1}]` | http | must |
| T3.7 | T3 | Soft-deleted task keeps its `task_tags` row | happy | Given P: A `[bug]` live, D `[bug]` soft-deleted / When DELETE bug / Then `removed_from` 1; via the `app` fixture DB, row `(D, 'bug')` exists and D's `updated_at` is unchanged | integration | must |
| T3.8 | T3 | `Bug` / `%20bug%20` normalised | happy | Given A `[bug]` / When `DELETE /projects/<P>/tags/Bug` / Then 200 `{"tag":"bug","removed_from":1}`; A.tags `[]` | http | must |
| T3.9 | T3 | `Bug` / `%20bug%20` normalised | happy | Given A `[bug]` / When `DELETE /projects/<P>/tags/%20bug%20` / Then 200 `{"tag":"bug","removed_from":1}` | http | must |
| T3.10 | T3 | `Bug` / `%20bug%20` normalised | edge | Given A `[foo bar, foobar]` / When `DELETE /projects/<P>/tags/foo%20bar` / Then `{"tag":"foo bar","removed_from":1}`; A.tags `["foobar"]` | http | should |
| T3.11 | T3 | `ui%2Fux` removes `ui/ux` | happy | Given A `[ui/ux, ui, ux]` / When `DELETE /projects/<P>/tags/ui%2Fux` / Then 200 `{"tag":"ui/ux","removed_from":1}`; A.tags `["ui", "ux"]` | http | must |
| T3.12 | T3 | `ui%2Fux` removes `ui/ux` | edge | Given A `[ui/ux]` / When `DELETE /projects/<P>/tags/ui/ux` (unencoded) / Then 200 `{"tag":"ui/ux","removed_from":1}` | http | should |
| T3.13 | T3 | `ui%2Fux` removes `ui/ux` | edge | Given A `[bug]`, B `[bug/]` / When `DELETE /projects/<P>/tags/bug/` / Then `{"tag":"bug/","removed_from":1}`; A.tags `["bug"]` | http | should |
| T3.14 | T3 | Retry → 404 | error | Given A `[bug]`; first `DELETE /projects/<P>/tags/bug` returns 200 / When the same DELETE again / Then 404 `tag bug not found in project <P numeric id>` | http | must |
| T3.15 | T3 | Tag only on deleted tasks → 404 | error | Given P: D `[bug]` soft-deleted, A `[ui]` live / When DELETE bug / Then 404 `tag bug not found in project <P>`; DB row `(D, 'bug')` still present | integration | must |
| T3.16 | T3 | Tag only in another project → 404 | edge | Given `bug` only on a task of project Q / When `DELETE /projects/<P>/tags/bug` / Then 404 `tag bug not found in project <P>`; Q's task keeps `["bug"]` | http | should |
| T3.17 | T3 | Unknown tag → 404 with normalised tag | edge | Given P with no tasks / When `DELETE /projects/<P>/tags/%20NoPe%20` / Then 404 `tag nope not found in project <P>` (normalised in message) | http | should |
| T3.18 | T3 | `%20` → 400 | error | Given live P / When `DELETE /projects/<P>/tags/%20` / Then 400 `tag must not be empty` | http | must |
| T3.19 | T3 | `%20` → 400 | edge | When `DELETE /projects/<P>/tags/%20%09%20` / Then 400 `tag must not be empty` | http | should |
| T3.20 | T3 | 404 missing or deleted project | error | When `DELETE /projects/999/tags/bug` / Then 404 `project 999 not found` | http | must |
| T3.21 | T3 | 404 missing or deleted project | error | Given P with A `[bug]`, then `DELETE /projects/<P>` / When `DELETE /projects/<P>/tags/bug` / Then 404 `project <P> not found`; DB row `(A, 'bug')` still present | integration | must |
| T3.22 | T3 | Project checked before tag | error | When `DELETE /projects/999/tags/%20` / Then 404 `project 999 not found` (not 400) | http | must |
| T3.23 | T3 | Project checked before tag | edge | Given soft-deleted project P / When `DELETE /projects/<P>/tags/%20` / Then 404 `project <P> not found` | http | should |
| T3.24 | T3 | Project `updated_at` unchanged | happy | Given `_now` at `09:00:00` when creating P and A `[bug]`, then `10:00:00` / When DELETE bug (200) / Then `GET /projects/<P>` `updated_at` equals its value before | http | must |
| T3.25 | T3 | Project `updated_at` unchanged | edge | Given A `[ui]` with stepped `_now` / When `DELETE .../tags/bug` (404) and `.../tags/%20` (400) / Then A.tags, A.updated_at and project `updated_at` unchanged | http | should |
