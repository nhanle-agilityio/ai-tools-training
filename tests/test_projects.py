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


# --- delete project ---------------------------------------------------------------


def _deleted_at(app, table, row_id):
    with app.app_context():
        from taskboard.db import get_db

        row = get_db().execute(f"SELECT deleted_at FROM {table} WHERE id = ?", (row_id,)).fetchone()
        return row["deleted_at"]


def test_delete_project_returns_204_and_soft_deletes_project_and_live_tasks(
    app, client, project, make_task, frozen_now
):
    t1 = make_task(title="one")
    t2 = make_task(title="two")
    resp = client.delete(f"/projects/{project['id']}")
    assert resp.status_code == 204
    assert resp.data == b""
    assert _deleted_at(app, "projects", project["id"]) == frozen_now
    assert _deleted_at(app, "tasks", t1["id"]) == frozen_now
    assert _deleted_at(app, "tasks", t2["id"]) == frozen_now


def test_delete_project_keeps_earlier_task_deleted_at(app, client, project, make_task, monkeypatch):
    from datetime import datetime

    old = make_task(title="old")
    live = make_task(title="live")

    class Earlier(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2029, 1, 1, 0, 0, 0)

    monkeypatch.setattr("taskboard.services.datetime", Earlier)
    assert client.delete(f"/tasks/{old['id']}").status_code == 204

    class Later(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2030, 1, 2, 3, 4, 5)

    monkeypatch.setattr("taskboard.services.datetime", Later)
    assert client.delete(f"/projects/{project['id']}").status_code == 204
    assert _deleted_at(app, "tasks", old["id"]) == "2029-01-01T00:00:00"
    assert _deleted_at(app, "tasks", live["id"]) == "2030-01-02T03:04:05"


def test_deleted_project_returns_404_on_project_endpoints(client, project):
    client.delete(f"/projects/{project['id']}")
    pid = project["id"]
    for resp in (
        client.get(f"/projects/{pid}"),
        client.patch(f"/projects/{pid}", json={"name": "X"}),
        client.delete(f"/projects/{pid}"),
        client.get(f"/projects/{pid}/stats"),
    ):
        assert resp.status_code == 404
        assert resp.get_json() == {"error": f"project {pid} not found"}


def test_deleted_project_absent_from_project_list(client, project):
    client.delete(f"/projects/{project['id']}")
    assert client.get("/projects").get_json()["items"] == []


def test_deleted_project_tasks_are_hidden(client, project, make_task):
    task = make_task(title="late", due_date="2000-01-01")
    client.delete(f"/projects/{project['id']}")
    assert client.get(f"/tasks/{task['id']}").status_code == 404
    listing = client.get("/tasks").get_json()
    assert listing["items"] == []
    assert listing["pagination"]["total"] == 0
    assert client.get("/tasks/overdue").get_json()["items"] == []


def test_create_task_in_deleted_project_returns_404(client, project):
    client.delete(f"/projects/{project['id']}")
    resp = client.post("/tasks", json={"project_id": project["id"], "title": "T"})
    assert resp.status_code == 404
    assert resp.get_json() == {"error": f"project {project['id']} not found"}


def test_deleted_project_name_can_be_reused(client, project):
    client.delete(f"/projects/{project['id']}")
    resp = client.post("/projects", json={"name": project["name"]})
    assert resp.status_code == 201


def test_delete_missing_project_returns_404(client):
    resp = client.delete("/projects/999")
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "project 999 not found"}


# --- GET /projects/<id>/tags (T2) ---------------------------------------------


def test_t2_1_project_tags_counts_and_order(client, project, make_task):
    make_task(tags=["bug", "ui"])
    make_task(tags=["bug"])
    make_task(tags=["android", "bug"])

    resp = client.get(f"/projects/{project['id']}/tags")
    assert resp.status_code == 200
    assert resp.get_json() == {
        "items": [
            {"tag": "bug", "task_count": 3},
            {"tag": "android", "task_count": 1},
            {"tag": "ui", "task_count": 1},
        ]
    }


def test_t2_6_project_tags_count_done_tasks(client, project, make_task):
    make_task(tags=["bug"], status="todo")
    make_task(tags=["bug"], status="done")

    body = client.get(f"/projects/{project['id']}/tags").get_json()
    assert body["items"] == [{"tag": "bug", "task_count": 2}]


def test_t2_7_project_tags_ignore_deleted_tasks(client, project, make_task):
    make_task(tags=["bug"])
    deleted = make_task(tags=["bug", "legacy"])
    assert client.delete(f"/tasks/{deleted['id']}").status_code == 204

    body = client.get(f"/projects/{project['id']}/tags").get_json()
    assert body["items"] == [{"tag": "bug", "task_count": 1}]


def test_t2_9_project_tags_ignore_other_projects(client, project, make_task):
    other = client.post("/projects", json={"name": "Other"}).get_json()
    make_task(tags=["bug"])
    client.post("/tasks", json={"project_id": other["id"], "title": "x", "tags": ["bug"]})
    client.post("/tasks", json={"project_id": other["id"], "title": "y", "tags": ["other"]})

    body = client.get(f"/projects/{project['id']}/tags").get_json()
    assert body["items"] == [{"tag": "bug", "task_count": 1}]


def test_t2_10_project_tags_empty_project(client, project):
    resp = client.get(f"/projects/{project['id']}/tags")
    assert resp.status_code == 200
    assert resp.get_json() == {"items": []}


def test_t2_11_project_tags_untagged_tasks_only(client, project, make_task):
    make_task()
    make_task()

    resp = client.get(f"/projects/{project['id']}/tags")
    assert resp.status_code == 200
    assert resp.get_json() == {"items": []}


def test_t2_12_project_tags_missing_project(client):
    resp = client.get("/projects/999/tags")
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "project 999 not found"}


def test_t2_13_project_tags_deleted_project(client, project, make_task):
    make_task(tags=["bug"])
    assert client.delete(f"/projects/{project['id']}").status_code == 204

    resp = client.get(f"/projects/{project['id']}/tags")
    assert resp.status_code == 404
    assert resp.get_json() == {"error": f"project {project['id']} not found"}
