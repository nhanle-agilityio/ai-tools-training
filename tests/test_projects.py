import pytest


def test_health(client):
    assert client.get("/health").get_json() == {"status": "ok"}


def test_create_and_get_project(client):
    resp = client.post("/projects", json={"name": "  Website  ", "description": "Marketing"})
    assert resp.status_code == 201
    project = resp.get_json()
    assert project["name"] == "Website"

    resp = client.get(f"/projects/{project['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["description"] == "Marketing"


def test_create_project_requires_name(client):
    resp = client.post("/projects", json={"description": "no name"})
    assert resp.status_code == 400
    assert "name" in resp.get_json()["error"]


def test_project_names_are_unique(client, project):
    resp = client.post("/projects", json={"name": project["name"]})
    assert resp.status_code == 409
    assert resp.get_json() == {"error": "a project with this name already exists"}


def test_duplicate_project_name_is_compared_after_strip(client, project):
    resp = client.post("/projects", json={"name": f"  {project['name']}  "})
    assert resp.status_code == 409


def test_list_projects_sorted_by_name(client):
    for name in ["Zeta", "Alpha", "Mid"]:
        client.post("/projects", json={"name": name})
    names = [p["name"] for p in client.get("/projects").get_json()["items"]]
    assert names == ["Alpha", "Mid", "Zeta"]


def test_get_missing_project_returns_404(client):
    assert client.get("/projects/999").status_code == 404


def test_project_stats_counts_by_status(client, project, make_task):
    make_task(status="todo")
    make_task(status="todo")
    make_task(status="in_progress")
    make_task(status="done")

    stats = client.get(f"/projects/{project['id']}/stats").get_json()
    assert stats["total"] == 4
    assert stats["by_status"] == {"todo": 2, "in_progress": 1, "done": 1}


@pytest.mark.parametrize(
    "done, todo, expected",
    [
        (1, 2, 33.3),
        (2, 1, 66.7),
        (3, 0, 100),
    ],
)
def test_project_stats_completion_rate_is_rounded_percentage(
    client, project, make_task, done, todo, expected
):
    for _ in range(done):
        make_task(status="done")
    for _ in range(todo):
        make_task(status="todo")

    stats = client.get(f"/projects/{project['id']}/stats").get_json()
    assert stats["completion_rate"] == expected


def test_project_stats_for_project_without_tasks(client, project):
    resp = client.get(f"/projects/{project['id']}/stats")
    assert resp.status_code == 200
    stats = resp.get_json()
    assert stats["total"] == 0
    assert stats["by_status"] == {"todo": 0, "in_progress": 0, "done": 0}
    assert stats["completion_rate"] == 0
    assert stats["in_progress_rate"] == 0


def test_project_stats_in_progress_rate(client, project, make_task):
    make_task(status="in_progress")
    make_task(status="todo")
    make_task(status="todo")

    stats = client.get(f"/projects/{project['id']}/stats").get_json()
    assert stats["in_progress_rate"] == 33.3


def test_create_project_sets_updated_at_equal_to_created_at(client):
    resp = client.post("/projects", json={"name": "A"})
    assert resp.status_code == 201
    project = resp.get_json()
    assert project["updated_at"] == project["created_at"]
    assert "deleted_at" not in project


def test_read_projects_return_updated_at_and_hide_deleted_at(client, project):
    single = client.get(f"/projects/{project['id']}").get_json()
    listed = client.get("/projects").get_json()["items"][0]
    for body in (single, listed):
        assert body["updated_at"] == body["created_at"]
        assert "deleted_at" not in body


def test_project_name_unique_index_is_partial_on_live_rows(app):
    from taskboard.db import get_db

    with app.app_context():
        sql = (
            get_db().execute("SELECT sql FROM sqlite_master WHERE name = 'idx_projects_live_name'").fetchone()
        )
    assert sql is not None
    assert "UNIQUE" in sql[0] and "deleted_at IS NULL" in sql[0]


def test_project_stats_exclude_deleted_tasks(client, project, make_task):
    make_task(status="todo")
    gone = make_task(status="done")
    client.delete(f"/tasks/{gone['id']}")
    stats = client.get(f"/projects/{project['id']}/stats").get_json()
    assert stats["total"] == 1
    assert stats["by_status"] == {"todo": 1, "in_progress": 0, "done": 0}


@pytest.fixture
def frozen_now(monkeypatch):
    from datetime import datetime

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2030, 1, 2, 3, 4, 5)

    monkeypatch.setattr("taskboard.services.datetime", FrozenDatetime)
    return "2030-01-02T03:04:05"


def test_patch_project_name_updates_name_and_updated_at(client, project, frozen_now):
    resp = client.patch(f"/projects/{project['id']}", json={"name": "New"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["name"] == "New"
    assert body["description"] == project["description"]
    assert body["updated_at"] == frozen_now
    assert body["created_at"] == project["created_at"]
    assert client.get(f"/projects/{project['id']}").get_json()["name"] == "New"


def test_patch_project_description_only(client, project):
    resp = client.patch(f"/projects/{project['id']}", json={"description": "D"})
    assert resp.status_code == 200
    assert resp.get_json()["description"] == "D"
    assert resp.get_json()["name"] == project["name"]


def test_patch_project_name_is_stripped(client, project):
    resp = client.patch(f"/projects/{project['id']}", json={"name": "  New  "})
    assert resp.status_code == 200
    assert resp.get_json()["name"] == "New"


def test_patch_project_empty_body_touches_updated_at(client, project, frozen_now):
    resp = client.patch(f"/projects/{project['id']}", json={})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["name"] == project["name"]
    assert body["description"] == project["description"]
    assert body["updated_at"] == frozen_now


def test_patch_project_ignores_unknown_keys(client, project):
    resp = client.patch(f"/projects/{project['id']}", json={"id": 99, "created_at": "x"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["id"] == project["id"]
    assert body["created_at"] == project["created_at"]


@pytest.mark.parametrize("name", ["", "  ", 5])
def test_patch_project_invalid_name_returns_400(client, project, name):
    resp = client.patch(f"/projects/{project['id']}", json={"name": name})
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "name is required"}


def test_patch_project_invalid_description_returns_400(client, project):
    resp = client.patch(f"/projects/{project['id']}", json={"description": 5})
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "description must be a string"}


def test_patch_project_non_object_body_returns_400(client, project):
    resp = client.patch(f"/projects/{project['id']}", json=[])
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "request body must be a JSON object"}


def test_patch_project_duplicate_name_returns_409(client, project):
    other = client.post("/projects", json={"name": "Other"}).get_json()
    resp = client.patch(f"/projects/{other['id']}", json={"name": f" {project['name']} "})
    assert resp.status_code == 409
    assert resp.get_json() == {"error": "a project with this name already exists"}


def test_patch_project_with_own_name_returns_200(client, project):
    resp = client.patch(f"/projects/{project['id']}", json={"name": project["name"]})
    assert resp.status_code == 200


def test_patch_missing_project_returns_404(client):
    resp = client.patch("/projects/999", json={"name": "X"})
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "project 999 not found"}
