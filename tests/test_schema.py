"""Non-destructive schema creation on startup (spec: railway-deploy-readiness, task T2)."""

import re
import sqlite3
from pathlib import Path

import pytest

from taskboard import create_app

PKG = Path(__file__).resolve().parent.parent / "taskboard"
TABLES = {"projects", "tasks", "task_tags", "task_comments"}
INDEXES = {"idx_projects_live_name", "idx_tasks_project", "idx_task_comments_task"}

DDL_PROJECTS = """CREATE TABLE projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT);"""
DDL_TASKS = """CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
    title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'todo',
    priority TEXT NOT NULL DEFAULT 'medium', due_date TEXT,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT);"""
DDL_TAGS = """CREATE TABLE task_tags (
    task_id INTEGER NOT NULL REFERENCES tasks (id) ON DELETE CASCADE, tag TEXT NOT NULL,
    PRIMARY KEY (task_id, tag));"""
DDL_COMMENTS = """CREATE TABLE task_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES tasks (id) ON DELETE CASCADE,
    author TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    deleted_at TEXT);"""
DDL_IDX = {
    "idx_projects_live_name": "CREATE UNIQUE INDEX idx_projects_live_name ON projects (name) "
    "WHERE deleted_at IS NULL;",
    "idx_tasks_project": "CREATE INDEX idx_tasks_project ON tasks (project_id);",
    "idx_task_comments_task": "CREATE INDEX idx_task_comments_task ON task_comments (task_id);",
}
NOW = "2026-01-01T00:00:00+00:00"


def make(path):
    return create_app({"TESTING": True, "DATABASE": str(path)})


def raw(path, sql, params=()):
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute(sql, params).fetchall()
        conn.commit()
        return rows
    finally:
        conn.close()


def objects(path, kind):
    rows = raw(path, "SELECT name FROM sqlite_master WHERE type=? AND name NOT LIKE 'sqlite_%'", (kind,))
    return [r[0] for r in rows]


def assert_full_schema(path):
    assert set(objects(path, "table")) >= TABLES
    assert set(objects(path, "index")) >= INDEXES


def build_partial(path, with_comments=False, skip_index=None, tasks_idx_sql=None):
    conn = sqlite3.connect(path)
    ddl = [DDL_PROJECTS, DDL_TASKS, DDL_TAGS] + ([DDL_COMMENTS] if with_comments else [])
    for stmt in ddl:
        conn.execute(stmt)
    for name, sql in DDL_IDX.items():
        if name == skip_index or (name == "idx_task_comments_task" and not with_comments):
            continue
        if name == "idx_tasks_project" and tasks_idx_sql:
            sql = tasks_idx_sql
        conn.execute(sql)
    conn.execute("INSERT INTO projects (name, created_at, updated_at) VALUES ('P', ?, ?)", (NOW, NOW))
    conn.execute(
        "INSERT INTO tasks (project_id, title, created_at, updated_at) VALUES (1, 'T', ?, ?)", (NOW, NOW)
    )
    conn.execute("INSERT INTO task_tags (task_id, tag) VALUES (1, 'x')")
    if with_comments:
        conn.execute(
            "INSERT INTO task_comments (task_id, author, body, created_at, updated_at) "
            "VALUES (1, 'a', 'b', ?, ?)",
            (NOW, NOW),
        )
    conn.commit()
    conn.close()


def populate(client):
    p = client.post("/projects", json={"name": "P"}).get_json()
    t = client.post("/tasks", json={"project_id": p["id"], "title": "T", "tags": ["x", "y"]}).get_json()
    c = client.post(f"/tasks/{t['id']}/comments", json={"author": "a", "body": "hi"}).get_json()
    return p, t, c


def init(app):
    from taskboard.db import init_db

    with app.app_context():
        init_db()


def cli(app, command):
    with app.app_context():
        return app.test_cli_runner().invoke(args=[command])


def counts(path):
    return {t: raw(path, f"SELECT COUNT(*) FROM {t}")[0][0] for t in sorted(TABLES)}


# --- fresh database -----------------------------------------------------------


def test_deploy_t2_1_fresh_path_gets_full_schema(tmp_path):
    path = tmp_path / "none.sqlite"
    resp = make(path).test_client().get("/projects")
    assert resp.status_code == 200
    assert resp.get_json()["items"] == []
    assert_full_schema(path)


def test_deploy_t2_2_zero_byte_file_gets_full_schema(tmp_path):
    path = tmp_path / "empty.sqlite"
    path.touch()
    resp = make(path).test_client().get("/projects")
    assert resp.status_code == 200
    assert resp.get_json()["items"] == []
    assert_full_schema(path)


def test_deploy_t2_3_valid_empty_sqlite_file_keeps_user_version(tmp_path):
    path = tmp_path / "v1.sqlite"
    raw(path, "PRAGMA user_version=1")
    resp = make(path).test_client().get("/projects")
    assert resp.status_code == 200
    assert resp.get_json()["items"] == []
    assert_full_schema(path)
    assert raw(path, "PRAGMA user_version")[0][0] == 1


def test_deploy_t2_4_fresh_db_accepts_writes(tmp_path):
    client = make(tmp_path / "w.sqlite").test_client()
    resp = client.post("/projects", json={"name": "P"})
    assert resp.status_code == 201
    resp = client.post("/tasks", json={"project_id": resp.get_json()["id"], "title": "T", "tags": ["a"]})
    assert resp.status_code == 201
    resp = client.post(f"/tasks/{resp.get_json()['id']}/comments", json={"author": "a", "body": "b"})
    assert resp.status_code == 201


# --- existing rows survive ----------------------------------------------------


def test_deploy_t2_5_rows_survive_second_create_app(tmp_path):
    path = tmp_path / "db.sqlite"
    app1 = make(path)
    init(app1)
    c1 = app1.test_client()
    p, t, _c = populate(c1)
    urls = [f"/projects/{p['id']}", f"/tasks/{t['id']}", f"/tasks/{t['id']}/comments"]
    saved = [c1.get(u).get_json() for u in urls]
    c2 = make(path).test_client()
    for url, body in zip(urls, saved):
        resp = c2.get(url)
        assert resp.status_code == 200
        assert resp.get_json() == body


def test_deploy_t2_6_soft_deleted_rows_unchanged(tmp_path):
    path = tmp_path / "db.sqlite"
    app1 = make(path)
    init(app1)
    c1 = app1.test_client()
    p, t, c = populate(c1)
    assert c1.delete(f"/comments/{c['id']}").status_code == 204
    assert c1.delete(f"/tasks/{t['id']}").status_code == 204
    assert c1.delete(f"/projects/{p['id']}").status_code == 204
    queries = [
        ("SELECT * FROM projects WHERE id=?", p["id"]),
        ("SELECT * FROM tasks WHERE id=?", t["id"]),
        ("SELECT * FROM task_comments WHERE id=?", c["id"]),
    ]
    before = [raw(path, q, (i,)) for q, i in queries]
    assert all(rows and rows[0][-1] is not None for rows in before)
    make(path)
    assert [raw(path, q, (i,)) for q, i in queries] == before


def test_deploy_t2_7_new_ids_continue_after_restart(tmp_path):
    path = tmp_path / "db.sqlite"
    app1 = make(path)
    init(app1)
    first = app1.test_client().post("/projects", json={"name": "One"}).get_json()["id"]
    resp = make(path).test_client().post("/projects", json={"name": "Two"})
    assert resp.status_code == 201
    assert resp.get_json()["id"] > first


# --- partial schema -----------------------------------------------------------


def test_deploy_t2_8_missing_comments_table_is_created(tmp_path):
    path = tmp_path / "partial.sqlite"
    build_partial(path)
    before = {t: raw(path, f"SELECT * FROM {t}") for t in ("projects", "tasks", "task_tags")}
    client = make(path).test_client()
    assert "task_comments" in objects(path, "table")
    assert "idx_task_comments_task" in objects(path, "index")
    assert {t: raw(path, f"SELECT * FROM {t}") for t in before} == before
    assert client.post("/tasks/1/comments", json={"author": "a", "body": "b"}).status_code == 201


@pytest.mark.parametrize("missing", sorted(INDEXES))
def test_deploy_t2_9_missing_index_is_created(tmp_path, missing):
    path = tmp_path / "idx.sqlite"
    build_partial(path, with_comments=True, skip_index=missing)
    assert missing not in objects(path, "index")
    before = counts(path)
    make(path)
    assert missing in objects(path, "index")
    assert counts(path) == before


def test_deploy_t2_10_existing_index_definition_is_kept(tmp_path):
    path = tmp_path / "idx.sqlite"
    build_partial(path, with_comments=True, tasks_idx_sql="CREATE INDEX idx_tasks_project ON tasks (status);")
    make(path)
    (sql,) = raw(path, "SELECT sql FROM sqlite_master WHERE name='idx_tasks_project'")[0]
    assert "status" in sql
    assert "project_id" not in sql


def test_deploy_t2_11_unrelated_table_is_untouched(tmp_path):
    path = tmp_path / "notes.sqlite"
    raw(path, "CREATE TABLE notes (id INTEGER)")
    raw(path, "INSERT INTO notes (id) VALUES (7)")
    make(path)
    assert raw(path, "SELECT id FROM notes") == [(7,)]
    assert_full_schema(path)


# --- schema.sql / drop.sql ----------------------------------------------------


def _sql_statements(name):
    text = "\n".join(line.split("--")[0] for line in (PKG / name).read_text().splitlines())
    return [s.strip() for s in text.split(";") if s.strip()]


def test_deploy_t2_12_schema_has_no_drop_and_creates_are_idempotent():
    stmts = _sql_statements("schema.sql")
    assert not any(re.search(r"\bdrop\b", s, re.IGNORECASE) for s in stmts)
    creates = [s for s in stmts if re.match(r"create\b", s, re.IGNORECASE)]
    guarded = [
        s
        for s in creates
        if re.match(r"create\s+(unique\s+)?(table|index)\s+if\s+not\s+exists\b", s, re.IGNORECASE)
    ]
    assert len(creates) == len(guarded) == 7


def test_deploy_t2_13_schema_runs_twice_without_error():
    conn = sqlite3.connect(":memory:")
    script = (PKG / "schema.sql").read_text()
    conn.executescript(script)
    conn.executescript(script)
    conn.close()


def test_deploy_t2_14_drop_sql_order():
    stmts = _sql_statements("drop.sql")
    assert len(stmts) == 4
    for stmt, table in zip(stmts, ["task_comments", "task_tags", "tasks", "projects"]):
        assert re.fullmatch(rf"drop\s+table\s+if\s+exists\s+{table}", stmt, re.IGNORECASE)


# --- init-db / seed -----------------------------------------------------------


def test_deploy_t2_15_init_db_wipes_data(tmp_path):
    path = tmp_path / "db.sqlite"
    app = make(path)
    init(app)
    populate(app.test_client())
    assert counts(path)["projects"] == 1
    result = cli(app, "init-db")
    assert result.exit_code == 0, result.output
    resp = app.test_client().get("/projects")
    assert resp.status_code == 200
    assert resp.get_json()["items"] == []
    assert_full_schema(path)
    assert set(counts(path).values()) == {0}


def test_deploy_t2_16_init_db_on_partial_db(tmp_path):
    path = tmp_path / "partial.sqlite"
    build_partial(path)
    app = make(path)
    result = cli(app, "init-db")
    assert result.exit_code == 0, result.output
    assert set(objects(path, "table")) >= TABLES
    assert set(counts(path).values()) == {0}


def test_deploy_t2_17_seed_resets_and_loads_demo(tmp_path):
    path = tmp_path / "db.sqlite"
    app = make(path)
    init(app)
    assert app.test_client().post("/projects", json={"name": "Mine"}).status_code == 201
    result = cli(app, "seed")
    assert result.exit_code == 0, result.output
    names = [r[0] for r in raw(path, "SELECT name FROM projects")]
    assert "Mine" not in names
    assert len(names) >= 1


# --- repeated creates ---------------------------------------------------------


def test_deploy_t2_18_two_creates_do_not_raise(tmp_path):
    path = tmp_path / "db.sqlite"
    make(path)
    make(path)
    tables = objects(path, "table")
    indexes = objects(path, "index")
    assert sorted(t for t in tables if t in TABLES) == sorted(TABLES)
    assert len(tables) == len(set(tables))
    assert sorted(i for i in indexes if i in INDEXES) == sorted(INDEXES)
    assert len(indexes) == len(set(indexes))


def test_deploy_t2_19_three_creates_keep_counts(tmp_path):
    path = tmp_path / "db.sqlite"
    app = make(path)
    init(app)
    populate(app.test_client())
    before = counts(path)
    for _ in range(3):
        make(path)
    assert counts(path) == before


def test_deploy_t2_20_no_connection_left_open(tmp_path):
    path = tmp_path / "db.sqlite"
    make(path)
    conn = sqlite3.connect(path, timeout=0, isolation_level=None)
    try:
        conn.execute("BEGIN EXCLUSIVE")
        conn.execute("ROLLBACK")
    finally:
        conn.close()
