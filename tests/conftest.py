import pytest

from taskboard import create_app
from taskboard.db import init_db


@pytest.fixture
def app(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.sqlite")})
    with app.app_context():
        init_db()
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def project(client):
    resp = client.post("/projects", json={"name": "Demo", "description": "Test project"})
    assert resp.status_code == 201
    return resp.get_json()


@pytest.fixture
def make_task(client, project):
    def _make_task(**overrides):
        payload = {"project_id": project["id"], "title": "A task", **overrides}
        resp = client.post("/tasks", json=payload)
        assert resp.status_code == 201, resp.get_json()
        return resp.get_json()

    return _make_task
