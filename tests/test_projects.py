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
