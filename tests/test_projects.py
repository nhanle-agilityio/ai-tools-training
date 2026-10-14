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
    assert resp.status_code == 400


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
