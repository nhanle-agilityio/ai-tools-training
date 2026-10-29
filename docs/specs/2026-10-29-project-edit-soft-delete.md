# Edit and soft-delete projects

- **Status:** draft
- **Date:** 2026-10-29
- **Slug:** `project-edit-soft-delete`

## Problem

A project can be created and read, but never changed or removed. A typo in a project name stays
forever, and a finished project keeps showing up in `GET /projects`. Tasks can be deleted, but only
with a hard `DELETE` that loses the row for good. Today there is no `PATCH` or `DELETE` on
`/projects/<id>`, the `projects` table has no `updated_at`, and `DELETE /tasks/<id>` removes the row.

## Goals

- A client can rename a project or change its description with `PATCH /projects/<id>`.
- A client can delete a project with `DELETE /projects/<id>`; the project and its tasks disappear
  from every endpoint but stay in the database.
- `DELETE /tasks/<id>` becomes a soft delete with the same visibility rules.
- A deleted project's name can be reused by a new project.
- Duplicate project names return `409 Conflict` on both create and edit.

## Non-goals

- Restoring a deleted project or task (no restore endpoint). Deferred: no user need yet.
- Listing or reading deleted projects or tasks. Deferred with restore.
- Purging soft-deleted rows. Deferred: data volume is small.
- `PUT /projects/<id>` (full replace). `PATCH` covers the need.
- A migration script. The schema has no migration tooling; local databases are reset with `make seed`.
- Browser verification. TaskBoard is an HTTP API with no UI, so every task is verified over HTTP only.

## Decisions

| Question | Decision | Why |
| --- | --- | --- |
| Edit method | `PATCH /projects/<id>`, partial update | Same pattern as `PATCH /tasks/<id>` |
| Editable fields | `name`, `description` only | `id` and timestamps are system-owned |
| PATCH body rules | Non-object body: 400. Unknown keys (incl. `id`, `created_at`): ignored. `{}`: 200 | Same as `PATCH /tasks/<id>` |
| `updated_at` on projects | Add it. Equals `created_at` on create; set to now on every successful PATCH; returned in responses | Clients can see when a project last changed |
| Duplicate name | `409 Conflict` on create and edit; renaming to the project's own name is allowed; compared case-sensitively after `strip()` | 409 describes a state conflict, not bad input |
| Existing create duplicate test | Changes from 400 to 409 | New requirement, applied consistently |
| Conflict error type | New `ConflictError`, mapped to 409 in `__init__.py` | Same pattern as `ValidationError` / `NotFoundError` |
| Project delete | Soft delete; also soft-deletes the project's live tasks with the same timestamp, in one transaction | Keeps data recoverable later; no half-deleted state |
| Soft-delete storage | `deleted_at TEXT NULL` (ISO timestamp) on `projects` and `tasks` | Records when, not only whether |
| `deleted_at` in responses | Never returned | Visible resources always have `null` |
| Deleted project visibility | `GET` / `PATCH` / `DELETE` / `stats` return 404; absent from `GET /projects`; `POST /tasks` with its id returns 404 | Behaves as if it does not exist |
| Task delete | `DELETE /tasks/<id>` becomes a soft delete, still 204 | One consistent delete model |
| Deleted task visibility | `GET` / `PATCH` / `DELETE` return 404; absent from `GET /tasks` (incl. `pagination.total`), `GET /tasks/overdue` and project stats; `updated_at` and tags unchanged | Behaves as if it does not exist |
| Name of a deleted project | Freed: column `UNIQUE` replaced by a partial unique index on live rows | Users can recreate a project with the same name |
| Migration | Edit `schema.sql` only; reset local DBs with `make seed` | No migration tooling in the repo |
| Verification | `needs-e2e = no`; HTTP checks only | No UI |

## Design

### API contracts

**`POST /projects`** (changed)

- Duplicate live name: `409 {"error": "a project with this name already exists"}` (was 400).
- `201` response gains `updated_at`, equal to `created_at`.

**`GET /projects`, `GET /projects/<id>`, `GET /projects/<id>/stats`** (changed)

- Soft-deleted projects are excluded or return 404.
- Project objects include `updated_at`, never `deleted_at`.
- Stats count only live tasks.

**`PATCH /projects/<id>`** (new)

Request (all keys optional):

```json
{ "name": "New name", "description": "New description" }
```

Response `200`: the full project object.

```json
{ "id": 1, "name": "New name", "description": "New description",
  "created_at": "2026-10-29T09:00:00", "updated_at": "2026-10-29T10:15:00" }
```

Errors:

| Case | Status | Body `error` |
| --- | --- | --- |
| Project missing or deleted | 404 | `project <id> not found` |
| Body not a JSON object | 400 | `request body must be a JSON object` |
| `name` empty, blank or not a string | 400 | `name is required` |
| `description` not a string | 400 | `description must be a string` |
| `name` (stripped) equals another live project's name | 409 | `a project with this name already exists` |

**`DELETE /projects/<id>`** (new)

- `204`, empty body. Sets `deleted_at` on the project and on all its live tasks.
- Project missing or already deleted: `404 project <id> not found`.

**`DELETE /tasks/<id>`** (changed)

- Still `204`. Sets `deleted_at` instead of removing the row; tags stay.
- Task missing or already deleted: `404 task <id> not found`.

**`GET /tasks`, `GET /tasks/<id>`, `PATCH /tasks/<id>`, `GET /tasks/overdue`** (changed)

- Soft-deleted tasks are excluded (also from `pagination.total`) or return 404.
- Task objects never include `deleted_at`.

**`POST /tasks`** (changed)

- `project_id` of a deleted project: `404 project <id> not found`.

### Data model

`taskboard/schema.sql`:

```sql
CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);

CREATE UNIQUE INDEX idx_projects_live_name ON projects (name) WHERE deleted_at IS NULL;

-- tasks gains:
    deleted_at TEXT
```

- `ON DELETE CASCADE` stays; it only matters for hard deletes, which the API no longer does.
- No migration: run `make seed` (or `flask --app taskboard init-db`) after pulling.
- Every repository read of projects or tasks filters `deleted_at IS NULL`, including the duplicate
  name lookup, `count_tasks_by_status`, `list_tasks`, and `list_open_tasks_with_due_date`.
- `deleted_at` is removed from rows in `services` before they reach the client
  (`get_project`, `list_projects`, `_serialize_tasks`).

### Other areas

- `errors.py`: add `ConflictError`. `__init__.py`: handler returns `409 {"error": ...}`.
- Layering per `CLAUDE.md`: routes → services → repository; validation in `validators.py`.

## Risks and unknowns

- **Local data reset.** Pulling the schema change requires `make seed`, which wipes local data.
  Mitigation: stated here and in the T1 PR.
- **A read path that misses the `deleted_at` filter** would leak deleted rows. Mitigation: T4 and T5
  each test every listed endpoint after a delete.
- **Partial cascade.** If the task update ran without the project update, tasks would vanish under a
  live project. Mitigation: both updates share one transaction and one commit (T5).
- **Behaviour change for clients.** Duplicate create moves from 400 to 409. Mitigation: stated in the
  T2 PR.

## Tasks

| Id | Title | Type | Area | Depends on | Size | Needs e2e |
| --- | --- | --- | --- | --- | --- | --- |
| T1 | Add updated_at and deleted_at columns to the schema | feat | data | - | S | no |
| T2 | Return 409 for duplicate project names | feat | backend | - | S | no |
| T3 | Edit a project with PATCH /projects/{id} | feat | backend | T1, T2 | M | no |
| T4 | Soft-delete tasks | feat | backend | T1 | M | no |
| T5 | Soft-delete a project and its tasks | feat | backend | T1, T4 | M | no |

### T1: Add updated_at and deleted_at columns to the schema

- **Type:** feat
- **Area:** data
- **Depends on:** none
- **Size:** S
- **Needs e2e:** no

**Acceptance criteria**

- [ ] `POST /projects {"name": "A"}` returns 201 with `updated_at` equal to `created_at`.
- [ ] `GET /projects/<id>` and `GET /projects` return `updated_at` and no `deleted_at` key.
- [ ] `POST /tasks` and `GET /tasks/<id>` responses contain no `deleted_at` key.
- [ ] `projects.name` uniqueness is enforced by a partial unique index on rows where `deleted_at IS NULL`.
- [ ] `make seed` runs without errors on the new schema.

**Scope**

- `taskboard/schema.sql`, `taskboard/repository.py` (insert project), `taskboard/services.py`
  (hide `deleted_at`), `tests/test_projects.py`, `tests/test_tasks.py`.

**Test plan**

- HTTP tests on create and read responses for projects and tasks (keys and `updated_at == created_at`).
- Run `make seed` once.

### T2: Return 409 for duplicate project names

- **Type:** feat
- **Area:** backend
- **Depends on:** none
- **Size:** S
- **Needs e2e:** no

**Acceptance criteria**

- [ ] `POST /projects` with the name of an existing project returns `409 {"error": "a project with this name already exists"}`.
- [ ] `POST /projects` with `"  Demo  "` when `Demo` exists returns 409.
- [ ] Other validation errors on `POST /projects` still return 400.

**Scope**

- `taskboard/errors.py` (`ConflictError`), `taskboard/__init__.py` (409 handler), `taskboard/services.py`
  (`create_project`), `tests/test_projects.py` (update the existing duplicate test from 400 to 409).

**Test plan**

- Change the existing duplicate-name test to expect 409 (failing first), add the stripped-name case.

### T3: Edit a project with PATCH /projects/{id}

- **Type:** feat
- **Area:** backend
- **Depends on:** T1, T2
- **Size:** M
- **Needs e2e:** no

**Acceptance criteria**

- [ ] `PATCH /projects/<id> {"name": "New"}` returns 200 with `name` `New`, `description` unchanged, and `updated_at` set to the request time.
- [ ] `PATCH /projects/<id> {"description": "D"}` returns 200 with `description` `D`, `name` unchanged.
- [ ] `PATCH /projects/<id> {"name": "  New  "}` stores `New`.
- [ ] `PATCH /projects/<id> {}` returns 200 with the same `name` and `description`; `updated_at` is set to now.
- [ ] `PATCH /projects/<id> {"id": 99, "created_at": "x"}` returns 200 and `id` / `created_at` are unchanged.
- [ ] `PATCH /projects/<id>` with `{"name": ""}`, `{"name": "  "}` or `{"name": 5}` returns `400 name is required`.
- [ ] `PATCH /projects/<id> {"description": 5}` returns `400 description must be a string`.
- [ ] `PATCH /projects/<id>` with a non-object JSON body (e.g. `[]`) returns `400 request body must be a JSON object`.
- [ ] `PATCH /projects/<id>` with the name of another project returns `409 a project with this name already exists`.
- [ ] `PATCH /projects/<id>` with the project's own current name returns 200.
- [ ] `PATCH /projects/999` returns `404 project 999 not found`.

**Scope**

- `taskboard/routes.py`, `taskboard/services.py`, `taskboard/repository.py`, `taskboard/validators.py`,
  `tests/test_projects.py`.

**Test plan**

- HTTP tests for each criterion. Freeze `datetime` with `monkeypatch` to assert `updated_at` changes.

### T4: Soft-delete tasks

- **Type:** feat
- **Area:** backend
- **Depends on:** T1
- **Size:** M
- **Needs e2e:** no

**Acceptance criteria**

- [ ] `DELETE /tasks/<id>` returns 204 and the row stays in `tasks` with `deleted_at` set; its tags stay in `task_tags`.
- [ ] After the delete, `GET /tasks/<id>`, `PATCH /tasks/<id>` and `DELETE /tasks/<id>` return `404 task <id> not found`.
- [ ] After the delete, `GET /tasks` does not list the task and `pagination.total` excludes it.
- [ ] After deleting an overdue task, `GET /tasks/overdue` does not list it.
- [ ] After the delete, `GET /projects/<id>/stats` `total` and `by_status` exclude it.

**Scope**

- `taskboard/repository.py` (task delete and every task read), `taskboard/services.py`, `tests/test_tasks.py`,
  `tests/test_projects.py` (stats).

**Test plan**

- HTTP tests for each endpoint after a delete. Check the row and tags still exist via the `app`
  fixture's database connection.

### T5: Soft-delete a project and its tasks

- **Type:** feat
- **Area:** backend
- **Depends on:** T1, T4
- **Size:** M
- **Needs e2e:** no

**Acceptance criteria**

- [ ] `DELETE /projects/<id>` returns 204; the project row and all its live task rows get the same `deleted_at`, written in one commit.
- [ ] A task of that project deleted earlier keeps its original `deleted_at`.
- [ ] After the delete, `GET /projects/<id>`, `PATCH /projects/<id>`, `DELETE /projects/<id>` and `GET /projects/<id>/stats` return `404 project <id> not found`.
- [ ] After the delete, `GET /projects` does not list the project.
- [ ] After the delete, the project's tasks return 404 on `GET /tasks/<id>` and are absent from `GET /tasks` and `GET /tasks/overdue`.
- [ ] After the delete, `POST /tasks` with that `project_id` returns `404 project <id> not found`.
- [ ] After the delete, `POST /projects` with the deleted project's name returns 201.
- [ ] `DELETE /projects/999` returns `404 project 999 not found`.

**Scope**

- `taskboard/routes.py`, `taskboard/services.py`, `taskboard/repository.py` (project delete and every
  project read), `tests/test_projects.py`.

**Test plan**

- HTTP tests for each criterion; check `deleted_at` values via the `app` fixture's database connection.
