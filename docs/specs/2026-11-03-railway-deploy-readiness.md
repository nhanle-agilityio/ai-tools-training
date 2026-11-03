# Railway deploy readiness

- **Status:** draft
- **Date:** 2026-11-03
- **Slug:** `railway-deploy-readiness`

## Problem

TaskBoard can only run on a developer machine. Deploying it to Railway is not possible today without
manual hacks, and a naive deploy would lose or wipe data.

Current behaviour:

- `create_app()` hard-codes `DATABASE` to `<instance_path>/taskboard.sqlite`; only `test_config` can
  override it. There is no environment variable.
- `taskboard/schema.sql` starts with `DROP TABLE IF EXISTS ...` for every table. The schema is only created
  by `flask init-db` or `flask seed`, and both wipe all data. A fresh database has no tables, so every
  request fails until someone runs one of them.
- The only way to serve the app is `make run` (`flask run --debug`, the development server). gunicorn is not
  a dependency.
- `GET /health` exists and returns `200 {"status": "ok"}` without touching the database.
- There is no Railway configuration and no Python version pin (the Makefile defaults to `python3.12`).

## Goals

- The SQLite path comes from the `DATABASE` environment variable; the default is unchanged.
- On startup, missing tables and indexes are created; existing tables and their data are never touched.
- The app runs under gunicorn on `$PORT`, with the same command locally (`make serve`) and on Railway.
- The repo carries Railway config: start command, health check on `/health`, restart policy, Python 3.12.
- The README explains how to deploy to Railway, including a persistent volume.

## Non-goals

- Column-level migrations (adding a missing column to an existing table). Deferred: there is no migration
  tool and no current need. A database with an old column layout may fail to start (see Risks).
- A database check in `/health` (for example `SELECT 1` and `503` on failure). Deferred: `/health` stays as
  is; the request only asks for the health check to be wired to Railway.
- `DATABASE=:memory:`. Not supported: each connection would get its own empty database.
- Custom error handling at startup (unwritable directory, a directory or a corrupt file at the path): the
  underlying exception is raised and the process exits; Railway restarts it (`ON_FAILURE`).
- Safe concurrent first start of two processes without preload (e.g. `flask run` next to `make serve`).
- Seeding demo data automatically on Railway. Seeding wipes data; it stays a manual step.
- Changing what `flask init-db` / `flask seed` do: they still drop and recreate everything.
- Changing CI, the Railway builder, or adding a Procfile / Dockerfile. Windows support for `make serve`
  (gunicorn is POSIX only).

## Decisions

| Question | Decision | Why |
| --- | --- | --- |
| Partial schema (some tables exist, some missing) | Create each missing table and index; leave existing ones untouched. An existing index with the same name but another definition is kept | Older databases (e.g. without `task_comments`) keep their data and gain the new tables |
| How schema creation becomes non-destructive | Every `CREATE TABLE` / `CREATE INDEX` in `schema.sql` gets `IF NOT EXISTS`; the `DROP TABLE` statements move to a new `taskboard/drop.sql`. New `db.ensure_schema()` runs `schema.sql` only; `init_db()` runs `drop.sql` then `schema.sql` | One schema file stays the source of truth; reset commands keep their behaviour |
| Where `ensure_schema()` runs | In `create_app()`, inside `with app.app_context():`, every time an app is created (gunicorn, `flask run`, CLI, tests). The connection is closed when the context exits, before `create_app()` returns | Simple; a fresh clone works with `make run` without `init-db`; tests still call `init_db()` afterwards; no connection survives a gunicorn fork |
| `DATABASE` precedence | `test_config["DATABASE"]` > env `DATABASE` > default `<instance_path>/taskboard.sqlite` | Tests must stay isolated; production sets the env var |
| Whitespace in `DATABASE` | The value is stripped. Empty or whitespace-only is treated as unset (default path) | Avoids opening a database named `""` or with stray spaces |
| Relative `DATABASE` | Used as given (not rewritten to absolute), relative to the process working directory | Standard SQLite behaviour |
| Missing parent directory | Created on startup with `os.makedirs(..., exist_ok=True)` for the final configured path (any source); skipped when the path has no directory part (e.g. `rel.sqlite`) | A volume path like `/data/db/taskboard.sqlite` works without a manual mkdir |
| CLI commands and `DATABASE` | `flask init-db` and `flask seed` use the same `create_app()`, so they act on the env `DATABASE` file | The README's manual seed on Railway relies on it |
| gunicorn options | In `gunicorn.conf.py` (auto-loaded by gunicorn from the working directory): `bind = f"0.0.0.0:{os.environ.get('PORT') or '5050'}"`, `workers = 2`, `preload_app = True`, `accesslog = "-"`. Command: `gunicorn "taskboard:create_app()"` | No shell expansion needed in Railway's start command; empty `PORT` falls back to `5050`; preload runs `create_app()` (and `ensure_schema`) once before forking, so workers do not race; 2 sync workers suit SQLite |
| Invalid `PORT` or port in use | gunicorn's own error; nothing custom | Not worth custom handling |
| gunicorn version | `gunicorn==23.0.0` in `requirements.txt` | Exact pins like the other dependencies |
| Railway config format | `railway.json` with `$schema`, `deploy.startCommand: "gunicorn \"taskboard:create_app()\""`, `deploy.healthcheckPath: "/health"`, `deploy.restartPolicyType: "ON_FAILURE"`; no `build.builder` | JSON schema gives editor validation; the default builder reads `.python-version` |
| Python version | `.python-version` whose trimmed content is exactly `3.12` | Read by Railway's builders and by pyenv/uv locally |
| `/health` | Unchanged: `200 {"status": "ok"}` | See non-goals |
| Persistence on Railway | README: mount a volume at `/data` and set `DATABASE=/data/taskboard.sqlite` | Railway's container filesystem is reset on every deploy |
| Demo data on Railway | README documents a manual seed via `railway ssh` then `flask --app taskboard seed`, with a data-loss warning next to the command | Seeding is destructive; never automatic |
| Local gunicorn | New `make serve` target: `$(BIN)/gunicorn "taskboard:create_app()"` | Same command as Railway; lets developers and the verify stage run it |
| Testing the default path | Tests that create the app without `DATABASE` (T1.3-T1.5) check only `app.config["DATABASE"]` and stub schema creation with `monkeypatch.setattr("taskboard.db.ensure_schema", lambda: None, raising=False)` (`raising=False` so the test also runs before T2 adds the function) | No hook exists to move `instance_path`; without the stub the tests would write to, and depend on, the developer's real `instance/taskboard.sqlite` |
| Recovery from schema drift | No CLI recovery: `flask init-db` / `flask seed` also go through `create_app()`, so on a drifted database they fail in `ensure_schema()` before resetting. Documented manual recovery: delete the database file (on Railway: `railway ssh`, then `rm /data/taskboard.sqlite`) and restart; tables are recreated empty | Column migrations are a non-goal; keeping `ensure_schema()` unconditional keeps `create_app()` simple |
| Testing hidden rows | Rows the API hides (e.g. soft-deleted projects) are compared with raw SQL | Not visible through HTTP |
| Testing `make serve` | Not in pytest (port-bound, flaky in CI). Checked by hand in the verify stage, output pasted in the PR. pytest checks the static files only | Keeps CI fast and stable |
| Testing on Railway | The owner checks a real deploy after merge (health check passes, Python 3.12 used, app reachable). Not a merge gate | Cannot run Railway from the repo |
| Testing the README | Reviewer checklist; no automated test. "Match" means: the README names `railway.json` and `.python-version`, and its start command, `/health`, default port `5050` and Python `3.12` equal the config; `gunicorn.conf.py` need not be named, but anything said about it must be right | Wording needs human judgement |
| Testing "no connection left open" | After `create_app()` returns, an outside `sqlite3` connection can run `BEGIN EXCLUSIVE` on the file at once | Observable without spying on internals |
| Evidence for non-pytest criteria | "No existing test file modified": reviewer checks `git diff --name-only <base> -- tests/`. gunicorn version: static check of `requirements.txt` plus `gunicorn --version` in the verify stage. Worker count: exactly two `Booting worker` lines at startup | Cannot be asserted from inside pytest |
| `test_config={"DATABASE": ""}` | Not specified; only the env var is stripped and falls back | `test_config` is an internal test input |
| `~`, `$HOME`, `file:` URIs in `DATABASE` | Not supported; the value is used literally (no expansion, no URI mode). README says to use a plain absolute or relative path | Keep config reading trivial |
| Test naming | Tests for this spec are named `test_deploy_t<task>_<n>_<description>` | `tests/test_stats.py` already uses `test_t2_*` from another spec |
| `railway.json` key set | Exactly the listed keys; the test compares the whole object | No hidden settings |
| Shell `DATABASE` leaking into the existing suite | New tests `delenv`/`setenv` as needed; `conftest.py` is not changed (see Risks) | T1 must not modify existing test files |
| Odd partial layouts (e.g. `task_tags` without `tasks`) | No special handling; missing tables are created like any other case; no dedicated test | Same rule covers it |
| Task split | T1 env var, T2 non-destructive schema, T3 gunicorn + Railway config + `make serve`, T4 README | Small, separately reviewable; T2 is the only high-risk change |

## Design

### API contracts

No endpoint changes. `GET /health` keeps returning `200 {"status": "ok"}`.

### Data model

No new tables or columns. `taskboard/schema.sql` changes form only:

```sql
CREATE TABLE IF NOT EXISTS projects (...);          -- same columns as today
CREATE TABLE IF NOT EXISTS tasks (...);
CREATE TABLE IF NOT EXISTS task_tags (...);
CREATE TABLE IF NOT EXISTS task_comments (...);
CREATE UNIQUE INDEX IF NOT EXISTS idx_projects_live_name ON projects (name) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks (project_id);
CREATE INDEX IF NOT EXISTS idx_task_comments_task ON task_comments (task_id);
```

New `taskboard/drop.sql` holds the four `DROP TABLE IF EXISTS` statements in today's order:
`task_comments`, `task_tags`, `tasks`, `projects`.

`taskboard/db.py`:

- `ensure_schema()`: runs `schema.sql` on the current connection. Never drops or deletes anything.
- `init_db()`: runs `drop.sql`, then `schema.sql`. Behaviour of `flask init-db` and `flask seed` is unchanged.

### Other areas

**Configuration (`taskboard/__init__.py`)**

```python
database = (os.environ.get("DATABASE") or "").strip() or os.path.join(app.instance_path, "taskboard.sqlite")
app.config.from_mapping(DATABASE=database, ...)
if test_config is not None:
    app.config.update(test_config)
os.makedirs(app.instance_path, exist_ok=True)
parent = os.path.dirname(app.config["DATABASE"])
if parent:
    os.makedirs(parent, exist_ok=True)
db.init_app(app)
with app.app_context():
    db.ensure_schema()   # added by T2
```

**gunicorn**

- `requirements.txt`: add `gunicorn==23.0.0`.
- New `gunicorn.conf.py` at the repo root:

  ```python
  import os

  bind = f"0.0.0.0:{os.environ.get('PORT') or '5050'}"
  workers = 2
  preload_app = True
  accesslog = "-"
  ```

- `Makefile`: new `serve` target (added to `.PHONY`): `$(BIN)/gunicorn "taskboard:create_app()"`.

**Railway**

`railway.json`:

```json
{
  "$schema": "https://railway.com/railway.schema.json",
  "deploy": {
    "startCommand": "gunicorn \"taskboard:create_app()\"",
    "healthcheckPath": "/health",
    "restartPolicyType": "ON_FAILURE"
  }
}
```

`.python-version`: `3.12`.

**README**: new "Deploy to Railway" section: create the service from the repo; add a volume mounted at
`/data`; set `DATABASE=/data/taskboard.sqlite`; Railway sets `PORT`; the health check is `/health`; tables
are created on first start; optional manual seed via `railway ssh` then `flask --app taskboard seed` with a
data-loss warning next to it; recovery when the app fails to start on a database with an old column layout
(delete the database file, restart; data is lost); `make serve` runs the same command locally (macOS/Linux only). Also list
`make serve` in Quick start and document `DATABASE` and its default.

## Risks and unknowns

- **Data loss on deploy.** Mitigated by T2 (no `DROP` on startup) and by tests that start the app against a
  database with existing rows. T2 is high risk and gets human review.
- **No volume configured.** Data disappears on each deploy. Mitigated by the README; cannot be enforced in code.
- **Schema drift.** A database with an old column layout (e.g. `projects` without `deleted_at`) makes
  `CREATE UNIQUE INDEX ... WHERE deleted_at IS NULL` fail, so the app does not start. `flask init-db` /
  `flask seed` cannot fix it either: they run `create_app()` (and `ensure_schema()`) first and fail the same
  way. Accepted (non-goal); manual recovery is to delete the database file and restart (documented in the
  README by T4), or fix the table by hand with `sqlite3`.
- **SQLite with 2 workers.** Concurrent writes can hit `database is locked` under load. Acceptable for a
  training app; preload removes the startup race.
- **Railway behaviour unverified in the repo.** That the builder reads `.python-version`, the start command,
  and the health check are confirmed by the owner's first real deploy after merge. If the builder ignores
  `.python-version`, a follow-up adds the builder-specific setting.
- **Test cost.** Every test now runs `ensure_schema()` before conftest's `init_db()`. Small; accepted.
- **`DATABASE` exported in a developer's shell or CI.** Existing tests that build an app without a
  `DATABASE` in `test_config` (if any) would use that file. Follow-up: clear `DATABASE` in `conftest.py`
  (out of scope for T1, which must not modify existing test files).

## Tasks

| Id | Title | Type | Area | Depends on | Size | Needs e2e | Risk | Risk reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| T1 | Read the SQLite path from the DATABASE env var | feat | backend | - | S | no | low | Config read only; default unchanged; no data or API change |
| T2 | Create missing schema on startup without dropping data | feat | data | - | M | no | high | Touches `schema.sql` and `db.py` (high paths); risk of deleting stored data |
| T3 | Serve with gunicorn and add Railway config | chore | infra | - | S | no | low | New config files and a dependency; no app behaviour change |
| T4 | Document Railway deployment in the README | docs | docs | T1, T2, T3 | S | no | low | Docs only |

### T1: Read the SQLite path from the DATABASE env var

- **Type:** feat
- **Area:** backend
- **Depends on:** none
- **Size:** S
- **Needs e2e:** no
- **Risk:** low - config read only; default path unchanged; no data or API change
- **Hotspot files:** `taskboard/__init__.py`

**Acceptance criteria**

- [ ] With env `DATABASE=<path>` set and no `DATABASE` in `test_config`, `create_app()` uses `<path>`:
      after `init_db()`, `POST /projects` -> 201 and the row is in the SQLite file at `<path>`.
- [ ] With `DATABASE` unset, `app.config["DATABASE"]` is `<instance_path>/taskboard.sqlite` (unchanged).
- [ ] With `DATABASE` set to `""` or whitespace only, the default path is used; a value with surrounding
      whitespace (e.g. `" /tmp/x.sqlite "`) is used stripped.
- [ ] `test_config={"DATABASE": X}` wins over env `DATABASE`.
- [ ] A relative `DATABASE` value is used as given (not made absolute), resolved against the working
      directory; a bare file name such as `rel.sqlite` works.
- [ ] If the parent directory of the configured path does not exist, `create_app()` creates it and the app
      starts.
- [ ] `flask --app taskboard init-db` with env `DATABASE=<path>` creates the schema in `<path>`.
- [ ] No existing test file is modified and the full suite passes; `GET /health` still returns
      `200 {"status": "ok"}`.

**Scope**

- `taskboard/__init__.py`
- New tests (e.g. `tests/test_config.py`); use `monkeypatch.setenv` / `monkeypatch.chdir` / `tmp_path`;
  tests call `init_db()` before HTTP calls (T2 not required)

**Test plan**

- Test cases: T1.1-T1.17 (see Test matrix). T1.15 is a reviewer check.

### T2: Create missing schema on startup without dropping data

- **Type:** feat
- **Area:** data
- **Depends on:** none
- **Size:** M
- **Needs e2e:** no
- **Risk:** high - touches `taskboard/schema.sql` and `taskboard/db.py` (high paths); risk of deleting stored data
- **Hotspot files:** `taskboard/__init__.py`, `taskboard/db.py`, `taskboard/schema.sql`

**Acceptance criteria**

- [ ] Starting the app (`create_app()`) on a database path where the file does not exist, is zero bytes, or
      is a valid SQLite file with no tables creates all four tables and the three indexes; `GET /projects`
      then returns `200` with an empty list, without running `init-db`.
- [ ] Starting the app on a database that already has rows keeps every row: projects, tasks, tags and
      comments created before are returned unchanged by the API after a second `create_app()`; rows the API
      hides (e.g. a soft-deleted project) are unchanged in raw SQL.
- [ ] Starting the app on a database that has `projects`, `tasks` and `task_tags` with data but no
      `task_comments` table creates `task_comments` (and its index) and keeps the existing rows; a missing
      index on an existing table is also created.
- [ ] `taskboard/schema.sql` contains no `DROP` statement; every `CREATE` uses `IF NOT EXISTS`.
- [ ] `taskboard/drop.sql` contains the four `DROP TABLE IF EXISTS` statements in the order `task_comments`,
      `task_tags`, `tasks`, `projects`; `flask init-db` still drops and recreates all tables (existing data
      gone, schema present).
- [ ] `flask seed` still resets the database and loads the demo data (existing seed tests pass).
- [ ] Creating the app twice in a row on the same database does not raise.
- [ ] (should) No database connection opened by `ensure_schema()` is left open after `create_app()` returns.

**Scope**

- `taskboard/schema.sql`, new `taskboard/drop.sql`, `taskboard/db.py`, `taskboard/__init__.py`
- New tests (e.g. `tests/test_schema.py`); a test may build the partial database with raw `sqlite3`

**Test plan**

- Test cases: T2.1-T2.20 (see Test matrix).

### T3: Serve with gunicorn and add Railway config

- **Type:** chore
- **Area:** infra
- **Depends on:** none
- **Size:** S
- **Needs e2e:** no
- **Risk:** low - new config files and a dependency; no app behaviour change
- **Hotspot files:** `Makefile`, `requirements.txt`

**Acceptance criteria**

- [ ] `requirements.txt` pins `gunicorn==23.0.0`; after `make setup`, `.venv/bin/gunicorn --version`
      reports `23.0.0`.
- [ ] `gunicorn.conf.py` sets `bind` to `0.0.0.0:<PORT>` with `5050` when `PORT` is unset or empty,
      `workers = 2`, `preload_app = True`, `accesslog = "-"`.
- [ ] (manual, verify stage) `PORT=5099 make serve` logs `Listening at: http://0.0.0.0:5099` and two
      `Booting worker` lines; `GET /health` on port 5099 returns `200 {"status": "ok"}` and an access log
      line containing `GET /health` and `200` is printed.
- [ ] (manual, verify stage) `make serve` without `PORT` listens on `0.0.0.0:5050`.
- [ ] `railway.json` is valid JSON with `$schema` = `https://railway.com/railway.schema.json`,
      `deploy.startCommand` = `gunicorn "taskboard:create_app()"` (the `make serve` command without the
      `.venv/bin/` prefix), `deploy.healthcheckPath` = `"/health"`, `deploy.restartPolicyType` =
      `"ON_FAILURE"`, and no `build.builder`.
- [ ] `.python-version` trimmed content is exactly `3.12`.

**Scope**

- `requirements.txt`, `Makefile`, new `gunicorn.conf.py`, new `railway.json`, new `.python-version`
- New static tests (e.g. `tests/test_deploy_config.py`); manual run output goes in the PR

**Test plan**

- Test cases: T3.1-T3.13 (see Test matrix). T3.2, T3.6-T3.8 run by hand in the verify stage; paste the output in the PR.

### T4: Document Railway deployment in the README

- **Type:** docs
- **Area:** docs
- **Depends on:** T1, T2, T3
- **Size:** S
- **Needs e2e:** no
- **Risk:** low - docs only
- **Hotspot files:** `README.md`

**Acceptance criteria**

- [ ] README has a "Deploy to Railway" section covering: creating the service from the repo, a volume
      mounted at `/data`, `DATABASE=/data/taskboard.sqlite`, `PORT` set by Railway, the `/health` check, tables
      created on first start, and the optional manual seed via `railway ssh` then `flask --app taskboard seed`
      with a data-loss warning next to the command, and the manual recovery for a database with an old column
      layout (delete the database file, e.g. `railway ssh` then `rm /data/taskboard.sqlite`, and restart).
- [ ] Quick start lists `make serve` (noted as macOS/Linux only); the README names `DATABASE` as a supported
      environment variable with its default `instance/taskboard.sqlite`.
- [ ] Commands and file names in the README match `railway.json`, `gunicorn.conf.py`, the Makefile and
      `.python-version`.

**Scope**

- `README.md`

**Test plan**

- Test cases: T4.1-T4.5 (see Test matrix). Reviewer checklist; no automated test.

## Test matrix

55 rows (40 must, 15 should). Tests are named `test_deploy_t<task>_<n>_<description>` (for example
`test_deploy_t2_5_existing_rows_survive_restart`); rows with level `manual` are run by hand in the verify
stage or checked by the reviewer, and carry `# T<task>.<n>` in the PR checklist.

| Id | Task | Criterion | Case | Given / When / Then | Level | Priority |
| --- | --- | --- | --- | --- | --- | --- |
| T1.1 | T1 | Env `DATABASE` is used | happy | Given `monkeypatch.setenv("DATABASE", str(tmp_path/"env.sqlite"))` and `create_app({"TESTING": True})` with no DATABASE key / When `init_db()` runs, then `POST /projects {"name":"P1"}` / Then 201, `app.config["DATABASE"] == str(tmp_path/"env.sqlite")`, and raw `sqlite3` on that file returns `["P1"]` for `SELECT name FROM projects` | integration | must |
| T1.2 | T1 | Env `DATABASE` is used | edge | Given env `DATABASE=<tmp>/env.sqlite` and `test_config={"TESTING": True, "SECRET_KEY": "x"}` (other keys only) / When `create_app` / Then config DATABASE is the env path | unit | should |
| T1.3 | T1 | Default when unset | happy | Given `monkeypatch.delenv("DATABASE", raising=False)` and `ensure_schema` stubbed (see Decisions) / When `create_app()` / Then `app.config["DATABASE"] == os.path.join(app.instance_path, "taskboard.sqlite")`; no HTTP calls | unit | must |
| T1.4 | T1 | Empty / whitespace means default | edge | Given env `DATABASE=""` and `ensure_schema` stubbed / When `create_app()` / Then config DATABASE = `<instance_path>/taskboard.sqlite` | unit | must |
| T1.5 | T1 | Empty / whitespace means default | edge | Given env `DATABASE="   "`, then `"\t\n"` (parametrized) and `ensure_schema` stubbed / When `create_app()` / Then config DATABASE = default path; no file named with spaces is created in cwd | unit | must |
| T1.6 | T1 | Surrounding whitespace is stripped | edge | Given env `DATABASE=" <tmp>/x.sqlite "` / When `create_app()` and `init_db()` / Then config DATABASE == `"<tmp>/x.sqlite"` and that file exists | unit | must |
| T1.7 | T1 | test_config wins | happy | Given env `DATABASE=<tmp>/env.sqlite` and `test_config={"DATABASE": "<tmp>/tc.sqlite"}` / When `create_app`, `init_db()`, `POST /projects {"name":"P"}` / Then config DATABASE = tc path; the row is in `tc.sqlite`; `env.sqlite` does not exist or has no row | integration | must |
| T1.8 | T1 | Relative path used as given | happy | Given `monkeypatch.chdir(tmp_path)` and env `DATABASE=rel.sqlite` / When `create_app`, `init_db()`, `POST /projects` / Then 201; config DATABASE == `"rel.sqlite"` (not absolute); `tmp_path/"rel.sqlite"` holds the row | integration | must |
| T1.9 | T1 | Relative path used as given | edge | Given chdir(tmp_path), env `DATABASE=sub/dir/rel.sqlite` / When `create_app()` / Then config value stays `"sub/dir/rel.sqlite"`; `tmp_path/sub/dir` is created | unit | should |
| T1.10 | T1 | Missing parent directory is created | happy | Given env `DATABASE=<tmp>/a/b/c/db.sqlite` and `<tmp>/a` absent / When `create_app()`, `init_db()`, `GET /health` / Then `<tmp>/a/b/c` exists, no exception, health 200 | integration | must |
| T1.11 | T1 | Missing parent directory is created | edge | Given `test_config={"DATABASE": "<tmp>/new/x.sqlite"}` (no env) and `<tmp>/new` absent / When `create_app` / Then `<tmp>/new` exists | unit | should |
| T1.12 | T1 | Missing parent directory is created | boundary | Given parent already exists / When `create_app` twice / Then no error | unit | should |
| T1.13 | T1 | `flask init-db` honours env | happy | Given env `DATABASE=<tmp>/cli.sqlite` / When `app.test_cli_runner().invoke(args=["init-db"])` on an app built from env / Then exit code 0; raw `sqlite_master` of `cli.sqlite` lists `projects`, `tasks`, `task_tags`, `task_comments` | integration | must |
| T1.14 | T1 | `flask init-db` honours env | edge | Given env `DATABASE=<tmp>/missing/cli.sqlite` (parent absent) / When `init-db` / Then exit 0 and the schema is in that file | integration | should |
| T1.15 | T1 | Existing tests untouched, suite green | happy | Given the branch / When the reviewer runs `git diff --name-only feature/example_taskboard -- tests/` and `make test` / Then only new test files appear; all tests pass | manual | must |
| T1.16 | T1 | `/health` unchanged | happy | Given env `DATABASE=<tmp>/h.sqlite` / When `GET /health` / Then 200 and body exactly `{"status": "ok"}` | http | must |
| T1.17 | T1 | `flask seed` honours env | edge | Given env `DATABASE=<tmp>/s/seed.sqlite` (parent absent) / When `invoke(args=["seed"])` / Then exit 0; `<tmp>/s/seed.sqlite` holds the demo projects | integration | should |
| T2.1 | T2 | Fresh DB gets the full schema | happy | Given `<tmp>/none.sqlite` does not exist / When `create_app({"DATABASE": path})` with no `init_db()`, then `GET /projects` / Then 200, empty list; raw `sqlite_master` has the 4 tables plus `idx_projects_live_name`, `idx_tasks_project`, `idx_task_comments_task` | integration | must |
| T2.2 | T2 | Fresh DB gets the full schema | edge | Given a 0-byte file at the path (`path.touch()`) / When `create_app`, `GET /projects` / Then 200, empty list; 4 tables and 3 indexes exist | integration | must |
| T2.3 | T2 | Fresh DB gets the full schema | edge | Given a valid SQLite file with no tables (`PRAGMA user_version=1` committed) / When `create_app`, `GET /projects` / Then 200, empty list; 4 tables and 3 indexes; `user_version` still 1 | integration | must |
| T2.4 | T2 | Fresh DB gets the full schema | edge | Given a fresh DB / When `create_app`, then `POST /projects`, `POST /tasks` with `tags:["a"]`, `POST /tasks/<id>/comments` / Then all 201 | http | should |
| T2.5 | T2 | Existing rows survive a restart | happy | Given app #1 on `<tmp>/db.sqlite` + `init_db()`; project P, task T with tags `["x","y"]`, comment C; GET responses saved / When `create_app` #2 on the same path (no `init_db`) / Then `GET /projects/<P>`, `GET /tasks/<T>`, `GET /tasks/<T>/comments` equal the saved bodies | integration | must |
| T2.6 | T2 | Existing rows survive a restart | edge | Given app #1 with a soft-deleted project, task and comment; their raw SQL rows saved / When `create_app` #2 / Then `SELECT * ... WHERE id=?` rows match, `deleted_at` included | integration | must |
| T2.7 | T2 | Existing rows survive a restart | boundary | Given app #1 with 1 project / When `create_app` #2, then `POST /projects` / Then the new id is greater than every earlier id | integration | should |
| T2.8 | T2 | Partial schema completed | happy | Given a raw `sqlite3` DB with `projects`, `tasks`, `task_tags` (current DDL) and their indexes, 1 row each, no `task_comments` / When `create_app` / Then `task_comments` and `idx_task_comments_task` exist; existing rows unchanged in raw SQL; `POST /tasks/<id>/comments` -> 201 | integration | must |
| T2.9 | T2 | Missing index created | edge | Given a DB with all 4 tables + data but one index missing (parametrize over the 3 indexes) / When `create_app` / Then that index is in `sqlite_master`; row counts unchanged | integration | must |
| T2.10 | T2 | Partial schema completed | edge | Given `idx_tasks_project` exists with another definition (`ON tasks (status)`) / When `create_app` / Then `sqlite_master.sql` for it is still the `status` version; no error | integration | should |
| T2.11 | T2 | Partial schema completed | edge | Given a DB with an extra table `notes(id)` holding 1 row / When `create_app` / Then `notes` and its row are unchanged | integration | should |
| T2.12 | T2 | `schema.sql` has no DROP; CREATEs use IF NOT EXISTS | happy | Given `taskboard/schema.sql` / When read case-insensitively, ignoring `--` comments / Then no `DROP`; count(`CREATE`) == count(`CREATE ... IF NOT EXISTS`) == 7 | unit | must |
| T2.13 | T2 | `schema.sql` is idempotent | edge | Given `schema.sql` / When run twice with `executescript` on one connection / Then no error | unit | should |
| T2.14 | T2 | `drop.sql` content and order | happy | Given `taskboard/drop.sql` / When split into statements / Then exactly 4: `DROP TABLE IF EXISTS` `task_comments`, `task_tags`, `tasks`, `projects`, in that order | unit | must |
| T2.15 | T2 | `flask init-db` still resets | happy | Given an app with project P and a task / When `runner.invoke(args=["init-db"])` / Then exit 0; `GET /projects` 200 empty; raw SQL shows 4 tables, 3 indexes, 0 rows (soft-deleted included) | integration | must |
| T2.16 | T2 | `flask init-db` still resets | edge | Given a partial DB (no `task_comments`) with data / When `init-db` / Then all 4 tables exist and are empty | integration | should |
| T2.17 | T2 | `flask seed` still resets and loads demo | happy | Given an app with a custom project `"Mine"` / When `runner.invoke(args=["seed"])` / Then exit 0; `"Mine"` gone (raw SQL); demo projects present; `tests/test_seed.py` passes unchanged | integration | must |
| T2.18 | T2 | Two creates in a row do not raise | happy | Given `<tmp>/db.sqlite` / When `create_app` twice with the same DATABASE, no `init_db` in between / Then no exception; each table and index listed once | unit | must |
| T2.19 | T2 | Two creates in a row do not raise | boundary | Given a populated DB / When `create_app` 3 times / Then no exception; row counts unchanged | unit | should |
| T2.20 | T2 | (should) No connection left open | happy | Given `create_app({"DATABASE": p})` has returned / When an outside `sqlite3.connect(p, timeout=0)` runs `BEGIN EXCLUSIVE` / Then it succeeds at once (no `database is locked`) | unit | should |
| T3.1 | T3 | gunicorn pinned | happy | Given `requirements.txt` / When parsed / Then exactly one line equals `gunicorn==23.0.0` | unit | must |
| T3.2 | T3 | gunicorn installed | happy | Given `make setup` has run / When `.venv/bin/gunicorn --version` / Then output contains `23.0.0` | manual | must |
| T3.3 | T3 | `gunicorn.conf.py` values | happy | Given `monkeypatch.setenv("PORT","5099")` / When `runpy.run_path("gunicorn.conf.py")` / Then `bind == "0.0.0.0:5099"`, `workers == 2`, `preload_app is True`, `accesslog == "-"` | unit | must |
| T3.4 | T3 | `gunicorn.conf.py` values | edge | Given `PORT` unset / When `run_path` / Then `bind == "0.0.0.0:5050"` | unit | must |
| T3.5 | T3 | `gunicorn.conf.py` values | boundary | Given `PORT=""` / When `run_path` / Then `bind == "0.0.0.0:5050"` | unit | must |
| T3.6 | T3 | Manual run on `PORT=5099` | happy | Given `make setup` / When `PORT=5099 make serve`, then `curl -i http://127.0.0.1:5099/health` / Then the log shows `Listening at: http://0.0.0.0:5099` and exactly 2 `Booting worker` lines at startup; 200 `{"status": "ok"}`; an access log line contains `GET /health` and `200`. Output pasted in the PR | manual | must |
| T3.7 | T3 | Manual run on `PORT=5099` | edge | Given `DATABASE=/tmp/tb-verify/x.sqlite` (dir absent) / When `PORT=5099 make serve`, then `curl http://127.0.0.1:5099/projects` / Then 200 with an empty list; no worker error | manual | should |
| T3.8 | T3 | `make serve` default port | happy | Given `PORT` unset / When `make serve` / Then the log shows `Listening at: http://0.0.0.0:5050`; `curl :5050/health` -> 200 | manual | must |
| T3.9 | T3 | `make serve` target is wired | happy | Given `Makefile` / When parsed / Then `serve` is in `.PHONY` and its recipe is `$(BIN)/gunicorn "taskboard:create_app()"` | unit | must |
| T3.10 | T3 | `railway.json` content | happy | Given `railway.json` / When `json.load` / Then it equals exactly `{"$schema": "https://railway.com/railway.schema.json", "deploy": {"startCommand": "gunicorn \"taskboard:create_app()\"", "healthcheckPath": "/health", "restartPolicyType": "ON_FAILURE"}}` | unit | must |
| T3.11 | T3 | `railway.json` content | edge | Given `railway.json` / When loaded / Then there is no `build` key (so no `build.builder`) | unit | must |
| T3.12 | T3 | Start command matches `make serve` | edge | Given the Makefile `serve` recipe / When `$(BIN)/` is removed / Then it equals `deploy.startCommand` byte for byte | unit | must |
| T3.13 | T3 | `.python-version` | happy | Given `.python-version` / When read and stripped / Then `== "3.12"` | unit | must |
| T4.1 | T4 | "Deploy to Railway" section | happy | Given README.md / When the reviewer reads it / Then a "Deploy to Railway" heading covers: create the service from the repo, a volume at `/data`, `DATABASE=/data/taskboard.sqlite`, `PORT` set by Railway, `/health` check, tables created on first start | manual | must |
| T4.2 | T4 | Manual seed step | edge | Given the seed step / When reviewed / Then it shows `railway ssh` then `flask --app taskboard seed`, marked optional, with a data-loss warning in the same block or the line just before or after | manual | must |
| T4.5 | T4 | Schema-drift recovery documented | edge | Given README / When reviewed / Then it explains that if the app fails to start with `no such column` on an old database, `init-db` / `seed` do not help; recovery is deleting the database file (`railway ssh`, `rm /data/taskboard.sqlite`) and restarting, with a data-loss warning | manual | must |
| T4.3 | T4 | Quick start and `DATABASE` | happy | Given README / When reviewed / Then Quick start lists `make serve` marked macOS/Linux only; `DATABASE` is named as an env var with default `instance/taskboard.sqlite`, and plain paths only (no `~`, no URI) | manual | must |
| T4.4 | T4 | README matches config | happy | Given README, `railway.json`, `gunicorn.conf.py`, Makefile, `.python-version` / When cross-checked / Then README names `railway.json` and `.python-version`; start command, `/health`, port default `5050`, `make serve` and Python `3.12` match exactly; anything said about `gunicorn.conf.py` is correct | manual | must |
