"""Smoke tests for the demo seed (`make seed`)."""

from datetime import date

import pytest

from taskboard.db import get_db
from taskboard.seed import seed


@pytest.fixture
def seeded(app):
    with app.app_context():
        seed(get_db())
    return app


def _live_tasks(client, **params):
    items, page = [], 1
    while True:
        query = {"per_page": 50, "page": page, **params}
        body = client.get("/tasks", query_string=query).get_json()
        items += body["items"]
        if page >= body["pagination"]["pages"]:
            return items
        page += 1


def _comments(client, task_id):
    resp = client.get(f"/tasks/{task_id}/comments")
    assert resp.status_code == 200
    return resp.get_json()["items"]


def _query(app, sql):
    with app.app_context():
        return [dict(r) for r in get_db().execute(sql).fetchall()]


def _projects(client):
    body = client.get("/projects").get_json()
    return body["items"] if isinstance(body, dict) else body


def test_t3_1_visible_comments_with_authors_in_two_projects(seeded, client):
    comments, project_ids = [], set()
    for task in _live_tasks(client):
        found = _comments(client, task["id"])
        comments += found
        if found:
            project_ids.add(task["project_id"])
    assert len(comments) >= 5
    assert all(c["author"].strip() != "" for c in comments)
    assert len(project_ids) >= 2


def test_t3_2_comment_count_matches_listing(seeded, client):
    for task in _live_tasks(client):
        assert task["comment_count"] == len(_comments(client, task["id"]))


def test_t3_3_exactly_one_deleted_comment_on_live_task(seeded, client):
    rows = _query(
        seeded,
        "SELECT c.id, c.task_id FROM task_comments c JOIN tasks t ON t.id = c.task_id "
        "WHERE c.deleted_at IS NOT NULL AND t.deleted_at IS NULL",
    )
    assert len(rows) == 1
    cid, task_id = rows[0]["id"], rows[0]["task_id"]
    task = client.get(f"/tasks/{task_id}")
    assert task.status_code == 200
    assert client.get(f"/comments/{cid}").status_code == 404
    listed = _comments(client, task_id)
    assert cid not in [c["id"] for c in listed]
    assert task.get_json()["comment_count"] == len(listed)


def test_t3_4_exactly_one_deleted_task_with_tags_and_comment(seeded, client):
    rows = _query(seeded, "SELECT id FROM tasks WHERE deleted_at IS NOT NULL")
    assert len(rows) == 1
    tid = rows[0]["id"]
    assert client.get(f"/tasks/{tid}").status_code == 404
    assert tid not in [t["id"] for t in _live_tasks(client)]
    assert _query(seeded, f"SELECT 1 FROM task_tags WHERE task_id = {tid}")
    assert _query(seeded, f"SELECT 1 FROM task_comments WHERE task_id = {tid}")


def _stats_matches_listing(client, project_id):
    stats = client.get(f"/projects/{project_id}/stats").get_json()
    listing = client.get("/tasks", query_string={"project_id": project_id}).get_json()
    assert stats["total"] == listing["pagination"]["total"]


def test_t3_6_stats_total_excludes_deleted_task(seeded, client):
    row = _query(seeded, "SELECT project_id FROM tasks WHERE deleted_at IS NOT NULL")[0]
    _stats_matches_listing(client, row["project_id"])


def test_t3_7_stats_total_matches_for_every_project(seeded, client):
    for p in _projects(client):
        _stats_matches_listing(client, p["id"])


def test_t3_8_website_has_more_than_five_tasks(seeded, client):
    website = next(p for p in _projects(client) if p["name"] == "Website")
    body = client.get("/tasks", query_string={"project_id": website["id"]}).get_json()
    assert body["pagination"]["total"] > 5


def test_t3_9_at_least_eight_distinct_tags(seeded, client):
    tags = {tag for task in _live_tasks(client) for tag in task["tags"]}
    assert len(tags) >= 8


def test_t3_10_seed_on_fresh_db_lists_projects(seeded, client):
    assert len(_projects(client)) >= 2


def test_t3_11_overdue_and_upcoming_tasks_exist(seeded, client):
    tasks = _live_tasks(client)
    today = date.today().isoformat()
    assert any(t["is_overdue"] for t in tasks)
    assert any(t["due_date"] and t["due_date"] >= today for t in tasks)
