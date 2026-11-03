"""DATABASE environment variable handling in create_app (railway-deploy-readiness, T1)."""

import os
import sqlite3

import pytest

from taskboard import create_app
from taskboard.db import init_db


def _stub_schema(monkeypatch):
    monkeypatch.setattr("taskboard.db.ensure_schema", lambda: None, raising=False)


def _names(path, sql="SELECT name FROM projects"):
    conn = sqlite3.connect(path)
    try:
        return [r[0] for r in conn.execute(sql).fetchall()]
    finally:
        conn.close()


def _build(config=None):
    app = create_app(config if config is not None else {"TESTING": True})
    with app.app_context():
        init_db()
    return app


def test_deploy_t1_1_env_database_is_used(monkeypatch, tmp_path):
    path = str(tmp_path / "env.sqlite")
    monkeypatch.setenv("DATABASE", path)
    app = _build()
    resp = app.test_client().post("/projects", json={"name": "P1"})
    assert resp.status_code == 201
    assert app.config["DATABASE"] == path
    assert _names(path) == ["P1"]


def test_deploy_t1_2_env_used_with_other_test_config_keys(monkeypatch, tmp_path):
    path = str(tmp_path / "env.sqlite")
    monkeypatch.setenv("DATABASE", path)
    app = create_app({"TESTING": True, "SECRET_KEY": "x"})
    assert app.config["DATABASE"] == path


def test_deploy_t1_3_default_when_unset(monkeypatch):
    _stub_schema(monkeypatch)
    monkeypatch.delenv("DATABASE", raising=False)
    app = create_app({"TESTING": True})
    assert app.config["DATABASE"] == os.path.join(app.instance_path, "taskboard.sqlite")


def test_deploy_t1_4_empty_env_means_default(monkeypatch):
    _stub_schema(monkeypatch)
    monkeypatch.setenv("DATABASE", "")
    app = create_app({"TESTING": True})
    assert app.config["DATABASE"] == os.path.join(app.instance_path, "taskboard.sqlite")


@pytest.mark.parametrize("value", ["   ", "\t\n"])
def test_deploy_t1_5_whitespace_env_means_default(monkeypatch, tmp_path, value):
    _stub_schema(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE", value)
    app = create_app({"TESTING": True})
    assert app.config["DATABASE"] == os.path.join(app.instance_path, "taskboard.sqlite")
    assert os.listdir(tmp_path) == []


def test_deploy_t1_6_surrounding_whitespace_is_stripped(monkeypatch, tmp_path):
    path = str(tmp_path / "x.sqlite")
    monkeypatch.setenv("DATABASE", f" {path} ")
    app = _build()
    assert app.config["DATABASE"] == path
    assert os.path.exists(path)


def test_deploy_t1_7_test_config_wins_over_env(monkeypatch, tmp_path):
    env_path = str(tmp_path / "env.sqlite")
    tc_path = str(tmp_path / "tc.sqlite")
    monkeypatch.setenv("DATABASE", env_path)
    app = _build({"TESTING": True, "DATABASE": tc_path})
    assert app.config["DATABASE"] == tc_path
    assert app.test_client().post("/projects", json={"name": "P"}).status_code == 201
    assert _names(tc_path) == ["P"]
    if os.path.exists(env_path):
        tables = _names(env_path, "SELECT name FROM sqlite_master WHERE type='table'")
        assert "projects" not in tables or _names(env_path) == []


def test_deploy_t1_8_relative_path_used_as_given(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE", "rel.sqlite")
    app = _build()
    resp = app.test_client().post("/projects", json={"name": "R"})
    assert resp.status_code == 201
    assert app.config["DATABASE"] == "rel.sqlite"
    assert _names(str(tmp_path / "rel.sqlite")) == ["R"]


def test_deploy_t1_9_relative_nested_path_parent_created(monkeypatch, tmp_path):
    _stub_schema(monkeypatch)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE", "sub/dir/rel.sqlite")
    app = create_app({"TESTING": True})
    assert app.config["DATABASE"] == "sub/dir/rel.sqlite"
    assert (tmp_path / "sub" / "dir").is_dir()


def test_deploy_t1_10_missing_parent_directory_is_created(monkeypatch, tmp_path):
    path = tmp_path / "a" / "b" / "c" / "db.sqlite"
    monkeypatch.setenv("DATABASE", str(path))
    app = _build()
    assert path.parent.is_dir()
    assert app.test_client().get("/health").status_code == 200


def test_deploy_t1_11_parent_created_for_test_config_path(monkeypatch, tmp_path):
    _stub_schema(monkeypatch)
    monkeypatch.delenv("DATABASE", raising=False)
    create_app({"TESTING": True, "DATABASE": str(tmp_path / "new" / "x.sqlite")})
    assert (tmp_path / "new").is_dir()


def test_deploy_t1_12_existing_parent_twice_no_error(monkeypatch, tmp_path):
    _stub_schema(monkeypatch)
    monkeypatch.setenv("DATABASE", str(tmp_path / "x.sqlite"))
    create_app({"TESTING": True})
    create_app({"TESTING": True})


def test_deploy_t1_13_init_db_cli_honours_env(monkeypatch, tmp_path):
    path = str(tmp_path / "cli.sqlite")
    monkeypatch.setenv("DATABASE", path)
    app = create_app({"TESTING": True})
    with app.app_context():
        result = app.test_cli_runner().invoke(args=["init-db"])
    assert result.exit_code == 0, result.output
    tables = _names(path, "SELECT name FROM sqlite_master WHERE type='table'")
    assert {"projects", "tasks", "task_tags", "task_comments"} <= set(tables)


def test_deploy_t1_14_init_db_cli_missing_parent(monkeypatch, tmp_path):
    path = str(tmp_path / "missing" / "cli.sqlite")
    monkeypatch.setenv("DATABASE", path)
    app = create_app({"TESTING": True})
    with app.app_context():
        result = app.test_cli_runner().invoke(args=["init-db"])
    assert result.exit_code == 0, result.output
    tables = _names(path, "SELECT name FROM sqlite_master WHERE type='table'")
    assert "projects" in tables


def test_deploy_t1_16_health_unchanged_with_env(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE", str(tmp_path / "h.sqlite"))
    app = _build()
    resp = app.test_client().get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_deploy_t1_17_seed_cli_honours_env(monkeypatch, tmp_path):
    path = str(tmp_path / "s" / "seed.sqlite")
    monkeypatch.setenv("DATABASE", path)
    app = create_app({"TESTING": True})
    with app.app_context():
        result = app.test_cli_runner().invoke(args=["seed"])
    assert result.exit_code == 0, result.output
    assert len(_names(path)) > 0
