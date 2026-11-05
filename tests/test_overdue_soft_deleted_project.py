from datetime import date, datetime, timedelta

from taskboard.db import get_db


def test_g1_1_overdue_list_excludes_tasks_of_project_soft_deleted_in_db(app, client, project):
    # G1.1: stats and /tasks/overdue agree when a project is soft-deleted directly in the DB
    b = client.post("/projects", json={"name": "B"}).get_json()
    due = (date.today() - timedelta(days=1)).isoformat()
    a_task = client.post(
        "/tasks", json={"project_id": project["id"], "title": "A", "status": "todo", "due_date": due}
    ).get_json()
    resp = client.post(
        "/tasks", json={"project_id": b["id"], "title": "B", "status": "todo", "due_date": due}
    )
    assert resp.status_code == 201
    with app.app_context():
        db = get_db()
        db.execute(
            "UPDATE projects SET deleted_at = ? WHERE id = ?",
            (datetime.now().isoformat(timespec="seconds"), b["id"]),
        )
        db.commit()
    stats = client.get("/stats").get_json()
    overdue = client.get("/tasks/overdue").get_json()
    items = overdue["items"] if isinstance(overdue, dict) else overdue
    assert stats["overdue"] == 1
    assert [t["id"] for t in items] == [a_task["id"]]
