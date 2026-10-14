# TaskBoard — Claude training app

A small task management REST API (project → task → tag) built with Python, Flask and SQLite. It is the practice app for the 15-day Claude training program. The code intentionally contains a few real bugs for practicing the ticket → fix → MR → review workflow.

> Training-only repository. It contains no client code.

## Requirements

- Python 3.10+ (the Makefile defaults to `python3.12`; override with `make setup PYTHON=python3.11`)

## Quick start

```bash
make setup   # create .venv and install dependencies
make test    # run pytest
make seed    # reset the DB (instance/taskboard.sqlite) and load demo data
make run     # start the server at http://127.0.0.1:5050
```

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
| GET | `/projects/<id>/stats` | Task counts by status and `completion_rate` |
| GET | `/tasks` | List tasks. Query params: `project_id`, `status`, `q` (search), `sort` (`created_at` \| `due_date` \| `priority`), `page`, `per_page` (max 50) |
| POST | `/tasks` | Create a task `{project_id, title, description?, status?, priority?, due_date?, tags?}` |
| GET | `/tasks/overdue` | Open tasks past their due date |
| GET | `/tasks/<id>` | Get a task |
| PATCH | `/tasks/<id>` | Partially update a task |
| DELETE | `/tasks/<id>` | Delete a task |

Allowed values: `status` ∈ `todo, in_progress, done`; `priority` ∈ `low, medium, high`; `due_date` is `YYYY-MM-DD`.

Errors are returned as `{"error": "..."}` with status 400 (invalid input) or 404 (not found).

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
tests/            # pytest; each test uses a temporary database
docs/tickets/     # ticket backlog
```
