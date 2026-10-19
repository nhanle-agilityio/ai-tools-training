# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repository is

TaskBoard is a small task-management REST API (project → task → tag) built with Flask + SQLite. It is the **practice app for a 15-day Claude training program**, not production or client code. The codebase **intentionally contains a few real bugs** so trainees can practice the full workflow: ticket → reproduce → fix on a branch → PR → review → resolve conflicts → merge. Bug tickets live in `docs/tickets/` (TB-101…TB-106).

When asked to "fix" something, first check whether it maps to a ticket in `docs/tickets/` — the ticket is the source of truth for expected behavior.

## Commands

All commands go through the Makefile (which drives a `.venv`):

```bash
make setup                     # create .venv and install requirements (override: make setup PYTHON=python3.11)
make test                      # run the full pytest suite
make seed                      # reset instance/taskboard.sqlite and load demo data
make run                       # serve at http://127.0.0.1:5050 (flask --debug)
make clean                     # remove .venv, instance/, .pytest_cache
```

Direct tooling (useful for narrower loops):

```bash
.venv/bin/pytest tests/test_tasks.py                          # one test file
.venv/bin/pytest tests/test_tasks.py::test_name              # one test
.venv/bin/pytest -k overdue                                   # tests matching a keyword
.venv/bin/flask --app taskboard init-db                      # drop + recreate tables (no demo data)
.venv/bin/ruff format .                                       # format the whole tree
.venv/bin/ruff check .                                        # lint
```

There is no separate build step — it's a pure-Python app run via the Flask CLI.

## Architecture

The app uses the **Flask application-factory pattern** and a strict one-way layering. A request always flows down these layers and never skips one:

```
routes.py      HTTP only: read request args/body, call a service, jsonify the result
   ↓
services.py    business logic + orchestration; the ONLY layer that calls validators
   ↓
validators.py  pure input validation; raises ValidationError
repository.py  all SQL lives here; returns sqlite3.Row objects, never dicts of business logic
   ↓
db.py          per-request SQLite connection
```

Key things that require reading several files to understand:

- **App wiring** — `create_app()` in `taskboard/__init__.py` builds the app, registers the `routes.py` blueprint, wires `db.init_app`, and registers the two error handlers that turn exceptions into JSON. `/health` is defined inline here, not in the blueprint.

- **Error model is exception-driven.** Services and validators raise `ValidationError` / `NotFoundError` (defined in `errors.py`). They are *never* caught in routes — the handlers registered in `__init__.py` map them to `{"error": ...}` with HTTP **400** and **404** respectively. To signal a bad request from anywhere below the route, raise `ValidationError`; don't build an error response by hand.

- **Database lifecycle.** `db.get_db()` lazily opens one `sqlite3` connection per request, stores it on Flask's `g`, sets `row_factory = sqlite3.Row` and enables `PRAGMA foreign_keys = ON`. `init_app` registers a teardown that closes it. Rows are `sqlite3.Row`; convert with `dict(row)` at the service boundary. `init-db` and `seed` are Flask CLI commands added in `db.py`, backed by `schema.sql` and `seed.py`.

- **Task serialization is centralized.** `services._serialize_tasks` is the single place that attaches `tags` (batch-fetched via `repository.get_tags` to avoid N+1) and the computed `is_overdue` flag onto task rows. Any new read path that returns tasks should go through it so the shape stays consistent.

- **Overdue is computed, not stored.** `is_overdue` compares ISO-8601 strings; a task is overdue only if it has a `due_date`, is past it, and is not `done`. `list_overdue_tasks` filters in Python after the repository narrows to open tasks with a due date.

- **Allowed values & sorting are defined once.** `VALID_STATUSES`/priority live in `validators.py`; sortable columns are `repository.SORT_CLAUSES`. `list_tasks` validates `sort` against that dict rather than interpolating user input into SQL.

## Testing conventions

Tests use the real app through Flask's test client against a **fresh temporary SQLite file per test** (`conftest.py` `app` fixture + `tmp_path`). Prefer exercising behavior through the HTTP layer via the `client`, `project`, and `make_task` fixtures rather than calling services directly — that is the established pattern in `tests/`.

## Workflow conventions

- **Commits/PRs are in English and follow Conventional Commits** (`type(scope): subject`), where `scope` is the ticket id (e.g. `fix(TB-104): …`) or a module. A `commit-message` skill encodes this.
- A **ruff format hook** (`.claude/settings.json`, PostToolUse on Write|Edit) auto-formats `.py` files after every edit. Match ruff's output; don't hand-format against it.
- `docs/tickets/` (English) is the committed backlog.

## Model selection (token optimization)

Match the model to the work to minimize tokens — **plan & review on Opus, code on Sonnet, test on Haiku.**

| Phase | Model | Model ID |
| --- | --- | --- |
| Plan (analysis, root cause, design, conflicts) | Opus 5.5 | `claude-opus-5-5` |
| Code (implement the fix, PR text, routine edits) | Sonnet 5.5 | `claude-sonnet-5-5` |
| Review / advice (PR review, bug hunting, second opinion) | Opus 5.5 | `claude-opus-5-5` |
| Test (run/scaffold tests, search, pass/fail triage) | Haiku 5.5 | `claude-haiku-5-5` |

Opus 5.5's biggest capability gains are in **code review** and acting as a thought partner, so it's the model for the review/advice step as well as planning. Switch the main thread with `/model`; give subagents a cheaper `model` override (e.g. Haiku for search/test). Lower `effort` for simple tasks. This is a cost strategy only — move back up to Sonnet/Opus if a step turns into real debugging.
