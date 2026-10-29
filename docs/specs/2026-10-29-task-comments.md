# Comments on tasks

- **Status:** draft
- **Date:** 2026-10-29
- **Slug:** `task-comments`

## Problem

People working on a task have no place to leave notes, questions or progress updates. The only free
text on a task is `description`, which callers overwrite, so earlier text is lost and nobody can see who
wrote what or when. Today TaskBoard has no comment entity, no comment endpoints and no user model.

## Goals

- A client can add a comment to a live task, with an author label and a body.
- A client can list a task's comments in conversation order (oldest first).
- A client can read, edit (body only) and soft-delete a single comment.
- Every task returned by the API shows how many live comments it has (`comment_count`).
- Comments of a deleted task, or of a task in a deleted project, are unreachable.

## Non-goals

- Pagination of comments. Deferred: comment volume per task is small.
- Restoring a deleted comment, or listing deleted comments. Deferred, same as tasks and projects.
- Real users or authentication. `author` is a free-text label with no identity behind it.
- Threaded replies, mentions, reactions or attachments.
- Embedding the full comment list in task responses. Only `comment_count` is added.
- A migration script. Local databases are reset with `make seed`, as in earlier specs.
- Browser verification. TaskBoard is an HTTP API with no UI, so every task is verified over HTTP only.

## Decisions

| Question | Decision | Why |
| --- | --- | --- |
| Operations in scope | `POST` / `GET /tasks/<id>/comments`; `GET` / `PATCH` / `DELETE /comments/<id>` | Full lifecycle; flat item path mirrors `/tasks/<id>` |
| Author | Required string, stripped, 1-100 characters | No user model; a label is enough to tell writers apart |
| Body | Required string, stripped, 1-2000 characters; stripped value stored | Same rules as `validate_title`, with a longer limit |
| Order and pagination | Oldest first (`created_at ASC, id ASC`); no pagination; `{"items": [...]}` | Comments read as a conversation; volume is small |
| Embedding in tasks | Add `comment_count` (live comments) to every task from `_serialize_tasks`, loaded in one batched query | Cheap signal without bloating task responses; avoids N+1 |
| `task.updated_at` | Not touched by comment create, edit or delete | `updated_at` tracks the task's own fields |
| Deleted task or project | Comment routes behave as if the task does not exist (404); comments are not cascade-deleted, only hidden through the parent | Same visibility model as tasks under a deleted project |
| Comment delete | Soft delete with `deleted_at`; `204` | Same model as tasks and projects |
| PATCH rules | Only `body` is editable; unknown keys (incl. `author`, `task_id`, `id`, timestamps) are ignored; `{}` returns 200 and sets `updated_at` to now; non-object body is 400 | Same as `PATCH /tasks` and `PATCH /projects` |
| Response shape | `id, task_id, author, body, created_at, updated_at`; `updated_at == created_at` on create; never `deleted_at` | Matches the other resources |
| Verification | `needs-e2e = no`; HTTP checks only | No UI |

## Design

### API contracts

A comment object:

```json
{ "id": 1, "task_id": 7, "author": "Lan", "body": "Blocked on review.",
  "created_at": "2026-10-29T09:00:00", "updated_at": "2026-10-29T09:00:00" }
```

A comment is **visible** when its own `deleted_at` is null and its task is live (the task's
`deleted_at` is null; a deleted project already soft-deletes its tasks).

**`POST /tasks/<task_id>/comments`** (new)

Request:

```json
{ "author": "Lan", "body": "Blocked on review." }
```

Response `201`: the comment object.

| Case | Status | Body `error` |
| --- | --- | --- |
| Task missing or deleted | 404 | `task <id> not found` |
| Body not a JSON object | 400 | `request body must be a JSON object` |
| `author` missing, blank or not a string | 400 | `author is required` |
| `author` longer than 100 characters after strip | 400 | `author must be at most 100 characters` |
| `body` missing, blank or not a string | 400 | `body is required` |
| `body` longer than 2000 characters after strip | 400 | `body must be at most 2000 characters` |

The task check (404) runs before body validation, as in `update_task`.

**`GET /tasks/<task_id>/comments`** (new)

Response `200`: `{"items": [<comment>, ...]}`, visible comments only, ordered `created_at ASC, id ASC`.
A task with no comments returns `{"items": []}`. Task missing or deleted: `404 task <id> not found`.

**`GET /comments/<comment_id>`** (new)

Response `200`: the comment object. Not visible: `404 comment <id> not found`.

**`PATCH /comments/<comment_id>`** (new)

Request (all keys optional; only `body` is used):

```json
{ "body": "Review done." }
```

Response `200`: the comment object with `updated_at` set to now.

| Case | Status | Body `error` |
| --- | --- | --- |
| Comment not visible | 404 | `comment <id> not found` |
| Body not a JSON object | 400 | `request body must be a JSON object` |
| `body` blank or not a string | 400 | `body is required` |
| `body` longer than 2000 characters after strip | 400 | `body must be at most 2000 characters` |

The 404 check runs before body validation.

**`DELETE /comments/<comment_id>`** (new)

`204`, empty body; sets `deleted_at`. Not visible (incl. already deleted): `404 comment <id> not found`.

**Task responses** (changed: `POST /tasks`, `GET /tasks`, `GET /tasks/<id>`, `PATCH /tasks/<id>`,
`GET /tasks/overdue`)

Each task object gains `comment_count`: the number of its comments with `deleted_at` null.

### Data model

`taskboard/schema.sql` gains (and `DROP TABLE IF EXISTS task_comments;` at the top, before `tasks`):

```sql
CREATE TABLE task_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
    author TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);

CREATE INDEX idx_task_comments_task ON task_comments (task_id);
```

- No migration: run `make seed` after pulling.
- Single-comment reads join `tasks` and filter both `c.deleted_at IS NULL` and `t.deleted_at IS NULL`.
- `comment_count` is loaded for a list of task ids in one `GROUP BY task_id` query, like `get_tags`.
- `deleted_at` is removed in `services` with `_public` before a comment reaches the client.

### Other areas

- Layering per `CLAUDE.md`: routes → services → repository; validation in `validators.py`
  (`validate_new_comment`, `validate_comment_body`).
- Timestamps come from `services._now()`.

## Risks and unknowns

- **Local data reset.** The schema change needs `make seed`, which wipes local data. Mitigation: stated
  here and in the T1 PR.
- **Leaking comments of deleted tasks.** A comment read that does not join the task would expose
  comments under a deleted task or project. Mitigation: T3 and T4 test every comment route after a task
  delete and after a project delete.
- **N+1 on task lists.** Counting comments per task inside a loop would add one query per task.
  Mitigation: T5 requires one batched query.
- **`author` is not trusted.** Anyone can write any name. Accepted: no auth exists; stated as a non-goal.

## Tasks

| Id | Title | Type | Area | Depends on | Size | Needs e2e |
| --- | --- | --- | --- | --- | --- | --- |
| T1 | Add a comment to a task | feat | backend | - | M | no |
| T2 | List a task's comments | feat | backend | T1 | S | no |
| T3 | Read and edit a single comment | feat | backend | T1 | M | no |
| T4 | Soft-delete a comment | feat | backend | T2, T3 | S | no |
| T5 | Show comment_count on tasks | feat | backend | T1, T4 | S | no |

### T1: Add a comment to a task

- **Type:** feat
- **Area:** backend
- **Depends on:** none
- **Size:** M
- **Needs e2e:** no

**Acceptance criteria**

- [ ] `POST /tasks/<id>/comments {"author": "Lan", "body": "Hi"}` returns 201 with `id`, `task_id`, `author`, `body`, `created_at`, `updated_at`; `updated_at` equals `created_at`; no `deleted_at` key.
- [ ] `POST /tasks/<id>/comments {"author": "  Lan  ", "body": "  Hi  "}` stores and returns `Lan` and `Hi`.
- [ ] `author` missing, `""`, `"   "` or `5` returns `400 author is required`.
- [ ] `author` of 101 characters returns `400 author must be at most 100 characters`; 100 characters returns 201.
- [ ] `body` missing, `""`, `"   "` or `5` returns `400 body is required`.
- [ ] `body` of 2001 characters returns `400 body must be at most 2000 characters`; 2000 characters returns 201.
- [ ] A non-object JSON body (e.g. `[]`) returns `400 request body must be a JSON object`.
- [ ] `POST /tasks/999/comments` returns `404 task 999 not found`, also when the body is invalid.
- [ ] `POST` on a soft-deleted task, or on a task whose project was deleted, returns `404 task <id> not found`.
- [ ] The task's `updated_at` is unchanged after adding a comment.
- [ ] `make seed` runs without errors on the new schema.

**Scope**

- `taskboard/schema.sql`, `taskboard/repository.py`, `taskboard/services.py`, `taskboard/validators.py`,
  `taskboard/routes.py`, new `tests/test_comments.py` (a `make_comment` fixture may go in `tests/conftest.py`).

**Test plan**

- HTTP tests for each criterion in `tests/test_comments.py`. Run `make seed` once.

### T2: List a task's comments

- **Type:** feat
- **Area:** backend
- **Depends on:** T1
- **Size:** S
- **Needs e2e:** no

**Acceptance criteria**

- [ ] `GET /tasks/<id>/comments` on a task with no comments returns `200 {"items": []}`.
- [ ] With three comments created in order A, B, C, it returns them as A, B, C.
- [ ] Two comments with the same `created_at` are ordered by `id` ascending.
- [ ] Comments of another task are not listed.
- [ ] Returned items have no `deleted_at` key.
- [ ] `GET /tasks/999/comments` returns `404 task 999 not found`.
- [ ] After the task is soft-deleted, or its project is deleted, the request returns `404 task <id> not found`.

**Scope**

- `taskboard/routes.py`, `taskboard/services.py`, `taskboard/repository.py`, `tests/test_comments.py`.

**Test plan**

- HTTP tests for each criterion. Freeze `datetime` with `monkeypatch` for the same-timestamp case.

### T3: Read and edit a single comment

- **Type:** feat
- **Area:** backend
- **Depends on:** T1
- **Size:** M
- **Needs e2e:** no

**Acceptance criteria**

- [ ] `GET /comments/<id>` returns 200 with the comment object.
- [ ] `GET /comments/999` returns `404 comment 999 not found`.
- [ ] `PATCH /comments/<id> {"body": "New"}` returns 200 with `body` `New`, `author` unchanged and `updated_at` set to the request time.
- [ ] `PATCH /comments/<id> {"body": "  New  "}` stores `New`.
- [ ] `PATCH /comments/<id> {}` returns 200 with the same `body`; `updated_at` is set to now.
- [ ] `PATCH /comments/<id> {"author": "X", "task_id": 99, "id": 5, "created_at": "x"}` returns 200 and those fields are unchanged.
- [ ] `PATCH` with `{"body": ""}`, `{"body": "  "}` or `{"body": 5}` returns `400 body is required`.
- [ ] `PATCH` with a 2001-character `body` returns `400 body must be at most 2000 characters`.
- [ ] `PATCH` with a non-object JSON body returns `400 request body must be a JSON object`.
- [ ] `PATCH /comments/999` returns `404 comment 999 not found`, also when the body is invalid.
- [ ] After the comment's task is soft-deleted, or its project is deleted, `GET` and `PATCH /comments/<id>` return `404 comment <id> not found`.
- [ ] The task's `updated_at` is unchanged after editing a comment.

**Scope**

- `taskboard/routes.py`, `taskboard/services.py`, `taskboard/repository.py`, `taskboard/validators.py`,
  `tests/test_comments.py`.

**Test plan**

- HTTP tests for each criterion. Freeze `datetime` with `monkeypatch` to assert `updated_at` changes.

### T4: Soft-delete a comment

- **Type:** feat
- **Area:** backend
- **Depends on:** T2, T3
- **Size:** S
- **Needs e2e:** no

**Acceptance criteria**

- [ ] `DELETE /comments/<id>` returns 204 with an empty body; the row stays in `task_comments` with `deleted_at` set.
- [ ] After the delete, `GET`, `PATCH` and `DELETE /comments/<id>` return `404 comment <id> not found`.
- [ ] After the delete, `GET /tasks/<task_id>/comments` does not list it; other comments stay listed.
- [ ] `DELETE /comments/999` returns `404 comment 999 not found`.
- [ ] After the comment's task is soft-deleted, `DELETE /comments/<id>` returns `404 comment <id> not found`.
- [ ] The task's `updated_at` is unchanged after deleting a comment.

**Scope**

- `taskboard/routes.py`, `taskboard/services.py`, `taskboard/repository.py`, `tests/test_comments.py`.

**Test plan**

- HTTP tests for each criterion; check the row and `deleted_at` via the `app` fixture's database connection.

### T5: Show comment_count on tasks

- **Type:** feat
- **Area:** backend
- **Depends on:** T1, T4
- **Size:** S
- **Needs e2e:** no

**Acceptance criteria**

- [ ] `POST /tasks` returns `comment_count: 0`.
- [ ] After adding two comments, `GET /tasks/<id>` returns `comment_count: 2`.
- [ ] After deleting one of them, `GET /tasks/<id>` returns `comment_count: 1`.
- [ ] `GET /tasks`, `PATCH /tasks/<id>` and `GET /tasks/overdue` items include `comment_count` with the same values.
- [ ] In `GET /tasks`, each task's count includes only its own comments.
- [ ] Counts for a page of tasks are loaded with one query, not one per task.

**Scope**

- `taskboard/services.py` (`_serialize_tasks`), `taskboard/repository.py`, `tests/test_comments.py`
  (or `tests/test_tasks.py`).

**Test plan**

- HTTP tests for each criterion. For the single-query criterion, count `SELECT ... task_comments`
  statements with `sqlite3` `set_trace_callback` during one `GET /tasks` call.
