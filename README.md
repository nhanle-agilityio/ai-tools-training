# TaskBoard — Claude training app

A small task management REST API (project → task → tag) built with Python, Flask and SQLite. It is the practice app for the 15-day Claude training program. The code intentionally contains a few real bugs for practicing the ticket → fix → MR → review workflow.

> Training-only repository. It contains no client code.

## Requirements

- Python 3.10+ (the Makefile defaults to `python3.12`; override with `make setup PYTHON=python3.11`)

## Quick start

```bash
make setup   # create .venv and install dependencies
make test    # run pytest
make lint    # ruff check and format check (read-only, same as CI)
make fmt     # apply ruff fixes and format, then re-check
make seed    # reset the DB (instance/taskboard.sqlite) and load demo data
make run     # start the server at http://127.0.0.1:5050
make serve   # run under gunicorn on 0.0.0.0:$PORT (default 5050); macOS/Linux only
```

### Configuration

| Variable | Default | Description |
| --- | --- | --- |
| `DATABASE` | `instance/taskboard.sqlite` | Path of the SQLite file. Use a plain absolute or relative path: no `~`, no `$HOME`, no `file:` URI. Missing tables are created on startup; existing tables and data are left untouched. |
| `PORT` | `5050` | Port gunicorn listens on (read by `gunicorn.conf.py`, bound to `0.0.0.0`). Used by `make serve` and on Railway. |

Try the API:

```bash
curl -s localhost:5050/projects | python3 -m json.tool
curl -s "localhost:5050/tasks?project_id=1&per_page=5" | python3 -m json.tool
curl -s -X PATCH localhost:5050/tasks/1 -H 'Content-Type: application/json' -d '{"status":"done"}'
```

## API

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | Health check |
| GET | `/projects` | List projects |
| POST | `/projects` | Create a project `{name, description?}` |
| GET | `/projects/<id>` | Get a project |
| GET | `/projects/<id>/stats` | Project task stats: `project_id`, `total`, `by_status`, `by_priority`, `overdue`, `completion_rate`, `in_progress_rate` |
| GET | `/stats` | Summary across active projects: `projects`, `total`, `by_status`, `overdue`, `top_tags` |
| GET | `/tasks` | List tasks. Query params: `project_id`, `status`, `q` (search), `sort` (`created_at` \| `due_date` \| `priority` \| `comments`), `page`, `per_page` (max 50) |
| POST | `/tasks` | Create a task `{project_id, title, description?, status?, priority?, due_date?, tags?}` |
| GET | `/tasks/overdue` | Open tasks past their due date |
| GET | `/tasks/<id>` | Get a task |
| PATCH | `/tasks/<id>` | Partially update a task |
| DELETE | `/tasks/<id>` | Delete a task |

Allowed values: `status` ∈ `todo, in_progress, done`; `priority` ∈ `low, medium, high`; `due_date` is `YYYY-MM-DD`.

Errors are returned as `{"error": "..."}` with status 400 (invalid input) or 404 (not found).

### Stats endpoints

`GET /projects/<id>/stats` (numbers are illustrative):

```json
{
  "project_id": 1,
  "total": 8,
  "by_status": { "todo": 3, "in_progress": 2, "done": 3 },
  "by_priority": { "low": 2, "medium": 4, "high": 2 },
  "overdue": 1,
  "completion_rate": 37.5,
  "in_progress_rate": 25.0
}
```

`GET /stats` (no parameters; numbers are illustrative):

```json
{
  "projects": 2,
  "total": 14,
  "by_status": { "todo": 6, "in_progress": 4, "done": 4 },
  "overdue": 3,
  "top_tags": [
    { "tag": "backend", "task_count": 5 },
    { "tag": "bug", "task_count": 5 },
    { "tag": "docs", "task_count": 2 }
  ]
}
```

- Overdue: a task that is not `done` and has a `due_date` before today (a task due today is not overdue). It is the same rule as `GET /tasks/overdue`.
- `completion_rate` and `in_progress_rate` are percentages of `total` (`0` when there are no tasks).
- `top_tags` counts tasks in active projects that carry the tag, ordered by `task_count` descending then `tag` ascending, at most 5 items (`[]` when there are none).

## Deploy to Railway

The repo carries the Railway config, so no build or start settings are needed in the dashboard.

1. Create a Railway service from this repo. `railway.json` sets the start command `gunicorn "taskboard:create_app()"` (the same command as `make serve`, without the `.venv/bin/` prefix), the health check path `/health`, and the restart policy `ON_FAILURE`. `.python-version` pins Python `3.12`.
2. Add a volume to the service and mount it at `/data`. The container filesystem is reset on every deploy, so without a volume the data is lost.
3. In the service variables, set `DATABASE=/data/taskboard.sqlite`.
4. Do not set `PORT`: Railway sets it, and `gunicorn.conf.py` binds `0.0.0.0:$PORT` (locally it falls back to `5050`).
5. Deploy. Railway calls `GET /health` (returns `200 {"status": "ok"}`) to check the service.

Tables and indexes are created on first start. Existing tables and their data are never touched, so redeploys keep your data.

### Optional: load demo data

> **WARNING: seeding deletes all existing data in the database.** Run it only on a new or disposable database.

```bash
railway ssh
flask --app taskboard seed
```

### Recovery: `no such column` on an old database

If the app fails to start with `no such column` because the database file has an old column layout, `flask init-db` and `flask seed` do not help: they go through the same startup and fail the same way. Column migrations are not supported.

> **WARNING: this loses the data in the old file.** The new file starts empty and nothing is migrated.

1. In the Railway service variables, set `DATABASE` to a new file, for example `DATABASE=/data/taskboard-v2.sqlite`.
2. Redeploy. No running container is needed. The app starts with empty tables.
3. Optional, once the service is healthy: run `railway ssh`, then `rm /data/taskboard.sqlite` to remove the old file.

## Project layout

```text
taskboard/
  __init__.py     # app factory, error handlers
  routes.py       # HTTP layer: parse the request, call services
  services.py     # business logic
  repository.py   # SQL queries
  validators.py   # input validation
  db.py           # SQLite connection and CLI commands (init-db, seed)
  schema.sql
  seed.py         # demo data
railway.json      # Railway start command, health check, restart policy
gunicorn.conf.py  # gunicorn bind ($PORT, default 5050), workers, preload
.python-version   # Python 3.12 for Railway
tests/            # pytest; each test uses a temporary database
docs/tickets/     # ticket backlog
```
